"""Run once on a fresh deployment to create all database tables."""
import os
from sqlalchemy import text, inspect as sa_inspect
from app import create_app, db

config_name = os.environ.get('FLASK_CONFIG', 'production')
app = create_app(config_name)

with app.app_context():
    db.create_all()

    # Inline migrations — safe to run repeatedly; ADD COLUMN is a no-op if already present
    insp = sa_inspect(db.engine)
    existing = {c['name'] for c in insp.get_columns('questions')}
    if 'diagram_svg' not in existing:
        db.session.execute(text('ALTER TABLE questions ADD COLUMN diagram_svg TEXT'))
        db.session.commit()
        print('  Migrated: added diagram_svg to questions')

    print(f'Database initialised ({config_name}).')
    print(f'  URI: {app.config["SQLALCHEMY_DATABASE_URI"]}')
