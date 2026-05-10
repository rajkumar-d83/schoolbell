import os


def generate_quiz_message(student_name, chapter_title, score_percent, correct, total, level_name):
    """Generate a short personalised encouraging message after a quiz.
    Tries Gemini first (GOOGLE_API_KEY), falls back to Anthropic (ANTHROPIC_API_KEY)."""

    if score_percent == 100:
        tone = "extremely excited and celebratory — they got every single question right"
    elif score_percent >= 80:
        tone = "genuinely enthusiastic and proud of them"
    elif score_percent >= 60:
        tone = "warm, positive, and encouraging"
    else:
        tone = "very gentle, kind, and extra motivating — they need a confidence boost"

    first_name = student_name.split()[0]

    prompt = f"""You are a warm, friendly teacher. Write a short personalised message for {first_name} who just scored {score_percent:.0f}% ({correct} out of {total} correct) on a quiz about "{chapter_title}". They are a {level_name} level learner.

Tone: {tone}.

Rules:
- Exactly 2 sentences only
- Use their first name naturally
- Reference their actual score or the chapter topic specifically
- Keep language simple enough for a school child
- No markdown, no bullet points, no emojis
- Second sentence should encourage a specific next action (re-read the chapter, try again, help a friend, etc.)"""

    google_key    = os.environ.get('GOOGLE_API_KEY')
    anthropic_key = os.environ.get('ANTHROPIC_API_KEY')

    if google_key:
        try:
            from google import genai
            from google.genai import types as gtypes
            client = genai.Client(api_key=google_key)
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=gtypes.GenerateContentConfig(
                    max_output_tokens=150,
                    temperature=0.9,
                )
            )
            return response.text.strip()
        except Exception as e:
            print(f"Gemini message error: {e}")

    if anthropic_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=anthropic_key, timeout=25.0)
            msg = client.messages.create(
                model='claude-haiku-4-5-20251001',
                max_tokens=130,
                messages=[{'role': 'user', 'content': prompt}]
            )
            return msg.content[0].text.strip()
        except Exception as e:
            print(f"Anthropic message error: {e}")

    return None
