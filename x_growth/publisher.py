"""Post a tweet to X via API v2 with OAuth1."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from requests.adapters import HTTPAdapter
from requests_oauthlib import OAuth1Session
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

_TWEETS_URL = "https://api.x.com/2/tweets"
_MAX_CHARS = 280
_REQUIRED_ENV = (
    "X_OAUTH_CONSUMER_KEY",
    "X_OAUTH_CONSUMER_SECRET",
    "X_OAUTH_ACCESS_TOKEN",
    "X_OAUTH_ACCESS_TOKEN_SECRET",
)
_REPO_ROOT = Path(__file__).resolve().parents[1]
_POSTED_IDS_JSON = _REPO_ROOT / "out" / "x-growth" / "posted_ids.json"
_KEEP_DAYS = 30


def _load_credentials() -> tuple[str, str, str, str]:
    missing = [k for k in _REQUIRED_ENV if not os.environ.get(k)]
    if missing:
        raise EnvironmentError(f"Missing required env vars: {', '.join(missing)}")
    return tuple(os.environ[k] for k in _REQUIRED_ENV)  # type: ignore[return-value]


def _append_posted_id(tweet_id: str, pillar: str) -> None:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=_KEEP_DAYS)).isoformat()
    records: list[dict[str, str]] = []
    if _POSTED_IDS_JSON.exists():
        try:
            records = json.loads(_POSTED_IDS_JSON.read_text(encoding="utf-8"))
        except Exception:
            records = []
    records = [r for r in records if r.get("posted_at", "") >= cutoff]
    records.append({
        "id": tweet_id,
        "pillar": pillar,
        "posted_at": datetime.now(timezone.utc).isoformat(),
    })
    _POSTED_IDS_JSON.parent.mkdir(parents=True, exist_ok=True)
    _POSTED_IDS_JSON.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


def post_tweet(
    text: str,
    *,
    reply_to_id: str | None = None,
    quote_tweet_id: str | None = None,
    pillar: str = "",
) -> dict[str, Any]:
    """Post a tweet and return result dict with id, url, status.

    Args:
        text: Tweet body (≤280 chars).
        reply_to_id: Tweet ID to reply to.
        quote_tweet_id: Tweet ID to quote.
        pillar: Content pillar label for posted_ids.json logging.
    """
    if len(text) > _MAX_CHARS:
        raise ValueError(f"Tweet too long ({len(text)} > {_MAX_CHARS})")

    ck, cs, at, ats = _load_credentials()

    session = OAuth1Session(
        client_key=ck,
        client_secret=cs,
        resource_owner_key=at,
        resource_owner_secret=ats,
    )
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 503])
    session.mount("https://", HTTPAdapter(max_retries=retry))

    payload: dict[str, Any] = {"text": text}
    if reply_to_id:
        payload["reply"] = {"in_reply_to_tweet_id": reply_to_id}
    if quote_tweet_id:
        payload["quote_tweet_id"] = quote_tweet_id

    logger.info(
        "Posting tweet (%d chars) reply_to=%s quote=%s: %.60s...",
        len(text), reply_to_id, quote_tweet_id, text,
    )
    resp = session.post(_TWEETS_URL, json=payload, timeout=30)
    if not resp.ok:
        try:
            err = resp.json()
            detail = err.get("detail") or err.get("title") or "(no detail)"
        except Exception:
            detail = "(non-JSON body)"
        logger.error("X API error %d: %s", resp.status_code, detail)
    resp.raise_for_status()
    data = resp.json().get("data", {})
    tweet_id = data.get("id", "")
    url = f"https://x.com/i/web/status/{tweet_id}"
    logger.info("Posted: id=%s url=%s", tweet_id, url)

    _append_posted_id(tweet_id, pillar)
    return {"id": tweet_id, "url": url, "status": "published"}
