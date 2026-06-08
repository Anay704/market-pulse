# Live index quotes (S&P / Nasdaq / Dow) and watchlist quote strip for the ticker tape.

import yfinance as yf

from services.stock import sanitize_number


INDEX_MAP = [
    ("S&P 500", "^GSPC"),
    ("NASDAQ",  "^IXIC"),
    ("DOW",     "^DJI"),
]


def _quote(symbol):
    """Single ticker → {price, change, change_pct} or None on failure."""
    try:
        info  = yf.Ticker(symbol).info or {}
        price = sanitize_number(
            info.get("regularMarketPrice")
            or info.get("currentPrice")
            or info.get("previousClose")
        )
        prev  = sanitize_number(
            info.get("regularMarketPreviousClose") or info.get("previousClose")
        )
        if price is None:
            return None
        prev = prev if prev is not None else price
        change = price - prev
        change_pct = (change / prev * 100) if prev else 0.0
        return {
            "price":      round(price, 2),
            "change":     round(change, 2),
            "change_pct": round(change_pct, 2),
        }
    except Exception as exc:
        print(f"Quote error {symbol}: {exc}")
        return None


def get_indices():
    """Return [{label, symbol, value, change, change_pct}] for the major US indices."""
    out = []
    for label, sym in INDEX_MAP:
        q = _quote(sym) or {"price": None, "change": None, "change_pct": None}
        out.append({
            "label":      label,
            "symbol":     sym,
            "value":      q["price"],
            "change":     q["change"],
            "change_pct": q["change_pct"],
        })
    return out


def get_quote_strip(tickers):
    """For watchlist ticker tape: [{ticker, price, change_pct}] (skip failures)."""
    out = []
    for sym in (tickers or []):
        sym = (sym or "").strip().upper()
        if not sym:
            continue
        q = _quote(sym)
        if not q:
            continue
        out.append({"ticker": sym, "price": q["price"], "change_pct": q["change_pct"]})
    return out
