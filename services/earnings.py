# Next-earnings dates from yfinance — single-ticker lookup + watchlist calendar roll-up.

from datetime import datetime, timezone

import yfinance as yf


def _to_utc(dt):
    """Coerce a possibly-naive datetime to UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def get_next_earnings(ticker):
    """Return {ticker, date_iso, date_str, days_until} for next earnings, or None."""
    try:
        stock = yf.Ticker(ticker)
        ed = None
        try:
            ed = stock.earnings_dates
        except Exception:
            ed = None

        candidates = []
        if ed is not None and not ed.empty:
            now = datetime.now(timezone.utc)
            for d in ed.index:
                dt = _to_utc(d.to_pydatetime())
                if dt and dt >= now:
                    candidates.append(dt)

        # Fallback: yfinance .calendar dict may carry an "Earnings Date" list
        if not candidates:
            try:
                cal = stock.calendar
                if isinstance(cal, dict):
                    raw = cal.get("Earnings Date") or []
                    if not isinstance(raw, list):
                        raw = [raw]
                    for r in raw:
                        dt = _to_utc(r if isinstance(r, datetime) else datetime.fromisoformat(str(r)))
                        if dt and dt >= datetime.now(timezone.utc):
                            candidates.append(dt)
            except Exception:
                pass

        if not candidates:
            return None

        next_dt = min(candidates)
        days_until = (next_dt - datetime.now(timezone.utc)).days
        return {
            "ticker":     ticker.upper(),
            "date_iso":   next_dt.isoformat(),
            "date_str":   next_dt.strftime("%b %d, %Y"),
            "days_until": days_until,
        }
    except Exception as exc:
        print(f"Earnings lookup error for {ticker}: {exc}")
        return None


def get_earnings_for_watchlist(tickers):
    """Return upcoming earnings for *tickers*, sorted by soonest first."""
    out = []
    for t in (tickers or []):
        t = (t or "").strip().upper()
        if not t:
            continue
        info = get_next_earnings(t)
        if info:
            out.append(info)
    return sorted(out, key=lambda x: x["days_until"])
