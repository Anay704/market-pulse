# Prediction market odds via Kalshi with Polymarket fallback, plus arbitrage scan.

import json
from datetime import datetime, timezone

import requests


def _cents(value, default=None):
    """Coerce a Kalshi cents field (0-100) to float, or return default."""
    try:
        if value is None:
            return default
        f = float(value)
        if f != f or f in (float("inf"), float("-inf")):  # NaN / Inf
            return default
        return f
    except (TypeError, ValueError):
        return default


def get_prediction_markets(ticker, company_name=""):
    """Fetch up to 3 prediction markets relevant to *ticker*.

    Tries Kalshi first; falls back to Polymarket if unavailable.

    Returns (markets: list[dict], source: str).
    Each market dict has keys: title, yes_pct, no_pct, volume.
    """
    # ── 1. Kalshi ──────────────────────────────────────────────────────────────
    try:
        r = requests.get(
            "https://api.elections.kalshi.com/trade-api/v2/markets",
            params={"limit": 20, "status": "open"},
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=8,
        )
        if r.status_code == 200:
            all_mkts = r.json().get("markets", [])

            # Find the longest word in company_name (>3 chars) for fuzzy matching
            company_word = ""
            if company_name:
                company_word = next(
                    (w for w in company_name.lower().split() if len(w) > 3), ""
                )

            fin_kw = [
                "s&p", "sp500", "nasdaq", "dow", "fed", "inflation",
                "recession", "rate", "gdp", "economy", "market",
            ]
            ticker_hits, fin_hits = [], []
            for m in all_mkts:
                text = f"{m.get('title', '')} {m.get('subtitle', '')}".lower()
                if ticker.lower() in text or (company_word and company_word in text):
                    ticker_hits.append(m)
                elif any(kw in text for kw in fin_kw):
                    fin_hits.append(m)

            chosen = ticker_hits[:3]
            if len(chosen) < 3:
                chosen += fin_hits[: 3 - len(chosen)]
            if len(chosen) < 3:
                chosen = all_mkts[:3]

            out = []
            for m in chosen[:3]:
                yes_b = m.get("yes_bid") or m.get("yes_ask") or m.get("last_price") or 50
                out.append({
                    "title":   m.get("title", "Unknown"),
                    "yes_pct": int(yes_b),
                    "no_pct":  100 - int(yes_b),
                    "volume":  int(m.get("volume") or 0),
                })
            if out:
                return out, "Kalshi"
    except Exception:
        pass

    # ── 2. Polymarket fallback ─────────────────────────────────────────────────
    try:
        r = requests.get(
            "https://gamma-api.polymarket.com/markets",
            params={"active": "true", "limit": 5},
            headers={"Accept": "application/json"},
            timeout=8,
        )
        if r.status_code == 200:
            out = []
            for m in r.json()[:5]:
                raw = m.get("outcomePrices", "[]")
                try:
                    prices  = json.loads(raw) if isinstance(raw, str) else raw
                    yes_pct = round(float(prices[0]) * 100) if prices else 50
                except Exception:
                    yes_pct = 50
                out.append({
                    "title":   m.get("question", "Unknown"),
                    "yes_pct": int(yes_pct),
                    "no_pct":  100 - int(yes_pct),
                    "volume":  int(float(m.get("volume") or 0)),
                })
            if out:
                return out, "Polymarket"
    except Exception:
        pass

    return [], "unavailable"


# ── Arbitrage / edge scanner ─────────────────────────────────────────────────

CATEGORY_KEYWORDS = {
    "Fed & Interest Rates": ["fed", "federal reserve", "interest rate", "fomc",
                             "rate cut", "rate hike", "basis points"],
    "Inflation & Economy":  ["inflation", "cpi", "pce", "gdp", "recession",
                             "unemployment", "jobs"],
    "Stock Market":         ["s&p", "nasdaq", "dow", "sp500", "market",
                             "stocks", "equities"],
    "Crypto":               ["bitcoin", "btc", "ethereum", "eth", "crypto",
                             "cryptocurrency"],
    "Politics & Policy":    ["president", "congress", "senate", "election",
                             "policy", "regulation"],
    "Tech & AI":            ["ai", "artificial intelligence", "tech", "apple",
                             "google", "microsoft", "nvidia"],
}


def _categorize(title):
    t = (title or "").lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in t for kw in keywords):
            return category
    return "Other"


def _empty_arb():
    return {
        "categories":        {},
        "top_opportunities": [],
        "total_markets":     0,
        "last_updated":      datetime.now(timezone.utc).isoformat(),
    }


def get_arbitrage_opportunities():
    """Fetch open Kalshi markets and compute edge / expected-value per market.

    Returns a JSON-safe dict: {categories, top_opportunities, total_markets,
    last_updated}. Never raises — returns an empty structure on any failure.
    """
    try:
        r = requests.get(
            "https://api.elections.kalshi.com/trade-api/v2/markets",
            params={"limit": 50, "status": "open"},
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=10,
        )
        if r.status_code != 200:
            return _empty_arb()

        raw = r.json().get("markets", [])
        markets = []

        for m in raw:
            title = m.get("title") or m.get("subtitle") or "Untitled market"

            # Kalshi quotes prices in cents (0-100).
            yes_ask = _cents(m.get("yes_ask"))
            no_ask  = _cents(m.get("no_ask"))
            yes_bid = _cents(m.get("yes_bid"))
            last    = _cents(m.get("last_price"))

            # Fall back sensibly when a side is missing.
            if yes_ask is None:
                yes_ask = last if last is not None else 50.0
            if no_ask is None:
                no_ask = (100.0 - yes_bid) if yes_bid is not None else (100.0 - yes_ask)

            yes_price = max(0.0, min(1.0, yes_ask / 100.0))
            no_price  = max(0.0, min(1.0, no_ask / 100.0))
            total_cost   = yes_price + no_price
            implied_edge = 1.0 - total_cost   # >0 ⇒ arbitrage, <0 ⇒ spread

            # Probability estimate: last trade if present, else the YES mid.
            if last is not None:
                prob_yes_c = last
            elif yes_bid is not None:
                prob_yes_c = (yes_bid + yes_ask) / 2.0
            else:
                prob_yes_c = yes_ask
            prob_yes_c = max(0.0, min(100.0, prob_yes_c))
            yes_probability = prob_yes_c
            no_probability  = 100.0 - prob_yes_c

            ev_yes = (yes_probability / 100.0) - yes_price
            ev_no  = (no_probability  / 100.0) - no_price
            best_side = "YES" if ev_yes >= ev_no else "NO"
            edge_pct  = max(ev_yes, ev_no) * 100.0

            markets.append({
                "title":              title,
                "category":           _categorize(title),
                "yes_price":          round(yes_price, 4),
                "no_price":           round(no_price, 4),
                "yes_probability":    round(yes_probability, 1),
                "no_probability":     round(no_probability, 1),
                "total_cost":         round(total_cost, 4),
                "implied_edge":       round(implied_edge, 4),
                "expected_value_yes": round(ev_yes, 4),
                "expected_value_no":  round(ev_no, 4),
                "best_side":          best_side,
                "edge_pct":           round(edge_pct, 2),
                "volume":             int(m.get("volume") or 0),
                "close_time":         m.get("close_time") or m.get("expiration_time") or "",
            })

        # Sort everything by edge_pct descending (best first).
        markets.sort(key=lambda x: x["edge_pct"], reverse=True)

        categories = {}
        for mk in markets:
            categories.setdefault(mk["category"], []).append(mk)

        return {
            "categories":        categories,
            "top_opportunities": markets[:5],
            "total_markets":     len(markets),
            "last_updated":      datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        print(f"Kalshi arbitrage error: {exc}")
        return _empty_arb()
