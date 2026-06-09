# Market Pulse — Flask entry point: route definitions and request orchestration only.

import math
import os

from dotenv import load_dotenv
load_dotenv(override=True)   # force .env values to win over shell env

from flask import Flask, jsonify, render_template, request

from services.ai import (analyze_chart_image, get_analyst_verdict,
                          get_company_summary, get_earnings_summary,
                          get_financial_commentary, get_red_green_flags,
                          get_risk_commentary, get_sentiment_score,
                          get_trade_narrative)
from services.chat import chat_about_ticker
from services.earnings import get_earnings_for_watchlist, get_next_earnings
from services.indices import get_indices, get_quote_strip
from services.kalshi import (get_arbitrage_opportunities,
                             get_prediction_markets)
from services.news import extract_titles, get_news_headlines
from services.portfolio import get_portfolio_narrative, summarize_portfolio
from services.research import get_research_report
from services.symbols import get_all_symbols
from services.sentiment import (calculate_event_probability,
                                 calculate_fundamental_score,
                                 calculate_price_targets)
from services.stock import get_price_history, get_stock_data
from services.trade_analyzer import (calculate_combined_score,
                                      calculate_suggested_action,
                                      get_trade_recommendation)

app = Flask(__name__)


# ── JSON safety ──────────────────────────────────────────────────────────────

def clean_for_json(obj):
    """Recursively replace NaN/Infinity floats with None so the payload is valid JSON."""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: clean_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean_for_json(i) for i in obj]
    return obj


def ok(payload, status=200):
    """jsonify a payload after scrubbing NaN/Infinity."""
    return jsonify(clean_for_json(payload)), status


# ── Global error handler ──────────────────────────────────────────────────────

@app.errorhandler(Exception)
def handle_exception(e):
    print(f"Unhandled exception: {e}")
    return jsonify({
        "error":   str(e),
        "message": "Something went wrong. Please try again.",
    }), 500


# ── Page routes (single-page app; every path serves index.html) ───────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze-trade")
def analyze_trade_page():
    # Kept for backwards-compatible deep links — the SPA handles the view switch.
    return render_template("index.html")


@app.route("/kalshi")
def kalshi_page():
    return render_template("index.html")


@app.route("/portfolio")
def portfolio_page():
    return render_template("index.html")


# ── API routes ────────────────────────────────────────────────────────────────

@app.route("/api/analyze", methods=["POST"])
def analyze():
    try:
        body   = request.get_json(silent=True) or {}
        ticker = (body.get("ticker") or "").upper().strip()
        if not ticker:
            return ok({"error": "Ticker symbol is required"}, 400)

        stock = get_stock_data(ticker)
        if "error" in stock:
            return ok(stock, 404)

        headlines, news_src = get_news_headlines(ticker)   # rich list[dict]
        titles              = extract_titles(headlines)     # strings for AI calls
        earnings            = get_earnings_summary(ticker, titles)
        markets, mkt_src    = get_prediction_markets(ticker, stock["name"])
        sentiment           = get_sentiment_score(ticker, stock, titles)

        prob = calculate_event_probability(
            stock, stock.get("options_flow"),
            sentiment.get("sentiment_score", 0.0),
            markets[0]["yes_pct"] / 100.0 if markets else 0.5,
        )
        prob["price_targets"] = calculate_price_targets(stock)

        return ok({
            "stock":         stock,
            "chart":         get_price_history(ticker),
            "earnings":      earnings,
            "kalshi":        markets,
            "kalshi_source": mkt_src,
            "news":          headlines,
            "news_source":   news_src,
            "sentiment":     sentiment,
            "probability":   prob,
            "verdict":       get_analyst_verdict(stock, earnings, markets),
        })
    except Exception as exc:
        print(f"/api/analyze error: {exc}")
        return ok({"error": str(exc), "message": "Failed to analyze ticker."}, 500)


@app.route("/api/analyze-trade", methods=["POST"])
def analyze_trade():
    try:
        ticker = (request.form.get("ticker") or "").upper().strip()
        if not ticker:
            return ok({"error": "Ticker symbol is required"}, 400)

        owns_stock = request.form.get("owns_stock") == "true"
        try:
            shares    = float(request.form.get("shares")    or 0)
            avg_price = float(request.form.get("avg_price") or 0)
        except (ValueError, TypeError):
            shares, avg_price = 0.0, 0.0
        image_file = request.files.get("image")

        stock = get_stock_data(ticker)
        if "error" in stock:
            return ok(stock, 404)

        price_history           = get_price_history(ticker, days=40)
        fund_score, fund_detail = calculate_fundamental_score(stock, price_history.get("prices", []))
        headlines, _            = get_news_headlines(ticker)
        titles                  = extract_titles(headlines)
        markets, _              = get_prediction_markets(ticker, stock["name"])
        sentiment               = get_sentiment_score(ticker, stock, titles)

        technical = None
        if image_file and image_file.filename:
            technical = analyze_chart_image(
                image_file.read(), image_file.content_type or "image/jpeg", ticker
            )

        pred_prob   = markets[0]["yes_pct"] / 100.0 if markets else 0.5
        prob_data   = calculate_event_probability(
            stock, stock.get("options_flow"), sentiment.get("sentiment_score", 0.0), pred_prob
        )
        sent_signal = prob_data["probability"] / 100.0
        final_score = calculate_combined_score(
            technical.get("technical_score") if technical else None,
            fund_score, sent_signal, bool(technical),
        )
        rec, rec_color = get_trade_recommendation(final_score)
        position = (
            calculate_suggested_action(shares, avg_price, stock["price"], final_score)
            if (owns_stock and shares > 0 and avg_price > 0) else None
        )

        return ok({
            "stock":              stock,
            "fundamental_score":  round(fund_score, 4),
            "fundamental_detail": fund_detail,
            "technical":          technical,
            "sentiment":          sentiment,
            "final_score":        round(final_score, 4),
            "recommendation":     rec,
            "rec_color":          rec_color,
            "score_components": {
                "technical":   round(technical.get("technical_score", 0), 4) if technical else None,
                "fundamental": round(fund_score, 4),
                "sentiment":   round(sent_signal, 4),
            },
            "position":  position,
            "narrative": get_trade_narrative(
                ticker, stock, fund_score, sent_signal,
                final_score, rec, technical, position
            ),
        })
    except Exception as exc:
        print(f"/api/analyze-trade error: {exc}")
        return ok({"error": str(exc), "message": "Failed to analyze trade."}, 500)


@app.route("/api/kalshi-opportunities", methods=["GET"])
def kalshi_opportunities():
    try:
        return ok(get_arbitrage_opportunities())
    except Exception as exc:
        print(f"/api/kalshi-opportunities error: {exc}")
        return ok({"error": str(exc), "message": "Failed to load Kalshi opportunities."}, 500)


@app.route("/api/indices", methods=["GET"])
def indices_route():
    try:
        raw = request.args.get("tickers", "")
        tickers = [t.strip() for t in raw.split(",") if t.strip()] if raw else []
        return ok({
            "indices": get_indices(),
            "quotes":  get_quote_strip(tickers),
        })
    except Exception as exc:
        print(f"/api/indices error: {exc}")
        return ok({"indices": [], "quotes": []})


@app.route("/api/chat", methods=["POST"])
def chat_route():
    try:
        body = request.get_json(silent=True) or {}
        question = (body.get("question") or "").strip()
        context  = body.get("context") or {}
        if not question:
            return ok({"error": "Question is required"}, 400)
        return ok({"answer": chat_about_ticker(question, context)})
    except Exception as exc:
        print(f"/api/chat error: {exc}")
        return ok({"answer": f"Chat unavailable: {exc}"}, 500)


@app.route("/api/earnings", methods=["POST"])
def earnings_route():
    try:
        body = request.get_json(silent=True) or {}
        tickers = body.get("tickers") or []
        return ok({"earnings": get_earnings_for_watchlist(tickers)})
    except Exception as exc:
        print(f"/api/earnings error: {exc}")
        return ok({"earnings": []})


@app.route("/api/earnings/<ticker>", methods=["GET"])
def earnings_single_route(ticker):
    try:
        return ok({"earnings": get_next_earnings(ticker)})
    except Exception as exc:
        print(f"/api/earnings/{ticker} error: {exc}")
        return ok({"earnings": None})


@app.route("/api/symbols", methods=["GET"])
def symbols_route():
    try:
        return ok({"symbols": get_all_symbols()})
    except Exception as exc:
        print(f"/api/symbols error: {exc}")
        return ok({"symbols": []})


@app.route("/api/research/<ticker>", methods=["GET"])
def research_route(ticker):
    """Full research report for *ticker*: 6 data sections + 4 AI commentaries."""
    try:
        ticker = (ticker or "").upper().strip()
        if not ticker:
            return ok({"error": "Ticker symbol is required"}, 400)

        report = get_research_report(ticker)

        # Layer AI commentary on top (each call is independent + safe-defaulted)
        report["company_summary"]      = get_company_summary(ticker,
                                            report["company_overview"].get("summary"))
        report["financial_commentary"] = get_financial_commentary(ticker,
                                            report["quarterly_financials"])
        report["risk_commentary"]      = get_risk_commentary(ticker,
                                            report["risk_metrics"])
        report["flags"]                = get_red_green_flags(ticker, report)

        return ok(report)
    except Exception as exc:
        print(f"/api/research/{ticker} error: {exc}")
        return ok({"error": str(exc), "message": "Failed to load research report."}, 500)


@app.route("/api/portfolio", methods=["POST"])
def portfolio_route():
    try:
        body = request.get_json(silent=True) or {}
        holdings = body.get("holdings") or []
        summary = summarize_portfolio(holdings)
        summary["narrative"] = get_portfolio_narrative(summary)
        return ok(summary)
    except Exception as exc:
        print(f"/api/portfolio error: {exc}")
        return ok({"error": str(exc), "message": "Failed to compute portfolio."}, 500)


if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
