from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, current_app)
from flask_login import login_required, current_user
from functools import wraps
import os
from app import db
from app.models.models import ExamCategory, YearPaper, JeeQuestion
from app.services.pdf_service import (extract_pdf_text, extract_jee_questions_from_paper,
                                      download_pdf_from_url)

jee_bp = Blueprint('jee', __name__, url_prefix='/parent/jee')


def parent_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if current_user.role != 'parent':
            flash('Parent access required.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


# ── Category list ──────────────────────────────────────────────────────────────
@jee_bp.route('/')
@login_required
@parent_required
def index():
    categories = ExamCategory.query.order_by(ExamCategory.name).all()
    return render_template('parent/jee_categories.html', categories=categories)


# ── Year papers for a category ─────────────────────────────────────────────────
@jee_bp.route('/<int:cat_id>/papers')
@login_required
@parent_required
def papers(cat_id):
    category = ExamCategory.query.get_or_404(cat_id)
    year_papers = (YearPaper.query
                   .filter_by(category_id=cat_id)
                   .order_by(YearPaper.year.desc(), YearPaper.paper_name)
                   .all())
    return render_template('parent/jee_papers.html',
                           category=category, year_papers=year_papers)


# ── Add a year paper (URL download or file upload) ─────────────────────────────
@jee_bp.route('/<int:cat_id>/papers/add', methods=['GET', 'POST'])
@login_required
@parent_required
def add_paper(cat_id):
    category = ExamCategory.query.get_or_404(cat_id)

    if request.method == 'POST':
        year       = request.form.get('year', type=int)
        paper_name = request.form.get('paper_name', '').strip()
        source_url = request.form.get('source_url', '').strip()

        if not year or not paper_name:
            flash('Year and paper name are required.', 'danger')
            return render_template('parent/jee_add_paper.html', category=category)

        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        pdf_filename  = None
        pdf_text      = ''

        # ── URL download ───────────────────────────────────────────────────────
        if source_url:
            try:
                pdf_filename, filepath = download_pdf_from_url(source_url, upload_folder)
                pdf_text = extract_pdf_text(filepath)
                if not pdf_text:
                    flash('PDF downloaded but no text could be extracted. '
                          'It may be a scanned image — try uploading a text-based PDF.', 'warning')
            except Exception as e:
                flash(f'Download failed: {e}', 'danger')
                return render_template('parent/jee_add_paper.html', category=category)

        # ── File upload ────────────────────────────────────────────────────────
        elif 'pdf_file' in request.files and request.files['pdf_file'].filename:
            import uuid
            f = request.files['pdf_file']
            pdf_filename = str(uuid.uuid4()) + '.pdf'
            filepath = os.path.join(upload_folder, pdf_filename)
            f.save(filepath)
            pdf_text = extract_pdf_text(filepath)
        else:
            flash('Please provide a URL or upload a PDF file.', 'danger')
            return render_template('parent/jee_add_paper.html', category=category)

        paper = YearPaper(
            category_id  = cat_id,
            year         = year,
            paper_name   = paper_name,
            pdf_filename = pdf_filename,
            pdf_text     = pdf_text,
            source_url   = source_url or None,
        )
        db.session.add(paper)
        db.session.commit()
        flash(f'{year} – {paper_name} added successfully.', 'success')
        return redirect(url_for('jee.generate_questions', paper_id=paper.id))

    return render_template('parent/jee_add_paper.html', category=category)


# ── Delete a year paper ────────────────────────────────────────────────────────
@jee_bp.route('/papers/<int:paper_id>/delete', methods=['POST'])
@login_required
@parent_required
def delete_paper(paper_id):
    paper = YearPaper.query.get_or_404(paper_id)
    cat_id = paper.category_id
    if paper.pdf_filename:
        try:
            path = os.path.join(current_app.config.get('UPLOAD_FOLDER', 'uploads'),
                                paper.pdf_filename)
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass
    db.session.delete(paper)
    db.session.commit()
    flash('Paper deleted.', 'success')
    return redirect(url_for('jee.papers', cat_id=cat_id))


# ── Generate / extract questions from a paper ─────────────────────────────────
@jee_bp.route('/papers/<int:paper_id>/generate', methods=['GET', 'POST'])
@login_required
@parent_required
def generate_questions(paper_id):
    paper    = YearPaper.query.get_or_404(paper_id)
    category = paper.category

    if request.method == 'POST':
        if not paper.pdf_text:
            flash('No PDF text found. Please re-add the paper with a valid PDF.', 'danger')
            return redirect(url_for('jee.generate_questions', paper_id=paper_id))

        questions = extract_jee_questions_from_paper(
            paper.pdf_text, paper.year, paper.paper_name, category.name
        )

        if questions:
            existing_texts = {
                q.question_text.strip().lower()
                for q in JeeQuestion.query.filter_by(year_paper_id=paper_id).all()
            }
            added = 0
            for q in questions:
                if q['question_text'].strip().lower() in existing_texts:
                    continue
                db.session.add(JeeQuestion(
                    year_paper_id  = paper_id,
                    question_text  = q['question_text'],
                    option_a       = q['option_a'],
                    option_b       = q['option_b'],
                    option_c       = q['option_c'],
                    option_d       = q['option_d'],
                    correct_answer = q['correct_answer'],
                    explanation    = q.get('explanation', ''),
                    difficulty     = q.get('difficulty', 'hard'),
                    topic_tag      = q.get('topic_tag', ''),
                    subject_tag    = q.get('subject_tag', ''),
                    diagram_svg    = q.get('diagram_svg'),
                ))
                added += 1
            paper.is_processed = True
            db.session.commit()
            total = JeeQuestion.query.filter_by(year_paper_id=paper_id).count()
            flash(f'{added} questions extracted. Total in bank: {total}.', 'success')
            return redirect(url_for('jee.view_questions', paper_id=paper_id))
        else:
            flash('Question extraction failed. Check the error log and try again.', 'danger')

    existing_count = JeeQuestion.query.filter_by(year_paper_id=paper_id).count()
    return render_template('parent/jee_generate.html',
                           paper=paper, category=category,
                           existing_count=existing_count)


# ── View questions for a paper ─────────────────────────────────────────────────
@jee_bp.route('/papers/<int:paper_id>/questions')
@login_required
@parent_required
def view_questions(paper_id):
    paper     = YearPaper.query.get_or_404(paper_id)
    category  = paper.category
    questions = (JeeQuestion.query
                 .filter_by(year_paper_id=paper_id)
                 .order_by(JeeQuestion.subject_tag, JeeQuestion.id)
                 .all())
    return render_template('parent/jee_view_questions.html',
                           paper=paper, category=category, questions=questions)
