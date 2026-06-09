# News headline fetching via NewsAPI with Google News RSS fallback.

import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime

import requests


def _parse_iso(s):
    """Best-effort ISO-ish date parse → 'Jun 8, 2026' or original string."""
    if not s:
        return ""
    try:
        # NewsAPI uses ISO 8601 with Z, e.g. 2026-06-08T14:32:00Z
        dt = datetime.strptime(s.replace("Z", "+0000")[:19], "%Y-%m-%dT%H:%M:%S")
        return dt.strftime("%b %d, %Y")
    except Exception:
        try:
            # RFC822 used by RSS, e.g. "Sun, 08 Jun 2026 14:32:00 GMT"
            dt = datetime.strptime(s[:25], "%a, %d %b %Y %H:%M:%S")
            return dt.strftime("%b %d, %Y")
        except Exception:
            return s


def get_news_headlines(ticker):
    """Fetch up to 8 recent headlines for *ticker*.

    Tries NewsAPI first (reads NEWS_API_KEY from env), then falls back to
    Google News RSS.

    Returns (headlines: list[dict], source: str). Each dict has:
        title, description, url, source, published_at
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
                    "pageSize": 8,
                    "apiKey":   news_api_key,
                },
                timeout=8,
            )
            if r.status_code == 200:
                articles = r.json().get("articles", [])
                items = []
                for a in articles:
                    title = (a.get("title") or "").strip()
                    if not title or title == "[Removed]":
                        continue
                    items.append({
                        "title":        title,
                        "description":  (a.get("description") or "").strip(),
                        "url":          a.get("url") or "",
                        "source":       (a.get("source") or {}).get("name") or "NewsAPI",
                        "published_at": _parse_iso(a.get("publishedAt") or ""),
                    })
                if items:
                    return items[:8], "NewsAPI"
        except Exception as exc:
            print(f"NewsAPI error: {exc}")

    # ── 2. Google News RSS fallback ────────────────────────────────────────────
    try:
        r = requests.get(
            f"https://news.google.com/rss/search?q={ticker}+stock&hl=en-US",
            headers={"User-Agent": "MarketPulse/1.0"},
            timeout=8,
        )
        if r.status_code == 200:
            root  = ET.fromstring(r.content)
            items = []
            for item in root.findall(".//item")[:8]:
                t = item.find("title")
                if t is None or not t.text:
                    continue
                link = item.find("link")
                pub  = item.find("pubDate")
                src  = item.find("source")
                # Google often appends "- Source" to the title; split it out
                title  = t.text
                source = (src.text if src is not None else "Google News")
                m = re.match(r"^(.*?)\s+-\s+([^-]+)$", title)
                if m:
                    title, maybe_src = m.group(1).strip(), m.group(2).strip()
                    if src is None:
                        source = maybe_src
                items.append({
                    "title":        title,
                    "description":  "",
                    "url":          link.text if link is not None else "",
                    "source":       source,
                    "published_at": _parse_iso(pub.text if pub is not None else ""),
                })
            if items:
                return items, "Google News"
    except Exception as exc:
        print(f"Google News RSS error: {exc}")

    return [], "none"


def extract_titles(headlines):
    """Helper: pull just the title strings from rich headline dicts."""
    return [h.get("title", "") for h in (headlines or []) if h.get("title")]
