"""Run on every deployment to create/migrate tables and seed default data."""
import os
from sqlalchemy import text, inspect as sa_inspect
from app import create_app, db

config_name = os.environ.get('FLASK_CONFIG', 'production')
app = create_app(config_name)

with app.app_context():
    db.create_all()

    insp = sa_inspect(db.engine)

    # ── Column migrations ─────────────────────────────────────────────────────
    existing_q = {c['name'] for c in insp.get_columns('questions')}
    if 'diagram_svg' not in existing_q:
        db.session.execute(text('ALTER TABLE questions ADD COLUMN diagram_svg TEXT'))
        db.session.commit()
        print('  Migrated: added diagram_svg to questions')

    # ── Seed Grade 11 & 12 subjects ──────────────────────────────────────────
    from app.models.models import Subject, ExamCategory

    senior_subjects = ['Physics', 'Chemistry', 'Mathematics', 'Biology', 'English Core']
    for grade in (11, 12):
        for name in senior_subjects:
            exists = Subject.query.filter_by(name=name, grade=grade).first()
            if not exists:
                db.session.add(Subject(name=name, grade=grade))
                print(f'  Seeded: Grade {grade} – {name}')
    db.session.commit()

    # ── Seed JEE categories ───────────────────────────────────────────────────
    jee_cats = [
        ('JEE Main',     'Joint Entrance Examination – Main (NTA). Previous year question papers.'),
        ('JEE Advanced', 'Joint Entrance Examination – Advanced (IIT). Previous year question papers.'),
    ]
    for name, desc in jee_cats:
        if not ExamCategory.query.filter_by(name=name).first():
            db.session.add(ExamCategory(name=name, description=desc))
            print(f'  Seeded: ExamCategory – {name}')
    db.session.commit()

    print(f'Database initialised ({config_name}).')
    print(f'  URI: {app.config["SQLALCHEMY_DATABASE_URI"]}')
