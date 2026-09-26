# Prediction market odds via Kalshi (series-matched per ticker), plus arbitrage scan.
#
# NOTE (June 2026): Kalshi rotated their public API:
#   - price fields are now `*_dollars` (e.g. yes_ask_dollars = 0.43) not `*` cents
#   - volume field is now `volume_fp` (floating point) not `volume`
#   - the default /markets endpoint surfaces multi-leg sports parlays (KXMVE*)
#     first; real financial markets must be fetched per-series.

import time
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


# Series-catalogue cache. Listing every series in a category costs ~0.15s, so we
# fetch the three relevant categories once and reuse the map for an hour.
_SERIES_CACHE      = {"at": 0.0, "map": {}}
_SERIES_CACHE_TTL  = 3600
_SERIES_CATEGORIES = ("Companies", "Financials", "Crypto")


def _series_catalogue():
    """{series_ticker: title} for the categories that hold single-name markets."""
    now = time.time()
    if _SERIES_CACHE["map"] and now - _SERIES_CACHE["at"] < _SERIES_CACHE_TTL:
        return _SERIES_CACHE["map"]

    catalogue = {}
    for category in _SERIES_CATEGORIES:
        try:
            r = requests.get(
                "https://api.elections.kalshi.com/trade-api/v2/series",
                params={"category": category, "limit": 200},
                timeout=8,
            )
            if r.status_code != 200:
                continue
            for s in r.json().get("series", []):
                if s.get("ticker"):
                    catalogue[s["ticker"]] = s.get("title") or ""
        except Exception:
            continue

    if catalogue:
        _SERIES_CACHE.update(at=now, map=catalogue)
    return catalogue


def _series_for_ticker(ticker):
    """Series tickers that genuinely belong to *ticker*.

    Kalshi names single-name series after the symbol — AAPL → KXAAPLA, BTC → KXBTC.
    Matching only these exact shapes is what keeps unrelated markets out; a
    substring search would pull in every series that happens to contain the
    letters (e.g. "KXCOSTCO" for "COST").
    """
    base = (ticker or "").upper().split("-")[0]
    if not base:
        return []
    candidates = (f"KX{base}A", f"KX{base}", base)
    catalogue  = _series_catalogue()
    return [c for c in candidates if c in catalogue]


def _market_price_pct(m):
    """Best available YES probability as an integer 0-100, or None if unpriced.

    Kalshi's current API returns dollars (0.0-1.0) in `*_dollars` fields. The old
    integer-cent fields are read as a fallback for older/cached payloads.
    """
    last = _num(m.get("last_price_dollars"))
    bid  = _num(m.get("yes_bid_dollars"))
    ask  = _num(m.get("yes_ask_dollars"))

    if last is not None and last > 0:
        price = last
    elif bid is not None and ask is not None and (bid > 0 or ask > 0):
        price = (bid + ask) / 2.0
    elif ask is not None and ask > 0:
        price = ask
    else:
        cents = _num(m.get("last_price")) or _num(m.get("yes_bid")) or _num(m.get("yes_ask"))
        if cents is None or cents <= 0:
            return None
        price = cents / 100.0

    return int(round(max(0.0, min(1.0, price)) * 100))


def get_prediction_markets(ticker, company_name=""):
    """Fetch up to 3 prediction markets that are genuinely about *ticker*.

    Returns (markets: list[dict], source: str) — each dict has title, yes_pct,
    no_pct, volume.

    Returns an empty list when nothing relevant is trading. That is deliberate:
    the default /markets feed is dominated by multi-leg sports parlays (KXMVE*),
    so a "show something" fallback surfaces baseball odds on a stock page.
    """
    try:
        out = []
        for series_ticker in _series_for_ticker(ticker):
            r = requests.get(
                "https://api.elections.kalshi.com/trade-api/v2/markets",
                params={"series_ticker": series_ticker, "status": "open", "limit": 20},
                headers={"Accept": "application/json"},
                timeout=8,
            )
            if r.status_code != 200:
                continue

            for m in r.json().get("markets", []):
                if (m.get("event_ticker") or "").startswith("KXMVE"):
                    continue  # multi-leg parlay
                yes_pct = _market_price_pct(m)
                if yes_pct is None:
                    continue  # unpriced — nothing meaningful to show
                volume = int(_num(m.get("volume_fp"), 0.0) or _num(m.get("volume"), 0.0) or 0)
                if volume < MIN_VOLUME:
                    continue  # dead or already-decided contract

                # yes_sub_title carries the actual strike ("Above 170000"); the
                # title is the same long question repeated across every strike.
                title  = (m.get("title") or "Untitled").strip()
                strike = (m.get("yes_sub_title") or "").strip()
                # Only append the strike when the title doesn't already state it —
                # some series repeat it ("...above 172000..." / "Above 172000").
                if strike and strike.lower() not in title.lower():
                    title = f"{title} — {strike}"
                if len(title) > 140:
                    title = title[:137] + "…"

                out.append({
                    "title":   title,
                    "yes_pct": yes_pct,
                    "no_pct":  100 - yes_pct,
                    "volume":  volume,
                })

        if out:
            out.sort(key=lambda m: m["volume"], reverse=True)
            return out[:3], "Kalshi"
    except Exception as exc:
        print(f"Kalshi prediction-market error: {exc}")

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
