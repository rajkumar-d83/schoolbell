"""Run once on a fresh deployment to create all database tables."""
import os
from app import create_app, db

config_name = os.environ.get('FLASK_CONFIG', 'production')
app = create_app(config_name)

with app.app_context():
    db.create_all()
    print(f'Database initialised ({config_name}).')
    print(f'  URI: {app.config["SQLALCHEMY_DATABASE_URI"]}')
