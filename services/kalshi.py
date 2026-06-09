# Prediction market odds via Kalshi with Polymarket fallback, plus arbitrage scan.
#
# NOTE (June 2026): Kalshi rotated their public API:
#   - price fields are now `*_dollars` (e.g. yes_ask_dollars = 0.43) not `*` cents
#   - volume field is now `volume_fp` (floating point) not `volume`
#   - the default /markets endpoint surfaces multi-leg sports parlays (KXMVE*)
#     first; real financial markets must be fetched per-series.

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import requests


def _num(value, default=None):
    """Coerce a Kalshi numeric field to float, or return default. Handles None/NaN/Inf."""
    try:
        if value is None:
            return default
        f = float(value)
        if f != f or f in (float("inf"), float("-inf")):
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


# Map Kalshi's native /series categories → our user-facing display labels.
TARGET_CATEGORIES = {
    "Financials":          "Financials",
    "Crypto":              "Crypto",
    "Politics":            "Politics & Policy",
    "Companies":           "Companies",
    "Climate and Weather": "Climate & Weather",
    "Science and Technology": "Tech & AI",
    "Elections":           "Politics & Policy",
}

# Minimum 24-hour traded contracts to consider a market "real". Markets with
# zero or near-zero volume often look like 99% arbitrage but are actually
# already-decided contracts with no live two-sided action.
MIN_VOLUME = 10

# Cap the number of series we hit per request (keeps latency under ~5s).
MAX_SERIES_PER_REQUEST = 50


# Known-good high-liquidity series — these always go to the front of the queue
# so we never miss the Fed / major macro markets even if dynamic discovery is
# overwhelmed by niche series.
PRIORITY_SERIES = [
    ("KXFED",         "Fed & Interest Rates"),
    ("KXFEDDECISION", "Fed & Interest Rates"),
]


def _fetch_series_for_categories():
    """Pull series for each target category, returning a CATEGORY-BALANCED list
    so we don't end up with 30 markets all from one niche Financials series.

    Returns list of (series_ticker, display_category) tuples — priority series
    first, then up to ~8 per category in round-robin order.
    """
    # Group series by display category
    per_cat = {}  # display_cat → [(ticker, display_cat), ...]
    for kalshi_cat, display_cat in TARGET_CATEGORIES.items():
        try:
            r = requests.get(
                "https://api.elections.kalshi.com/trade-api/v2/series",
                params={"category": kalshi_cat, "limit": 30},
                timeout=10,
            )
            if r.status_code != 200:
                continue
            for s in r.json().get("series", []):
                tkr = s.get("ticker")
                if not tkr:
                    continue
                per_cat.setdefault(display_cat, []).append((tkr, display_cat))
        except Exception:
            continue

    # Start with the high-priority list
    out, seen = list(PRIORITY_SERIES), {t for t, _ in PRIORITY_SERIES}

    # Round-robin: take up to 8 from each category
    cat_lists = list(per_cat.values())
    for i in range(8):
        for lst in cat_lists:
            if i < len(lst):
                tkr, cat = lst[i]
                if tkr not in seen:
                    out.append((tkr, cat))
                    seen.add(tkr)
    return out


def _fetch_series_markets(args):
    """Worker for the thread pool: pull open markets for one series ticker."""
    series_ticker, category = args
    try:
        r = requests.get(
            "https://api.elections.kalshi.com/trade-api/v2/markets",
            params={"series_ticker": series_ticker, "status": "open", "limit": 8},
            timeout=10,
        )
        if r.status_code != 200:
            return []
        return [(m, category) for m in r.json().get("markets", [])]
    except Exception:
        return []


def get_arbitrage_opportunities():
    """Fetch open Kalshi markets across financial-category series and compute
    edge / expected-value per market.

    Pipeline:
      1. Pull series tickers for relevant categories (Financials / Crypto /
         Politics / Companies / Tech & AI / Climate).
      2. Parallel-fetch each series' open markets.
      3. Drop multi-leg parlays (KXMVE*) and markets below MIN_VOLUME.
      4. Compute YES/NO edge + expected value using the new `*_dollars` fields.
      5. Sort by edge desc and group by display category.
    """
    try:
        # Step 1: discover relevant series dynamically (~6 API calls).
        series_list = _fetch_series_for_categories()
        if not series_list:
            return _empty_arb()
        series_list = series_list[:MAX_SERIES_PER_REQUEST]

        # Step 2: parallel-fetch markets for each series (~30 calls, 1-3s).
        with ThreadPoolExecutor(max_workers=15) as ex:
            results = list(ex.map(_fetch_series_markets, series_list))

        markets = []
        for pairs in results:
            for m, category in pairs:
                event_ticker = m.get("event_ticker") or ""
                if event_ticker.startswith("KXMVE"):
                    continue  # skip multi-leg parlays

                # New Kalshi field names (post-2025 rotation): *_dollars / volume_fp
                yes_ask = _num(m.get("yes_ask_dollars"))
                no_ask  = _num(m.get("no_ask_dollars"))
                yes_bid = _num(m.get("yes_bid_dollars"))
                last    = _num(m.get("last_price_dollars"))
                vol     = _num(m.get("volume_fp"), 0.0) or 0.0

                # Require BOTH sides to have real prices — otherwise the
                # market has no two-sided liquidity worth showing.
                if yes_ask is None or no_ask is None:
                    continue
                if yes_ask <= 0 and no_ask <= 0:
                    continue
                # Drop dead / already-resolved markets (no recent trading).
                if vol < MIN_VOLUME:
                    continue

                yes_price = max(0.0, min(1.0, yes_ask))   # already in dollars (0.0-1.0)
                no_price  = max(0.0, min(1.0, no_ask))
                total_cost   = yes_price + no_price
                implied_edge = 1.0 - total_cost

                # True probability estimate: last trade > yes mid > yes ask
                if last is not None:
                    prob_yes = last
                elif yes_bid is not None:
                    prob_yes = (yes_bid + yes_ask) / 2.0
                else:
                    prob_yes = yes_ask
                prob_yes = max(0.0, min(1.0, prob_yes))

                yes_probability = prob_yes * 100.0
                no_probability  = (1.0 - prob_yes) * 100.0
                ev_yes = prob_yes - yes_price
                ev_no  = (1.0 - prob_yes) - no_price
                best_side = "YES" if ev_yes >= ev_no else "NO"
                edge_pct  = max(ev_yes, ev_no) * 100.0

                title = (m.get("title") or m.get("subtitle") or "Untitled").strip()
                if len(title) > 160:
                    title = title[:157] + "…"

                markets.append({
                    "title":              title,
                    "category":           category,
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
                    "volume":             int(vol),
                    "close_time":         m.get("close_time") or m.get("expiration_time") or "",
                })

        # Sort by edge desc, then by volume desc as tiebreaker.
        markets.sort(key=lambda x: (x["edge_pct"], x["volume"]), reverse=True)

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
