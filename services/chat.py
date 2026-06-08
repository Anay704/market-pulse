# Claude Q&A panel: answers follow-up questions about the currently loaded ticker.

import json
import os

import anthropic

MODEL = "claude-sonnet-4-6"


def chat_about_ticker(question, ticker_context):
    """Answer a free-form question about a stock analysis using the loaded dashboard data.

    Returns a plain-text string. Never raises — surfaces an error message instead.
    """
    if not question:
        return "Ask a question about the loaded ticker."
    try:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return "AI chat unavailable: ANTHROPIC_API_KEY is not set."

        client = anthropic.Anthropic(api_key=api_key)

        # Cap context to keep prompts cheap and fast (≈ first 8k chars of JSON).
        ctx_json = json.dumps(ticker_context or {}, default=str)[:8000]

        system = (
            "You are Market Pulse's AI analyst. The user is looking at a stock-analysis "
            "dashboard. The full JSON of that dashboard is provided below. Answer their "
            "follow-up question directly and concretely — cite the actual numbers from the "
            "JSON whenever possible. Keep responses to 4 sentences or less. "
            "Respond in plain text only — no markdown, no asterisks, no bullet points.\n\n"
            f"Dashboard JSON:\n{ctx_json}"
        )

        resp = client.messages.create(
            model=MODEL,
            max_tokens=400,
            system=system,
            messages=[{"role": "user", "content": question.strip()}],
        )
        return resp.content[0].text
    except Exception as exc:
        print(f"Chat error: {exc}")
        return f"AI chat unavailable: {exc}"
