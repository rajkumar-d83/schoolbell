from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, current_app, jsonify, send_from_directory)
from flask_login import login_required, current_user
from functools import wraps
from app import db
from app.models.models import (User, Subject, Chapter, Question,
                                QuizSession, QuestionAttempt, TeachSession)
from app.services.pdf_service import extract_pdf_text, generate_questions_from_text
from app.services.analytics import get_student_performance
import os

parent_bp = Blueprint('parent', __name__, url_prefix='/parent')


# ── Decorator ──────────────────────────────────────────────────────────────────
def parent_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if current_user.role != 'parent':
            flash('Parent access required.', 'danger')
            return redirect(url_for('student.dashboard'))
        return f(*args, **kwargs)
    return decorated


# ── Dashboard ──────────────────────────────────────────────────────────────────
@parent_bp.route('/dashboard')
@login_required
@parent_required
def dashboard():
    students       = User.query.filter_by(role='student', is_active=True).all()
    subjects       = Subject.query.all()
    total_questions = Question.query.count()
    recent_chapters = (Chapter.query
                       .order_by(Chapter.uploaded_at.desc())
                       .limit(5).all())
    return render_template('parent/dashboard.html',
                           students=students,
                           subjects=subjects,
                           total_questions=total_questions,
                           recent_chapters=recent_chapters)


# ── Students ───────────────────────────────────────────────────────────────────
@parent_bp.route('/students')
@login_required
@parent_required
def students():
    student_list = User.query.filter_by(role='student', is_active=True).order_by(User.name).all()
    return render_template('parent/students.html', students=student_list)


@parent_bp.route('/students/add', methods=['GET', 'POST'])
@login_required
@parent_required
def add_student():
    from app import bcrypt
    if request.method == 'POST':
        name     = request.form.get('name', '').strip()
        username = request.form.get('username', '').strip()
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        grade    = request.form.get('grade', type=int)

        if not all([name, username, email, password, grade]):
            flash('All fields are required.', 'danger')
            return redirect(url_for('parent.add_student'))

        if User.query.filter_by(username=username).first():
            flash('Username already taken.', 'danger')
            return redirect(url_for('parent.add_student'))

        if User.query.filter_by(email=email).first():
            flash('Email already in use.', 'danger')
            return redirect(url_for('parent.add_student'))

        pw_hash = bcrypt.generate_password_hash(password).decode('utf-8')
        new_student = User(name=name, username=username, email=email,
                           password_hash=pw_hash, role='student', grade=grade)
        db.session.add(new_student)
        db.session.commit()
        flash(f'Student {name} added successfully!', 'success')
        return redirect(url_for('parent.students'))

    return render_template('parent/add_student.html')


@parent_bp.route('/students/<int:student_id>/report')
@login_required
@parent_required
def student_report(student_id):
    student = User.query.get_or_404(student_id)
    performance = get_student_performance(student_id)
    return render_template('parent/student_report.html',
                           student=student, performance=performance)


# ── Subjects ───────────────────────────────────────────────────────────────────
@parent_bp.route('/subjects', methods=['GET', 'POST'])
@login_required
@parent_required
def subjects():
    if request.method == 'POST':
        name  = request.form.get('name', '').strip()
        grade = request.form.get('grade', type=int)
        if not name or not grade:
            flash('Valid subject name and grade are required.', 'danger')
        else:
            db.session.add(Subject(name=name, grade=grade))
            db.session.commit()
            flash(f'Subject "{name}" added for Grade {grade}.', 'success')
        return redirect(url_for('parent.subjects'))

    all_subjects = Subject.query.order_by(Subject.grade, Subject.name).all()
    subjects_by_grade = {}
    for s in all_subjects:
        subjects_by_grade.setdefault(s.grade, []).append(s)
    return render_template('parent/subjects.html', subjects_by_grade=subjects_by_grade)


@parent_bp.route('/subjects/<int:subject_id>/chapters')
@login_required
@parent_required
def subject_chapters(subject_id):
    subject  = Subject.query.get_or_404(subject_id)
    chapters = (Chapter.query
                .filter_by(subject_id=subject_id)
                .order_by(Chapter.chapter_number, Chapter.uploaded_at)
                .all())
    return render_template('parent/chapters.html', subject=subject, chapters=chapters)


@parent_bp.route('/subjects/<int:subject_id>/delete', methods=['POST'])
@login_required
@parent_required
def delete_subject(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    subject_name = subject.name
    for chapter in list(subject.chapters):
        _delete_chapter_cascade(chapter)
    db.session.delete(subject)
    db.session.commit()
    flash(f'Subject "{subject_name}" and all its chapters have been deleted.', 'success')
    return redirect(url_for('parent.subjects'))


@parent_bp.route('/chapters/<int:chapter_id>/delete', methods=['POST'])
@login_required
@parent_required
def delete_chapter(chapter_id):
    chapter    = Chapter.query.get_or_404(chapter_id)
    subject_id = chapter.subject_id
    title      = chapter.title
    _delete_chapter_cascade(chapter)
    db.session.commit()
    flash(f'Chapter "{title}" has been deleted.', 'success')
    return redirect(url_for('parent.subject_chapters', subject_id=subject_id))


def _delete_chapter_cascade(chapter):
    """Delete a chapter and all its related data (no commit)."""
    # Remove PDF file from disk
    if chapter.pdf_filename:
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], chapter.pdf_filename)
        try:
            os.remove(filepath)
        except OSError:
            pass
    # Delete in dependency order
    session_ids = [s.id for s in chapter.quiz_sessions]
    if session_ids:
        QuestionAttempt.query.filter(
            QuestionAttempt.session_id.in_(session_ids)
        ).delete(synchronize_session=False)
    QuizSession.query.filter_by(chapter_id=chapter.id).delete(synchronize_session=False)
    TeachSession.query.filter_by(chapter_id=chapter.id).delete(synchronize_session=False)
    Question.query.filter_by(chapter_id=chapter.id).delete(synchronize_session=False)
    db.session.delete(chapter)


# ── Upload PDF ─────────────────────────────────────────────────────────────────
@parent_bp.route('/upload', methods=['GET', 'POST'])
@login_required
@parent_required
def upload():
    subjects = Subject.query.order_by(Subject.grade, Subject.name).all()

    if request.method == 'POST':
        subject_id     = request.form.get('subject_id', type=int)
        chapter_title  = request.form.get('chapter_title', '').strip()
        chapter_number = request.form.get('chapter_number', type=int)
        pdf_file       = request.files.get('pdf_file')

        if not all([subject_id, chapter_title, pdf_file]):
            flash('Subject, chapter title, and PDF are required.', 'danger')
            return redirect(url_for('parent.upload'))

        allowed = {'pdf'}
        if '.' not in pdf_file.filename or \
                pdf_file.filename.rsplit('.', 1)[1].lower() not in allowed:
            flash('Only PDF files are allowed.', 'danger')
            return redirect(url_for('parent.upload'))

        upload_folder = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)
        filename = f"chapter_{subject_id}_{chapter_number or 0}_{pdf_file.filename}"
        filepath = os.path.join(upload_folder, filename)
        pdf_file.save(filepath)

        pdf_text = extract_pdf_text(filepath)

        chapter = Chapter(
            subject_id=subject_id,
            title=chapter_title,
            chapter_number=chapter_number,
            pdf_filename=filename,
            pdf_text=pdf_text,
            uploaded_by=current_user.id
        )
        db.session.add(chapter)
        db.session.commit()
        flash(f'Chapter "{chapter_title}" uploaded successfully!', 'success')
        return redirect(url_for('parent.generate_questions', chapter_id=chapter.id))

    return render_template('parent/upload.html', subjects=subjects)


# ── Generate Questions ─────────────────────────────────────────────────────────
@parent_bp.route('/chapters/<int:chapter_id>/generate', methods=['GET', 'POST'])
@login_required
@parent_required
def generate_questions(chapter_id):
    chapter = Chapter.query.get_or_404(chapter_id)

    if request.method == 'POST':
        num_questions = request.form.get('num_questions', 10, type=int)
        num_questions = max(5, min(20, num_questions))

        if not chapter.pdf_text:
            flash('No PDF text found. Please re-upload the PDF.', 'danger')
            return redirect(url_for('parent.generate_questions', chapter_id=chapter_id))

        questions = generate_questions_from_text(chapter.pdf_text, num_questions,
                                                 chapter.title)
        if questions:
            # Remove old questions first
            Question.query.filter_by(chapter_id=chapter_id).delete()
            for q in questions:
                db.session.add(Question(
                    chapter_id=chapter_id,
                    question_text=q['question_text'],
                    option_a=q['option_a'],
                    option_b=q['option_b'],
                    option_c=q['option_c'],
                    option_d=q['option_d'],
                    correct_answer=q['correct_answer'],
                    explanation=q.get('explanation', ''),
                    difficulty=q.get('difficulty', 'medium'),
                    topic_tag=q.get('topic_tag', '')
                ))
            chapter.is_processed = True
            db.session.commit()
            flash(f'{len(questions)} questions generated successfully!', 'success')
            return redirect(url_for('parent.view_questions', chapter_id=chapter_id))
        else:
            flash('Question generation failed. Check your API key and try again.', 'danger')

    page_count = 0
    if chapter.pdf_text:
        page_count = chapter.pdf_text.count('\f') + 1

    return render_template('parent/generate_questions.html',
                           chapter=chapter, page_count=page_count)


# ── View Questions ─────────────────────────────────────────────────────────────
@parent_bp.route('/chapters/<int:chapter_id>/questions')
@login_required
@parent_required
def view_questions(chapter_id):
    chapter   = Chapter.query.get_or_404(chapter_id)
    questions = Question.query.filter_by(chapter_id=chapter_id).all()
    return render_template('parent/view_questions.html',
                           chapter=chapter, questions=questions)


# ── Teaching Mode ──────────────────────────────────────────────────────────────
@parent_bp.route('/chapters/<int:chapter_id>/teach')
@login_required
@parent_required
def teach(chapter_id):
    chapter  = Chapter.query.get_or_404(chapter_id)
    subject  = Subject.query.get(chapter.subject_id)
    students = User.query.filter_by(role='student', grade=subject.grade).all()
    questions = Question.query.filter_by(chapter_id=chapter_id).all()

    teach_session = TeachSession(
        chapter_id=chapter_id,
        parent_id=current_user.id
    )
    db.session.add(teach_session)
    db.session.commit()

    return render_template('parent/teach.html',
                           chapter=chapter, subject=subject,
                           students=students, questions=questions,
                           teach_session_id=teach_session.id)


@parent_bp.route('/teach-session/<int:session_id>/notes', methods=['POST'])
@login_required
@parent_required
def save_teach_notes(session_id):
    teach_session = TeachSession.query.get_or_404(session_id)
    data = request.get_json()
    teach_session.notes = data.get('notes', '')
    db.session.commit()
    return jsonify({'status': 'saved'})


# ── Serve PDF ──────────────────────────────────────────────────────────────────
@parent_bp.route('/chapters/<int:chapter_id>/pdf')
@login_required
def serve_pdf(chapter_id):
    """Serve raw PDF file for PDF.js viewer. Accessible to both roles."""
    chapter = Chapter.query.get_or_404(chapter_id)
    if not chapter.pdf_filename:
        return 'PDF not found', 404
    upload_folder = current_app.config['UPLOAD_FOLDER']
    return send_from_directory(upload_folder, chapter.pdf_filename)
