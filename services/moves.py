# "Why did it move?" — the biggest price days of the last three months, each
# explained in plain English from the headlines around that day.

import math
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from services.ai import explain_price_moves
from services.news import get_headlines_around, short_company_name
from services.stock import get_daily_closes

BENCHMARK    = "SPY"
_WINDOW_DAYS = 92
# "Big" is relative to the stock itself: 2% is a big day for Coca-Cola and an
# ordinary one for Tesla. A day qualifies at 2 standard deviations of its own
# daily moves over the past year (roughly the top 5% of days), and at least 1%.
_VOL_LOOKBACK = 252
_MIN_Z        = 2.0
_MIN_MOVE     = 0.01
_MAX_MOVES    = 5

_CACHE     = {}
_CACHE_TTL = 3600
# A failed Claude call is retried sooner rather than pinned for the full hour.
_CACHE_TTL_UNEXPLAINED = 300


def _returns(rows):
    """[(date, return)] for each close after the first."""
    return [(rows[i][0], rows[i][1] / rows[i - 1][1] - 1) for i in range(1, len(rows))]


def get_price_moves(ticker):
    """Price series for the last ~3 months plus its unusually big days, explained.

    Returns {ticker, series{dates, prices}, typical_pct, biggest, moves[], explained}.
    Each move has date, index (into series), change_pct, market_change_pct,
    label, explanation, clarity, sources (indices into headlines) and headlines.
    """
    ticker = ticker.upper()
    hit = _CACHE.get(ticker)
    if hit and time.time() - hit[0] < hit[1]:
        return hit[2]

    # Raw closes: this feeds a price chart, and the dividend adjustment would
    # put past prices slightly off what the stock actually traded at.
    with ThreadPoolExecutor(max_workers=2) as pool:
        f_rows = pool.submit(get_daily_closes, ticker, False)
        f_mkt  = pool.submit(get_daily_closes, BENCHMARK, False)
        rows, mkt_rows = f_rows.result(), f_mkt.result()

    result = {"ticker": ticker, "series": {"dates": [], "prices": []}, "typical_pct": None,
              "biggest": None, "moves": [], "explained": False}
    if len(rows) < 30:
        return result

    end     = rows[-1][0]
    start_i = next(i for i, (d, _) in enumerate(rows) if d >= end - timedelta(days=_WINDOW_DAYS))
    start_i = max(start_i, 1)            # the first day needs a previous close
    window  = rows[start_i:]
    rets    = _returns(rows)             # rets[k] is the move into rows[k + 1]
    window_rets = rets[start_i - 1:]     # aligned with window

    lookback = [r for _, r in rets[-_VOL_LOOKBACK:]]
    mean     = sum(lookback) / len(lookback)
    sigma    = math.sqrt(sum((r - mean) ** 2 for r in lookback) / max(len(lookback) - 1, 1))
    typical  = sum(abs(r) for r in lookback) / len(lookback)
    mkt_ret  = dict(_returns(mkt_rows))

    result["series"] = {
        "dates":  [d.isoformat() for d, _ in window],
        "prices": [round(c, 2) for _, c in window],
    }
    result["typical_pct"] = round(typical * 100, 2)
    big_i = max(range(len(window_rets)), key=lambda i: abs(window_rets[i][1]))
    result["biggest"] = {"date": window_rets[big_i][0].isoformat(),
                         "change_pct": round(window_rets[big_i][1] * 100, 2)}

    candidates = [
        (i, d, r, r / sigma) for i, (d, r) in enumerate(window_rets)
        if sigma > 0 and abs(r / sigma) >= _MIN_Z and abs(r) >= _MIN_MOVE
    ]
    picked = sorted(sorted(candidates, key=lambda c: -abs(c[3]))[:_MAX_MOVES])
    if not picked:
        _CACHE[ticker] = (time.time(), _CACHE_TTL, result)
        return result

    with ThreadPoolExecutor(max_workers=len(picked)) as pool:
        headlines = list(pool.map(lambda c: get_headlines_around(ticker, c[1]), picked))

    moves = []
    for (i, d, r, z), heads in zip(picked, headlines):
        m = mkt_ret.get(d)
        moves.append({
            "date":              d.isoformat(),
            "index":             i,
            "change_pct":        round(r * 100, 2),
            "market_change_pct": round(m * 100, 2) if m is not None else None,
            "z":                 round(z, 1),
            "headlines":         heads,
        })

    explanations = explain_price_moves(
        short_company_name(ticker) or ticker,
        [dict(m, typical_pct=typical * 100) for m in moves],
    )
    for m, e in zip(moves, explanations or [{}] * len(moves)):
        m["label"]       = e.get("label")
        m["explanation"] = e.get("explanation")
        m["clarity"]     = e.get("clarity")
        m["sources"]     = e.get("sources", [])

    result["moves"]     = moves
    result["explained"] = explanations is not None
    ttl = _CACHE_TTL if explanations is not None else _CACHE_TTL_UNEXPLAINED
    _CACHE[ticker] = (time.time(), ttl, result)
    return result
