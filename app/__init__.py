from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_wtf.csrf import CSRFProtect
from config import config

db = SQLAlchemy()
login_manager = LoginManager()
bcrypt = Bcrypt()
csrf = CSRFProtect()

login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'warning'


def create_app(config_name='development'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    db.init_app(app)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    csrf.init_app(app)

    # Enable WAL mode for SQLite so readers don't block writers
    if app.config['SQLALCHEMY_DATABASE_URI'].startswith('sqlite'):
        from sqlalchemy import event
        from sqlalchemy.engine import Engine
        import sqlite3

        @event.listens_for(Engine, 'connect')
        def set_wal_mode(dbapi_conn, _):
            if isinstance(dbapi_conn, sqlite3.Connection):
                dbapi_conn.execute('PRAGMA journal_mode=WAL')
                dbapi_conn.execute('PRAGMA synchronous=NORMAL')

    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.student import student_bp
    from app.routes.parent import parent_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(parent_bp)

    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template('errors/500.html'), 500

    @app.errorhandler(413)
    def file_too_large(e):
        from flask import flash, redirect, url_for
        flash('File too large. Maximum upload size is 16 MB.', 'danger')
        return redirect(url_for('parent.upload'))

    return app


@login_manager.user_loader
def load_user(user_id):
    from app.models.models import User
    return User.query.get(int(user_id))
