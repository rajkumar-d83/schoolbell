import os
import json
import anthropic
import fitz  # PyMuPDF


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
    """Send PDF text to Claude API and get MCQ questions back."""
    try:
        client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))

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

        with client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=24000,
            messages=[{"role": "user", "content": prompt}]
        ) as stream:
            response_text = stream.get_final_text().strip()

        # Strip markdown code fences if present
        if response_text.startswith('```'):
            lines = response_text.split('\n')
            response_text = '\n'.join(lines[1:-1])

        questions = json.loads(response_text)
        return questions

    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        return []
    except Exception as e:
        print(f"Claude API error: {e}")
        return []
