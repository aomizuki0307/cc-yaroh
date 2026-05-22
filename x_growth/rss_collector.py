"""Fetch AI/Claude trend headlines from RSS/Atom feeds.

Feeds are polled in order. Returns the most-recent titles within the look-back
window. Fails silently per feed so one broken endpoint never blocks the others.
"""

from __future__ import annotations

import logging
import socket
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

_FEEDS: list[str] = [
    # Anthropic blog (Atom)
    "https://www.anthropic.com/rss.xml",
    # Zenn — Japanese developer platform
    "https://zenn.dev/topics/claudecode/feed",
    "https://zenn.dev/topics/llm/feed",
    # TechCrunch AI
    "https://techcrunch.com/category/artificial-intelligence/feed/",
]

_TIMEOUT_SEC = 10
_DEFAULT_MAX_AGE_HOURS = 48
_DEFAULT_MAX_ITEMS = 10


def fetch_headlines(
    *,
    max_age_hours: int = _DEFAULT_MAX_AGE_HOURS,
    max_items: int = _DEFAULT_MAX_ITEMS,
) -> list[str]:
    """Return recent AI/Claude headlines from RSS feeds.

    Args:
        max_age_hours: Skip entries older than this many hours. Use 0 to skip
            date filtering entirely (useful when feeds have no date info).
        max_items: Maximum number of headlines to return.

    Returns:
        List of headline strings, possibly empty if all feeds fail.
    """
    import feedparser  # lazy import — not available at test time without install

    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    headlines: list[str] = []

    for url in _FEEDS:
        if len(headlines) >= max_items:
            break
        try:
            feed: Any = _parse_with_timeout(feedparser, url)
        except Exception as exc:
            logger.warning("RSS fetch error [%s]: %s", url, exc)
            continue

        if feed.bozo and not feed.entries:
            logger.warning("RSS parse failed [%s]: %s", url, getattr(feed, "bozo_exception", "unknown"))
            continue

        added = 0
        for entry in feed.entries:
            title = (entry.get("title") or "").strip()
            if not title:
                continue
            if max_age_hours > 0 and not _is_recent(entry, cutoff):
                continue
            headlines.append(title)
            added += 1
            if len(headlines) >= max_items:
                break

        logger.debug("RSS [%s]: %d headlines added", url, added)

    logger.info("fetch_headlines: %d total headlines fetched", len(headlines))
    return headlines


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
            parsed = (entry.get(attr) if hasattr(entry, "get") else None)  # type: ignore[union-attr]
        if parsed:
            try:
                pub = datetime(*parsed[:6], tzinfo=timezone.utc)
                return pub >= cutoff
            except Exception:
                continue
    # No date info — include by default
    return True
