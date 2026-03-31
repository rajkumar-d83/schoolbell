from datetime import datetime
from app import db


class User(db.Model):
    __tablename__ = 'users'

    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(100), nullable=False)
    username      = db.Column(db.String(50), nullable=False, unique=True)
    email         = db.Column(db.String(150), nullable=False, unique=True)
    password_hash = db.Column(db.String(200), nullable=False)
    role          = db.Column(db.String(20), nullable=False)   # 'student' | 'parent'
    grade         = db.Column(db.Integer, nullable=True)       # 3 or 7 for students
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    is_active     = db.Column(db.Boolean, default=True)

    # Relationships
    quiz_sessions   = db.relationship('QuizSession', foreign_keys='QuizSession.student_id', backref='student', lazy=True)
    uploaded_chapters = db.relationship('Chapter', foreign_keys='Chapter.uploaded_by', backref='uploader', lazy=True)
    teach_sessions_as_parent  = db.relationship('TeachSession', foreign_keys='TeachSession.parent_id', backref='teacher', lazy=True)
    teach_sessions_as_student = db.relationship('TeachSession', foreign_keys='TeachSession.student_id', backref='learner', lazy=True)

    # Flask-Login
    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)

    def __repr__(self):
        return f'<User {self.username} ({self.role})>'


class Subject(db.Model):
    __tablename__ = 'subjects'

    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(100), nullable=False)
    grade      = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    chapters = db.relationship('Chapter', backref='subject', lazy=True)

    def __repr__(self):
        return f'<Subject {self.name} Grade {self.grade}>'


class Chapter(db.Model):
    __tablename__ = 'chapters'

    id             = db.Column(db.Integer, primary_key=True)
    subject_id     = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    title          = db.Column(db.String(200), nullable=False)
    chapter_number = db.Column(db.Integer, nullable=True)
    pdf_filename   = db.Column(db.String(300), nullable=True)
    pdf_text       = db.Column(db.Text, nullable=True)
    is_processed   = db.Column(db.Boolean, default=False)
    uploaded_at    = db.Column(db.DateTime, default=datetime.utcnow)
    uploaded_by    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    questions      = db.relationship('Question', backref='chapter', lazy=True)
    quiz_sessions  = db.relationship('QuizSession', backref='chapter', lazy=True)
    teach_sessions = db.relationship('TeachSession', backref='chapter', lazy=True)

    def __repr__(self):
        return f'<Chapter {self.title}>'


class Question(db.Model):
    __tablename__ = 'questions'

    id             = db.Column(db.Integer, primary_key=True)
    chapter_id     = db.Column(db.Integer, db.ForeignKey('chapters.id'), nullable=False)
    question_text  = db.Column(db.Text, nullable=False)
    option_a       = db.Column(db.String(500), nullable=False)
    option_b       = db.Column(db.String(500), nullable=False)
    option_c       = db.Column(db.String(500), nullable=False)
    option_d       = db.Column(db.String(500), nullable=False)
    correct_answer = db.Column(db.String(1), nullable=False)   # A/B/C/D
    explanation    = db.Column(db.Text, nullable=True)
    difficulty     = db.Column(db.String(20), default='medium')
    topic_tag      = db.Column(db.String(100), nullable=True)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    attempts = db.relationship('QuestionAttempt', backref='question', lazy=True)

    def __repr__(self):
        return f'<Question {self.id}: {self.question_text[:40]}>'


class QuizSession(db.Model):
    __tablename__ = 'quiz_sessions'

    id              = db.Column(db.Integer, primary_key=True)
    student_id      = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    chapter_id      = db.Column(db.Integer, db.ForeignKey('chapters.id'), nullable=False)
    total_questions = db.Column(db.Integer, default=0)
    correct_answers = db.Column(db.Integer, default=0)
    score_percent   = db.Column(db.Float, default=0.0)
    started_at      = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at    = db.Column(db.DateTime, nullable=True)
    is_completed    = db.Column(db.Boolean, default=False)

    attempts = db.relationship('QuestionAttempt', backref='session', lazy=True)

    def __repr__(self):
        return f'<QuizSession {self.id} student={self.student_id}>'


class QuestionAttempt(db.Model):
    __tablename__ = 'question_attempts'

    id                 = db.Column(db.Integer, primary_key=True)
    session_id         = db.Column(db.Integer, db.ForeignKey('quiz_sessions.id'), nullable=False)
    question_id        = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    chosen_answer      = db.Column(db.String(1), nullable=True)
    is_correct         = db.Column(db.Boolean, default=False)
    time_taken_seconds = db.Column(db.Integer, nullable=True)
    answered_at        = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<QuestionAttempt session={self.session_id} q={self.question_id}>'


class TeachSession(db.Model):
    __tablename__ = 'teach_sessions'

    id         = db.Column(db.Integer, primary_key=True)
    chapter_id = db.Column(db.Integer, db.ForeignKey('chapters.id'), nullable=False)
    parent_id  = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes      = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f'<TeachSession chapter={self.chapter_id} parent={self.parent_id}>'
