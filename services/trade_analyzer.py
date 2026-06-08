# Trade analysis: position metrics, recommendation thresholds, and combined score.

import math


def _num(value, default=0.0):
    if value is None:
        return default
    try:
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except (TypeError, ValueError):
        return default


# ── Position metrics ───────────────────────────────────────────────────────────

def calculate_position_metrics(shares_owned, avg_buy_price, current_price):
    """Compute basic P&L metrics for an existing position. Safe against zeros/None."""
    shares_owned  = _num(shares_owned, 0.0)
    avg_buy_price = _num(avg_buy_price, 0.0)
    current_price = _num(current_price, 0.0)

    cost_basis     = shares_owned * avg_buy_price
    current_value  = shares_owned * current_price
    unrealized_pnl = (current_price - avg_buy_price) * shares_owned
    pnl_pct        = ((current_price - avg_buy_price) / avg_buy_price * 100) if avg_buy_price else 0.0

    return {
        "shares":         shares_owned,
        "avg_price":      round(avg_buy_price, 2),
        "cost_basis":     round(cost_basis, 2),
        "current_value":  round(current_value, 2),
        "unrealized_pnl": round(unrealized_pnl, 2),
        "pnl_pct":        round(pnl_pct, 2),
    }


# ── Trade recommendation ───────────────────────────────────────────────────────

def get_trade_recommendation(final_score):
    """Map a 0-1 composite score to a recommendation string and CSS color key."""
    final_score = _num(final_score, 0.5)
    if final_score >= 0.75:
        return "STRONG BUY",  "strong-pos"
    if final_score >= 0.60:
        return "BUY",          "pos"
    if final_score >= 0.40:
        return "HOLD",         "neutral"
    if final_score >= 0.25:
        return "SELL",         "neg"
    return     "STRONG SELL",  "strong-neg"


# ── Full position action ───────────────────────────────────────────────────────

def calculate_suggested_action(shares_owned, avg_buy_price, current_price,
                                final_score, shares_considering=0):
    """Combine position metrics with score-driven action guidance. Never divides by zero."""
    final_score   = _num(final_score, 0.5)
    current_price = _num(current_price, 0.0)
    metrics       = calculate_position_metrics(shares_owned, avg_buy_price, current_price)

    if final_score >= 0.60:
        sell_pct = 0
    elif final_score >= 0.40:
        sell_pct = 25
    elif final_score >= 0.25:
        sell_pct = 50
    else:
        sell_pct = 100

    stop_loss    = current_price * 0.92
    target_price = current_price * (1.0 + final_score * 0.20)
    risk         = current_price - stop_loss
    reward       = target_price - current_price
    rr_ratio     = round(reward / risk, 2) if risk > 0 else 0.0

    return {
        **metrics,
        "sell_pct":          sell_pct,
        "stop_loss":         round(stop_loss, 2),
        "target_price":      round(target_price, 2),
        "risk_reward_ratio": rr_ratio,
    }


# ── Combined score ─────────────────────────────────────────────────────────────

def calculate_combined_score(technical_score, fundamental_score, sentiment_score,
                              has_image=False):
    """Blend sub-scores into a final 0-1 composite.

    With chart image:  technical 35% + fundamental 35% + sentiment 30%
    Without image:     fundamental 55% + sentiment 45%
    Returns float clamped to [0.0, 1.0].
    """
    fundamental_score = _num(fundamental_score, 0.5)
    sentiment_score   = _num(sentiment_score, 0.5)
    if has_image and technical_score is not None:
        technical_score = _num(technical_score, 0.5)
        score = technical_score * 0.35 + fundamental_score * 0.35 + sentiment_score * 0.30
    else:
        score = fundamental_score * 0.55 + sentiment_score * 0.45
    return max(0.0, min(1.0, _num(score, 0.5)))
