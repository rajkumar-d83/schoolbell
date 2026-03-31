from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime
from app import db
from app.models.models import Subject, Chapter, Question, QuizSession, QuestionAttempt
from app.services.analytics import get_student_performance

student_bp = Blueprint('student', __name__, url_prefix='/student')


def student_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if current_user.role != 'student':
            flash('Student access required.', 'danger')
            return redirect(url_for('parent.dashboard'))
        return f(*args, **kwargs)
    return decorated


@student_bp.route('/dashboard')
@login_required
@student_required
def dashboard():
    subjects = Subject.query.filter_by(grade=current_user.grade).all()
    performance = get_student_performance(current_user.id)
    return render_template('student/dashboard.html',
                           subjects=subjects, performance=performance)


@student_bp.route('/subjects')
@login_required
@student_required
def subjects():
    subjects = Subject.query.filter_by(grade=current_user.grade).all()
    return render_template('student/subjects.html', subjects=subjects)


@student_bp.route('/subjects/<int:subject_id>/chapters')
@login_required
@student_required
def chapters(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    chapters = Chapter.query.filter_by(subject_id=subject_id).order_by(Chapter.chapter_number).all()
    return render_template('student/chapters.html', subject=subject, chapters=chapters)


@student_bp.route('/quiz/start/<int:chapter_id>')
@login_required
def start_quiz(chapter_id):
    chapter = Chapter.query.get_or_404(chapter_id)
    questions = Question.query.filter_by(chapter_id=chapter_id).all()

    if not questions:
        flash('No questions available for this chapter yet.', 'warning')
        return redirect(url_for('student.subjects'))

    # Create a new quiz session
    session = QuizSession(
        student_id=current_user.id,
        chapter_id=chapter_id,
        total_questions=len(questions)
    )
    db.session.add(session)
    db.session.commit()

    return redirect(url_for('student.quiz',
                            session_id=session.id, question_index=0))


@student_bp.route('/quiz/<int:session_id>/<int:question_index>')
@login_required
def quiz(session_id, question_index):
    quiz_session = QuizSession.query.get_or_404(session_id)
    chapter = Chapter.query.get(quiz_session.chapter_id)
    questions = Question.query.filter_by(chapter_id=quiz_session.chapter_id).all()

    if question_index >= len(questions):
        return redirect(url_for('student.complete_quiz', session_id=session_id))

    question = questions[question_index]
    return render_template('student/quiz.html',
                           quiz_session=quiz_session,
                           chapter=chapter,
                           question=question,
                           question_index=question_index,
                           total_questions=len(questions),
                           session_id=session_id)


@student_bp.route('/quiz/submit', methods=['POST'])
@login_required
def submit_answer():
    session_id     = request.form.get('session_id', type=int)
    question_id    = request.form.get('question_id', type=int)
    question_index = request.form.get('question_index', type=int)
    chosen_answer  = request.form.get('chosen_answer', '').strip().upper() or None
    time_taken     = request.form.get('time_taken', type=int)

    quiz_session = QuizSession.query.get_or_404(session_id)
    question     = Question.query.get_or_404(question_id)

    is_correct = chosen_answer == question.correct_answer

    attempt = QuestionAttempt(
        session_id=session_id,
        question_id=question_id,
        chosen_answer=chosen_answer,
        is_correct=is_correct,
        time_taken_seconds=time_taken
    )
    db.session.add(attempt)

    if is_correct:
        quiz_session.correct_answers += 1

    db.session.commit()

    next_index = question_index + 1
    questions = Question.query.filter_by(chapter_id=quiz_session.chapter_id).all()

    if next_index >= len(questions):
        return redirect(url_for('student.complete_quiz', session_id=session_id))

    return redirect(url_for('student.quiz',
                            session_id=session_id, question_index=next_index))


@student_bp.route('/quiz/<int:session_id>/complete')
@login_required
def complete_quiz(session_id):
    quiz_session = QuizSession.query.get_or_404(session_id)

    if not quiz_session.is_completed:
        if quiz_session.total_questions > 0:
            quiz_session.score_percent = (
                quiz_session.correct_answers / quiz_session.total_questions * 100
            )
        quiz_session.is_completed = True
        quiz_session.completed_at = datetime.utcnow()
        db.session.commit()

    attempts = QuestionAttempt.query.filter_by(session_id=session_id).all()
    return render_template('student/quiz_complete.html',
                           quiz_session=quiz_session, attempts=attempts)


@student_bp.route('/performance')
@login_required
@student_required
def performance():
    performance = get_student_performance(current_user.id)
    return render_template('student/performance.html', performance=performance)
