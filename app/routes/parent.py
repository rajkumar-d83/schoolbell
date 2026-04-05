from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, current_app, jsonify, send_from_directory)
from flask_login import login_required, current_user
from functools import wraps
from app import db
from app.models.models import (User, Subject, Chapter, Question,
                                QuizSession, QuestionAttempt, TeachSession)
from app.services.pdf_service import extract_pdf_text, generate_questions_from_text
import fitz as _fitz_lib
from app.services.analytics import get_student_performance
import os, re, shutil, uuid

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


@parent_bp.route('/students/<int:student_id>/edit', methods=['GET', 'POST'])
@login_required
@parent_required
def edit_student(student_id):
    from app import bcrypt
    student = User.query.get_or_404(student_id)

    if request.method == 'POST':
        name     = request.form.get('name', '').strip()
        username = request.form.get('username', '').strip()
        email    = request.form.get('email', '').strip()
        grade    = request.form.get('grade', type=int)
        password = request.form.get('password', '').strip()

        if not all([name, username, email, grade]):
            flash('Name, username, email and grade are required.', 'danger')
            return redirect(url_for('parent.edit_student', student_id=student_id))

        conflict = User.query.filter(User.username == username, User.id != student_id).first()
        if conflict:
            flash('Username already taken by another account.', 'danger')
            return redirect(url_for('parent.edit_student', student_id=student_id))

        email_conflict = User.query.filter(User.email == email, User.id != student_id).first()
        if email_conflict:
            flash('Email already in use by another account.', 'danger')
            return redirect(url_for('parent.edit_student', student_id=student_id))

        student.name     = name
        student.username = username
        student.email    = email
        student.grade    = grade
        if password:
            student.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

        db.session.commit()
        flash(f'Student "{name}" updated successfully.', 'success')
        return redirect(url_for('parent.students'))

    return render_template('parent/edit_student.html', student=student)


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


@parent_bp.route('/chapters/<int:chapter_id>/rename', methods=['POST'])
@login_required
@parent_required
def rename_chapter(chapter_id):
    chapter = Chapter.query.get_or_404(chapter_id)
    new_title = request.form.get('title', '').strip()
    new_number = request.form.get('chapter_number', '').strip()
    if not new_title:
        flash('Chapter title cannot be empty.', 'danger')
    else:
        chapter.title = new_title[:200]
        chapter.chapter_number = int(new_number) if new_number.isdigit() else None
        db.session.commit()
        flash(f'Chapter renamed to "{chapter.title}".', 'success')
    return redirect(url_for('parent.subject_chapters', subject_id=chapter.subject_id))


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
    # Delete in dependency order using raw SQL to avoid ORM cache staleness
    db.session.execute(
        db.text('DELETE FROM question_attempts WHERE session_id IN '
                '(SELECT id FROM quiz_sessions WHERE chapter_id = :cid)'),
        {'cid': chapter.id}
    )
    db.session.execute(db.text('DELETE FROM quiz_sessions WHERE chapter_id = :cid'), {'cid': chapter.id})
    db.session.execute(db.text('DELETE FROM teach_sessions WHERE chapter_id = :cid'), {'cid': chapter.id})
    db.session.execute(db.text('DELETE FROM questions WHERE chapter_id = :cid'), {'cid': chapter.id})
    db.session.execute(db.text('DELETE FROM chapters WHERE id = :cid'), {'cid': chapter.id})
    db.session.expire_all()


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
        num_questions = request.form.get('num_questions', 100, type=int)
        num_questions = max(10, min(100, num_questions))

        if not chapter.pdf_text:
            flash('No PDF text found. Please re-upload the PDF.', 'danger')
            return redirect(url_for('parent.generate_questions', chapter_id=chapter_id))

        questions = generate_questions_from_text(chapter.pdf_text, num_questions,
                                                 chapter.title)
        if questions:
            # Delete attempts referencing old questions, then the questions
            db.session.execute(
                db.text('DELETE FROM question_attempts WHERE question_id IN '
                        '(SELECT id FROM questions WHERE chapter_id = :cid)'),
                {'cid': chapter_id}
            )
            db.session.execute(db.text('DELETE FROM questions WHERE chapter_id = :cid'), {'cid': chapter_id})
            db.session.expire_all()
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


# ── Bulk Import from directory ─────────────────────────────────────────────────
_META   = re.compile(r'Textbook|Curiosity|Grade|Reprint', re.IGNORECASE)
_STOP   = re.compile(r'probe and ponder|reprint|share your question', re.IGNORECASE)
_BULLET = re.compile(r'^[z•]\s|^\d+\.\s')

def _is_title_line(l):
    return (not _META.search(l) and not _STOP.search(l)
            and not _BULLET.match(l) and 3 < len(l) < 110)


def _parse_chapter_info(page_text):
    """Extract (chapter_number, chapter_title) from a page's text."""
    lines = [l.strip() for l in page_text.splitlines() if l.strip()]

    # P1: "Chapter N — Title" on one line
    for line in lines:
        m = re.match(r'Chapter\s+(\d+)\s*[—–\-]+\s*(.+)', line, re.IGNORECASE)
        if m:
            return int(m.group(1)), m.group(2).strip()

    # P2: "N – Title" on one line  (Social Science style)
    for line in lines:
        m = re.match(r'^(\d{1,2})\s*[–—]\s*(.+)', line)
        if m:
            num, title = int(m.group(1)), m.group(2).strip()
            if len(title) > 4:
                return num, title

    # P3: "CHAPTER\n<num>" block — title is immediately before CHAPTER keyword
    for i, line in enumerate(lines):
        if line.upper() == 'CHAPTER' and i + 1 < len(lines):
            m = re.match(r'^(\d{1,2})$', lines[i + 1])
            if m:
                num = int(m.group(1))
                before = [l for l in lines[max(0, i - 4):i] if _is_title_line(l)]
                if before:
                    return num, ' '.join(before[-3:]).strip()

    # P3b: "Title words N" — chapter number appended at end of title line
    for i, line in enumerate(lines):
        if _META.search(line):
            continue
        m = re.match(r'^(.+?)\s+(\d{1,2})\s*$', line)
        if m:
            title_part, num = m.group(1).strip(), int(m.group(2))
            if num == 0 or len(title_part) < 5:
                continue
            # absorb preceding title line if present
            if i > 0 and _is_title_line(lines[i - 1]):
                title_part = lines[i - 1] + ' ' + title_part
            return num, title_part

    # P4: standalone chapter number 1–20 with surrounding title lines
    for i, line in enumerate(lines):
        if not re.match(r'^(\d{1,2})$', line):
            continue
        num = int(line)
        if num == 0 or num > 20:       # exclude page numbers
            continue

        before_parts = []
        for j in range(i - 1, max(-1, i - 6), -1):
            candidate = lines[j]
            if re.match(r'^\d{2,}$', candidate):
                break
            if _META.search(candidate) or _STOP.search(candidate):
                break
            if not _is_title_line(candidate):
                break
            before_parts.insert(0, candidate)

        after_parts = []
        for j in range(i + 1, min(i + 5, len(lines))):
            candidate = lines[j]
            if re.match(r'^\d+$', candidate):
                break
            if _STOP.search(candidate) or _BULLET.match(candidate):
                break
            if not _is_title_line(candidate):
                break
            after_parts.append(candidate)

        if before_parts:
            title = ' '.join(before_parts + after_parts[:1]).strip()
        else:
            title = ' '.join(after_parts[:3]).strip()

        if len(title) > 4:
            return num, title

    return None, None


def _normalize_subject(folder_name):
    """Convert folder name like 'Social_science' → 'Social Science'."""
    return folder_name.replace('_', ' ').title()


def _collect_pdfs(subject_dir):
    """Return all PDF paths under subject_dir (handles one level of subfolders)."""
    pdfs = []
    for entry in os.scandir(subject_dir):
        if entry.is_file() and entry.name.lower().endswith('.pdf'):
            pdfs.append(entry.path)
        elif entry.is_dir():
            for sub in os.scandir(entry.path):
                if sub.is_file() and sub.name.lower().endswith('.pdf'):
                    pdfs.append(sub.path)
    return sorted(pdfs)


@parent_bp.route('/bulk-import', methods=['GET', 'POST'])
@login_required
@parent_required
def bulk_import():
    ncert_folder = current_app.config['NCERT_BOOKS_FOLDER']

    if request.method == 'POST':
        source_dir = request.form.get('source_dir', '').strip() or ncert_folder

        if not os.path.isdir(source_dir):
            flash('Directory not found. Check the path and try again.', 'danger')
            return redirect(url_for('parent.bulk_import'))

        upload_folder = current_app.config['UPLOAD_FOLDER']

        imported, skipped = 0, []

        # ── Scan Grade_N folders ───────────────────────────────────────────────
        for grade_entry in sorted(os.scandir(source_dir), key=lambda e: e.name):
            if not grade_entry.is_dir():
                continue
            grade_match = re.match(r'Grade[_\s]?(\d+)', grade_entry.name, re.IGNORECASE)
            if not grade_match:
                continue
            grade = int(grade_match.group(1))

            for subj_entry in sorted(os.scandir(grade_entry.path), key=lambda e: e.name):
                if not subj_entry.is_dir():
                    continue

                subject_name = _normalize_subject(subj_entry.name)
                subject = Subject.query.filter_by(name=subject_name, grade=grade).first()
                if not subject:
                    subject = Subject(name=subject_name, grade=grade)
                    db.session.add(subject)
                    db.session.flush()

                pdfs = _collect_pdfs(subj_entry.path)
                for pdf_path in pdfs:
                    try:
                        _doc = _fitz_lib.open(pdf_path)
                        # Extract chapter info from first 2 pages
                        chapter_num, chapter_title = None, None
                        for _pg in range(min(2, len(_doc))):
                            chapter_num, chapter_title = _parse_chapter_info(_doc[_pg].get_text())
                            if chapter_title:
                                break
                        # Extract full text from all pages in one pass
                        full_text = ''.join(page.get_text() + '\f' for page in _doc).strip()
                        _doc.close()

                        if not chapter_title:
                            # Fallback: use filename (likely prelims/glossary, skip)
                            skipped.append(os.path.basename(pdf_path) + ' (no chapter info found)')
                            continue

                        chapter_title = chapter_title[:200]

                        # Skip if a chapter with the same title already exists in this subject
                        exists = Chapter.query.filter_by(
                            subject_id=subject.id, title=chapter_title
                        ).first()
                        if exists:
                            continue

                        # Copy PDF to uploads
                        dest_name = f"{uuid.uuid4().hex}.pdf"
                        shutil.copy2(pdf_path, os.path.join(upload_folder, dest_name))

                        db.session.add(Chapter(
                            subject_id=subject.id,
                            title=chapter_title,
                            chapter_number=chapter_num,
                            pdf_filename=dest_name,
                            pdf_text=full_text,
                            uploaded_by=current_user.id
                        ))
                        imported += 1
                    except Exception as e:
                        skipped.append(f"{os.path.basename(pdf_path)}: {e}")

        db.session.commit()

        if imported:
            flash(f'{imported} new chapter(s) imported.', 'success')
        else:
            flash('No new chapters found — everything is already up to date.', 'info')
        if skipped:
            flash(f'Skipped {len(skipped)} file(s): ' + '; '.join(skipped[:5]), 'warning')
        return redirect(url_for('parent.subjects'))

    return render_template('parent/bulk_import.html', ncert_folder=ncert_folder)
