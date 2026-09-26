# News headline fetching via NewsAPI with Google News RSS fallback.

import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

import requests

from services.symbols import get_all_symbols

# Required alongside the company name so product listings and deal posts
# ("$23 Apple Watch charger at Amazon") don't crowd out market news.
_FINANCE_CONTEXT = "(stock OR shares OR earnings OR revenue OR investors OR analysts OR sales OR profit)"

# Stripped from display names to get the name headlines actually use:
# "Apple Inc." -> "Apple", "Alphabet (Google) Class A" -> "Alphabet",
# "Berkshire Hathaway B" -> "Berkshire Hathaway", "S&P 500 ETF (SPDR)" -> "S&P 500".
_NAME_NOISE = re.compile(
    r"\s*\([^)]*\)"
    r"|\s+Class\s+[A-Z]\b"
    r"|,?\s+(Inc|Corp|Corporation|Company|Co|Holdings|plc|Ltd|Platforms|ETF)\b\.?"
    r"|\s+[A-C]$"
)

_SEARCH_NAMES = None


def short_company_name(ticker):
    """The name to search news for, or None for tickers outside the symbol list.

    Searching the bare ticker matches ordinary words and other languages —
    "KO" returns boxing knockouts — so the company name is used instead.
    """
    global _SEARCH_NAMES
    if _SEARCH_NAMES is None:
        _SEARCH_NAMES = {
            s["ticker"]: _NAME_NOISE.sub("", s["name"]).rstrip(" &")
            for s in get_all_symbols()
        }
    return _SEARCH_NAMES.get(ticker.upper()) or None


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
    subject      = short_company_name(ticker) or ticker

    # ── 1. NewsAPI ─────────────────────────────────────────────────────────────
    if news_api_key:
        try:
            r = requests.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q":        f'"{subject}" AND {_FINANCE_CONTEXT}',
                    "searchIn": "title,description",
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
        items = _google_news(f'"{subject}" stock')
        if items:
            return items, "Google News"
    except Exception as exc:
        print(f"Google News RSS error: {exc}")

    return [], "none"


def get_headlines_around(ticker, day, limit=8):
    """Headlines about *ticker* from the day before *day* through the day after.

    A move on day D is usually explained by news from the evening before, that
    morning, or the next day's "why it moved" write-ups. Uses Google News
    because its date filters reach back further than NewsAPI's free tier.
    """
    subject = short_company_name(ticker) or ticker
    keyword = "price" if ticker.upper().endswith("-USD") else "stock"
    query   = (f'"{subject}" {keyword} after:{(day - timedelta(days=1)).isoformat()} '
               f'before:{(day + timedelta(days=1)).isoformat()}')
    try:
        return _google_news(query, limit)
    except Exception as exc:
        print(f"Google News dated search error: {exc}")
        return []


def _google_news(query, limit=8):
    """Up to *limit* Google News RSS results for *query*, as headline dicts."""
    r = requests.get(
        "https://news.google.com/rss/search",
        params={"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"},
        headers={"User-Agent": "MarketPulse/1.0"},
        timeout=8,
    )
    if r.status_code != 200:
        return []

    items, seen = [], set()
    for item in ET.fromstring(r.content).findall(".//item"):
        t = item.find("title")
        if t is None or not t.text:
            continue
        link = item.find("link")
        pub  = item.find("pubDate")
        src  = item.find("source")
        # Google appends " - Source" to the title; split it out. Match the
        # <source> name exactly first, since names like "coca-colacompany.com"
        # contain hyphens the generic pattern can't split on.
        title  = t.text
        source = (src.text if src is not None and src.text else "Google News")
        if src is not None and src.text and title.endswith(" - " + src.text):
            title = title[: -len(src.text) - 3].strip()
        else:
            m = re.match(r"^(.*?)\s+-\s+([^-]+)$", title)
            if m:
                title, maybe_src = m.group(1).strip(), m.group(2).strip()
                if src is None:
                    source = maybe_src
        # Syndicated stories show up once per outlet; keep the first.
        if title.lower() in seen:
            continue
        seen.add(title.lower())
        items.append({
            "title":        title,
            "description":  "",
            "url":          link.text if link is not None else "",
            "source":       source,
            "published_at": _parse_iso(pub.text if pub is not None else ""),
        })
        if len(items) >= limit:
            break
    return items


def extract_titles(headlines):
    """Helper: pull just the title strings from rich headline dicts."""
    return [h.get("title", "") for h in (headlines or []) if h.get("title")]
