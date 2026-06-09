# Deep-research data sections: company overview, analyst consensus, insider trading,
# institutional ownership, quarterly financials, risk metrics. All powered by yfinance.

import math

import yfinance as yf

from services.fmp import get_fmp_bundle
from services.stock import sanitize_number


# ── Helpers ──────────────────────────────────────────────────────────────────

def _safe_df_to_records(df, max_rows=10):
    """Convert a pandas DataFrame to a JSON-safe list of dicts."""
    try:
        if df is None or df.empty:
            return []
        out = []
        for _, row in df.head(max_rows).iterrows():
            rec = {}
            for col, val in row.items():
                col_s = str(col)
                if val is None:
                    rec[col_s] = None
                elif isinstance(val, float):
                    rec[col_s] = None if (math.isnan(val) or math.isinf(val)) else round(val, 4)
                elif hasattr(val, "isoformat"):
                    rec[col_s] = val.strftime("%Y-%m-%d")
                else:
                    rec[col_s] = str(val) if not isinstance(val, (int, str, bool)) else val
            out.append(rec)
        return out
    except Exception as exc:
        print(f"DataFrame conversion error: {exc}")
        return []


def _fmt_big(n):
    """Format a large number into $1.2B / $345M / etc."""
    n = sanitize_number(n)
    if n is None:
        return None
    a = abs(n); sign = "-" if n < 0 else ""
    if a >= 1e12: return f"{sign}${a/1e12:.2f}T"
    if a >= 1e9:  return f"{sign}${a/1e9:.2f}B"
    if a >= 1e6:  return f"{sign}${a/1e6:.2f}M"
    if a >= 1e3:  return f"{sign}${a/1e3:.2f}K"
    return f"{sign}${a:,.0f}"


# ── 1. Company Overview ──────────────────────────────────────────────────────

def get_company_overview(ticker):
    """Static company profile: business summary, sector, employees, HQ, website."""
    try:
        info = yf.Ticker(ticker).info or {}
        return {
            "summary":        (info.get("longBusinessSummary") or "").strip()[:2200],
            "sector":         info.get("sector")   or None,
            "industry":       info.get("industry") or None,
            "country":        info.get("country")  or None,
            "city":           info.get("city")     or None,
            "state":          info.get("state")    or None,
            "address":        info.get("address1") or None,
            "website":        info.get("website")  or None,
            "employees":      sanitize_number(info.get("fullTimeEmployees")),
            "exchange":       info.get("exchange") or None,
            "currency":       info.get("currency") or None,
            "ipo_year":       sanitize_number(info.get("ipoExpectedDate")) or None,
            "ceo":            (info.get("companyOfficers") or [{}])[0].get("name") if info.get("companyOfficers") else None,
        }
    except Exception as exc:
        print(f"Company overview error for {ticker}: {exc}")
        return {"summary": "", "sector": None, "industry": None, "employees": None}


# ── 2. Analyst Consensus ─────────────────────────────────────────────────────

def get_analyst_consensus(ticker):
    """Wall Street ratings + price targets."""
    try:
        stock = yf.Ticker(ticker)
        info  = stock.info or {}

        # Recommendation buckets — yfinance returns a small DataFrame in newer versions
        buckets = {"strongBuy": 0, "buy": 0, "hold": 0, "sell": 0, "strongSell": 0}
        try:
            recs = stock.recommendations
            if recs is not None and not recs.empty:
                # Take the most recent row (period 0m if present, else first row)
                row = recs.iloc[0]
                for k in buckets.keys():
                    if k in row:
                        buckets[k] = int(sanitize_number(row[k]) or 0)
        except Exception:
            pass

        total = sum(buckets.values())

        # Price targets — newer yfinance exposes analyst_price_targets dict
        targets = {"current": None, "high": None, "low": None, "mean": None, "median": None}
        try:
            t = stock.analyst_price_targets
            if isinstance(t, dict):
                for k in targets.keys():
                    if k in t:
                        targets[k] = sanitize_number(t[k])
        except Exception:
            pass
        # Fall back to info fields
        if targets["mean"] is None:
            targets["mean"] = sanitize_number(info.get("targetMeanPrice"))
        if targets["high"] is None:
            targets["high"] = sanitize_number(info.get("targetHighPrice"))
        if targets["low"] is None:
            targets["low"]  = sanitize_number(info.get("targetLowPrice"))
        if targets["median"] is None:
            targets["median"] = sanitize_number(info.get("targetMedianPrice"))
        if targets["current"] is None:
            targets["current"] = sanitize_number(
                info.get("regularMarketPrice") or info.get("currentPrice")
            )

        # Upside percent
        upside = None
        if targets["mean"] and targets["current"]:
            upside = round((targets["mean"] / targets["current"] - 1.0) * 100.0, 2)

        # Headline recommendation
        rec_key = (info.get("recommendationKey") or "").upper()  # 'buy', 'hold', etc.
        rec_mean = sanitize_number(info.get("recommendationMean"))  # 1=strong buy → 5=sell
        num_analysts = sanitize_number(info.get("numberOfAnalystOpinions"))

        return {
            "buckets":         buckets,
            "total_analysts":  int(num_analysts) if num_analysts else total,
            "recommendation":  rec_key or None,
            "rec_score":       round(rec_mean, 2) if rec_mean else None,
            "targets":         {k: (round(v, 2) if v is not None else None) for k, v in targets.items()},
            "upside_pct":      upside,
        }
    except Exception as exc:
        print(f"Analyst consensus error for {ticker}: {exc}")
        return {"buckets": {}, "total_analysts": 0, "targets": {}, "upside_pct": None}


# ── 3. Insider Trading (SEC Form 4) ──────────────────────────────────────────

def get_insider_activity(ticker):
    """Recent insider buy/sell transactions."""
    try:
        stock = yf.Ticker(ticker)
        rows = _safe_df_to_records(stock.insider_transactions, max_rows=15)
        out = []
        net_buys = 0; net_sells = 0
        for r in rows:
            txn = (r.get("Transaction") or "").lower()
            shares = sanitize_number(r.get("Shares")) or 0
            value  = sanitize_number(r.get("Value"))  or 0
            kind = (
                "BUY"  if "purchase" in txn or "buy" in txn or "acquisition" in txn else
                "SELL" if "sale" in txn or "sell" in txn or "disposition" in txn else
                "OTHER"
            )
            out.append({
                "insider":   r.get("Insider")  or "Unknown",
                "position":  r.get("Position") or "—",
                "date":      r.get("Start Date") or r.get("Date") or "",
                "type":      kind,
                "shares":    int(shares) if shares else 0,
                "value":     _fmt_big(value),
                "value_raw": round(value, 2) if value else 0,
                "text":      (r.get("Text") or "")[:200],
            })
            if   kind == "BUY":  net_buys  += value
            elif kind == "SELL": net_sells += value
        return {
            "transactions":   out,
            "buy_value":      _fmt_big(net_buys),
            "sell_value":     _fmt_big(net_sells),
            "net_value":      _fmt_big(net_buys - net_sells),
            "net_value_raw":  round(net_buys - net_sells, 2),
            "count":          len(out),
        }
    except Exception as exc:
        print(f"Insider activity error for {ticker}: {exc}")
        return {"transactions": [], "count": 0, "buy_value": None, "sell_value": None}


# ── 4. Institutional Ownership (13F) ─────────────────────────────────────────

def get_institutional_ownership(ticker):
    """Top institutional + mutual-fund holders."""
    try:
        stock = yf.Ticker(ticker)
        info  = stock.info or {}

        institutions = _safe_df_to_records(stock.institutional_holders, max_rows=10)
        mutual_funds = _safe_df_to_records(stock.mutualfund_holders, max_rows=10)

        def _slim(rows):
            slim = []
            for r in rows:
                slim.append({
                    "holder":      r.get("Holder")      or r.get("name") or "Unknown",
                    "shares":      sanitize_number(r.get("Shares") or r.get("shares")),
                    "pct_held":    sanitize_number(r.get("pctHeld") or r.get("% Out")),
                    "value":       _fmt_big(sanitize_number(r.get("Value") or r.get("value"))),
                    "date":        r.get("Date Reported") or r.get("reportDate") or "",
                })
            return slim

        institutions = _slim(institutions)
        mutual_funds = _slim(mutual_funds)

        # Some yfinance versions return pctHeld as fraction (0.0735), some as percent (7.35)
        # Detect by max value and rescale if needed.
        def _to_pct(rows):
            if not rows: return rows
            mx = max((r["pct_held"] or 0) for r in rows)
            if mx <= 1.0:  # treat as fraction
                for r in rows:
                    if r["pct_held"] is not None:
                        r["pct_held"] = round(r["pct_held"] * 100, 2)
            else:
                for r in rows:
                    if r["pct_held"] is not None:
                        r["pct_held"] = round(r["pct_held"], 2)
            return rows
        _to_pct(institutions); _to_pct(mutual_funds)

        held_pct_inst   = sanitize_number(info.get("heldPercentInstitutions"))
        held_pct_insider = sanitize_number(info.get("heldPercentInsiders"))
        if held_pct_inst    is not None: held_pct_inst    = round(held_pct_inst * (100 if held_pct_inst <= 1 else 1), 2)
        if held_pct_insider is not None: held_pct_insider = round(held_pct_insider * (100 if held_pct_insider <= 1 else 1), 2)

        return {
            "institutions":         institutions,
            "mutual_funds":         mutual_funds,
            "pct_institutional":    held_pct_inst,
            "pct_insider":          held_pct_insider,
            "institutions_count":   len(institutions),
        }
    except Exception as exc:
        print(f"Institutional ownership error for {ticker}: {exc}")
        return {"institutions": [], "mutual_funds": [], "pct_institutional": None, "pct_insider": None}


# ── 5. Quarterly Financials (QoQ revenue / income / margins) ─────────────────

def get_quarterly_financials(ticker):
    """Last 4-5 quarters of revenue, net income, EPS, plus computed margins."""
    try:
        stock = yf.Ticker(ticker)
        q = stock.quarterly_income_stmt   # DataFrame: rows=metrics, cols=quarter dates
        if q is None or q.empty:
            return {"quarters": [], "metrics_available": False}

        # Pick the canonical rows yfinance provides (accept first match across aliases)
        def _row(*aliases):
            for key in aliases:
                for variant in (key, key.replace(" ", ""), key.lower()):
                    if variant in q.index:
                        return q.loc[variant]
            return None

        revenue_row = _row("Total Revenue", "Revenue", "Operating Revenue")
        op_inc_row  = _row("Operating Income", "Total Operating Income As Reported")
        net_inc_row = _row("Net Income", "Net Income Common Stockholders",
                           "Net Income Continuous Operations")
        eps_row     = _row("Basic EPS", "Diluted EPS")
        gross_row   = _row("Gross Profit")

        cols = list(q.columns)[:5]   # latest 5 quarters
        quarters = []
        for c in cols:
            rev = sanitize_number(revenue_row[c]) if revenue_row is not None else None
            op  = sanitize_number(op_inc_row[c])  if op_inc_row  is not None else None
            ni  = sanitize_number(net_inc_row[c]) if net_inc_row is not None else None
            eps = sanitize_number(eps_row[c])     if eps_row     is not None else None
            gp  = sanitize_number(gross_row[c])   if gross_row   is not None else None
            quarters.append({
                "quarter":        c.strftime("%b %Y") if hasattr(c, "strftime") else str(c),
                "revenue":        rev,
                "revenue_fmt":    _fmt_big(rev),
                "operating_income": op,
                "operating_income_fmt": _fmt_big(op),
                "net_income":     ni,
                "net_income_fmt": _fmt_big(ni),
                "eps":            round(eps, 2) if eps is not None else None,
                "gross_margin":   round(gp / rev * 100, 2) if (gp and rev) else None,
                "operating_margin": round(op / rev * 100, 2) if (op and rev) else None,
                "net_margin":     round(ni / rev * 100, 2) if (ni and rev) else None,
            })
        # YoY growth: latest vs 4 quarters ago
        yoy = None
        if len(quarters) >= 5 and quarters[0]["revenue"] and quarters[4]["revenue"]:
            yoy = round((quarters[0]["revenue"] / quarters[4]["revenue"] - 1.0) * 100, 2)
        return {
            "quarters":          quarters,
            "yoy_revenue_growth": yoy,
            "metrics_available": True,
        }
    except Exception as exc:
        print(f"Quarterly financials error for {ticker}: {exc}")
        return {"quarters": [], "metrics_available": False}


# ── 6. Risk Metrics (balance-sheet & cash-flow health) ───────────────────────

def get_risk_metrics(ticker):
    """Leverage, liquidity, cash-flow strength."""
    try:
        stock = yf.Ticker(ticker)
        info  = stock.info or {}

        # Prefer info fields when present (yfinance pre-computes some)
        debt_to_equity = sanitize_number(info.get("debtToEquity"))
        # yfinance returns this as 'percent of equity' sometimes (e.g. 150.5 = 1.505)
        if debt_to_equity is not None and debt_to_equity > 10:
            debt_to_equity = round(debt_to_equity / 100, 2)
        current_ratio = sanitize_number(info.get("currentRatio"))
        quick_ratio   = sanitize_number(info.get("quickRatio"))
        op_cashflow   = sanitize_number(info.get("operatingCashflow"))
        free_cashflow = sanitize_number(info.get("freeCashflow"))
        ebitda        = sanitize_number(info.get("ebitda"))
        total_cash    = sanitize_number(info.get("totalCash"))
        total_debt    = sanitize_number(info.get("totalDebt"))
        roe           = sanitize_number(info.get("returnOnEquity"))
        roa           = sanitize_number(info.get("returnOnAssets"))

        # Normalize ratios that may come as fractions
        if roe is not None and abs(roe) <= 1: roe = round(roe * 100, 2)
        if roa is not None and abs(roa) <= 1: roa = round(roa * 100, 2)

        # Interest coverage — approximate from EBITDA / interestExpense if possible
        interest_coverage = None
        try:
            cf = stock.quarterly_income_stmt
            if cf is not None and not cf.empty:
                # Annualize: sum last 4 quarters
                if "Interest Expense" in cf.index and ebitda:
                    ie = cf.loc["Interest Expense"].iloc[:4].sum()
                    ie = sanitize_number(ie)
                    if ie and ie != 0:
                        interest_coverage = round(abs(ebitda / ie), 2)
        except Exception:
            pass

        # Simple risk flag synthesis
        flags = []
        if debt_to_equity is not None and debt_to_equity > 2.0:
            flags.append({"severity": "high",   "msg": f"High leverage: D/E ratio {debt_to_equity:.2f}"})
        elif debt_to_equity is not None and debt_to_equity > 1.0:
            flags.append({"severity": "med",    "msg": f"Elevated leverage: D/E ratio {debt_to_equity:.2f}"})
        if current_ratio is not None and current_ratio < 1.0:
            flags.append({"severity": "high",   "msg": f"Liquidity concern: current ratio {current_ratio:.2f} below 1.0"})
        if free_cashflow is not None and free_cashflow < 0:
            flags.append({"severity": "high",   "msg": f"Negative free cash flow ({_fmt_big(free_cashflow)})"})
        if interest_coverage is not None and interest_coverage < 3.0:
            flags.append({"severity": "med",    "msg": f"Tight interest coverage: {interest_coverage:.1f}x"})
        if not flags:
            flags.append({"severity": "low",    "msg": "No major leverage, liquidity, or cash-flow red flags."})

        return {
            "debt_to_equity":    debt_to_equity,
            "current_ratio":     round(current_ratio, 2) if current_ratio else None,
            "quick_ratio":       round(quick_ratio, 2)   if quick_ratio   else None,
            "interest_coverage": interest_coverage,
            "operating_cashflow": op_cashflow,
            "operating_cashflow_fmt": _fmt_big(op_cashflow),
            "free_cashflow":     free_cashflow,
            "free_cashflow_fmt": _fmt_big(free_cashflow),
            "ebitda":            ebitda,
            "ebitda_fmt":        _fmt_big(ebitda),
            "total_cash":        total_cash,
            "total_cash_fmt":    _fmt_big(total_cash),
            "total_debt":        total_debt,
            "total_debt_fmt":    _fmt_big(total_debt),
            "roe":               roe,
            "roa":               roa,
            "flags":             flags,
        }
    except Exception as exc:
        print(f"Risk metrics error for {ticker}: {exc}")
        return {"flags": [{"severity": "low", "msg": f"Risk data unavailable: {exc}"}]}


# ── 7. Aggregator: full research report ──────────────────────────────────────

def get_earnings_call(ticker):
    """Latest earnings call transcript + Claude analysis. None if AV key
    missing, no transcript available, or any failure."""
    from services.ai import summarize_earnings_call
    from services.transcripts import fetch_latest_transcript

    t = fetch_latest_transcript(ticker)
    if not t:
        return None
    summary = summarize_earnings_call(ticker, t)
    return {
        "available":        True,
        "quarter":          t["quarter"],
        "year":             t.get("year"),
        "q_num":            t.get("q_num"),
        "speakers":         t["speakers"],
        "segments":         t["segments"],
        "transcript_chars": t["char_count"],
        "summary":          summary,
    }


def get_research_report(ticker):
    """Run all data fetchers in sequence and return a single report dict.

    Includes FMP-powered sections (forward estimates / rating changes / composite
    rating) when FMP_API_KEY is configured, and the earnings-call summary when
    ALPHAVANTAGE_API_KEY is configured. Missing keys = sections silently absent.
    """
    report = {
        "ticker":               ticker.upper(),
        "company_overview":     get_company_overview(ticker),
        "analyst_consensus":    get_analyst_consensus(ticker),
        "insider_activity":     get_insider_activity(ticker),
        "institutional":        get_institutional_ownership(ticker),
        "quarterly_financials": get_quarterly_financials(ticker),
        "risk_metrics":         get_risk_metrics(ticker),
    }
    # Optional FMP-powered sections
    fmp = get_fmp_bundle(ticker)
    if fmp:
        report["fmp"] = fmp
    # Optional Alpha Vantage earnings call section
    ec = get_earnings_call(ticker)
    if ec:
        report["earnings_call"] = ec
    return report
