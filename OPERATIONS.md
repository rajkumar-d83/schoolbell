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

# 1. Edit files in VS Code or any editor

# 2. Stage and commit
git add <filename>          # add specific file
git add .                   # add everything changed

git commit -m "Short description of what you changed"

# 3. Push to GitHub
git push origin main
```

### On the server — pull and restart

```bash
sudo bash /home/schoolbell/app/deploy/deploy_app.sh
```

This pulls the latest code, installs any new packages, and restarts the app automatically.

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

### Backup the production database (run on server)
```bash
cd /home/schoolbell/app
sudo -u schoolbell sqlite3 schoolbell.db ".backup '/home/schoolbell/schoolbell_backup_$(date +%Y%m%d).db'"
ls -lh /home/schoolbell/schoolbell_backup_*.db
```

### Download backup to your PC (run in local PowerShell)
```powershell
scp -i "C:\Users\durai\Downloads\schoolbell-key.pem" `
    ubuntu@3.26.97.121:/home/schoolbell/schoolbell_backup_*.db `
    C:\projects\SchoolBell\backups\
```

### Push local database to server (if you want to sync dev → prod)
```powershell
# Step 1: Flush WAL on local PC
cd C:\projects\SchoolBell
venv\Scripts\python.exe -c "import sqlite3; c=sqlite3.connect('schoolbell_dev.db'); c.execute('PRAGMA wal_checkpoint(TRUNCATE)'); c.close(); print('Done')"

# Step 2: Create clean copy
venv\Scripts\python.exe -c "
import sqlite3
src = sqlite3.connect('schoolbell_dev.db')
dst = sqlite3.connect('schoolbell_clean.db')
src.backup(dst); dst.close(); src.close()
print('Clean copy ready')
"

# Step 3: Upload to server
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
    # Change 'scott tiger' to the student's actual username
    s = User.query.filter_by(username='scott').first()
    new_pw = s.name.split()[-1].lower()   # resets to last name
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
sudo certbot renew --dry-run    # test renewal (safe, doesn't change anything)
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
# On server
sudo bash /home/schoolbell/app/deploy/setup_server.sh
# Then recreate .env (see step below)
sudo nano /home/schoolbell/app/.env
# Then deploy
sudo bash /home/schoolbell/app/deploy/deploy_app.sh
# Then SSL
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

```bash
# How long has the app been running?
sudo systemctl status schoolbell | grep Active

# Count uploaded PDFs
ls /home/schoolbell/app/uploads/*.pdf | wc -l

# Count questions in the database
sudo -u schoolbell sqlite3 /home/schoolbell/app/schoolbell.db "SELECT COUNT(*) FROM questions;"

# Count students
sudo -u schoolbell sqlite3 /home/schoolbell/app/schoolbell.db "SELECT COUNT(*) FROM users WHERE role='student';"

# Who logged in recently (last 20 access log lines)
sudo tail -20 /home/schoolbell/app/logs/access.log

# Restart everything at once
sudo systemctl restart schoolbell && sudo systemctl reload nginx
```
