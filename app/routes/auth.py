from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import bcrypt
from app.models.models import User

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.role == 'parent':
            return redirect(url_for('parent.dashboard'))
        return redirect(url_for('student.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        user = User.query.filter_by(username=username).first()

        if user and bcrypt.check_password_hash(user.password_hash, password):
            login_user(user)
            flash(f'Welcome back, {user.name}!', 'success')
            if user.role == 'parent':
                return redirect(url_for('parent.dashboard'))
            return redirect(url_for('student.dashboard'))
        else:
            flash('Invalid username or password.', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))
