# Market Pulse

> AI-powered financial terminal that fuses live market data, prediction-market odds, and Claude analysis into a single Bayesian-weighted verdict — for any stock, ETF, or crypto.

Built with Flask + Anthropic Claude + yFinance. Single-page app, no framework, ~2,000 LOC.

---

## What it does

- **Dashboard** — Type any of 147 supported symbols (stocks, ETFs, crypto). Pulls live quotes from yFinance, relevant Kalshi / Polymarket markets, the day's headlines, and runs Claude Sonnet over them for an earnings summary, a 0–100 sentiment gauge, an event-probability score (Bayesian blend of options flow, prediction-market odds, news sentiment, and price momentum), and a three-sentence analyst verdict.
- **Trade Analyzer** — Upload a chart screenshot. Claude Vision identifies the trend, pattern, support/resistance, and volume trend, then combines that technical score with fundamentals (P/E, momentum, 52-week range, MA-30) and the sentiment signal into a STRONG BUY → STRONG SELL recommendation. Optional position-sizer returns stop loss, target, risk/reward, and a suggested trim percentage.
- **Kalshi Opportunities** — Pulls 50 open prediction markets, computes the implied edge (`1 − total YES+NO cost`) and per-dollar expected value, categorizes by theme (Fed & rates, inflation, stocks, crypto, politics, tech & AI), sorts by edge, and surfaces the top 5 as gold-bordered cards.
- **Portfolio** — Add holdings (ticker, shares, cost basis), get aggregate value and P/L, sector exposure as a doughnut chart, upcoming earnings for each position, and a Claude-written 3-4 sentence posture summary.
- **AI chat panel** — Floating chat bubble over the dashboard. Asks Claude follow-up questions with the loaded ticker's full analysis JSON as context — "why is the P/E elevated?", "explain the put/call ratio", "compare to last quarter."
- **Live ticker tape** — S&P 500, NASDAQ, DOW plus any watchlist symbols, refreshing every 30 seconds.
- **Watchlist** — `localStorage`-backed, star button on the dashboard, click any saved ticker to jump straight to it.
- **Earnings alerts** — Yellow banner on the dashboard when the loaded ticker has earnings within 7 days.

---

## Stack

| Layer | Tools |
|---|---|
| Backend | Python · Flask · python-dotenv |
| AI | Anthropic Claude Sonnet · Claude Vision (multimodal) |
| Market data | yFinance |
| News | NewsAPI · Google News RSS (fallback) |
| Prediction markets | Kalshi · Polymarket (fallback) |
| Frontend | Vanilla JS SPA · Chart.js · Inter + Playfair Display |

---

## Quick start

```bash
git clone https://github.com/Anay704/market-pulse.git
cd market-pulse

# 1. Install Python deps
pip install -r requirements.txt

# 2. Set your API keys
cp .env.example .env
#   open .env and add your real ANTHROPIC_API_KEY (and optional NEWS_API_KEY)

# 3. Run
python app.py
```

Open `http://localhost:5000`.

> macOS users: if port 5000 is taken by Control Center (AirPlay Receiver), set `PORT=5001 python app.py`.

---

## API endpoints

| Method | Route | What it does |
|---|---|---|
| `POST` | `/api/analyze` | Full ticker analysis: stock + news + earnings summary + sentiment + probability + AI verdict |
| `POST` | `/api/analyze-trade` | Trade Analyzer: optional chart image (Claude Vision) + position math + final recommendation |
| `GET`  | `/api/kalshi-opportunities` | 50 live Kalshi markets categorized + sorted by edge |
| `GET`  | `/api/indices?tickers=A,B,C` | Live S&P/NASDAQ/DOW + watchlist quotes for the ticker tape |
| `GET`  | `/api/earnings/<ticker>` | Next earnings date + days until |
| `POST` | `/api/earnings` | Batch earnings for a list of tickers |
| `POST` | `/api/portfolio` | Aggregate basket: totals, P/L, sector exposure, AI posture summary |
| `POST` | `/api/chat` | Free-form Q&A with the loaded ticker's analysis as Claude context |

All responses are NaN/Infinity-scrubbed before serialization, all routes wrap a global error handler, and every AI call has a safe-default fallback so a missing API key degrades gracefully instead of breaking the UI.

---

## Architecture

```
market-pulse/
├── app.py                      # Flask entry point — routes only, no business logic
├── services/
│   ├── stock.py                # yFinance: prices, fundamentals, options flow, history
│   ├── news.py                 # NewsAPI + Google News RSS fallback
│   ├── kalshi.py               # Kalshi + Polymarket markets + arbitrage scanner
│   ├── ai.py                   # All Claude calls: earnings, verdict, sentiment, vision, narrative
│   ├── sentiment.py            # Probability engine + fundamental score + price targets
│   ├── trade_analyzer.py       # Combined score + position math + recommendations
│   ├── chat.py                 # AI chat with ticker context
│   ├── earnings.py             # Next-earnings date + watchlist calendar
│   ├── indices.py              # Index + watchlist quote strip for ticker tape
│   └── portfolio.py            # Basket aggregation + Claude posture summary
└── templates/
    └── index.html              # Single-page app with 4 views, autocomplete, chat panel
```

Routes in `app.py` are intentionally thin — every external call, math operation, and data fetch lives in its own module.

---

## Disclaimer

For educational purposes only. Not financial advice. Always do your own research.

---

*Built by [Anay Baheti](https://anaybaheti.vercel.app).*
