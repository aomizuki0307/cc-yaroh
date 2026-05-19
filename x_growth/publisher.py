"""Post a tweet to X via API v2 with OAuth1."""

from __future__ import annotations

import logging
import os
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


def _load_credentials() -> tuple[str, str, str, str]:
    missing = [k for k in _REQUIRED_ENV if not os.environ.get(k)]
    if missing:
        raise EnvironmentError(f"Missing required env vars: {', '.join(missing)}")
    return tuple(os.environ[k] for k in _REQUIRED_ENV)  # type: ignore[return-value]


def post_tweet(text: str) -> dict[str, Any]:
    """Post a tweet and return result dict with id, url, status."""
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

    logger.info("Posting tweet (%d chars): %.60s...", len(text), text)
    resp = session.post(_TWEETS_URL, json={"text": text}, timeout=30)
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
    return {"id": tweet_id, "url": url, "status": "published"}
