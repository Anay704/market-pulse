# Portfolio basket math: aggregate value, P/L, sector exposure + Claude posture summary.

import json
import os

import anthropic
import yfinance as yf

from services.stock import get_stock_data, sanitize_number

MODEL = "claude-sonnet-4-6"


def _safe_sector(ticker):
    """Pull a sector label from yfinance; never raises."""
    try:
        info = yf.Ticker(ticker).info or {}
        return info.get("sector") or "Unknown"
    except Exception:
        return "Unknown"


def summarize_portfolio(holdings):
    """Aggregate a list of {ticker, shares, cost_basis} into totals + per-position breakdown.

    Returns a JSON-safe dict with totals, positions list, and sector exposure %.
    Never raises — bad rows are skipped with an error field.
    """
    positions = []
    total_value = 0.0
    total_cost  = 0.0
    sectors     = {}

    for h in (holdings or []):
        ticker = (h.get("ticker") or "").upper().strip()
        shares = sanitize_number(h.get("shares"),     0.0) or 0.0
        cost   = sanitize_number(h.get("cost_basis"), 0.0) or 0.0
        if not ticker or shares <= 0 or cost <= 0:
            continue

        stock = get_stock_data(ticker)
        if "error" in stock:
            positions.append({
                "ticker":     ticker,
                "name":       ticker,
                "shares":     shares,
                "cost_basis": round(cost, 2),
                "price":      None,
                "value":      None,
                "pnl":        None,
                "pnl_pct":    None,
                "sector":     "Unknown",
                "error":      stock["error"],
            })
            continue

        price       = sanitize_number(stock.get("price"), 0.0) or 0.0
        change_pct  = sanitize_number(stock.get("change_pct"), 0.0)
        value       = price * shares
        pos_cost    = cost * shares
        pnl         = value - pos_cost
        pnl_pct     = (pnl / pos_cost * 100.0) if pos_cost else 0.0
        sector      = "Crypto" if stock.get("is_crypto") else _safe_sector(ticker)

        positions.append({
            "ticker":     ticker,
            "name":       stock.get("name", ticker),
            "shares":     shares,
            "cost_basis": round(cost, 2),
            "price":      round(price, 2),
            "value":      round(value, 2),
            "cost_total": round(pos_cost, 2),
            "pnl":        round(pnl, 2),
            "pnl_pct":    round(pnl_pct, 2),
            "sector":     sector,
            "change_pct": change_pct,
        })
        total_value += value
        total_cost  += pos_cost
        sectors[sector] = sectors.get(sector, 0.0) + value

    total_pnl     = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100.0) if total_cost else 0.0

    sector_breakdown = []
    if total_value > 0:
        for s, v in sorted(sectors.items(), key=lambda x: -x[1]):
            sector_breakdown.append({
                "sector": s,
                "value":  round(v, 2),
                "pct":    round(v / total_value * 100.0, 1),
            })

    return {
        "positions":        positions,
        "position_count":   len([p for p in positions if not p.get("error")]),
        "total_value":      round(total_value, 2),
        "total_cost":       round(total_cost, 2),
        "total_pnl":        round(total_pnl, 2),
        "total_pnl_pct":    round(total_pnl_pct, 2),
        "sector_breakdown": sector_breakdown,
    }


def get_portfolio_narrative(summary):
    """Three- to four-sentence Claude analysis of the portfolio posture."""
    if not summary or not summary.get("positions"):
        return "Add positions to see an AI summary of your portfolio."
    try:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return "AI narrative unavailable: ANTHROPIC_API_KEY is not set."
        client = anthropic.Anthropic(api_key=api_key)

        slim = {
            "total_value":      summary["total_value"],
            "total_pnl":        summary["total_pnl"],
            "total_pnl_pct":    summary["total_pnl_pct"],
            "positions": [
                {
                    "ticker":     p["ticker"],
                    "value":      p.get("value"),
                    "pnl":        p.get("pnl"),
                    "pnl_pct":    p.get("pnl_pct"),
                    "change_pct": p.get("change_pct"),
                    "sector":     p.get("sector"),
                }
                for p in summary["positions"][:30]
            ],
            "sector_breakdown": summary.get("sector_breakdown", [])[:8],
        }
        ctx = json.dumps(slim, default=str)[:6000]

        resp = client.messages.create(
            model=MODEL,
            max_tokens=320,
            system=(
                "You are a portfolio analyst. Given the portfolio JSON, write a 3-4 sentence "
                "summary covering: (1) overall posture — total P&L direction and magnitude, "
                "(2) today's biggest winner and biggest loser by name, "
                "(3) concentration or sector risk if any single position or sector is over-weighted. "
                "Cite specific numbers. Plain text only — no markdown, no bullet points."
            ),
            messages=[{"role": "user", "content": ctx}],
        )
        return resp.content[0].text
    except Exception as exc:
        print(f"Portfolio narrative error: {exc}")
        return f"AI narrative unavailable: {exc}"
