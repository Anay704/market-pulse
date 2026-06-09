# Financial Modeling Prep (FMP) integrations — free-tier endpoints only.
#
# Provides:
#   - get_analyst_estimates(ticker)   forward revenue/EBITDA/EPS forecasts
#   - get_rating_changes(ticker)      recent analyst upgrades / downgrades
#   - get_fmp_rating(ticker)          composite letter rating + sub-scores

import os

import requests

from services.stock import sanitize_number


BASE = "https://financialmodelingprep.com/stable"


def _key():
    return os.environ.get("FMP_API_KEY") or None


def _get(path, params=None, timeout=10):
    """Safe GET against FMP. Returns parsed JSON list/dict, or None on any failure."""
    k = _key()
    if not k:
        return None
    try:
        r = requests.get(
            f"{BASE}/{path}",
            params={**(params or {}), "apikey": k},
            timeout=timeout,
        )
        if r.status_code != 200:
            return None
        return r.json()
    except Exception as exc:
        print(f"FMP {path} error: {exc}")
        return None


# ── Forward analyst estimates ────────────────────────────────────────────────

def get_analyst_estimates(ticker):
    """Return list of forward estimates per period:
    [{period, date, revenue_avg, revenue_low, revenue_high, eps_avg, eps_low, eps_high, analysts}].
    """
    rows = _get("analyst-estimates",
                {"symbol": ticker, "period": "annual", "limit": 4})
    if not rows:
        return []
    out = []
    for r in rows:
        out.append({
            "period":         r.get("period", "FY"),
            "date":           r.get("date", "")[:10],
            "revenue_avg":    sanitize_number(r.get("revenueAvg")),
            "revenue_low":    sanitize_number(r.get("revenueLow")),
            "revenue_high":   sanitize_number(r.get("revenueHigh")),
            "eps_avg":        sanitize_number(r.get("epsAvg")),
            "eps_low":        sanitize_number(r.get("epsLow")),
            "eps_high":       sanitize_number(r.get("epsHigh")),
            "ebitda_avg":     sanitize_number(r.get("ebitdaAvg")),
            "analysts":       int(sanitize_number(r.get("numAnalystsRevenue")) or 0),
        })
    return out


# ── Recent rating changes ────────────────────────────────────────────────────

def get_rating_changes(ticker, limit=12):
    """Return list of recent analyst grade actions for *ticker*:
    [{date, firm, previous_grade, new_grade, action}].
    """
    rows = _get("grades", {"symbol": ticker, "limit": limit})
    if not rows:
        return []
    out = []
    for r in rows[:limit]:
        action = (r.get("action") or "").lower()
        # FMP uses 'upgraded', 'downgraded', 'maintained', 'initialised', etc.
        if "up" in action:
            cls = "upgrade"
        elif "down" in action:
            cls = "downgrade"
        elif "init" in action:
            cls = "initiate"
        else:
            cls = "maintain"
        out.append({
            "date":           (r.get("date") or "")[:10],
            "firm":           r.get("gradingCompany") or "Unknown",
            "previous_grade": r.get("previousGrade") or "—",
            "new_grade":      r.get("newGrade") or "—",
            "action":         r.get("action") or "—",
            "class":          cls,
        })
    return out


# ── FMP composite rating ─────────────────────────────────────────────────────

def get_fmp_rating(ticker):
    """Return FMP's letter rating + sub-scores (DCF, ROE, ROA, DE, PE, PB)."""
    rows = _get("ratings-snapshot", {"symbol": ticker})
    if not rows:
        return None
    r = rows[0] if isinstance(rows, list) else rows
    return {
        "rating":          r.get("rating"),
        "overall_score":   sanitize_number(r.get("overallScore")),
        "dcf_score":       sanitize_number(r.get("discountedCashFlowScore")),
        "roe_score":       sanitize_number(r.get("returnOnEquityScore")),
        "roa_score":       sanitize_number(r.get("returnOnAssetsScore")),
        "de_score":        sanitize_number(r.get("debtToEquityScore")),
        "pe_score":        sanitize_number(r.get("priceToEarningsScore")),
        "pb_score":        sanitize_number(r.get("priceToBookScore")),
    }


def get_fmp_bundle(ticker):
    """Pull all three FMP sections for one ticker. Returns {} if no FMP key."""
    if not _key():
        return {}
    return {
        "analyst_estimates":  get_analyst_estimates(ticker),
        "rating_changes":     get_rating_changes(ticker),
        "fmp_rating":         get_fmp_rating(ticker),
    }
