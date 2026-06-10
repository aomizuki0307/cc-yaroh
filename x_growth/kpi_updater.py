"""Fetch @cc_yaroh follower count and tweet metrics; update kpi.csv.

Runs once daily. Reads posted_ids.json to find today's tweets, fetches
their public_metrics + organic_metrics, then appends/updates today's row.

Usage:
    python -m x_growth.kpi_updater [--dry-run]
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_USERS_ME_URL = "https://api.x.com/2/users/me"
_TWEETS_URL = "https://api.x.com/2/tweets"
_REPO_ROOT = Path(__file__).resolve().parents[1]
_KPI_CSV = _REPO_ROOT / "docs" / "x-growth" / "kpi.csv"
_POSTED_IDS_JSON = _REPO_ROOT / "out" / "x-growth" / "posted_ids.json"
_PROJECT_START = date(2026, 5, 18)
JST = timezone(timedelta(hours=9))

_CSV_FIELDS = [
    "date", "week", "followers", "follows_delta",
    "impressions_7d",       # legacy column — kept for continuity
    "impressions_sum", "profile_clicks_sum",
    "replies_sum", "reposts_sum", "likes_sum",
    "revenue_jpy", "posts_7d", "notes",
]
_NEW_FIELDS = frozenset({
    "follows_delta", "impressions_sum", "profile_clicks_sum",
    "replies_sum", "reposts_sum", "likes_sum",
})


# ---------------------------------------------------------------------------
# OAuth helper
# ---------------------------------------------------------------------------

def _oauth_session():
    from requests_oauthlib import OAuth1Session
    required = (
        "X_OAUTH_CONSUMER_KEY", "X_OAUTH_CONSUMER_SECRET",
        "X_OAUTH_ACCESS_TOKEN", "X_OAUTH_ACCESS_TOKEN_SECRET",
    )
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        raise EnvironmentError(f"Missing env vars: {', '.join(missing)}")
    return OAuth1Session(
        client_key=os.environ["X_OAUTH_CONSUMER_KEY"],
        client_secret=os.environ["X_OAUTH_CONSUMER_SECRET"],
        resource_owner_key=os.environ["X_OAUTH_ACCESS_TOKEN"],
        resource_owner_secret=os.environ["X_OAUTH_ACCESS_TOKEN_SECRET"],
    )


# ---------------------------------------------------------------------------
# X API fetchers
# ---------------------------------------------------------------------------

def fetch_follower_count() -> int:
    """Return current follower count via GET /2/users/me."""
    session = _oauth_session()
    resp = session.get(_USERS_ME_URL, params={"user.fields": "public_metrics"}, timeout=15)
    resp.raise_for_status()
    metrics: dict[str, Any] = resp.json().get("data", {}).get("public_metrics", {})
    count = int(metrics.get("followers_count", 0))
    logger.info("Fetched followers_count=%d", count)
    return count


def _fetch_tweets_raw(tweet_ids: list[str], fields: str) -> list[dict[str, Any]]:
    """Batch-fetch tweets from X API v2 in pages of 100.

    Returns the combined list of tweet objects from all pages.
    """
    if not tweet_ids:
        return []
    session = _oauth_session()
    results: list[dict[str, Any]] = []
    for i in range(0, len(tweet_ids), 100):
        batch = tweet_ids[i:i + 100]
        resp = session.get(_TWEETS_URL, params={"ids": ",".join(batch), "tweet.fields": fields}, timeout=15)
        if not resp.ok:
            logger.warning("Tweet fetch failed (status=%d, fields=%s), skipping batch", resp.status_code, fields)
            continue
        results.extend(resp.json().get("data", []))
    return results


def fetch_tweet_metrics_batch(tweet_ids: list[str]) -> dict[str, int]:
    """Aggregate public_metrics + organic_metrics for given tweet IDs.

    Returns dict: impressions_sum, profile_clicks_sum, replies_sum, reposts_sum, likes_sum
    """
    totals: dict[str, int] = {
        "impressions_sum": 0, "profile_clicks_sum": 0,
        "replies_sum": 0, "reposts_sum": 0, "likes_sum": 0,
    }
    for t in _fetch_tweets_raw(tweet_ids, "public_metrics,organic_metrics"):
        pub = t.get("public_metrics", {})
        org = t.get("organic_metrics", {})
        totals["impressions_sum"] += int(org.get("impression_count", 0))
        totals["profile_clicks_sum"] += int(org.get("user_profile_clicks", 0))
        totals["replies_sum"] += int(pub.get("reply_count", 0))
        totals["reposts_sum"] += int(pub.get("retweet_count", 0))
        totals["likes_sum"] += int(pub.get("like_count", 0))
    logger.info("Tweet metrics batch (%d IDs): %s", len(tweet_ids), totals)
    return totals


def fetch_tweet_details(tweet_ids: list[str]) -> list[dict[str, Any]]:
    """Return raw tweet data (text + public_metrics) for given IDs.

    Used by weekly_reviewer for per-tweet analysis.
    """
    results = _fetch_tweets_raw(tweet_ids, "public_metrics,organic_metrics,text,created_at")
    logger.info("Fetched details for %d/%d IDs", len(results), len(tweet_ids))
    return results


# ---------------------------------------------------------------------------
# posted_ids.json helpers
# ---------------------------------------------------------------------------

def _load_posted_records() -> list[dict[str, str]]:
    if not _POSTED_IDS_JSON.exists():
        return []
    try:
        return json.loads(_POSTED_IDS_JSON.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Cannot read posted_ids.json: %s", exc)
        return []


def _record_date(record: dict[str, str]) -> date:
    """Parse posted_at to JST date. Returns date.min on parse failure."""
    raw = record.get("posted_at", "")
    try:
        return datetime.fromisoformat(raw).astimezone(JST).date()
    except (ValueError, OverflowError):
        logger.warning("Unparseable posted_at %r in record id=%s", raw, record.get("id", "?"))
        return date.min


def load_posted_ids_for_date(target_date: date) -> list[str]:
    """Return tweet IDs posted on target_date (JST)."""
    return [r["id"] for r in _load_posted_records() if _record_date(r) == target_date]


def load_posted_records_since(since_date: date) -> list[dict[str, str]]:
    """Return all posted_ids records for dates >= since_date (JST)."""
    return [r for r in _load_posted_records() if _record_date(r) >= since_date]


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------

def _week_label(today: date) -> str:
    return f"W{(today - _PROJECT_START).days // 7}"


def _migrate_row(row: dict[str, str]) -> dict[str, str]:
    """Return a new row dict with missing new columns filled with '0'."""
    return {**{f: "0" for f in _NEW_FIELDS}, **row}


def _read_rows() -> list[dict[str, str]]:
    if not _KPI_CSV.exists():
        return []
    with _KPI_CSV.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    return [_migrate_row(r) for r in rows]


def _write_rows(rows: list[dict[str, str]]) -> None:
    _KPI_CSV.parent.mkdir(parents=True, exist_ok=True)
    with _KPI_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Core update logic
# ---------------------------------------------------------------------------

def update_kpi(
    followers: int,
    metrics: dict[str, int],
    *,
    today: date | None = None,
    posts_today: int = 0,
    dry_run: bool = False,
) -> None:
    """Upsert today's row in kpi.csv with followers + tweet metrics."""
    today = today or date.today()
    today_str = today.isoformat()
    rows = _read_rows()

    # Use the last row that isn't today to compute follows_delta (re-run safe)
    prev_row = next((r for r in reversed(rows) if r.get("date") != today_str), None)
    prev_followers = int(prev_row.get("followers", 0)) if prev_row else 0
    follows_delta = followers - prev_followers

    metric_patch = {k: str(v) for k, v in metrics.items()}

    existing = next((r for r in rows if r.get("date") == today_str), None)
    if existing:
        updated = {
            **existing,
            "followers": str(followers),
            "follows_delta": str(follows_delta),
            **metric_patch,
            **({"posts_7d": str(posts_today)} if posts_today else {}),
        }
        rows = [updated if r.get("date") == today_str else r for r in rows]
        logger.info("Updated row %s: followers=%d delta=%+d", today_str, followers, follows_delta)
    else:
        new_row: dict[str, str] = {
            "date": today_str,
            "week": _week_label(today),
            "followers": str(followers),
            "follows_delta": str(follows_delta),
            "impressions_7d": "0",
            "impressions_sum": str(metrics.get("impressions_sum", 0)),
            "profile_clicks_sum": str(metrics.get("profile_clicks_sum", 0)),
            "replies_sum": str(metrics.get("replies_sum", 0)),
            "reposts_sum": str(metrics.get("reposts_sum", 0)),
            "likes_sum": str(metrics.get("likes_sum", 0)),
            "revenue_jpy": "0",
            "posts_7d": str(posts_today),
            "notes": "auto-updated",
        }
        rows = [*rows, new_row]
        logger.info("Added row %s: followers=%d delta=%+d", today_str, followers, follows_delta)

    if dry_run:
        logger.info("DRY-RUN: followers=%d delta=%+d metrics=%s", followers, follows_delta, metrics)
        return

    _write_rows(rows)
    logger.info("kpi.csv saved.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    from dotenv import load_dotenv

    env_path = _REPO_ROOT / ".env.x-growth"
    if env_path.exists():
        load_dotenv(env_path)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Update kpi.csv with follower count and tweet metrics")
    parser.add_argument("--dry-run", action="store_true", help="Fetch but do not write kpi.csv")
    args = parser.parse_args()

    today = date.today()
    followers = fetch_follower_count()
    tweet_ids = load_posted_ids_for_date(today)
    metrics = fetch_tweet_metrics_batch(tweet_ids)
    posts_today = len(tweet_ids)

    update_kpi(followers, metrics, posts_today=posts_today, dry_run=args.dry_run)
    logger.info("Done: followers=%d posts_today=%d", followers, posts_today)


if __name__ == "__main__":
    main()
