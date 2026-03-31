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

        prompt = f"""You are an expert CBSE/NCERT teacher creating multiple choice questions for Indian school students.

Chapter: {chapter_title}

Content:
{pdf_text[:12000]}

Generate exactly {num_questions} multiple choice questions based on this chapter content.

Return ONLY a valid JSON array with no other text. Each object must have these exact keys:
- "question_text": the question
- "option_a": first option
- "option_b": second option
- "option_c": third option
- "option_d": fourth option
- "correct_answer": one of "A", "B", "C", or "D"
- "explanation": brief explanation of why the answer is correct
- "difficulty": one of "easy", "medium", or "hard"
- "topic_tag": a short topic label (e.g. "photosynthesis", "fractions")

Return only the JSON array, nothing else."""

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = message.content[0].text.strip()

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
