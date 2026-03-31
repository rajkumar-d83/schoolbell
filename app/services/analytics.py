from app.models.models import QuizSession, QuestionAttempt, Subject, Chapter


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
