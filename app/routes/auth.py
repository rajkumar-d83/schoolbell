from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from app import bcrypt, db
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

    # Unclaimed students for the picker (up to 10)
    unclaimed = (User.query
                 .filter_by(role='student', is_active=True, is_claimed=False)
                 .order_by(User.name)
                 .limit(10)
                 .all())

    return render_template('auth/login.html', unclaimed=unclaimed)


@auth_bp.route('/claim', methods=['POST'])
def claim():
    """Student picks an unclaimed account, sets grade, and logs in."""
    student_id = request.form.get('student_id', type=int)
    grade      = request.form.get('grade', type=int)

    if not student_id or not grade:
        flash('Please select a name and a grade.', 'danger')
        return redirect(url_for('auth.login'))

    student = User.query.filter_by(id=student_id, role='student',
                                   is_active=True, is_claimed=False).first()
    if not student:
        flash('That account is no longer available. Please pick another.', 'warning')
        return redirect(url_for('auth.login'))

    student.grade      = grade
    student.is_claimed = True
    db.session.commit()

    login_user(student)
    flash('Welcome, ' + student.name + '! You are now logged in.', 'success')
    return redirect(url_for('student.dashboard'))


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))
