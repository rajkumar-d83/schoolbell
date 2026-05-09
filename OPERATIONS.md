# SchoolBell — Operations Handbook

## Quick Reference

| What | Value |
|---|---|
| Live site | https://schoolbell.fun |
| Server IP | 3.26.97.121 |
| SSH key | `C:\Users\durai\Downloads\schoolbell-key.pem` |
| GitHub repo | https://github.com/rajkumar-d83/schoolbell |
| Server app path | `/home/schoolbell/app` |
| Local project | `C:\projects\SchoolBell` |

---

## 1. Connect to the Server (SSH)

Open **PowerShell** on your PC:

```powershell
ssh -i "C:\Users\durai\Downloads\schoolbell-key.pem" ubuntu@3.26.97.121
```

---

## 2. Make a Code Change and Deploy

### On your local PC (PowerShell)

```powershell
cd C:\projects\SchoolBell

# 1. Edit files in VS Code

# 2. Stage and commit
git add <filename>
git commit -m "Short description of what you changed"

# 3. Push to GitHub
git push origin main
```

### On the server — pull and restart

```bash
sudo bash /home/schoolbell/app/deploy/deploy_app.sh
```

The deploy script does the following — safe to run at any time:
1. `git fetch origin` + `git reset --hard origin/main` — always syncs exactly to GitHub (no merge conflicts possible)
2. `pip install -r requirements.txt` — installs any new packages
3. `python init_db.py` — creates any new tables and runs inline column migrations
4. Fixes file permissions
5. Restarts gunicorn and reloads nginx

> **Note:** The deploy script uses `reset --hard` instead of `pull` so that permission-bit changes from `chmod` never cause conflicts. `core.fileMode false` is also set automatically on each deploy.

---

## 3. Day-to-Day Server Commands

### Check if the app is running
```bash
sudo systemctl status schoolbell
```

### Restart the app
```bash
sudo systemctl restart schoolbell
```

### Stop / Start the app
```bash
sudo systemctl stop schoolbell
sudo systemctl start schoolbell
```

### Check nginx
```bash
sudo systemctl status nginx
sudo nginx -t                     # test config for errors
sudo systemctl reload nginx       # apply config changes without downtime
```

### View live app logs (errors and requests)
```bash
# Live error stream — press Ctrl+C to stop
sudo journalctl -u schoolbell -f

# Last 50 lines
sudo journalctl -u schoolbell -n 50 --no-pager

# Gunicorn access log
sudo tail -f /home/schoolbell/app/logs/access.log

# Gunicorn error log
sudo tail -f /home/schoolbell/app/logs/error.log
```

---

## 4. Database — Backup and Restore

> **Note:** `sqlite3` CLI is not installed on the server. Use Python's built-in `sqlite3` module for all DB queries (see Section 10).

### Backup the production database (run on server)
```bash
cd /home/schoolbell/app
sudo -u schoolbell venv/bin/python3 -c "
import sqlite3
src = sqlite3.connect('schoolbell.db')
dst = sqlite3.connect('/home/schoolbell/schoolbell_backup_$(date +%Y%m%d).db')
src.backup(dst); dst.close(); src.close()
print('Backup done')
"
ls -lh /home/schoolbell/schoolbell_backup_*.db
```

### Download backup to your PC (run in local PowerShell)
```powershell
scp -i "C:\Users\durai\Downloads\schoolbell-key.pem" `
    ubuntu@3.26.97.121:/home/schoolbell/schoolbell_backup_*.db `
    C:\projects\SchoolBell\backups\
```

### Push local database to server (dev → prod sync)
```powershell
# Step 1: Create clean copy locally
cd C:\projects\SchoolBell
venv\Scripts\python.exe -c "
import sqlite3
src = sqlite3.connect('schoolbell_dev.db')
dst = sqlite3.connect('schoolbell_clean.db')
src.backup(dst); dst.close(); src.close()
print('Clean copy ready')
"

# Step 2: Upload to server
scp -i "C:\Users\durai\Downloads\schoolbell-key.pem" schoolbell_clean.db ubuntu@3.26.97.121:/tmp/schoolbell.db
```

Then on the server:
```bash
sudo systemctl stop schoolbell
sudo mv /home/schoolbell/app/schoolbell.db /home/schoolbell/app/schoolbell.db.bak
sudo mv /tmp/schoolbell.db /home/schoolbell/app/schoolbell.db
sudo chown schoolbell:schoolbell /home/schoolbell/app/schoolbell.db
sudo systemctl start schoolbell
```

---

## 5. Upload NCERT Books / PDFs to Server

```powershell
# From local PC — upload the ncert_books folder
scp -i "C:\Users\durai\Downloads\schoolbell-key.pem" `
    -r C:\projects\SchoolBell\ncert_books `
    ubuntu@3.26.97.121:/home/schoolbell/app/
```

Then log in to the site as parent → **Bulk Import** → run the import.

---

## 6. Reset a Student Password

On the server:
```bash
cd /home/schoolbell/app
sudo -u schoolbell venv/bin/python - <<'EOF'
import os; os.environ['FLASK_CONFIG'] = 'production'
from app import create_app, db, bcrypt
from app.models.models import User
app = create_app('production')
with app.app_context():
    s = User.query.filter_by(username='scott').first()
    new_pw = s.name.split()[-1].lower()
    s.password_hash    = bcrypt.generate_password_hash(new_pw).decode()
    s.display_password = new_pw
    db.session.commit()
    print(f'Password reset → {new_pw}')
EOF
```

### Reset ALL students to last-name passwords
```bash
cd /home/schoolbell/app
sudo -u schoolbell venv/bin/python - <<'EOF'
import os; os.environ['FLASK_CONFIG'] = 'production'
from app import create_app, db, bcrypt
from app.models.models import User
app = create_app('production')
with app.app_context():
    students = User.query.filter_by(role='student').all()
    for s in students:
        pw = s.name.split()[-1].lower()
        s.password_hash    = bcrypt.generate_password_hash(pw).decode()
        s.display_password = pw
        db.session.commit()
        print(f'  {s.name:20s} → {pw}')
    print(f'\nUpdated {len(students)} student(s)')
EOF
```

---

## 7. SSL Certificate

Certbot auto-renews every 90 days. To manually renew early:
```bash
sudo certbot renew --dry-run    # test (safe, doesn't change anything)
sudo certbot renew              # actually renew
sudo systemctl reload nginx
```

Check expiry date:
```bash
sudo certbot certificates
```

---

## 8. Disk Space Check

```bash
df -h                                         # overall disk usage
du -sh /home/schoolbell/app/uploads/          # PDF uploads size
du -sh /home/schoolbell/app/schoolbell.db     # database size
```

---

## 9. Full Redeploy from Scratch (emergency)

If the server is broken and you need to start fresh:

```bash
sudo bash /home/schoolbell/app/deploy/setup_server.sh
sudo nano /home/schoolbell/app/.env
sudo bash /home/schoolbell/app/deploy/deploy_app.sh
sudo certbot --nginx -d schoolbell.fun -d www.schoolbell.fun \
  --non-interactive --agree-tos -m rajkumar.durai@gmail.com
```

### .env file contents
```
FLASK_SECRET_KEY=<your-secret-key>
ANTHROPIC_API_KEY=<your-api-key>
FLASK_CONFIG=production
```

---

## 10. Useful One-Liners

> **sqlite3 CLI not installed.** Use Python instead:
> ```bash
> sudo -u schoolbell /home/schoolbell/app/venv/bin/python3 -c "
> import sqlite3; conn = sqlite3.connect('/home/schoolbell/app/schoolbell.db')
> cur = conn.cursor(); cur.execute('YOUR SQL HERE'); print(cur.fetchall()); conn.close()"
> ```

```bash
# How long has the app been running?
sudo systemctl status schoolbell | grep Active

# Count uploaded PDFs
ls /home/schoolbell/app/uploads/*.pdf | wc -l

# Count questions in the database
sudo -u schoolbell /home/schoolbell/app/venv/bin/python3 -c "
import sqlite3; c=sqlite3.connect('/home/schoolbell/app/schoolbell.db')
print(c.execute('SELECT COUNT(*) FROM questions').fetchone()[0],'questions'); c.close()"

# Count questions that have a diagram
sudo -u schoolbell /home/schoolbell/app/venv/bin/python3 -c "
import sqlite3; c=sqlite3.connect('/home/schoolbell/app/schoolbell.db')
print(c.execute(\"SELECT COUNT(*) FROM questions WHERE diagram_svg IS NOT NULL\").fetchone()[0],'with diagrams'); c.close()"

# Count students
sudo -u schoolbell /home/schoolbell/app/venv/bin/python3 -c "
import sqlite3; c=sqlite3.connect('/home/schoolbell/app/schoolbell.db')
print(c.execute(\"SELECT COUNT(*) FROM users WHERE role='student'\").fetchone()[0],'students'); c.close()"

# Who logged in recently (last 20 access log lines)
sudo tail -20 /home/schoolbell/app/logs/access.log

# Restart everything at once
sudo systemctl restart schoolbell && sudo systemctl reload nginx

# Check gunicorn workers
ps aux | grep gunicorn

# Check active connections to Anthropic API
ss -tp state established | grep python
```

---

## 11. Troubleshooting Question Generation

**Symptom:** Spinner runs forever, no questions generated.

**Step 1 — Check if the POST reaches the server:**
```bash
sudo tail -f /home/schoolbell/app/logs/error.log
```
You should see `[generate_questions] start` within a second of clicking Generate.

**Step 2 — If no log appears:** Worker threads may be exhausted. Restart gunicorn:
```bash
sudo systemctl restart schoolbell
```
Then try again with **10 questions** first to confirm it works.

**Step 3 — If you see a JSON parse error:** The API response was malformed or truncated. Try fewer questions. Maximum is 50 per run (enforced by the slider and server-side cap).

**Step 4 — If you see a timeout error:** The Anthropic API took >240 seconds. Try again — usually temporary API slowness. 10 questions ~30s; 50 questions ~90s.

**Step 5 — If you see "credit balance too low":** Top up at https://console.anthropic.com — go to Billing.

**Root causes discovered and fixed:**
- `btn.disabled = true` synchronously in `onclick` blocked Chrome from submitting — fixed by using the form `submit` event
- No timeout on Anthropic client caused threads to hang — fixed with 240s timeout
- Questions capped at 50 per run (slider max + server-side enforcement)
- `chmod -R 755` changing file permissions caused `git pull` conflicts — fixed by using `git reset --hard` in deploy script and setting `core.fileMode false`

---

## 12. Database Schema Notes

New columns added via inline migration in `init_db.py` (runs automatically on deploy):

| Table | Column | Added | Purpose |
|---|---|---|---|
| `questions` | `diagram_svg` | May 2026 | Optional inline SVG diagram for geometry/visual questions |

If you need to manually check or add a column:
```bash
sudo -u schoolbell /home/schoolbell/app/venv/bin/python3 -c "
import sqlite3; c=sqlite3.connect('/home/schoolbell/app/schoolbell.db')
print([r[1] for r in c.execute('PRAGMA table_info(questions)').fetchall()]); c.close()"
```
