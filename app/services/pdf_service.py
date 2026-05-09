import os
import sys
import json
import anthropic
import fitz  # PyMuPDF


def _log(msg):
    print(msg, file=sys.stderr)


def extract_pdf_text(filepath):
    """Extract all text from a PDF file using PyMuPDF."""
    try:
        doc = fitz.open(filepath)
        text = ''
        for page in doc:
            text += page.get_text() + '\f'
        doc.close()
        return text.strip()
    except Exception as e:
        print(f"PDF extraction error: {e}")
        return ''


def generate_questions_from_text(pdf_text, num_questions, chapter_title):
    """Send PDF text to Claude API and get MCQ questions back.
    Batches requests >50 questions into two API calls to stay within timeouts."""
    if num_questions > 50:
        half = num_questions // 2
        batch1 = _generate_batch(pdf_text, half, chapter_title)
        batch2 = _generate_batch(pdf_text, num_questions - half, chapter_title)
        return batch1 + batch2
    return _generate_batch(pdf_text, num_questions, chapter_title)


def _generate_batch(pdf_text, num_questions, chapter_title):
    """Single Claude API call for up to 50 questions."""
    try:
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        _log(f"[generate_questions] start — {num_questions} Qs, key={'set' if api_key else 'MISSING'}")
        client = anthropic.Anthropic(api_key=api_key, timeout=240.0)

        # Work out how many of each type to generate
        easy_n       = max(1, round(num_questions * 0.10))
        hard_n       = max(1, round(num_questions * 0.10))
        practical_n  = num_questions - easy_n - hard_n

        prompt = f"""You are a fun, encouraging CBSE/NCERT teacher creating quiz questions for Indian school students (ages 8–16).

Chapter: {chapter_title}

Content:
{pdf_text[:12000]}

Generate exactly {num_questions} multiple choice questions in this exact mix:

TYPE 1 — SIMPLE ({easy_n} question{'s' if easy_n != 1 else ''}):
  A short, direct recall question, like a textbook exercise.
  Example: "Which gas do plants take in during photosynthesis?"
  Set "difficulty": "easy"

TYPE 2 — CHALLENGING ({hard_n} question{'s' if hard_n != 1 else ''}):
  A harder direct question testing deeper understanding of definitions, formulae, or multi-step facts from the book.
  Example: "Which of the following correctly states Newton's Second Law of Motion?"
  Set "difficulty": "hard"

TYPE 3 — PRACTICAL / REAL-WORLD ({practical_n} questions):
  A scenario or mini-story where the student must THINK and APPLY the concept — NOT just recall a fact.
  Use relatable Indian names and everyday situations:
    "Riya notices…", "Arjun is cooking and…", "During a school trip, Meera sees…"
  Example: "Arjun fills an iron pot and a plastic bucket with water. The iron pot feels colder to touch. What property of iron explains this?"
  AVOID questions that just say "What is X?" or "Define Y."
  Set "difficulty": "medium"

RULES FOR ALL QUESTIONS:
- Keep language simple and friendly for school kids.
- Wrong options (distractors) must be plausible — not obviously silly.
- Explanation must be warm and encouraging — tell WHY in 1–2 sentences a child can understand.
- Mix up the types (do not group them all together); vary which letter (A/B/C/D) is correct.

Return ONLY a valid JSON array — no extra text, no markdown fences. Each object must have exactly these keys:
- "question_text": the question
- "option_a", "option_b", "option_c", "option_d": the four choices
- "correct_answer": one of "A", "B", "C", or "D"
- "explanation": friendly 1–2 sentence explanation (encouraging tone)
- "difficulty": one of "easy", "medium", or "hard"
- "topic_tag": short topic label (e.g. "photosynthesis", "fractions")

Return only the JSON array, nothing else."""

        _log(f"[generate_questions] calling Claude API…")
        with client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}]
        ) as stream:
            response_text = stream.get_final_text().strip()
        _log(f"[generate_questions] response received — {len(response_text)} chars")

        # Strip markdown code fences if present
        if response_text.startswith('```'):
            lines = response_text.split('\n')
            response_text = '\n'.join(lines[1:-1])

        questions = json.loads(response_text)
        _log(f"[generate_questions] parsed {len(questions)} questions")
        return questions

    except json.JSONDecodeError as e:
        _log(f"[generate_questions] JSON parse error: {e}")
        return []
    except Exception as e:
        _log(f"[generate_questions] error: {type(e).__name__}: {e}")
        return []


def generate_cheatsheet(pdf_text, chapter_title, subject_name, grade):
    """Generate a structured one-page cheatsheet for a chapter using Claude."""
    try:
        client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'), timeout=120.0)

        prompt = f"""You are a friendly CBSE/NCERT teacher creating a one-page cheatsheet for Grade {grade} students.

Subject: {subject_name}
Chapter: {chapter_title}

Content:
{pdf_text[:8000]}

Create a concise cheatsheet that fits on one page. Return ONLY a valid JSON object with exactly these keys:
- "overview": 2-3 sentence summary of what this chapter is about (simple, friendly language for the grade level)
- "key_concepts": array of objects with "term" and "definition" — max 8 items, definitions must be 1 short sentence
- "key_facts": array of strings — important facts, dates, names, formulas, or rules — max 8 items, keep each short
- "remember": array of strings — helpful tips, memory tricks, or common mistakes to avoid — max 4 items

Rules:
- Use simple, encouraging language a Grade {grade} student can understand
- Keep every item brief (one sentence)
- Make it memorable and practical
- Return ONLY the JSON object, no markdown fences, no extra text"""

        with client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        ) as stream:
            response_text = stream.get_final_text().strip()

        if response_text.startswith('```'):
            lines = response_text.split('\n')
            response_text = '\n'.join(lines[1:-1])

        return json.loads(response_text)

    except json.JSONDecodeError as e:
        print(f"Cheatsheet JSON parse error: {e}")
        return None
    except Exception as e:
        print(f"Cheatsheet generation error: {e}")
        return None
