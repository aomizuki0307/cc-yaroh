"""Fetch AI/Claude trend headlines from RSS/Atom feeds.

Feeds are polled in order. Returns the most-recent titles within the look-back
window, filtered by a seen-headlines cache to avoid repeating the same news on
consecutive days.

Seen-headlines cache: out/x-growth/seen_headlines.json
  Keys = ISO date strings, values = list of md5-prefix hashes.
  Entries older than 7 days are pruned on each load.
"""

from __future__ import annotations

import hashlib
import json
import logging
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SEEN_CACHE = _REPO_ROOT / "out" / "x-growth" / "seen_headlines.json"
_CACHE_TTL_DAYS = 7

_FEEDS: list[str] = [
    # Zenn — Japanese developer platform
    "https://zenn.dev/topics/claudecode/feed",
    "https://zenn.dev/topics/llm/feed",
    # Qiita — Japanese developer Q&A
    "https://qiita.com/tags/claudecode/feed",
    # TechCrunch AI
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    # Google AI Blog
    "https://blog.google/technology/ai/rss/",
]

_TIMEOUT_SEC = 10
_DEFAULT_MAX_AGE_HOURS = 48
_DEFAULT_MAX_ITEMS = 10


def fetch_headlines(
    *,
    max_age_hours: int = _DEFAULT_MAX_AGE_HOURS,
    max_items: int = _DEFAULT_MAX_ITEMS,
) -> list[str]:
    """Return recent AI/Claude headlines, deduplicated against a 7-day cache.

    Args:
        max_age_hours: Skip entries older than this many hours (0 = no filter).
        max_items: Maximum number of headlines to return.

    Returns:
        List of headline strings, possibly empty if all feeds fail.
    """
    import feedparser  # lazy import

    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    seen, seen_hashes, today = _load_seen()
    today_new: list[str] = []
    headlines: list[str] = []

    # ── RSS / Atom feeds ──────────────────────────────────────────────────────
    for url in _FEEDS:
        if len(headlines) >= max_items:
            break
        try:
            feed: Any = _parse_with_timeout(feedparser, url)
        except Exception as exc:
            logger.warning("RSS fetch error [%s]: %s", url, exc)
            continue

        if feed.bozo and not feed.entries:
            logger.warning(
                "RSS parse failed [%s]: %s",
                url,
                getattr(feed, "bozo_exception", "unknown"),
            )
            continue

        added = 0
        for entry in feed.entries:
            title = (entry.get("title") or "").strip()
            if not title:
                continue
            if max_age_hours > 0 and not _is_recent(entry, cutoff):
                continue
            h = _title_hash(title)
            if h in seen_hashes:
                logger.debug("Skipping seen headline: %s", title[:60])
                continue
            seen_hashes.add(h)
            today_new.append(h)
            headlines.append(title)
            added += 1
            if len(headlines) >= max_items:
                break

        logger.debug("RSS [%s]: %d headlines added", url, added)

    # ── Anthropic news (HTML scrape — RSS feed is broken XML) ─────────────────
    if len(headlines) < max_items:
        for title in _fetch_anthropic_news(max_items - len(headlines)):
            h = _title_hash(title)
            if h in seen_hashes:
                continue
            seen_hashes.add(h)
            today_new.append(h)
            headlines.append(title)

    # ── Persist updated cache ─────────────────────────────────────────────────
    if today_new:
        seen[today] = seen.get(today, []) + today_new
        _save_seen(seen)

    logger.info("fetch_headlines: %d total headlines fetched", len(headlines))
    return headlines


# ---------------------------------------------------------------------------
# Anthropic news HTML scraping
# ---------------------------------------------------------------------------

def _fetch_anthropic_news(max_items: int = 5) -> list[str]:
    """Scrape article titles from https://www.anthropic.com/news."""
    try:
        from bs4 import BeautifulSoup  # type: ignore[import]
        import requests

        resp = requests.get("https://www.anthropic.com/news", timeout=_TIMEOUT_SEC)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        titles: list[str] = []
        for article in soup.find_all("article"):
            for tag in ("h2", "h3", "h1"):
                heading = article.find(tag)
                if heading:
                    text = heading.get_text(strip=True)
                    if text:
                        titles.append(text)
                    break
            if len(titles) >= max_items:
                break
        logger.info("Anthropic news: %d titles scraped", len(titles))
        return titles
    except ImportError:
        logger.debug("beautifulsoup4 not installed — skipping Anthropic HTML scrape")
        return []
    except Exception as exc:
        logger.warning("Anthropic news scrape failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Seen-headlines deduplication cache
# ---------------------------------------------------------------------------

def _title_hash(title: str) -> str:
    return hashlib.md5(title.strip().lower().encode()).hexdigest()[:16]


def _load_seen() -> tuple[dict[str, list[str]], set[str], str]:
    """Load cache, prune stale entries, return (cache_dict, flat_hash_set, today_iso)."""
    today = datetime.now(timezone.utc).date().isoformat()
    cutoff_date = (
        datetime.now(timezone.utc) - timedelta(days=_CACHE_TTL_DAYS)
    ).date().isoformat()

    if not _SEEN_CACHE.exists():
        return {}, set(), today
    try:
        with _SEEN_CACHE.open(encoding="utf-8") as f:
            raw: dict[str, list[str]] = json.load(f)
        pruned = {k: v for k, v in raw.items() if k >= cutoff_date}
        flat: set[str] = {h for hashes in pruned.values() for h in hashes}
        return pruned, flat, today
    except Exception as exc:
        logger.warning("seen cache load failed: %s", exc)
        return {}, set(), today


def _save_seen(seen: dict[str, list[str]]) -> None:
    try:
        _SEEN_CACHE.parent.mkdir(parents=True, exist_ok=True)
        with _SEEN_CACHE.open("w", encoding="utf-8") as f:
            json.dump(seen, f, ensure_ascii=False, indent=2)
        logger.debug("seen cache saved: %d day(s)", len(seen))
    except Exception as exc:
        logger.warning("seen cache save failed: %s", exc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_with_timeout(feedparser_mod: Any, url: str) -> Any:
    old = socket.getdefaulttimeout()
    socket.setdefaulttimeout(_TIMEOUT_SEC)
    try:
        return feedparser_mod.parse(url)  # type: ignore[attr-defined]
    finally:
        socket.setdefaulttimeout(old)


def _is_recent(entry: object, cutoff: datetime) -> bool:
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed is None:
            parsed = entry.get(attr) if hasattr(entry, "get") else None  # type: ignore[union-attr]
        if parsed:
            try:
                pub = datetime(*parsed[:6], tzinfo=timezone.utc)
                return pub >= cutoff
            except Exception:
                continue
    return True
