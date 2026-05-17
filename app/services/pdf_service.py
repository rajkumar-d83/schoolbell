import os
import re
import sys
import json
import uuid
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
    try:
        from flask import current_app
        current_app.logger.info(msg)
    except RuntimeError:
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
                model='gemini-2.5-pro',
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

        prompt = f"""You are an expert CBSE/NCERT teacher creating quiz questions for Indian school students (ages 8–16).

Chapter: {chapter_title}

Content:
{pdf_text[:12000]}

BEFORE writing any questions, think through these steps in your head:
1. Identify the 6–8 core concepts in this chapter.
2. For each concept, ask: "Where would a student actually SEE or USE this in daily Indian life?" Think of kitchens, markets, cricket grounds, monsoons, school labs, auto-rickshaws, phones, farms, rivers.
3. Only then write the questions — rooted in those real situations.

Generate exactly {num_questions} multiple choice questions in this exact mix:

TYPE 1 — SIMPLE ({easy_n} question{'s' if easy_n != 1 else ''}):
  A short, direct recall question, like a textbook exercise.
  Example: "Which gas do plants take in during photosynthesis?"
  Set "difficulty": "easy"

TYPE 2 — CHALLENGING ({hard_n} question{'s' if hard_n != 1 else ''}):
  A harder question testing deeper understanding of definitions, formulae, or multi-step reasoning.
  Example: "Which of the following correctly states Newton's Second Law of Motion?"
  Set "difficulty": "hard"

TYPE 3 — PRACTICAL / REAL-WORLD ({practical_n} questions):
  GOLDEN RULE: Start with an OBSERVATION or SITUATION — never with the concept name.
  The student must figure out which concept explains what they are seeing.

  WRONG (fake practical): "Riya's teacher explained that iron conducts heat. Which property does this show?"
  RIGHT (true practical): "Riya touches an iron tawa and a wooden rolling pin left on the kitchen counter on a cold morning. The tawa feels much colder even though both are in the same room. Why?"

  WRONG: "Arjun knows plants need sunlight for photosynthesis. What does sunlight provide?"
  RIGHT: "Arjun kept a money plant in a dark cupboard for 10 days. Its leaves slowly turned yellow and droopy. What is the most likely reason?"

  Real-world scene library — pick what fits the chapter topic:

  KITCHEN & FOOD
  - Pressure cooker whistling, steam condensing on lid
  - Chapati puffing up on the tawa, dosa batter fermenting overnight
  - Salt dissolving in dal, oil floating on water, turmeric staining a white cloth
  - Refrigerator keeping food fresh, ice melting in a juice glass on a hot day
  - Lemon juice removing rust stains, baking soda making a cake rise
  - Matka (clay pot) keeping water cooler than a steel bottle

  WEATHER & ENVIRONMENT
  - Monsoon puddles, flooded streets, iron gate rusting after rain
  - Fog forming on spectacle lenses when walking from AC room to outside
  - Clothes drying faster on a sunny windy day vs a cloudy still day
  - Rainbow after a shower, thunder heard after lightning is seen
  - Shade under a peepal tree feeling cooler than open road
  - Roads melting/cracking in peak summer heat

  TRANSPORT
  - Auto-rickshaw engine heating up, exhaust smoke colour
  - Bicycle tyre going flat in cold weather, brakes wearing down on a slope
  - Railway track expansion gaps, train wheels squealing on a curve
  - Boat floating on a river, a stone sinking — why the difference?
  - Car windshield fogging up inside on a cold morning

  HOME & DAILY LIFE
  - Ceiling fan slowing when a new appliance is switched on
  - Torch getting dim when battery is low
  - Mirror fogging after a hot shower, candle wax melting and solidifying
  - Rubber chappal melting if left near a gas flame
  - Wet clothes feeling colder than dry clothes on a breezy day
  - Mobile phone heating up while charging or playing a game
  - Solar panel on a neighbour's rooftop working even on a cloudy day

  SPORTS & PLAY
  - Cricket ball swinging more in humid evening air vs dry afternoon
  - Spin bowler making the ball turn — which force causes the curve?
  - Cycle gear making pedalling easier uphill
  - Swimmer moving faster in saltwater than in fresh water
  - Kite flying higher when the wind blows stronger
  - Rubber ball bouncing higher on a hard floor vs sand

  MARKET & SHOPPING
  - Weighing vegetables on a balance scale vs a spring scale — same in both places?
  - Ice blocks wrapped in jute sacks melting slowly at the sabzi market
  - Steel utensils feeling hotter than plastic handles on the same vessel
  - Shopkeeper mixing two paints — which colours blend and which don't?

  FARM & NATURE
  - Sandy soil water draining fast, clay soil staying waterlogged
  - Seeds sprouting faster in moist warm soil than dry cold soil
  - River water looking muddy after rain — what is suspended in it?
  - Leaves wilting on a hot afternoon, recovering in the evening
  - Birds flying in a V-formation, fish swimming in a school
  - Firefly glowing, earthworm coming out after rain

  SCHOOL & SCIENCE LAB
  - Magnet picking up iron filings but not aluminium foil
  - Circuit bulb glowing dim when connected with a longer wire
  - Thermometer in a beaker of hot water vs cold water
  - Ruler bending slightly when pressed — elastic or plastic change?
  - Ink drop spreading through water in a beaker without stirring

  FESTIVALS & CULTURE
  - Diwali sparkler burning bright — what chemical reaction?
  - Holi gulal (colour powder) dissolving in water vs oil
  - Hot air balloon / sky lantern rising — why does it float upward?
  - Clay diyas keeping flame stable even in light breeze
  - Fireworks showing different colours — what causes each colour?

  HEALTH & BODY
  - Sweating making you feel cooler — what process is at work?
  - Breathing hard after running up stairs — what does the body need more of?
  - Fever making you feel hot — what is the body trying to do?
  - Applying antiseptic cream — why does it sting, then feel better?

  Use Indian names naturally (Riya, Arjun, Meera, Rahul, Priya, Aditya, Kavya).
  Set "difficulty": "medium"

RULES FOR ALL QUESTIONS:
- Keep language simple and friendly for school kids.
- Wrong options (distractors) must be plausible — not obviously silly.
- Explanation: warm, encouraging, 1–2 sentences. Tell WHY in a way a child can picture it.
- Mix question types (do not group them all together); vary which letter (A/B/C/D) is correct.
- Self-check before finalising each TYPE 3 question: "Could a student answer this by just reading the definition?" If yes, rewrite it.

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
        response_text = _call_ai(prompt, max_tokens=32000, timeout=300.0)
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


def download_pdf_from_url(url, upload_folder):
    """Download a PDF from a URL, save to upload_folder. Returns (filename, filepath).
    Raises ValueError if the response doesn't look like a PDF, or requests exceptions on failure."""
    import requests
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    resp = requests.get(url, timeout=60, headers=headers, stream=True)
    resp.raise_for_status()
    content_type = resp.headers.get('content-type', '').lower()
    if 'pdf' not in content_type and not url.lower().split('?')[0].endswith('.pdf'):
        raise ValueError(f'URL does not appear to be a PDF (Content-Type: {content_type})')
    filename = str(uuid.uuid4()) + '.pdf'
    filepath = os.path.join(upload_folder, filename)
    with open(filepath, 'wb') as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    return filename, filepath


def extract_jee_questions_from_paper(pdf_text, year, paper_name, category_name):
    """Extract and format MCQ questions from a JEE exam paper PDF via AI."""
    try:
        prompt = f"""You are an expert at extracting JEE exam questions. Extract all multiple choice questions from this {category_name} {year} {paper_name} paper.

Paper content:
{pdf_text[:15000]}

For EACH MCQ question found in the paper:
- Extract the exact question text (including any numerical values, symbols, formulas)
- Extract all 4 options (A, B, C, D) exactly as written
- Identify the correct answer (use the answer key if present in the paper, otherwise use your knowledge)
- Write a clear 1-2 sentence explanation of why the answer is correct
- Identify the subject: "Physics", "Chemistry", "Mathematics", or "Biology"
- Identify the specific topic (e.g., "kinematics", "electrochemistry", "integration")

Return ONLY a valid JSON array. Each object must have exactly these keys:
- "question_text": full question text
- "option_a", "option_b", "option_c", "option_d": the four choices
- "correct_answer": "A", "B", "C", or "D"
- "explanation": 1-2 sentence explanation of the correct answer
- "difficulty": always "hard" for JEE
- "topic_tag": specific topic (e.g. "kinematics", "p-block elements")
- "subject_tag": "Physics", "Chemistry", "Mathematics", or "Biology"
- "diagram_svg": null for most questions. Only provide SVG for pure geometry/graph questions using viewBox="0 0 240 160", stroke="#94A3B8", fill="#818CF8" for highlights. Max 12 elements. No script/events.

Return only the JSON array, nothing else."""

        _log(f'[extract_jee] calling AI for {category_name} {year} {paper_name}…')
        response_text = _call_ai(prompt, max_tokens=32000, timeout=300.0)
        response_text = _strip_fences(response_text)
        _log(f'[extract_jee] response received — {len(response_text)} chars')

        questions = json.loads(response_text)
        for q in questions:
            raw_svg = q.get('diagram_svg')
            q['diagram_svg'] = sanitize_svg(raw_svg) if raw_svg else None
        _log(f'[extract_jee] parsed {len(questions)} questions')
        return questions

    except json.JSONDecodeError as e:
        _log(f'[extract_jee] JSON parse error: {e}')
        return []
    except Exception as e:
        _log(f'[extract_jee] error: {type(e).__name__}: {e}')
        return []


def generate_svg_for_question(question_text, subject_name, grade):
    """Generate a simple educational SVG illustration for one quiz question.
    Uses Gemini Flash with thinking disabled — fast and cheap. Returns sanitized SVG or None."""
    google_key = os.environ.get('GOOGLE_API_KEY')
    if not google_key:
        return None

    prompt = f"""You are an educational illustrator for Indian school textbooks (Grade {grade} {subject_name}).
Draw a simple cartoon SVG illustration of the SITUATION described in this quiz question.

Question: {question_text}

CRITICAL RULES:
1. Illustrate ONLY the scenario/situation — never the answer or any hint toward it
2. Do NOT label, highlight, or depict any of the answer choices
3. Use viewBox="0 0 300 200" — this exact attribute
4. Bright friendly colours: yellows, greens, blues, oranges
5. Draw ONE clear scene that shows what is happening in the question
6. Simple shapes only: rect, circle, ellipse, path, line, polygon
7. Short scene labels (1–3 words) as <text> elements are fine, but no answer clues
8. NO <script>, NO event handlers, NO external links or images
9. Return ONLY the raw <svg>...</svg> tag — no markdown, no explanation, nothing else"""

    try:
        from google import genai
        from google.genai import types as gtypes
        client = genai.Client(api_key=google_key)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=gtypes.GenerateContentConfig(
                max_output_tokens=2000,
                temperature=0.8,
                thinking_config=gtypes.ThinkingConfig(thinking_budget=0),
            )
        )
        raw = response.text.strip()
        if '```' in raw:
            raw = _strip_fences(raw)
        start = raw.find('<svg')
        end   = raw.rfind('</svg>')
        if start != -1 and end != -1:
            raw = raw[start:end + 6]
        return sanitize_svg(raw)
    except Exception as e:
        _log(f'[svg_gen] error: {type(e).__name__}: {e}')
        return None
