# News headline fetching via NewsAPI with Google News RSS fallback.

import os
import xml.etree.ElementTree as ET

import requests


def get_news_headlines(ticker):
    """Fetch up to 5 recent headlines for *ticker*.

    Tries NewsAPI first (reads NEWS_API_KEY from env), then falls back to
    Google News RSS.

    Returns (headlines: list[str], source: str).
    """
    news_api_key = os.environ.get("NEWS_API_KEY")

    # ── 1. NewsAPI ─────────────────────────────────────────────────────────────
    if news_api_key:
        try:
            r = requests.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q":        ticker,
                    "sortBy":   "publishedAt",
                    "language": "en",
                    "pageSize": 5,
                    "apiKey":   news_api_key,
                },
                timeout=8,
            )
            if r.status_code == 200:
                articles = r.json().get("articles", [])
                lines = []
                for a in articles:
                    title = (a.get("title") or "").strip()
                    desc  = (a.get("description") or "").strip()
                    if title and title != "[Removed]":
                        lines.append(f"{title}. {desc}" if desc else title)
                if lines:
                    return lines[:5], "NewsAPI"
        except Exception:
            pass

    # ── 2. Google News RSS fallback ────────────────────────────────────────────
    try:
        r = requests.get(
            f"https://news.google.com/rss/search?q={ticker}+stock&hl=en-US",
            headers={"User-Agent": "MarketPulse/1.0"},
            timeout=8,
        )
        if r.status_code == 200:
            root  = ET.fromstring(r.content)
            lines = []
            for item in root.findall(".//item")[:5]:
                t = item.find("title")
                if t is not None and t.text:
                    lines.append(t.text)
            if lines:
                return lines, "Google News"
    except Exception:
        pass

    return [], "none"
