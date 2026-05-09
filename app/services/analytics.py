from app.models.models import QuizSession, QuestionAttempt, Subject, Chapter

# ── XP / Level system ────────────────────────────────────────────
_LEVELS = [
    {'num': 1, 'name': 'Seedling',  'icon': '🌱', 'min': 0,    'max': 50},
    {'num': 2, 'name': 'Explorer',  'icon': '🔍', 'min': 50,   'max': 150},
    {'num': 3, 'name': 'Learner',   'icon': '📖', 'min': 150,  'max': 300},
    {'num': 4, 'name': 'Scholar',   'icon': '🎓', 'min': 300,  'max': 500},
    {'num': 5, 'name': 'Expert',    'icon': '⚡', 'min': 500,  'max': 800},
    {'num': 6, 'name': 'Master',    'icon': '🌟', 'min': 800,  'max': 1200},
    {'num': 7, 'name': 'Champion',  'icon': '🏆', 'min': 1200, 'max': None},
]


def xp_for_session(score_percent):
    """XP awarded for one completed quiz session."""
    xp = 10
    if score_percent >= 60:
        xp += 5
    if score_percent >= 80:
        xp += 10
    if score_percent == 100:
        xp += 20
    return xp


def compute_total_xp(sessions):
    return sum(xp_for_session(s.score_percent) for s in sessions)


def get_level_info(xp):
    for lvl in _LEVELS:
        if lvl['max'] is None or xp < lvl['max']:
            span = (lvl['max'] - lvl['min']) if lvl['max'] else 1
            progress = (xp - lvl['min']) / span * 100
            return {
                'level':    lvl['num'],
                'name':     lvl['name'],
                'icon':     lvl['icon'],
                'xp':       xp,
                'min_xp':   lvl['min'],
                'next_xp':  lvl['max'],
                'progress': min(100, max(0, progress)),
                'is_max':   lvl['max'] is None,
            }
    return get_level_info(0)


def get_student_badges(student_id):
    """Return a list of earned badge dicts for a student, computed from quiz history."""
    sessions = (QuizSession.query
                .filter_by(student_id=student_id, is_completed=True)
                .order_by(QuizSession.completed_at.asc())
                .all())

    badges = []

    if not sessions:
        return badges

    # First Quiz
    badges.append({'id': 'first_quiz', 'icon': '🎯', 'name': 'First Quiz',
                   'desc': 'Completed your very first quiz!'})

    # Volume milestones
    if len(sessions) >= 5:
        badges.append({'id': 'enthusiast', 'icon': '📚', 'name': 'Enthusiast',
                       'desc': 'Finished 5 quizzes — keep it up!'})
    if len(sessions) >= 20:
        badges.append({'id': 'quiz_master', 'icon': '🏅', 'name': 'Quiz Master',
                       'desc': 'Completed 20 quizzes. Impressive!'})

    # Perfect score ever
    if any(s.score_percent == 100 for s in sessions):
        badges.append({'id': 'perfect', 'icon': '🏆', 'name': 'Perfect Score',
                       'desc': 'Scored 100% on a quiz!'})

    # Overall average ≥ 80%
    avg = sum(s.score_percent for s in sessions) / len(sessions)
    if avg >= 80:
        badges.append({'id': 'high_achiever', 'icon': '⭐', 'name': 'High Achiever',
                       'desc': 'Overall average of 80% or above!'})

    # Hot streak: 3 consecutive sessions with score ≥ 80%
    streak = max_streak = 0
    for s in sessions:
        streak = streak + 1 if s.score_percent >= 80 else 0
        max_streak = max(max_streak, streak)
    if max_streak >= 3:
        badges.append({'id': 'on_fire', 'icon': '🔥', 'name': 'On Fire!',
                       'desc': '3 quizzes in a row scoring 80% or more!'})

    # Comeback Kid: improved score vs previous attempt in the same chapter
    chapter_scores = {}
    for s in sessions:
        prev = chapter_scores.get(s.chapter_id)
        if prev is not None and s.score_percent > prev:
            badges.append({'id': 'comeback', 'icon': '💪', 'name': 'Comeback Kid',
                           'desc': 'Scored higher than your previous attempt!'})
            break
        chapter_scores[s.chapter_id] = s.score_percent

    # XP level badges
    total_xp = compute_total_xp(sessions)
    level = get_level_info(total_xp)
    if level['level'] >= 3:
        badges.append({'id': 'lv3', 'icon': '📖', 'name': 'Learner',
                       'desc': 'Reached Level 3!'})
    if level['level'] >= 5:
        badges.append({'id': 'lv5', 'icon': '⚡', 'name': 'Expert',
                       'desc': 'Reached Level 5!'})
    if level['level'] >= 7:
        badges.append({'id': 'lv7', 'icon': '🏆', 'name': 'Champion',
                       'desc': 'Reached the maximum level!'})

    return badges


def get_student_performance(student_id):
    """Return a performance summary dict for a given student."""

    # All completed sessions
    sessions = (QuizSession.query
                .filter_by(student_id=student_id, is_completed=True)
                .order_by(QuizSession.completed_at.desc())
                .all())

    total_sessions = len(sessions)
    total_correct  = sum(s.correct_answers for s in sessions)
    avg_score      = (sum(s.score_percent for s in sessions) / total_sessions
                      if total_sessions else 0)

    # Per-subject breakdown
    subject_map = {}
    for session in sessions:
        chapter = Chapter.query.get(session.chapter_id)
        if not chapter:
            continue
        subject = Subject.query.get(chapter.subject_id)
        if not subject:
            continue
        key = subject.id
        if key not in subject_map:
            subject_map[key] = {
                'subject_name': subject.name,
                'quiz_count': 0,
                'score_sum': 0.0,
            }
        subject_map[key]['quiz_count'] += 1
        subject_map[key]['score_sum']  += session.score_percent

    subject_scores = []
    for data in subject_map.values():
        data['avg_score'] = data['score_sum'] / data['quiz_count']
        subject_scores.append(data)
    subject_scores.sort(key=lambda x: x['avg_score'])

    # Weak topic detection (accuracy < 60%)
    all_attempts = (QuestionAttempt.query
                    .join(QuizSession,
                          QuestionAttempt.session_id == QuizSession.id)
                    .filter(QuizSession.student_id == student_id)
                    .all())

    tag_map = {}
    for attempt in all_attempts:
        tag = attempt.question.topic_tag if attempt.question and attempt.question.topic_tag else None
        if not tag:
            continue
        if tag not in tag_map:
            tag_map[tag] = {'correct': 0, 'total': 0}
        tag_map[tag]['total'] += 1
        if attempt.is_correct:
            tag_map[tag]['correct'] += 1

    weak_topics = []
    for tag, data in tag_map.items():
        accuracy = data['correct'] / data['total'] * 100
        if accuracy < 60:
            weak_topics.append({'tag': tag, 'accuracy': accuracy})
    weak_topics.sort(key=lambda x: x['accuracy'])

    return {
        'total_sessions':  total_sessions,
        'total_correct':   total_correct,
        'avg_score':       avg_score,
        'subject_scores':  subject_scores,
        'weak_topics':     weak_topics,
        'recent_sessions': sessions[:10],
    }
