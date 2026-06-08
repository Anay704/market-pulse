# All Claude API calls: earnings summaries, verdicts, sentiment, vision, and trade narratives.

import base64
import json
import os

import anthropic

MODEL = "claude-sonnet-4-6"


def _client():
    """Create a fresh Anthropic client from ANTHROPIC_API_KEY env var."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    return anthropic.Anthropic(api_key=api_key)


# ── Earnings summary ───────────────────────────────────────────────────────────

def get_earnings_summary(ticker, headlines):
    """Summarise recent news headlines into a short analyst note.

    Returns a plain-text string (never raises).
    """
    if not headlines:
        return "No recent news headlines found for this ticker."
    try:
        client     = _client()
        news_block = "\n".join(f"- {h}" for h in headlines)
        resp = client.messages.create(
            model=MODEL,
            max_tokens=512,
            system=(
                "You are a financial analyst. Based on these recent news headlines "
                "about the company, give me: 1) A one sentence summary of the "
                "company's recent performance 2) Management sentiment: "
                "Bullish / Neutral / Bearish with one sentence explanation "
                "3) Top 2 risks to watch. Be concise and direct. "
                "Respond in plain text only — no markdown, no asterisks, "
                "no bullet points, no bold formatting, no headers."
            ),
            messages=[{
                "role":    "user",
                "content": f"Recent headlines for {ticker}:\n{news_block}",
            }],
        )
        return resp.content[0].text
    except Exception as exc:
        return f"AI analysis unavailable: {exc}"


# ── Sentiment score ────────────────────────────────────────────────────────────

def get_sentiment_score(ticker, stock_data, headlines):
    """Return a sentiment dict: {score: int 0-100, sentiment_score: float -1..1, reasoning: str}.

    Never raises — returns neutral defaults on any error.
    """
    price         = stock_data["price"]
    high52        = stock_data["week_52_high"]
    pct_from_high = round((price / high52 - 1) * 100, 1) if high52 else "N/A"

    data_text = (
        f"Ticker: {ticker}\n"
        f"Current Price: ${price} ({'+' if stock_data['change_pct'] >= 0 else ''}"
        f"{stock_data['change_pct']}% today)\n"
        f"52W High: ${high52} | 52W Low: ${stock_data['week_52_low']}\n"
        f"Price vs 52W High: {pct_from_high}%\n"
        f"P/E Ratio: {stock_data['pe_ratio']}\n"
        f"Recent Headlines:\n"
        + ("\n".join(f"- {h}" for h in headlines[:5]) if headlines else "No headlines.")
    )
    try:
        client = _client()
        resp   = client.messages.create(
            model=MODEL,
            max_tokens=150,
            system=(
                "You are a market sentiment analyzer. Based on the following data about "
                "a stock: price vs 52-week range, P/E ratio, recent news headlines, and "
                "today's price change — output ONLY a valid JSON object with exactly three "
                'fields: "score" (integer 0-100), "sentiment_score" (float between -1.0 '
                "and 1.0, where -1.0 is extremely bearish and 1.0 is extremely bullish), and "
                '"reasoning" (one sentence). No markdown, no code fences, no extra text.'
            ),
            messages=[{"role": "user", "content": data_text}],
        )
        text = resp.content[0].text.strip()
        if "```" in text:
            text = text.split("```")[1].lstrip("json").strip()
        parsed = json.loads(text)
        raw_ss = float(parsed.get("sentiment_score", 0.0))
        return {
            "score":           max(0, min(100, int(parsed.get("score", 50)))),
            "sentiment_score": max(-1.0, min(1.0, raw_ss)),
            "reasoning":       str(parsed.get("reasoning", "")),
        }
    except Exception as exc:
        return {
            "score": 50, "sentiment_score": 0.0,
            "reasoning": f"Sentiment score unavailable: {exc}",
        }


# ── Analyst verdict ────────────────────────────────────────────────────────────

def get_analyst_verdict(stock_data, earnings_summary, markets):
    """Write a 3-sentence analyst verdict for the stock. Returns plain-text string."""
    s    = stock_data
    sign = "+" if s["change_pct"] >= 0 else ""

    markets_ctx = ""
    if markets:
        markets_ctx = "\n\nPrediction market odds:\n" + "\n".join(
            f"  - {m['title']}: YES {m['yes_pct']}% / NO {m['no_pct']}%"
            for m in markets
        )

    of          = s.get("options_flow")
    options_ctx = (
        f"\nOptions flow P/C ratio: {of['ratio']} ({of['sentiment']})" if of else ""
    )

    prompt = (
        f"Stock: {s['ticker']} ({s['name']})\n"
        f"Price: ${s['price']} ({sign}{s['change_pct']}% today)\n"
        f"Market Cap: {s['market_cap']} | P/E: {s['pe_ratio']}\n"
        f"52-Week Range: ${s['week_52_low']} - ${s['week_52_high']}\n"
        f"{options_ctx}\n\n"
        f"Recent news analysis:\n{earnings_summary}"
        f"{markets_ctx}"
    )
    try:
        client = _client()
        resp   = client.messages.create(
            model=MODEL,
            max_tokens=300,
            system=(
                "You are a senior financial analyst. Given this data about a stock, "
                "write a 3 sentence verdict for a retail investor. "
                "Cover: current momentum, key risk, and one thing to watch. "
                "Be direct, no fluff, no disclaimers. "
                "Respond in plain text only — no markdown, no asterisks, "
                "no bullet points, no bold formatting, no headers."
            ),
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text
    except Exception as exc:
        return f"AI verdict unavailable: {exc}"


# ── Chart image analysis ───────────────────────────────────────────────────────

def analyze_chart_image(img_bytes, media_type, ticker):
    """Run Claude Vision on raw image bytes and return a technical analysis dict.

    Returns a dict with keys: technical_score, trend, support, resistance,
    pattern, volume_trend, technical_summary.  Returns None on any failure.
    """
    if not img_bytes:
        return None
    try:
        img_b64 = base64.standard_b64encode(img_bytes).decode("utf-8")
        client  = _client()
        resp    = client.messages.create(
            model=MODEL,
            max_tokens=400,
            system=(
                "You are a technical analysis expert. Analyze the provided stock chart image "
                "and output ONLY a valid JSON object with exactly these fields: "
                '"technical_score" (float 0.0-1.0, higher is more bullish), '
                '"trend" (string: "UPTREND", "DOWNTREND", or "SIDEWAYS"), '
                '"support" (float price level or null), '
                '"resistance" (float price level or null), '
                '"pattern" (string describing chart pattern, e.g. "Bull flag"), '
                '"volume_trend" (string: "INCREASING", "DECREASING", or "NEUTRAL"), '
                '"technical_summary" (string, one sentence). '
                "No markdown, no code fences, no extra text."
            ),
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type":       "base64",
                            "media_type": media_type,
                            "data":       img_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": f"Analyze this stock chart for {ticker}. Return JSON only.",
                    },
                ],
            }],
        )
        text = resp.content[0].text.strip()
        if "```" in text:
            text = text.split("```")[1].lstrip("json").strip()
        data = json.loads(text)
        data["technical_score"] = max(0.0, min(1.0, float(data.get("technical_score", 0.5))))
        return data
    except Exception:
        return None


# ── Trade narrative ────────────────────────────────────────────────────────────

def get_trade_narrative(ticker, stock_data, fund_score, sent_signal,
                        final_score, recommendation,
                        technical_data=None, position=None):
    """Generate a 3-sentence trade assessment narrative. Returns plain-text string."""
    s    = stock_data
    sign = "+" if s["change_pct"] >= 0 else ""

    tech_ctx = ""
    if technical_data:
        tech_ctx = (
            f"\nChart: {technical_data.get('trend', 'N/A')} trend, "
            f"pattern: {technical_data.get('pattern', 'N/A')}, "
            f"technical score {technical_data.get('technical_score', 0):.0%}"
        )

    pos_ctx = ""
    if position:
        pnl      = position.get("unrealized_pnl", 0)
        pnl_sign = "+" if pnl >= 0 else ""
        pos_ctx  = (
            f"\nPosition: {position.get('shares', 0)} shares at ${position.get('avg_price', 0)}, "
            f"P&L: {pnl_sign}${abs(pnl):.2f} ({pnl_sign}{position.get('pnl_pct', 0):.1f}%)"
        )

    prompt = (
        f"Stock: {ticker} ({s['name']})\n"
        f"Price: ${s['price']:.2f} ({sign}{s['change_pct']:.2f}% today)\n"
        f"P/E: {s['pe_ratio']} | 52W Range: ${s['week_52_low']:.2f} - ${s['week_52_high']:.2f}\n"
        f"Fundamental Score: {fund_score:.2f}/1.0\n"
        f"Sentiment Signal: {sent_signal:.2f}/1.0\n"
        f"Final Score: {final_score:.2f}/1.0 — {recommendation}"
        f"{tech_ctx}{pos_ctx}"
    )
    try:
        client = _client()
        resp   = client.messages.create(
            model=MODEL,
            max_tokens=220,
            system=(
                "You are a senior financial analyst writing a trade assessment. "
                "Write exactly 3 sentences: "
                "1) The overall trade setup and what the score indicates. "
                "2) The key risk factor to monitor right now. "
                "3) A specific, actionable recommendation. "
                "Be direct, concrete, and avoid generic disclaimers. "
                "Respond in plain text only — no markdown, no asterisks, "
                "no bullet points, no bold, no headers."
            ),
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text
    except Exception as exc:
        return f"Narrative unavailable: {exc}"
