# Probability scoring, sentiment labels, price targets, and fundamental score math.

import math
from statistics import mean


def _num(value, default=0.0):
    """Local finite-float coercion (mirrors stock.sanitize_number)."""
    if value is None:
        return default
    try:
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except (TypeError, ValueError):
        return default


# ── Event probability (Bayesian blend) ────────────────────────────────────────

def calculate_event_probability(stock_data, options_flow,
                                 news_sentiment_score, prediction_market_prob):
    """Bayesian-weighted probability (0-100) of continued bullish momentum.

    Weights:  options 35% | prediction markets 30% | news sentiment 20% | momentum 15%
    Returns {probability, components{...}}. Always JSON-safe; never divides by zero.
    """
    pc_ratio          = _num(options_flow["ratio"], 1.0) if options_flow else 1.0
    options_signal    = max(0.0, min(1.0, 1.0 - (pc_ratio / 2.0)))
    prediction_signal = max(0.0, min(1.0, _num(prediction_market_prob, 0.5)))
    sentiment_signal  = max(0.0, min(1.0, (_num(news_sentiment_score, 0.0) + 1.0) / 2.0))

    high52 = stock_data.get("week_52_high")
    low52  = stock_data.get("week_52_low")
    price  = _num(stock_data.get("price"), 0.0)
    if high52 is not None and low52 is not None and high52 > low52:
        momentum_signal = max(0.0, min(1.0, (price - low52) / (high52 - low52)))
    else:
        momentum_signal = 0.5

    probability = (
        options_signal      * 0.35
        + prediction_signal * 0.30
        + sentiment_signal  * 0.20
        + momentum_signal   * 0.15
    ) * 100.0

    return {
        "probability": round(_num(probability, 50.0), 1),
        "components": {
            "options_signal":    round(options_signal,    4),
            "prediction_signal": round(prediction_signal, 4),
            "sentiment_signal":  round(sentiment_signal,  4),
            "momentum_signal":   round(momentum_signal,   4),
        },
    }


# ── Price targets ──────────────────────────────────────────────────────────────

# A 30-day window is ~21 trading days; daily vol scales by its square root.
_TRADING_DAYS_PER_MONTH = 21
# Sanity rails on the monthly move, as a fraction of price. The floor keeps
# mega-caps from showing a nonsense ±0% band; the ceiling stops a single gap day
# from projecting a ±40% range.
_MIN_MONTHLY_MOVE = 0.04
_MAX_MONTHLY_MOVE = 0.25


def calculate_price_targets(stock_data, prices=None):
    """Approximate 30-day bull/bear targets from realized volatility.

    *prices* is a list of recent closes (from get_price_history). When enough
    history is available the move is derived from the stock's actual daily
    volatility; otherwise it falls back to a conservative flat estimate.

    Using a single day's move as the volatility input — as an earlier version
    did — projects an earnings gap across the whole month: AAPL's -7.35% day
    became a ±40% monthly band. Realized vol over the full window absorbs that.
    """
    price = _num(stock_data.get("price"), 0.0)
    if price <= 0:
        return {"bull": 0.0, "bear": 0.0, "implied_move": 0.0}

    closes = [c for c in (prices or []) if isinstance(c, (int, float)) and c > 0]

    daily_vol = None
    if len(closes) >= 10:
        returns = [
            (closes[i] - closes[i - 1]) / closes[i - 1]
            for i in range(1, len(closes))
            if closes[i - 1] > 0
        ]
        if len(returns) >= 5:
            mean_return = sum(returns) / len(returns)
            variance    = sum((r - mean_return) ** 2 for r in returns) / (len(returns) - 1)
            daily_vol   = math.sqrt(variance)

    if daily_vol is None or daily_vol <= 0:
        # No usable history — assume a mid-range ~1.5% daily move.
        daily_vol = 0.015

    monthly_move = daily_vol * math.sqrt(_TRADING_DAYS_PER_MONTH)
    monthly_move = max(_MIN_MONTHLY_MOVE, min(_MAX_MONTHLY_MOVE, monthly_move))
    implied_move = price * monthly_move

    return {
        "bull":         round(price + implied_move, 2),
        "bear":         round(max(0.0, price - implied_move), 2),
        "implied_move": round(implied_move, 2),
        "move_pct":     round(monthly_move * 100, 1),
    }


# ── Sentiment label ────────────────────────────────────────────────────────────

def get_sentiment_label(score):
    """Map an integer score (0-100) to a label string and hex color."""
    score = int(_num(score, 50))
    if score <= 20:
        return {"label": "EXTREME FEAR", "color": "#ff4455"}
    if score <= 40:
        return {"label": "FEAR",         "color": "#ff8c42"}
    if score <= 59:
        return {"label": "NEUTRAL",      "color": "#f5c518"}
    if score <= 79:
        return {"label": "GREED",        "color": "#7ed84b"}
    return     {"label": "EXTREME GREED", "color": "#00ff88"}


# ── Fundamental score ──────────────────────────────────────────────────────────

def calculate_fundamental_score(stock_data, prices):
    """Score a stock's fundamentals on a 0-1 scale.

    Stocks:  P/E 30% | momentum 25% | 52W range 25% | above MA-30 20%
    Crypto:  P/E skipped entirely; remaining weights rescaled to sum to 1.0
             (momentum ~36% | 52W range ~36% | above MA-30 ~28%).

    Robust to None pe_ratio / week-52 fields; never divides by zero.
    Returns (score: float, detail: dict).
    """
    is_crypto = bool(stock_data.get("is_crypto"))
    price     = _num(stock_data.get("price"), 0.0)

    # P/E score — None (or crypto) → neutral 0.5
    pe_raw   = stock_data.get("pe_ratio")
    pe_ratio = pe_raw if isinstance(pe_raw, (int, float)) else None
    if pe_ratio is None or pe_ratio <= 0:
        pe_score = 0.5
    else:
        pe_score = max(0.0, 1.0 - (pe_ratio / 40.0))

    # Momentum
    change_pct    = _num(stock_data.get("change_pct"), 0.0)
    momentum      = min(max(change_pct / 100.0, -1.0), 1.0)
    momentum_score = (momentum + 1.0) / 2.0

    # 52-week range position — guard None / equal bounds / div-by-zero
    high52 = stock_data.get("week_52_high")
    low52  = stock_data.get("week_52_low")
    if high52 is None or low52 is None or high52 == low52 or high52 <= low52:
        range_position = 0.5
    else:
        range_position = max(0.0, min(1.0, (price - low52) / (high52 - low52)))

    # Above 30-day moving average
    closes = [c for c in (prices or []) if isinstance(c, (int, float))]
    if not closes:
        closes = [price] if price else [0.0]
    ma_30    = mean(closes[-30:]) if len(closes) >= 30 else mean(closes)
    above_ma = 1.0 if (price and price > ma_30) else 0.0

    if is_crypto:
        # Drop the 0.30 P/E weight, rescale the remaining 0.70 to 1.0
        score = (
            momentum_score   * (0.25 / 0.70)
            + range_position * (0.25 / 0.70)
            + above_ma       * (0.20 / 0.70)
        )
    else:
        score = (
            pe_score           * 0.30
            + momentum_score   * 0.25
            + range_position   * 0.25
            + above_ma         * 0.20
        )

    score  = max(0.0, min(1.0, _num(score, 0.5)))
    detail = {
        "pe_score":       None if is_crypto else round(pe_score, 4),
        "momentum_score": round(momentum_score, 4),
        "range_position": round(range_position, 4),
        "above_ma":       int(above_ma),
        "ma_30":          round(_num(ma_30, 0.0), 2),
        "is_crypto":      is_crypto,
    }
    return score, detail
