"""
seed_db.py — SchoolBell Database Seeder
========================================
Run once (or any number of times — it is fully idempotent) to:
  1. Create all database tables
  2. Create the default parent account
  3. Seed sample subjects for Grade 3 and Grade 7

Usage:
    python seed_db.py
"""

import sys
from app import create_app, db, bcrypt
from app.models.models import User, Subject


def seed():
    app = create_app('development')

    with app.app_context():

        # ── Step 1: Create all tables ──────────────────────────────────────────
        print("\n📦  SchoolBell Database Seeder")
        print("=" * 45)
        print("\n[1/3] Creating database tables...")
        try:
            db.create_all()
            print("      ✅  All tables created (or already exist).")
        except Exception as e:
            print(f"      ❌  Error creating tables: {e}")
            sys.exit(1)

        # ── Step 2: Default parent account ────────────────────────────────────
        print("\n[2/3] Seeding default parent account...")
        existing_parent = User.query.filter_by(username='parent').first()
        if existing_parent:
            print("      ⏭️   Parent account already exists — skipping.")
        else:
            try:
                pw_hash = bcrypt.generate_password_hash('schoolbell123').decode('utf-8')
                parent = User(
                    name='Parent / Teacher',
                    username='parent',
                    email='parent@schoolbell.local',
                    password_hash=pw_hash,
                    role='parent',
                    grade=None,
                    is_active=True,
                )
                db.session.add(parent)
                db.session.commit()
                print("      ✅  Parent account created.")
                print("          Username : parent")
                print("          Password : schoolbell123")
            except Exception as e:
                db.session.rollback()
                print(f"      ❌  Error creating parent account: {e}")
                sys.exit(1)

        # ── Step 3: Sample subjects ────────────────────────────────────────────
        print("\n[3/3] Seeding sample subjects...")

        sample_subjects = [
            ('Science',      7),
            ('Mathematics',  3),
            ('English',      7),
            ('English',      3),
            ('Social Science', 7),
        ]

        added = 0
        skipped = 0
        for name, grade in sample_subjects:
            exists = Subject.query.filter_by(name=name, grade=grade).first()
            if exists:
                print(f"      ⏭️   Subject '{name}' (Grade {grade}) already exists — skipping.")
                skipped += 1
            else:
                try:
                    db.session.add(Subject(name=name, grade=grade))
                    db.session.commit()
                    print(f"      ✅  Added subject '{name}' for Grade {grade}.")
                    added += 1
                except Exception as e:
                    db.session.rollback()
                    print(f"      ❌  Error adding subject '{name}': {e}")

        print(f"\n      Summary: {added} subject(s) added, {skipped} skipped.")

        # ── Done ───────────────────────────────────────────────────────────────
        print("\n" + "=" * 45)
        print("🎉  Seeding complete! You're ready to go.\n")
        print("    Run the app :  python run.py")
        print("    Open browser:  http://localhost:5000")
        print("    Login (parent): username=parent  password=schoolbell123")
        print("=" * 45 + "\n")


if __name__ == '__main__':
    seed()
