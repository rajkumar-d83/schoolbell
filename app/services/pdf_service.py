import os
import re
import sys
import json
import fitz  # PyMuPDF


def sanitize_svg(svg):
    """Strip dangerous SVG content; return cleaned string or None."""
    if not svg or not isinstance(svg, str):
        return None
    svg = svg.strip()
    if not svg.startswith('<svg'):
        return None
    svg = re.sub(r'\s+on\w+\s*=\s*"[^"]*"', '', svg, flags=re.IGNORECASE)
    svg = re.sub(r"\s+on\w+\s*=\s*'[^']*'", '', svg, flags=re.IGNORECASE)
    svg = re.sub(r'<script[\s\S]*?</script>', '', svg, flags=re.IGNORECASE)
    svg = re.sub(r'<image[^>]*/?\s*>', '', svg, flags=re.IGNORECASE)
    svg = re.sub(r'<foreignObject[\s\S]*?</foreignObject>', '', svg, flags=re.IGNORECASE)
    svg = re.sub(r'(xlink:)?href\s*=\s*"https?://[^"]*"', '', svg, flags=re.IGNORECASE)
    return svg


def _log(msg):
    print(msg, file=sys.stderr)


def _strip_fences(text):
    """Remove markdown code fences that some models wrap around JSON."""
    text = text.strip()
    if text.startswith('```'):
        lines = text.split('\n')
        text = '\n'.join(lines[1:-1])
    return text.strip()


def _call_ai(prompt, max_tokens=2000, timeout=120.0):
    """Call Gemini if GOOGLE_API_KEY is set, otherwise fall back to Anthropic.
    Returns the response text string, or raises on total failure."""
    google_key    = os.environ.get('GOOGLE_API_KEY')
    anthropic_key = os.environ.get('ANTHROPIC_API_KEY')

    if google_key:
        try:
            from google import genai
            from google.genai import types as gtypes
            client = genai.Client(api_key=google_key)
            response = client.models.generate_content(
                model='gemini-1.5-flash',
                contents=prompt,
                config=gtypes.GenerateContentConfig(
                    max_output_tokens=max_tokens,
                    temperature=0.7,
                )
            )
            _log('[AI] provider=Gemini')
            return response.text.strip()
        except Exception as e:
            _log(f'[AI] Gemini failed ({type(e).__name__}: {e}) — trying Anthropic…')

    if anthropic_key:
        import anthropic
        client = anthropic.Anthropic(api_key=anthropic_key, timeout=timeout)
        with client.messages.stream(
            model='claude-sonnet-4-6',
            max_tokens=max_tokens,
            messages=[{'role': 'user', 'content': prompt}]
        ) as stream:
            _log('[AI] provider=Anthropic')
            return stream.get_final_text().strip()

    raise RuntimeError(
        'No AI API key configured. Add GOOGLE_API_KEY or ANTHROPIC_API_KEY to .env'
    )


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
    """Generate up to 50 MCQ questions via AI (Gemini or Anthropic)."""
    try:
        google_key    = os.environ.get('GOOGLE_API_KEY')
        anthropic_key = os.environ.get('ANTHROPIC_API_KEY')
        _log(f"[generate_questions] start — {num_questions} Qs, "
             f"gemini={'set' if google_key else 'no'}, "
             f"anthropic={'set' if anthropic_key else 'no'}")

        easy_n      = max(1, round(num_questions * 0.10))
        hard_n      = max(1, round(num_questions * 0.10))
        practical_n = num_questions - easy_n - hard_n

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
- "diagram_svg": null for most questions. ONLY provide an SVG string for questions about geometry, angles, shapes, number lines, graphs, ray diagrams, electric circuits, or other visual concepts where a diagram genuinely helps the student. When provided, use a self-contained <svg> element with these exact attributes: viewBox="0 0 240 160" xmlns="http://www.w3.org/2000/svg". Use stroke="#94A3B8" fill="none" for shape outlines; fill="#818CF8" for highlighted points or areas; fill="#E2E8F0" font-size="13" for labels. Maximum 12 SVG child elements. No <script>, no event attributes, no external images. For text-recall or story questions, always set this to null.

Return only the JSON array, nothing else."""

        _log('[generate_questions] calling AI…')
        response_text = _call_ai(prompt, max_tokens=8000, timeout=240.0)
        response_text = _strip_fences(response_text)
        _log(f'[generate_questions] response received — {len(response_text)} chars')

        questions = json.loads(response_text)
        for q in questions:
            raw_svg = q.get('diagram_svg')
            q['diagram_svg'] = sanitize_svg(raw_svg) if raw_svg else None
        _log(f'[generate_questions] parsed {len(questions)} questions')
        return questions

    except json.JSONDecodeError as e:
        _log(f'[generate_questions] JSON parse error: {e}')
        return []
    except Exception as e:
        _log(f'[generate_questions] error: {type(e).__name__}: {e}')
        return []


def generate_cheatsheet(pdf_text, chapter_title, subject_name, grade):
    """Generate a structured one-page cheatsheet via AI (Gemini or Anthropic)."""
    try:
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

        response_text = _call_ai(prompt, max_tokens=2000, timeout=120.0)
        response_text = _strip_fences(response_text)
        return json.loads(response_text)

    except json.JSONDecodeError as e:
        print(f"Cheatsheet JSON parse error: {e}")
        return None
    except Exception as e:
        print(f"Cheatsheet generation error: {e}")
        return None
