from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime
import json, random
from app import db
from app.models.models import Subject, Chapter, Question, QuizSession, QuestionAttempt
from app.services.analytics import (get_student_performance, get_student_badges,
                                    xp_for_session, compute_total_xp, get_level_info)

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
    badges = get_student_badges(current_user.id)
    all_sessions = QuizSession.query.filter_by(student_id=current_user.id, is_completed=True).all()
    level_info = get_level_info(compute_total_xp(all_sessions))
    return render_template('student/dashboard.html',
                           subjects=subjects, performance=performance,
                           badges=badges, level_info=level_info)


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


QUIZ_SIZE = 5   # questions per quiz attempt

@student_bp.route('/quiz/start/<int:chapter_id>')
@login_required
def start_quiz(chapter_id):
    chapter = Chapter.query.get_or_404(chapter_id)
    all_questions = Question.query.filter_by(chapter_id=chapter_id).all()

    if not all_questions:
        flash('No questions available for this chapter yet.', 'warning')
        return redirect(url_for('student.subjects'))

    # IDs the student already got right in completed sessions for this chapter
    prev_correct_ids = {
        row[0] for row in
        db.session.query(QuestionAttempt.question_id)
        .join(QuizSession, QuestionAttempt.session_id == QuizSession.id)
        .filter(
            QuizSession.student_id == current_user.id,
            QuizSession.chapter_id == chapter_id,
            QuizSession.is_completed == True,
            QuestionAttempt.is_correct == True
        ).all()
    }

    # Prefer unseen/wrong questions; pad with correct ones only if needed
    fresh   = [q for q in all_questions if q.id not in prev_correct_ids]
    mastered = [q for q in all_questions if q.id in prev_correct_ids]

    if len(fresh) >= QUIZ_SIZE:
        selected = random.sample(fresh, QUIZ_SIZE)
    else:
        pad = random.sample(mastered, min(QUIZ_SIZE - len(fresh), len(mastered)))
        selected = fresh + pad
        random.shuffle(selected)

    selected_ids = [q.id for q in selected]

    session = QuizSession(
        student_id=current_user.id,
        chapter_id=chapter_id,
        total_questions=len(selected_ids),
        question_ids=json.dumps(selected_ids)
    )
    db.session.add(session)
    db.session.commit()

    return redirect(url_for('student.quiz',
                            session_id=session.id, question_index=0))


@student_bp.route('/quiz/mistakes/<int:chapter_id>')
@login_required
@student_required
def start_mistakes_quiz(chapter_id):
    chapter = Chapter.query.get_or_404(chapter_id)

    wrong_question_ids = {
        row[0] for row in
        db.session.query(QuestionAttempt.question_id)
        .join(QuizSession, QuestionAttempt.session_id == QuizSession.id)
        .filter(
            QuizSession.student_id == current_user.id,
            QuizSession.chapter_id == chapter_id,
            QuizSession.is_completed == True,
            QuestionAttempt.is_correct == False
        ).all()
    }

    if not wrong_question_ids:
        flash("No mistakes to practice — you've got them all right!", 'success')
        return redirect(url_for('student.chapters', subject_id=chapter.subject_id))

    questions = (Question.query
                 .filter(Question.id.in_(wrong_question_ids),
                         Question.chapter_id == chapter_id)
                 .all())
    random.shuffle(questions)
    selected = questions[:QUIZ_SIZE]

    session = QuizSession(
        student_id=current_user.id,
        chapter_id=chapter_id,
        total_questions=len(selected),
        question_ids=json.dumps([q.id for q in selected])
    )
    db.session.add(session)
    db.session.commit()

    return redirect(url_for('student.quiz', session_id=session.id, question_index=0))


@student_bp.route('/quiz/<int:session_id>/<int:question_index>')
@login_required
def quiz(session_id, question_index):
    quiz_session = QuizSession.query.get_or_404(session_id)
    chapter = Chapter.query.get(quiz_session.chapter_id)
    question_ids = json.loads(quiz_session.question_ids)

    if question_index >= len(question_ids):
        return redirect(url_for('student.complete_quiz', session_id=session_id))

    question = Question.query.get(question_ids[question_index])
    return render_template('student/quiz.html',
                           quiz_session=quiz_session,
                           chapter=chapter,
                           question=question,
                           question_index=question_index,
                           total_questions=len(question_ids),
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

    next_index   = question_index + 1
    question_ids = json.loads(quiz_session.question_ids)
    is_last      = next_index >= len(question_ids)

    next_url = (url_for('student.complete_quiz', session_id=session_id)
                if is_last
                else url_for('student.quiz', session_id=session_id, question_index=next_index))

    # AJAX response for the new instant-feedback quiz UI
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        correct_text = getattr(question, 'option_' + question.correct_answer.lower(), '')
        return jsonify({
            'is_correct':     is_correct,
            'correct_answer': question.correct_answer,
            'correct_text':   correct_text,
            'chosen_answer':  chosen_answer,
            'explanation':    question.explanation or '',
            'next_url':       next_url,
            'is_last':        is_last,
        })

    # Fallback for non-AJAX
    return redirect(next_url)


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
    xp_gained = xp_for_session(quiz_session.score_percent)
    all_sessions = QuizSession.query.filter_by(student_id=quiz_session.student_id, is_completed=True).all()
    level_info = get_level_info(compute_total_xp(all_sessions))
    return render_template('student/quiz_complete.html',
                           quiz_session=quiz_session, attempts=attempts,
                           xp_gained=xp_gained, level_info=level_info)


@student_bp.route('/quiz/<int:session_id>/message')
@login_required
def quiz_message(session_id):
    from app.services.ai_messages import generate_quiz_message
    quiz_session = QuizSession.query.get_or_404(session_id)
    chapter = Chapter.query.get(quiz_session.chapter_id)
    all_sessions = QuizSession.query.filter_by(student_id=quiz_session.student_id, is_completed=True).all()
    level_info = get_level_info(compute_total_xp(all_sessions))
    message = generate_quiz_message(
        student_name=current_user.name,
        chapter_title=chapter.title if chapter else 'the chapter',
        score_percent=quiz_session.score_percent,
        correct=quiz_session.correct_answers,
        total=quiz_session.total_questions,
        level_name=level_info['name'],
    )
    return jsonify({'message': message})


@student_bp.route('/chapters/<int:chapter_id>/read')
@login_required
@student_required
def read_chapter(chapter_id):
    chapter = Chapter.query.get_or_404(chapter_id)
    subject = Subject.query.get_or_404(chapter.subject_id)
    if not chapter.pdf_filename:
        flash('No PDF available for this chapter.', 'warning')
        return redirect(url_for('student.chapters', subject_id=subject.id))
    return render_template('student/read_chapter.html', chapter=chapter, subject=subject)


@student_bp.route('/performance')
@login_required
@student_required
def performance():
    performance = get_student_performance(current_user.id)
    return render_template('student/performance.html', performance=performance)


@student_bp.route('/chapters/<int:chapter_id>/flashcards')
@login_required
@student_required
def flashcards(chapter_id):
    chapter = Chapter.query.get_or_404(chapter_id)
    subject = Subject.query.get_or_404(chapter.subject_id)

    cards = []

    # Primary source: cheatsheet key_concepts + key_facts
    if chapter.cheatsheet:
        try:
            data = json.loads(chapter.cheatsheet)
            for item in data.get('key_concepts', []):
                cards.append({'front': item['term'], 'back': item['definition'], 'type': 'concept'})
            for fact in data.get('key_facts', []):
                cards.append({'front': 'Key Fact', 'back': fact, 'type': 'fact'})
        except Exception:
            pass

    # Fallback: quiz questions
    if not cards:
        qs = Question.query.filter_by(chapter_id=chapter_id).limit(20).all()
        for q in qs:
            correct_text = getattr(q, 'option_' + q.correct_answer.lower(), '')
            back = f"{q.correct_answer}: {correct_text}"
            if q.explanation:
                back += f"\n\n{q.explanation}"
            cards.append({'front': q.question_text, 'back': back, 'type': 'question',
                          'diagram_svg': q.diagram_svg or None})

    if not cards:
        flash('No flashcard content yet — generate questions or a cheatsheet first.', 'warning')
        return redirect(url_for('student.chapters', subject_id=subject.id))

    return render_template('student/flashcards.html',
                           chapter=chapter, subject=subject, cards=cards)


@student_bp.route('/subjects/<int:subject_id>/cheatsheet')
@login_required
@student_required
def subject_cheatsheet(subject_id):
    subject  = Subject.query.get_or_404(subject_id)
    chapters = (Chapter.query
                .filter_by(subject_id=subject_id)
                .order_by(Chapter.chapter_number, Chapter.uploaded_at)
                .all())

    chapter_data = []
    for ch in chapters:
        cs = None
        if ch.cheatsheet:
            try:
                cs = json.loads(ch.cheatsheet)
            except Exception:
                pass
        chapter_data.append({'chapter': ch, 'cheatsheet': cs})

    return render_template('shared/cheatsheet.html',
                           subject=subject,
                           chapter_data=chapter_data,
                           is_parent=False)
