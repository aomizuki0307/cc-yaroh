"""Post a tweet to X via API v2 with OAuth1."""

from __future__ import annotations

import logging
import os
from typing import Any

from requests_oauthlib import OAuth1Session

logger = logging.getLogger(__name__)

_TWEETS_URL = "https://api.x.com/2/tweets"
_MAX_CHARS = 280


def post_tweet(text: str) -> dict[str, Any]:
    """Post a tweet and return result dict with id, url, status."""
    if len(text) > _MAX_CHARS:
        raise ValueError(f"Tweet too long ({len(text)} > {_MAX_CHARS})")

    consumer_key = os.environ["X_OAUTH_CONSUMER_KEY"]
    consumer_secret = os.environ["X_OAUTH_CONSUMER_SECRET"]
    access_token = os.environ["X_OAUTH_ACCESS_TOKEN"]
    access_token_secret = os.environ["X_OAUTH_ACCESS_TOKEN_SECRET"]

    session = OAuth1Session(
        client_key=consumer_key,
        client_secret=consumer_secret,
        resource_owner_key=access_token,
        resource_owner_secret=access_token_secret,
    )

    logger.info("Posting tweet (%d chars): %s...", len(text), text[:60])
    resp = session.post(_TWEETS_URL, json={"text": text}, timeout=30)
    resp.raise_for_status()
    data = resp.json().get("data", {})
    tweet_id = data.get("id", "")
    url = f"https://x.com/i/web/status/{tweet_id}"
    logger.info("Posted: id=%s url=%s", tweet_id, url)
    return {"id": tweet_id, "url": url, "status": "published"}
