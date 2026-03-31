# 🔔 SchoolBell

A local learning portal for CBSE/NCERT students — built with Flask, PostgreSQL, and Claude AI.

Parents upload chapter PDFs, Claude generates MCQ quizzes automatically, and children study
and take quizzes at home. A built-in **Teaching Mode** lets a parent walk through a PDF
page by page before handing the laptop to the child for the quiz.

---

## ✨ Features

| Feature | Description |
|---|---|
| 📚 Chapter Upload | Upload NCERT PDF chapters — text is extracted automatically |
| 🤖 AI Question Generation | Claude reads the chapter and creates 5–20 MCQ questions with answers, explanations, difficulty ratings, and topic tags |
| 🖥️ Teaching Mode | Full-screen PDF viewer with page controls, zoom, keyboard navigation, and auto-saving teaching notes |
| 📝 Quizzes | Students take timed quizzes (60s per question) with instant score feedback |
| 📊 Performance Tracking | Per-subject scores, weak topic identification, quiz history |
| 👨‍👧 Two Roles | Separate dashboards for Parent (teacher) and Student |

---

## 🛠️ Prerequisites

- **Python 3.10+** — [python.org](https://www.python.org/downloads/)
- **PostgreSQL 13+** — [postgresql.org](https://www.postgresql.org/download/)
- **pip** (comes with Python)
- **git** (optional, if cloning)
- An **Anthropic API key** — [console.anthropic.com](https://console.anthropic.com/)

---

## 🚀 Setup Steps

### 1. Get the project

```bash
# Option A — unzip the downloaded archive
unzip SchoolBell.zip
cd SchoolBell

# Option B — if using git
git clone <your-repo-url>
cd SchoolBell
```

### 2. Create a virtual environment and install dependencies

```bash
python -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows
venv\Scripts\activate

pip install -r requirements.txt
```

### 3. Create the PostgreSQL database

Open a terminal and run `psql` as the postgres superuser:

```sql
-- Run these commands inside psql
CREATE DATABASE schoolbell_db;
CREATE USER schoolbell_user WITH PASSWORD 'yourpassword';
GRANT ALL PRIVILEGES ON DATABASE schoolbell_db TO schoolbell_user;
\q
```

> On macOS with Homebrew: `psql postgres`
> On Linux: `sudo -u postgres psql`
> On Windows: use pgAdmin or the psql shell from the Start menu.

### 4. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in your values:

```env
FLASK_SECRET_KEY=some-long-random-string-change-this
DATABASE_URL=postgresql://schoolbell_user:yourpassword@localhost/schoolbell_db
ANTHROPIC_API_KEY=sk-ant-...your-key-here...
```

> Generate a secret key: `python -c "import secrets; print(secrets.token_hex(32))"`

### 5. Create tables and seed default data

```bash
python seed_db.py
```

This creates all database tables and adds:
- A default **parent** account
- Sample subjects for Grade 3 and Grade 7

### 6. Start the app

```bash
python run.py
```

### 7. Open in browser

```
http://localhost:5000
```

---

## 🔄 How to Restart the App

### Activate the virtual environment

**PowerShell:**
```powershell
cd C:\projects\SchoolBell
.\venv\Scripts\Activate.ps1
```

**CMD:**
```cmd
cd C:\projects\SchoolBell
venv\Scripts\activate.bat
```

**macOS / Linux:**
```bash
cd /path/to/SchoolBell
source venv/bin/activate
```

### Install new dependencies (only needed after pulling updates)

```bash
pip install -r requirements.txt
```

### Start the development server

```bash
python run.py
```

App will be at **http://localhost:5000**

### Quick restart checklist

| Problem | Fix |
|---|---|
| `ModuleNotFoundError: flask_wtf` | Run `pip install -r requirements.txt` |
| Database connection error | Start PostgreSQL service |
| `CSRF token missing` error | Clear browser cookies and log in again |
| Tables don't exist | Run `python seed_db.py` |
| Port 5000 in use | Change port in `run.py` or kill the process |

---

## 🔑 Default Credentials

| Role | Username | Password |
|---|---|---|
| Parent / Teacher | `parent` | `schoolbell123` |
| Student | *(add via parent dashboard)* | *(set when adding)* |

> **First thing to do:** Log in as parent → go to **Students** → **Add Student** to create
> accounts for your children.

---

## 👨‍👩‍👧 How Parent Uses It

1. **Log in** with username `parent` / password `schoolbell123`
2. **Add Subjects** → Parent Dashboard → Manage Subjects → Add a subject (e.g. "Science", Grade 7)
3. **Upload a Chapter PDF** → Upload Chapter PDF → select subject, enter chapter title, upload the PDF file
4. **Generate Questions** → after upload, you are taken to the Generate Questions page → choose 5–20 questions → click **Generate Questions** → Claude reads the chapter and creates MCQs (takes ~15–30 seconds)
5. **Review Questions** → inspect the generated questions, correct answers, explanations, and topic tags
6. **Teach the Chapter** → click **Teach This Chapter** → Teaching Mode opens with the PDF on the left and controls on the right
7. **Hand Off** → click the green **Ready for Quiz →** button to send the student straight to the quiz

---

## 👦 How Student Uses It

1. **Log in** with their username and password (set by parent)
2. **Pick a Subject** from the subject grid
3. **Pick a Chapter** — chapters with a green "Start Quiz" button are ready
4. **Take the Quiz** — one question at a time, 60 seconds per question, click an option and submit
5. **See the Score** — score circle, correct/wrong count, full question review with explanations
6. **Track Progress** → My Performance page shows subject scores, weak topics, and quiz history

---

## 🖥️ Teaching Mode Walkthrough

Teaching Mode is a full-screen two-panel layout designed for a parent to teach and a child to follow along.

**Opening Teaching Mode:**
- Parent Dashboard → click **Teach** on any chapter, or
- View Questions → click **Teach This Chapter**

**Left panel — PDF Viewer (70% width):**
- The chapter PDF renders page by page on a canvas
- **Bottom controls:** ◀ Prev | Page N of M | Next ▶ | − zoom % + | ⛶ fullscreen
- **Keyboard shortcuts:** `←` previous page, `→` next page
- **Zoom range:** 50% to 300%, default 150%
- **Fullscreen:** click ⛶ or press F11 — great for projecting on a TV

**Right panel — Teaching Controls (30% width):**
- Chapter title and subject shown at top
- **Student selector** — pick which child is being taught (optional)
- **Teaching Notes** — type notes freely; they auto-save to the database when you click away
- **Questions to Cover** — collapsible list of all quiz questions so you know exactly what topics to cover before the child takes the quiz
- **Ready for Quiz →** — big green button; click when teaching is done to launch the quiz immediately

---

## 📁 Folder Structure

```
SchoolBell/
├── run.py                          # Dev entry point (reads FLASK_CONFIG env var)
├── wsgi.py                         # Production gunicorn entry point
├── seed_db.py                      # Database seeder (run once)
├── config.py                       # Configuration classes (dev/prod)
├── requirements.txt                # Python dependencies
├── .env.example                    # Environment variable template
├── .gitignore
├── uploads/                        # PDF files uploaded by parent (git-ignored)
└── app/
    ├── __init__.py                 # Flask app factory (db, auth, CSRF, error handlers)
    ├── models/
    │   ├── __init__.py
    │   └── models.py               # SQLAlchemy models (7 tables)
    ├── routes/
    │   ├── __init__.py
    │   ├── auth.py                 # Login / logout
    │   ├── main.py                 # Root redirect
    │   ├── student.py              # Student dashboard, quiz, performance
    │   └── parent.py               # Parent dashboard, upload, teach, reports
    ├── services/
    │   ├── __init__.py
    │   ├── pdf_service.py          # PyMuPDF text extraction + Claude API MCQ generation
    │   └── analytics.py            # Performance calculations, weak topic detection
    ├── static/
    │   ├── css/
    │   │   └── main.css            # Full stylesheet
    │   └── js/
    │       └── main.js             # Global JS (timer, flash, option highlight)
    └── templates/
        ├── shared/
        │   └── base.html           # Base layout (navbar, flash, footer, CSRF meta tag)
        ├── auth/
        │   └── login.html
        ├── errors/
        │   ├── 404.html            # Page not found
        │   └── 500.html            # Server error
        ├── student/
        │   ├── dashboard.html
        │   ├── subjects.html
        │   ├── chapters.html
        │   ├── quiz.html
        │   ├── quiz_complete.html
        │   └── performance.html
        └── parent/
            ├── dashboard.html
            ├── students.html
            ├── add_student.html
            ├── student_report.html
            ├── subjects.html       # Add + delete subjects
            ├── chapters.html       # Add + delete chapters per subject
            ├── upload.html
            ├── generate_questions.html
            ├── view_questions.html
            └── teach.html          # Teaching Mode (PDF.js viewer)
```

---

## ☁️ AWS Migration Notes

When you're ready to move SchoolBell from local to AWS:

### Database → Amazon RDS (PostgreSQL)
- Create an RDS PostgreSQL instance (db.t3.micro for small use)
- Update `DATABASE_URL` in your environment to the RDS endpoint
- Run `python seed_db.py` once against the RDS instance to create tables

### File Storage → Amazon S3
- Create an S3 bucket for PDF uploads
- Install `boto3` and `flask-s3` (or implement direct boto3 calls in `pdf_service.py`)
- Replace the local `UPLOAD_FOLDER` logic in `parent.py` with S3 `put_object` / `get_object`
- Update `serve_pdf` route to generate a pre-signed S3 URL instead of `send_from_directory`

### App Server → Elastic Beanstalk or EC2
- **Elastic Beanstalk (easier):** `eb init`, `eb create`, set environment variables in the EB console
- **EC2 (more control):** install nginx + gunicorn, run `gunicorn -w 4 run:app`
- Use `gunicorn` instead of Flask's dev server in production: `pip install gunicorn`

### Environment Variables → AWS Parameter Store or Secrets Manager
- Store `FLASK_SECRET_KEY`, `DATABASE_URL`, `ANTHROPIC_API_KEY` in Parameter Store
- Pull them in your app startup or via EB environment configuration
- Never commit `.env` to git (already in `.gitignore`)

### config.py change for production
```python
class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
```
Then in `run.py`: `app = create_app('production')`

---

## 🔧 Troubleshooting

**PDF not rendering in Teaching Mode**
- Check that the `uploads/` folder exists at the project root
- Verify `UPLOAD_FOLDER` in `config.py` points to the correct path
- Confirm the chapter's `pdf_filename` column is not null in the database

**Questions not generating**
- Check that `ANTHROPIC_API_KEY` is set correctly in `.env`
- Make sure the PDF text was extracted — view the chapter in the DB and check `pdf_text` is not empty
- Some scanned PDFs (images only) will not extract text — use text-based NCERT PDFs

**Database connection errors**
- Verify PostgreSQL is running: `pg_isready` or `sudo service postgresql status`
- Double-check `DATABASE_URL` format: `postgresql://user:password@host/dbname`
- Make sure the database and user exist (re-run the `CREATE DATABASE` SQL if needed)

**Port 5000 already in use**
- Change the port in `run.py`: `app.run(port=5001)`
- Or kill the process using port 5000: `lsof -ti:5000 | xargs kill`

**Flask can't find the app**
- Make sure your virtual environment is activated before running `python run.py`
- Run from the project root directory (where `run.py` lives)

---

## 📄 License

Built for personal/family use. Feel free to adapt for your own children's learning.

---

*SchoolBell · Flask + PostgreSQL + Claude AI · CBSE Grades 1–10*
