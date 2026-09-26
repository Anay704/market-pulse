# All Claude API calls: earnings summaries, verdicts, sentiment, vision, and trade narratives.

import base64
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import anthropic

MODEL = "claude-sonnet-4-6"


def _client():
    """Create a fresh Anthropic client from ANTHROPIC_API_KEY env var."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    return anthropic.Anthropic(api_key=api_key)


def _num(value, default=0.0):
    """Coerce a possibly-missing/None numeric field to a float for prompt text."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


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


# ── Plain-English summary (the "Bottom Line" card) ────────────────────────────

_PLAIN_FALLBACK = {
    "headline":  "Summary unavailable",
    "what_it_means": "We couldn't generate a plain-English summary for this ticker right now. "
                     "The data below is still accurate.",
    "bullets":   [],
    "risk_level": "unknown",
}


def get_plain_english_summary(ticker, stock_data, sentiment, earnings_summary):
    """Explain the stock to someone with no finance background.

    Returns {headline, what_it_means, bullets[3], risk_level}. Never raises —
    returns a safe placeholder so the card degrades instead of breaking the page.
    """
    s  = stock_data
    of = s.get("options_flow") or {}

    facts = (
        f"Company: {s.get('name')} ({ticker})\n"
        f"Share price: ${s.get('price')} ({'up' if _num(s.get('change_pct')) >= 0 else 'down'} "
        f"{abs(_num(s.get('change_pct')))}% today)\n"
        f"Company size (market cap): {s.get('market_cap')}\n"
        f"P/E ratio: {s.get('pe_ratio')}\n"
        f"52-week range: ${s.get('week_52_low')} to ${s.get('week_52_high')}\n"
        f"Profit margin: {s.get('profit_margin')}%\n"
        f"Revenue growth: {s.get('revenue_growth')}%\n"
        f"Sector: {s.get('sector')}\n"
        f"Options traders lean: {of.get('sentiment', 'N/A')}\n"
        f"News sentiment score (0-100): {(sentiment or {}).get('score')}\n"
        f"Recent news analysis: {earnings_summary}"
    )

    try:
        client = _client()
        resp   = client.messages.create(
            model=MODEL,
            max_tokens=700,
            system=(
                "You explain stocks to people who know nothing about finance — smart "
                "adults who have never bought a share and do not know what a P/E ratio is.\n\n"
                "Output ONLY a valid JSON object with exactly these four fields:\n"
                '  "headline": a 6-10 word plain-English take on how this company is doing. '
                'No jargon. Example: "A healthy giant having a rough month."\n'
                '  "what_it_means": 2-3 sentences explaining what is going on with this '
                "company in everyday language. Explain any necessary concept inline using a "
                "concrete comparison. Never use an unexplained finance term.\n"
                '  "bullets": an array of exactly 3 short strings. Each is one plain-English '
                "takeaway (max 14 words). Cover roughly: how the business itself is doing, "
                "what the stock price has been doing, and the single biggest thing to watch.\n"
                '  "risk_level": exactly one of "lower", "medium", or "higher" — how bumpy '
                "this stock is likely to be for a beginner.\n\n"
                "Rules: write like you are explaining to a friend over coffee. Use short "
                "sentences. Never say 'bullish', 'bearish', 'valuation', 'multiple', "
                "'headwinds', or 'fundamentals' without explaining them. Do not give buy or "
                "sell advice. No markdown, no code fences, no text outside the JSON object."
            ),
            messages=[{"role": "user", "content": facts}],
        )

        text = resp.content[0].text.strip()
        if "```" in text:
            text = text.split("```")[1].lstrip("json").strip()
        parsed = json.loads(text)

        bullets = [str(b) for b in (parsed.get("bullets") or [])][:3]
        risk    = str(parsed.get("risk_level", "medium")).lower()
        return {
            "headline":      str(parsed.get("headline") or _PLAIN_FALLBACK["headline"]),
            "what_it_means": str(parsed.get("what_it_means") or ""),
            "bullets":       bullets,
            "risk_level":    risk if risk in ("lower", "medium", "higher") else "medium",
        }
    except Exception as exc:
        print(f"Plain-English summary error: {exc}")
        return dict(_PLAIN_FALLBACK)


# ── Why did it move? (price-move explanations) ────────────────────────────────

def explain_price_moves(name, moves):
    """One plain-English reason per big price day, grounded in that day's headlines.

    *moves* is a list of {date, change_pct, typical_pct, market_change_pct,
    headlines[{title, source, published_at}]}. Returns a same-length list of
    {label, explanation, sources[0-based headline indices], clarity} — an
    entry is {} where that day's call failed — or None if every call failed,
    in which case the caller shows the raw headlines instead.

    Each day is its own request: batched together, a cause from one day (say,
    results on the 28th) leaked into another day's explanation.
    """
    if not moves:
        return []
    with ThreadPoolExecutor(max_workers=len(moves)) as pool:
        out = list(pool.map(lambda m: _explain_move(name, m), moves))
    return None if all(o is None for o in out) else [o or {} for o in out]


_MOVE_SYSTEM = (
    "You explain why a stock's price jumped or dropped on one specific day, for people "
    "with no finance background.\n\n"
    "You get the move, how big a normal day is, what the whole market (the S&P 500) did, "
    "and numbered headlines from the day before through the day after.\n\n"
    "Output ONLY a JSON object with exactly:\n"
    '  "label": 2-4 plain words naming the cause, with no finance jargon, e.g. '
    '"Weak quarterly results", "New product launch", "Whole market fell", "No clear cause".\n'
    '  "explanation": 1-2 short sentences, at most 35 words, in everyday language: what '
    "happened and why it moved the price. Explain any business term inline (say "
    "'quarterly results', not 'earnings print').\n"
    '  "sources": array of the headline numbers that directly state the cause.\n'
    '  "clarity": "clear" if the headlines directly explain the move, "likely" if they '
    'point to a probable cause, "unclear" if they do not explain it.\n\n'
    "Rules:\n"
    "- Use only the headlines given. Do not use outside knowledge of what happened, and "
    "never invent numbers, names or events that are not in them.\n"
    "- An event a headline calls upcoming ('ahead of earnings', 'will report') has not "
    "happened yet on this day.\n"
    "- Opinion and prediction pieces ('Here's what I think', 'Price prediction') are not "
    "evidence of a cause. Neither are headlines that only say the stock moved ('Why X "
    "stock jumped', 'X moved down 3%') without saying why.\n"
    "- Headlines are dated; one about a later day explains that day, not this one.\n"
    "- If nothing explains the move, use label \"No clear cause\", clarity \"unclear\" and "
    "no sources, and tell the reader plainly that no news story that day explains it. If "
    "the whole market moved the same way, add that it partly moved with the market.\n"
    "- Write to the reader about the company, never about the headlines themselves: no "
    "'headline 3 says', 'the headlines are opinion pieces'.\n"
    "- Explain what happened, not what it means for the future: leave out forecasts, "
    "price targets and 'this historically signals' claims even when a headline makes them.\n"
    "- No advice. No markdown, no code fences, no text outside the JSON object."
)


def _explain_move(name, m):
    """Claude's explanation for one move, or None if the call or its parse fails."""
    day    = date.fromisoformat(m["date"])
    mkt    = m.get("market_change_pct")
    market = (f"The S&P 500 {'rose' if mkt >= 0 else 'fell'} {abs(mkt):.1f}% that day."
              if mkt is not None else "The stock market was closed that day.")
    lines  = [f"{day.strftime('%A, %b %d, %Y')}: {name} {'rose' if m['change_pct'] >= 0 else 'fell'} "
              f"{abs(m['change_pct']):.1f}% (a typical day is about ±{m['typical_pct']:.1f}%). {market}"]
    if m["headlines"]:
        lines.append("Headlines:")
        lines += [f"  [{j}] {h['published_at']} — {h['title']} ({h['source']})"
                  for j, h in enumerate(m["headlines"], 1)]
    else:
        lines.append("Headlines: none found.")

    try:
        resp = _client().messages.create(
            model=MODEL,
            max_tokens=300,
            temperature=0,
            system=_MOVE_SYSTEM,
            messages=[{"role": "user", "content": "\n".join(lines)}],
        )
        text = resp.content[0].text.strip()
        if "```" in text:
            text = text.split("```")[1].lstrip("json").strip()
        p = json.loads(text)

        n       = len(m["headlines"])
        cited   = {int(s) for s in (p.get("sources") or []) if str(s).isdigit()}
        clarity = p.get("clarity") if p.get("clarity") in ("clear", "likely", "unclear") else "unclear"
        return {
            "label":       str(p.get("label") or "").strip()[:40] or None,
            "explanation": str(p.get("explanation") or "").strip() or None,
            "sources":     sorted(s - 1 for s in cited if 1 <= s <= n),
            "clarity":     clarity,
        }
    except Exception as exc:
        print(f"Price-move explanation error ({m['date']}): {exc}")
        return None


# ── Research-report synthesis (used by /api/research) ─────────────────────────

def get_company_summary(ticker, business_summary):
    """Distill a long SEC-style business summary into one analyst-friendly paragraph."""
    if not business_summary:
        return f"No company description available for {ticker}."
    try:
        client = _client()
        resp = client.messages.create(
            model=MODEL,
            max_tokens=220,
            system=(
                "You are a financial analyst. Distill the company description into ONE "
                "concise paragraph (3-4 sentences) covering: what they do, how they make "
                "money, and their key competitive positioning. Plain text only — no "
                "markdown, no bullet points."
            ),
            messages=[{"role": "user", "content": business_summary[:3000]}],
        )
        return resp.content[0].text
    except Exception as exc:
        return f"Company summary unavailable: {exc}"


def get_financial_commentary(ticker, quarterly_data):
    """Three-sentence Claude commentary on revenue / margin trends."""
    quarters = (quarterly_data or {}).get("quarters") or []
    if not quarters:
        return "Quarterly financial data unavailable."
    try:
        client = _client()
        slim = [{
            "quarter":          q.get("quarter"),
            "revenue":          q.get("revenue_fmt"),
            "operating_margin": q.get("operating_margin"),
            "net_margin":       q.get("net_margin"),
            "eps":              q.get("eps"),
        } for q in quarters[:5]]
        yoy = quarterly_data.get("yoy_revenue_growth")
        ctx = (
            f"Ticker: {ticker}\n"
            f"YoY revenue growth: {yoy}%\n"
            f"Quarters (most recent first):\n{json.dumps(slim, indent=2)}"
        )
        resp = client.messages.create(
            model=MODEL,
            max_tokens=260,
            system=(
                "You are a financial analyst. Given quarterly revenue, margin, and EPS "
                "data, write a 3-sentence commentary: (1) overall revenue and margin "
                "trajectory, (2) the single most notable QoQ or YoY change, "
                "(3) one specific number to watch next quarter. Cite the actual numbers. "
                "Plain text only — no markdown."
            ),
            messages=[{"role": "user", "content": ctx}],
        )
        return resp.content[0].text
    except Exception as exc:
        return f"Financial commentary unavailable: {exc}"


def get_risk_commentary(ticker, risk_data):
    """Three-sentence Claude commentary on leverage / liquidity / cash-flow risks."""
    if not risk_data:
        return "Risk data unavailable."
    try:
        client = _client()
        slim = {
            "debt_to_equity":    risk_data.get("debt_to_equity"),
            "current_ratio":     risk_data.get("current_ratio"),
            "interest_coverage": risk_data.get("interest_coverage"),
            "free_cashflow":     risk_data.get("free_cashflow_fmt"),
            "operating_cashflow": risk_data.get("operating_cashflow_fmt"),
            "total_cash":        risk_data.get("total_cash_fmt"),
            "total_debt":        risk_data.get("total_debt_fmt"),
            "roe":               risk_data.get("roe"),
            "flags":             [f["msg"] for f in (risk_data.get("flags") or [])][:5],
        }
        ctx = f"Ticker: {ticker}\nRisk metrics:\n{json.dumps(slim, indent=2)}"
        resp = client.messages.create(
            model=MODEL,
            max_tokens=240,
            system=(
                "You are a credit / risk analyst. Given these leverage, liquidity, and "
                "cash-flow numbers, write a 3-sentence assessment: "
                "(1) overall balance-sheet health, "
                "(2) the single biggest risk factor and what number proves it, "
                "(3) what an investor should monitor going forward. "
                "Plain text only — no markdown, no bullet points."
            ),
            messages=[{"role": "user", "content": ctx}],
        )
        return resp.content[0].text
    except Exception as exc:
        return f"Risk commentary unavailable: {exc}"


def get_red_green_flags(ticker, research):
    """Synthesize bullish (green) and bearish (red) flags from all research data.

    Returns {green: list[str], red: list[str]} — each list has 2-4 short bullets.
    """
    if not research:
        return {"green": [], "red": []}
    try:
        client = _client()
        # Build a compact context — extract only the high-signal fields
        ac = research.get("analyst_consensus") or {}
        ia = research.get("insider_activity") or {}
        io = research.get("institutional") or {}
        qf = research.get("quarterly_financials") or {}
        rm = research.get("risk_metrics") or {}
        slim = {
            "analyst_recommendation":  ac.get("recommendation"),
            "analyst_upside_pct":      ac.get("upside_pct"),
            "analyst_buckets":         ac.get("buckets"),
            "insider_net_value":       ia.get("net_value"),
            "insider_count":           ia.get("count"),
            "institutional_pct":       io.get("pct_institutional"),
            "yoy_revenue_growth":      qf.get("yoy_revenue_growth"),
            "latest_quarter":          (qf.get("quarters") or [{}])[0],
            "debt_to_equity":          rm.get("debt_to_equity"),
            "current_ratio":           rm.get("current_ratio"),
            "free_cashflow":           rm.get("free_cashflow_fmt"),
            "roe":                     rm.get("roe"),
            "risk_flags":              [f["msg"] for f in (rm.get("flags") or [])],
        }
        ctx = f"Ticker: {ticker}\n{json.dumps(slim, indent=2)}"

        resp = client.messages.create(
            model=MODEL,
            max_tokens=420,
            system=(
                "You are a research analyst synthesizing bullish (GREEN) and bearish "
                "(RED) flags from a stock's full research data. Output ONLY a valid JSON "
                "object with exactly two keys: \"green\" (list of 2-4 short bullet strings, "
                "each 10-18 words, citing a specific data point), \"red\" (same shape). "
                "Each bullet must reference a concrete number or fact from the data. "
                "No markdown, no code fences, no extra text."
            ),
            messages=[{"role": "user", "content": ctx}],
        )
        text = resp.content[0].text.strip()
        if "```" in text:
            text = text.split("```")[1].lstrip("json").strip()
        parsed = json.loads(text)
        return {
            "green": [str(x) for x in (parsed.get("green") or [])][:4],
            "red":   [str(x) for x in (parsed.get("red")   or [])][:4],
        }
    except Exception as exc:
        print(f"Red/green flags error: {exc}")
        return {"green": [], "red": [], "error": str(exc)}


def summarize_earnings_call(ticker, transcript):
    """Extract tone, forward guidance, capex signals, strategic shifts from a
    transcript dict ({symbol, quarter, transcript, ...}).

    Returns a structured dict {tone, tone_summary, forward_guidance,
    capex_signals, strategic_shifts, key_quotes}, or None on any failure.
    """
    if not transcript or not transcript.get("transcript"):
        return None
    try:
        client = _client()
        ctx = (
            f"Ticker: {ticker} | Quarter: {transcript.get('quarter')} | "
            f"Speakers: {transcript.get('speakers')}\n\n"
            f"Transcript (truncated):\n{transcript['transcript']}"
        )
        resp = client.messages.create(
            model=MODEL,
            max_tokens=700,
            system=(
                "You are an equity research analyst summarizing a quarterly earnings "
                "call transcript. Output ONLY a valid JSON object with exactly these keys: "
                '"tone" (one of: BULLISH, CAUTIOUS, DEFENSIVE, MIXED — pick one), '
                '"tone_summary" (one sentence explaining the management tone), '
                '"forward_guidance" (1-2 sentences citing the specific numbers '
                'management gave for the next quarter or year), '
                '"capex_signals" (1-2 sentences on capital expenditure plans or '
                'investment commitments), '
                '"strategic_shifts" (1-2 sentences on any new product launches, '
                'strategic moves, market pivots, or major announcements), '
                '"key_quotes" (array of 2-3 short VERBATIM quotes from management, '
                'each under 25 words, exactly as they appear in the transcript). '
                "Cite specific numbers wherever management provided them. "
                "Plain text only — no markdown, no code fences."
            ),
            messages=[{"role": "user", "content": ctx}],
        )
        text = resp.content[0].text.strip()
        if "```" in text:
            text = text.split("```")[1].lstrip("json").strip()
        parsed = json.loads(text)
        return {
            "tone":             parsed.get("tone") or "MIXED",
            "tone_summary":     parsed.get("tone_summary") or "",
            "forward_guidance": parsed.get("forward_guidance") or "",
            "capex_signals":    parsed.get("capex_signals") or "",
            "strategic_shifts": parsed.get("strategic_shifts") or "",
            "key_quotes":       [str(q) for q in (parsed.get("key_quotes") or [])][:3],
        }
    except Exception as exc:
        print(f"Earnings call summary error: {exc}")
        return None
