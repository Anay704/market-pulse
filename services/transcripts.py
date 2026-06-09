# Earnings call transcripts via Alpha Vantage.
#
# Free-tier quota is 25 requests/day. Each transcript lookup costs 1 request
# (sometimes more if we have to walk back through quarters), so the research
# report is the only caller and the frontend caches per-ticker.

import os
from datetime import datetime

import requests


BASE = "https://www.alphavantage.co/query"
_MAX_TRANSCRIPT_CHARS = 18000   # cap context sent to Claude


def _key():
    return (os.environ.get("ALPHAVANTAGE_API_KEY")
            or os.environ.get("ALPHA_VANTAGE_API_KEY"))


def _current_quarter():
    now = datetime.now()
    return now.year, (now.month - 1) // 3 + 1


def _walk_back(year, quarter, n=3):
    """Yield up to *n* quarter tuples walking backward in time."""
    for _ in range(n):
        yield (year, quarter)
        quarter -= 1
        if quarter < 1:
            quarter = 4
            year -= 1


def fetch_latest_transcript(ticker):
    """Return the most recent earnings-call transcript for *ticker*, or None.

    Walks back up to 3 quarters from today's calendar quarter (so worst case
    is 3 AV requests per ticker). Each segment carries {speaker, title,
    content, sentiment}; we concatenate them into a single text blob.
    """
    k = _key()
    if not k:
        return None

    y, q = _current_quarter()
    for yr, qt in _walk_back(y, q, n=3):
        q_str = f"{yr}Q{qt}"
        try:
            r = requests.get(BASE, params={
                "function": "EARNINGS_CALL_TRANSCRIPT",
                "symbol":   ticker.upper(),
                "quarter":  q_str,
                "apikey":   k,
            }, timeout=20)
            if r.status_code != 200:
                continue

            d = r.json()
            if not isinstance(d, dict):
                continue

            # Common AV rate-limit / info responses
            info = d.get("Note") or d.get("Information") or d.get("Error Message")
            if info:
                print(f"Alpha Vantage info for {ticker} {q_str}: {info[:200]}")
                return None

            segments = d.get("transcript") or []
            if not segments:
                continue

            # Build a single text blob, capped to ~18k chars for Claude
            chunks, total = [], 0
            speakers = set()
            for seg in segments:
                content = (seg.get("content") or "").strip()
                if not content:
                    continue
                speaker = (seg.get("speaker") or "?").strip()
                title   = (seg.get("title")   or "").strip()
                attr    = f"{speaker}" + (f" ({title})" if title else "")
                line    = f"{attr}: {content}"
                if total + len(line) > _MAX_TRANSCRIPT_CHARS:
                    break
                chunks.append(line)
                total += len(line)
                speakers.add(speaker)

            if not chunks:
                continue

            return {
                "symbol":     ticker.upper(),
                "quarter":    q_str,
                "year":       yr,
                "q_num":      qt,
                "speakers":   len(speakers),
                "segments":   len(segments),
                "transcript": "\n\n".join(chunks),
                "char_count": total,
            }
        except Exception as exc:
            print(f"AV transcript error for {ticker} {q_str}: {exc}")
            continue

    return None
