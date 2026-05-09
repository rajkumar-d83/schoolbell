# SchoolBell

A home-schooling portal for CBSE/NCERT students — built with Flask, SQLite, and Claude AI.
Live at **https://schoolbell.fun**

Parents upload chapter PDFs, Claude generates MCQ quizzes automatically, and children study
and take quizzes at home. A built-in **Teaching Mode** lets a parent walk through a PDF
page by page before handing the laptop to the child for the quiz.

---

## Features

| Feature | Description |
|---|---|
| 📚 Chapter Upload | Upload NCERT PDF chapters — text extracted automatically via PyMuPDF |
| 🤖 AI Question Generation | Claude reads the chapter and creates up to 50 MCQ questions with answers, explanations, difficulty ratings, topic tags, and optional SVG geometry diagrams |
| 📐 Geometry Diagrams | AI auto-generates inline SVG diagrams for geometry, angle, graph, and circuit questions |
| 🖥️ Teaching Mode | Full-screen PDF viewer with page controls, zoom, keyboard navigation, and auto-saving teaching notes |
| 📝 Quizzes | Timed quizzes (60s per question) with instant AI feedback and score tracking |
| 🃏 Flashcard Mode | 3D flip cards built from cheatsheet key concepts or quiz questions — Got it / Still Learning deck algorithm with swipe and keyboard support |
| 💪 Practice My Mistakes | One-click quiz using only questions the student previously got wrong |
| 📋 Cheatsheets | AI generates a one-page key-concept summary per chapter; printable |
| ⭐ XP & Levels | Students earn XP per quiz and progress through 7 levels: Seedling → Champion |
| 🏅 Badges | Achievement badges for milestones (perfect score, hot streak, comeback kid, level-up) |
| 🤖 AI Encouragement | Claude Haiku generates a personalised 2-sentence message after each quiz |
| 📊 Performance Tracking | Per-subject scores, weak topic detection, quiz history |
| 👨‍👧 Two Roles | Separate dashboards for Parent (teacher) and Student |

---

## Prerequisites

- **Python 3.10+** — [python.org](https://www.python.org/downloads/)
- **pip** (comes with Python)
- An **Anthropic API key** — [console.anthropic.com](https://console.anthropic.com/)

---

## Setup Steps

### 1. Get the project

```bash
git clone https://github.com/rajkumar-d83/schoolbell.git
cd SchoolBell
```

### 2. Create a virtual environment and install dependencies

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file in the project root:

```env
FLASK_SECRET_KEY=some-long-random-string-change-this
ANTHROPIC_API_KEY=sk-ant-...your-key-here...
FLASK_CONFIG=development
```

> Generate a secret key: `python -c "import secrets; print(secrets.token_hex(32))"`

### 4. Create the database

```bash
python init_db.py
```

### 5. Seed default accounts

```bash
python seed_db.py
```

This creates:
- A default **parent** account (`parent` / `schoolbell123`)
- Sample subjects for Grade 3 and Grade 7

### 6. Start the app

```bash
python run.py
```

Open **http://localhost:5000**

---

## How to Deploy Updates

```powershell
# On your PC — commit and push
git add <changed files>
git commit -m "Description of change"
git push origin main

# On the server — SSH in and run deploy script
ssh -i "C:\Users\durai\Downloads\schoolbell-key.pem" ubuntu@3.26.97.121
sudo bash /home/schoolbell/app/deploy/deploy_app.sh
```

See `OPERATIONS.md` for full deployment and server management instructions.

---

## Default Credentials

| Role | Username | Password |
|---|---|---|
| Parent / Teacher | `parent` | `schoolbell123` |
| Student | *(add via parent dashboard)* | last name in lowercase |

---

## How Parent Uses It

1. **Log in** as parent
2. **Add Subjects** → Manage Subjects → Add a subject (e.g. "Science", Grade 7)
3. **Upload a Chapter PDF** → Upload Chapter PDF → select subject, enter chapter title, upload
4. **Generate Questions** → choose up to 50 questions → click **Generate Questions** (~30–60 seconds)
5. **Generate Cheatsheet** → one-page AI summary of key concepts, printable
6. **Teach the Chapter** → Teaching Mode opens the PDF with a notes sidebar
7. **Hand Off** → click **Ready for Quiz →** to launch the quiz for the student

---

## How Student Uses It

1. **Log in** with their username and password
2. **Pick a Subject** from the dashboard
3. **Flashcards** → study key terms before the quiz (3D flip cards)
4. **Start Quiz** → timed MCQ quiz with instant feedback and explanations
5. **Fix Mistakes** → re-quiz on only the questions they got wrong
6. **See Score** → score circle, XP gained, personalised AI encouragement message
7. **Earn Badges** → milestone achievements shown on the dashboard
8. **Track Progress** → My Performance page shows subject scores and weak topics

---

## Folder Structure

```
SchoolBell/
├── run.py                          # Dev entry point
├── wsgi.py                         # Production gunicorn entry point (ProxyFix)
├── config.py                       # DevelopmentConfig / ProductionConfig
├── init_db.py                      # Create tables + run inline migrations
├── seed_db.py                      # Seed default accounts
├── requirements.txt
├── OPERATIONS.md                   # Server operations handbook
├── .env                            # Secrets (never commit)
├── uploads/                        # Uploaded PDFs (git-ignored)
├── ncert_books/                    # Bulk import staging area (git-ignored)
└── deploy/
│   ├── setup_server.sh             # One-shot Ubuntu server setup
│   ├── deploy_app.sh               # Pull + migrate + restart (safe to rerun)
│   ├── schoolbell.service          # systemd unit for gunicorn
│   └── nginx.conf                  # nginx reverse proxy config
└── app/
    ├── __init__.py                 # App factory: WAL mode, blueprints, logger wiring
    ├── models/models.py            # 7 SQLAlchemy models
    ├── routes/
    │   ├── auth.py                 # Login / logout / claim
    │   ├── main.py                 # Root redirect by role
    │   ├── student.py              # Student dashboard, quiz, flashcards, XP, mistakes
    │   └── parent.py               # Parent dashboard, upload, teach, reports
    ├── services/
    │   ├── pdf_service.py          # PDF extraction, question generation (with SVG diagrams), cheatsheet
    │   ├── analytics.py            # Performance, XP/levels, badges
    │   └── ai_messages.py          # Post-quiz encouraging messages (Claude Haiku)
    ├── static/
    │   ├── css/main.css            # Full stylesheet — premium dark theme
    │   ├── js/main.js              # Global JS (flash timeout, nav toggle, confirm)
    │   └── img/schoolbell-logo.png # App logo (favicon + login page)
    └── templates/
        ├── shared/base.html, cheatsheet.html
        ├── auth/login.html, claim.html
        ├── errors/404.html, 500.html
        ├── student/
        │   ├── dashboard.html      # XP bar, badges, stat cards, recent quizzes
        │   ├── subjects.html
        │   ├── chapters.html       # Flashcards / Start Quiz / Fix Mistakes buttons
        │   ├── quiz.html           # Timed quiz with SVG diagram support
        │   ├── quiz_complete.html  # Score, XP gained, confetti, AI message, review
        │   ├── flashcards.html     # 3D flip cards, swipe/keyboard, Got it / Still Learning
        │   ├── performance.html
        │   └── read_chapter.html
        └── parent/
            ├── dashboard.html
            ├── students.html, add_student.html, student_report.html
            ├── subjects.html, chapters.html
            ├── upload.html, generate_questions.html
            ├── view_questions.html # Shows SVG diagrams inline
            └── teach.html
```

---

## Tech Stack

| Layer | Tech |
|---|---|
| Backend | Flask 3.0.3, SQLAlchemy 2.0.31, SQLite (WAL mode) |
| Auth | Flask-Login 0.6.3, Flask-Bcrypt 1.0.1 |
| Security | Flask-WTF (CSRF global), ProxyFix (nginx ↔ Flask) |
| AI | Anthropic SDK — `claude-sonnet-4-6` (questions + cheatsheet), `claude-haiku-4-5-20251001` (encouragement) |
| PDF | PyMuPDF 1.24.5 (server extraction), PDF.js 3.11.174 (client viewer) |
| Production | gunicorn 22.0.0, nginx, Let's Encrypt SSL (certbot), AWS EC2 t2.micro |
| Frontend | Vanilla JS, CSS variables, Jinja2 — no JS framework |

---

*SchoolBell · Flask + SQLite + Claude AI · CBSE Grades 1–10 · schoolbell.fun*
