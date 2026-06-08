# Stock price, fundamentals, price history, and options flow via yfinance.

import math
from datetime import datetime, timedelta

import yfinance as yf


# ── Numeric sanitizer ───────────────────────────────────────────────────────

def sanitize_number(value, default=None):
    """Coerce *value* to a finite float, or return *default*.

    Guards against None, NaN, Infinity, and non-numeric input so that no
    invalid float ever reaches a JSON response.
    """
    if value is None:
        return default
    try:
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except (TypeError, ValueError):
        return default


# ── Private helpers ────────────────────────────────────────────────────────────

def _fmt_market_cap(n):
    n = sanitize_number(n)
    if not n:
        return "N/A"
    if n >= 1e12:
        return f"${n / 1e12:.2f}T"
    if n >= 1e9:
        return f"${n / 1e9:.2f}B"
    if n >= 1e6:
        return f"${n / 1e6:.2f}M"
    return f"${n:,.0f}"


def _get_options_flow(stock):
    """Compute put/call ratio from a yf.Ticker object. Returns dict or None."""
    try:
        expirations = stock.options
        if not expirations:
            return None
        chain    = stock.option_chain(expirations[0])
        call_vol = sanitize_number(chain.calls["volume"].fillna(0).sum(), 0.0)
        put_vol  = sanitize_number(chain.puts["volume"].fillna(0).sum(), 0.0)
        if not call_vol:
            return None
        ratio = sanitize_number(put_vol / call_vol)
        if ratio is None:
            return None
        if ratio < 0.7:
            sentiment, cls = "BULLISH", "pos"
        elif ratio <= 1.0:
            sentiment, cls = "NEUTRAL", "neutral"
        else:
            sentiment, cls = "BEARISH", "neg"
        return {
            "ratio":     round(ratio, 2),
            "sentiment": sentiment,
            "color":     cls,
            "call_vol":  int(call_vol),
            "put_vol":   int(put_vol),
        }
    except Exception as exc:
        print(f"Options flow error: {exc}")
        return None


# ── Public API ─────────────────────────────────────────────────────────────────

def get_stock_data(ticker):
    """Fetch price, fundamentals, and options flow for *ticker*.

    Every numeric field is run through sanitize_number() so the returned dict
    is always JSON-safe. Returns a data dict on success, or {"error": str} on
    failure. Crypto tickers (suffix -USD) are flagged and carry no P/E.
    """
    try:
        is_crypto = ticker.upper().endswith("-USD")
        stock = yf.Ticker(ticker)
        info  = stock.info or {}

        price = sanitize_number(
            info.get("regularMarketPrice")
            or info.get("currentPrice")
            or info.get("ask")
            or info.get("bid")
        )
        prev_close = sanitize_number(
            info.get("regularMarketPreviousClose") or info.get("previousClose")
        )

        if price is None and prev_close is None:
            return {"error": f'Ticker "{ticker}" not found — check the symbol and try again.'}

        price      = price if price is not None else prev_close
        prev_close = prev_close if prev_close is not None else price
        change     = sanitize_number(price - prev_close, 0.0)
        change_pct = sanitize_number((change / prev_close * 100) if prev_close else 0.0, 0.0)

        # P/E is meaningless for crypto → force null and skip
        pe_ratio = None if is_crypto else sanitize_number(info.get("trailingPE"), default=None)

        week52_high = sanitize_number(info.get("fiftyTwoWeekHigh"), default=None)
        week52_low  = sanitize_number(info.get("fiftyTwoWeekLow"),  default=None)
        market_cap  = sanitize_number(info.get("marketCap"),        default=None)

        return {
            "ticker":       ticker,
            "name":         info.get("longName") or info.get("shortName") or ticker,
            "is_crypto":    is_crypto,
            "price":        round(price, 2),
            "change":       round(change, 2),
            "change_pct":   round(change_pct, 2),
            "market_cap":   _fmt_market_cap(market_cap),
            "market_cap_raw": market_cap,
            "pe_ratio":     round(pe_ratio, 2) if pe_ratio is not None else "N/A",
            "week_52_high": round(week52_high, 2) if week52_high is not None else None,
            "week_52_low":  round(week52_low, 2)  if week52_low  is not None else None,
            "options_flow": None if is_crypto else _get_options_flow(stock),
        }
    except Exception as exc:
        print(f"Stock data error: {exc}")
        return {"error": f"Stock data error: {exc}"}


def get_price_history(ticker, days=35):
    """Return a chart dict with date labels and sanitized closing prices."""
    try:
        stock = yf.Ticker(ticker)
        end   = datetime.now()
        hist  = stock.history(start=end - timedelta(days=days), end=end)
        prices = [sanitize_number(p) for p in hist["Close"].tolist()]
        dates  = [d.strftime("%b %d") for d in hist.index]
        # Drop any rows where price sanitized to None (keep arrays aligned)
        clean_dates, clean_prices = [], []
        for d, p in zip(dates, prices):
            if p is not None:
                clean_dates.append(d)
                clean_prices.append(round(p, 2))
        return {"dates": clean_dates, "prices": clean_prices}
    except Exception as exc:
        print(f"Price history error: {exc}")
        return {"dates": [], "prices": []}


def get_options_data(ticker):
    """Public wrapper: fetch options flow for *ticker* string. Returns dict or None."""
    try:
        return _get_options_flow(yf.Ticker(ticker))
    except Exception as exc:
        print(f"Options data error: {exc}")
        return None
