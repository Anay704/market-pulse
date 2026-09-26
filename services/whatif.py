# "What if I'd invested?" — how money put into a ticker would have grown over
# 1/3/5/10 years, next to the same money in the S&P 500.
#
# Everything is expressed as growth of $1, so the page can rescale to any amount
# the reader types without another request.

from concurrent.futures import ThreadPoolExecutor

from services.stock import get_daily_closes

BENCHMARK = "SPY"
PERIODS   = (("1y", 1), ("3y", 3), ("5y", 5), ("10y", 10))

# A period only counts as available when the ticker traded for nearly all of it.
# Otherwise "10 years ago" would silently mean "since the 2023 IPO".
_COVERAGE = 0.97
# The "since it listed" fallback for tickers younger than a year needs at least
# a few months of history to say anything.
_MIN_FALLBACK_ROWS = 60
_CHART_POINTS      = 160


def _years_before(d, years):
    try:
        return d.replace(year=d.year - years)
    except ValueError:   # Feb 29
        return d.replace(year=d.year - years, day=28)


def _align(dates, bench_rows):
    """Benchmark close on or before each date, or None before the benchmark starts.

    Crypto trades on weekends and the S&P 500 doesn't, so the last weekday close
    is carried forward.
    """
    out, j, last = [], 0, None
    for d in dates:
        while j < len(bench_rows) and bench_rows[j][0] <= d:
            last = bench_rows[j][1]
            j += 1
        out.append(last)
    return out


def _max_drop(values, dates):
    """Largest peak-to-trough fall in *values*, and when (if ever) it recovered."""
    peak_i, worst, worst_peak_i, worst_trough_i = 0, 0.0, 0, 0
    for i, v in enumerate(values):
        if v > values[peak_i]:
            peak_i = i
        drop = v / values[peak_i] - 1
        if drop < worst:
            worst, worst_peak_i, worst_trough_i = drop, peak_i, i

    if worst >= 0:
        return None

    peak_value = values[worst_peak_i]
    recovered  = next((dates[i] for i in range(worst_trough_i + 1, len(values))
                       if values[i] >= peak_value), None)
    return {
        "pct":            round(worst, 4),
        "peak":           round(peak_value, 4),
        "trough":         round(values[worst_trough_i], 4),
        "peak_date":      dates[worst_peak_i].isoformat(),
        "trough_date":    dates[worst_trough_i].isoformat(),
        "recovered_date": recovered.isoformat() if recovered else None,
        "trough_index":   worst_trough_i,
    }


def _chart_indices(n, keep):
    """~_CHART_POINTS evenly spaced indices, plus the ones markers must land on."""
    if n <= _CHART_POINTS:
        return list(range(n))
    step = (n - 1) / (_CHART_POINTS - 1)
    picked = {round(i * step) for i in range(_CHART_POINTS)}
    return sorted(picked | set(keep))


def _period_stats(rows, bench):
    """Growth, low point, biggest drop and benchmark comparison for one window."""
    dates  = [d for d, _ in rows]
    base   = rows[0][1]
    values = [c / base for _, c in rows]
    years  = max((dates[-1] - dates[0]).days / 365.25, 1 / 365.25)

    low_i  = min(range(len(values)), key=values.__getitem__)
    drop   = _max_drop(values, dates)

    bench_values, bench_stats = None, None
    if bench is not None and bench[0] is not None:
        bench_values = [b / bench[0] for b in bench]
        bench_drop   = _max_drop(bench_values, dates)
        bench_stats  = {
            "growth":       round(bench_values[-1], 4),
            "annualized":   round(bench_values[-1] ** (1 / years) - 1, 4),
            "max_drop_pct": bench_drop["pct"] if bench_drop else 0.0,
        }

    keep = [low_i] + ([drop["trough_index"]] if drop else [])
    idx  = _chart_indices(len(values), keep)
    if drop:
        drop.pop("trough_index")

    return {
        "available":  True,
        "start_date": dates[0].isoformat(),
        "end_date":   dates[-1].isoformat(),
        "years":      round(years, 2),
        "growth":     round(values[-1], 4),
        "annualized": round(values[-1] ** (1 / years) - 1, 4),
        "low":        {"growth": round(values[low_i], 4), "date": dates[low_i].isoformat()},
        "max_drop":   drop,
        "benchmark":  bench_stats,
        "series": {
            "dates":  [dates[i].isoformat() for i in idx],
            "values": [round(values[i], 4) for i in idx],
            "bench":  [round(bench_values[i], 4) for i in idx] if bench_values else None,
            "low_index": idx.index(low_i),
        },
    }


def get_what_if(ticker):
    """Growth of $1 invested in *ticker* over each period, vs. the S&P 500.

    Returns {ticker, benchmark, first_date, default_period, periods}. A period
    the ticker hasn't traded long enough for is {"available": False}. Tickers
    younger than a year get a single "all" period covering their whole history.
    """
    ticker    = ticker.upper()
    use_bench = ticker != BENCHMARK

    with ThreadPoolExecutor(max_workers=2) as pool:
        f_rows  = pool.submit(get_daily_closes, ticker)
        f_bench = pool.submit(get_daily_closes, BENCHMARK) if use_bench else None
        rows       = f_rows.result()
        bench_rows = f_bench.result() if f_bench else []

    result = {
        "ticker":         ticker,
        "benchmark":      BENCHMARK if use_bench and bench_rows else None,
        "first_date":     rows[0][0].isoformat() if rows else None,
        "default_period": None,
        "periods":        {},
    }
    if len(rows) < 2:
        return result

    end = rows[-1][0]
    for key, years in PERIODS:
        target = _years_before(end, years)
        start  = next((i for i, (d, _) in enumerate(rows) if d >= target), None)
        span   = (end - rows[start][0]).days if start is not None else 0
        if start is None or span < _COVERAGE * (end - target).days:
            result["periods"][key] = {"available": False}
            continue
        window = rows[start:]
        bench  = _align([d for d, _ in window], bench_rows) if result["benchmark"] else None
        result["periods"][key] = _period_stats(window, bench)

    available = [k for k, _ in PERIODS if result["periods"][k]["available"]]
    if not available and len(rows) >= _MIN_FALLBACK_ROWS:
        bench = _align([d for d, _ in rows], bench_rows) if result["benchmark"] else None
        result["periods"]["all"] = _period_stats(rows, bench)
        available = ["all"]

    if available:
        result["default_period"] = "5y" if "5y" in available else available[-1]
    return result
