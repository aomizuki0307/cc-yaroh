"""Fetch @cc_yaroh follower count from X API and update kpi.csv.

Usage:
    python -m x_growth.kpi_updater [--dry-run]
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
from datetime import date
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_USERS_ME_URL = "https://api.x.com/2/users/me"
_REPO_ROOT = Path(__file__).resolve().parents[1]
_KPI_CSV = _REPO_ROOT / "docs" / "x-growth" / "kpi.csv"
_CSV_FIELDS = ["date", "week", "followers", "impressions_7d", "revenue_jpy", "posts_7d", "notes"]
_PROJECT_START = date(2026, 5, 18)


def fetch_follower_count() -> int:
    """Return current follower count via X API v2 GET /2/users/me."""
    from requests_oauthlib import OAuth1Session

    required = (
        "X_OAUTH_CONSUMER_KEY",
        "X_OAUTH_CONSUMER_SECRET",
        "X_OAUTH_ACCESS_TOKEN",
        "X_OAUTH_ACCESS_TOKEN_SECRET",
    )
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        raise EnvironmentError(f"Missing env vars: {', '.join(missing)}")

    session = OAuth1Session(
        client_key=os.environ["X_OAUTH_CONSUMER_KEY"],
        client_secret=os.environ["X_OAUTH_CONSUMER_SECRET"],
        resource_owner_key=os.environ["X_OAUTH_ACCESS_TOKEN"],
        resource_owner_secret=os.environ["X_OAUTH_ACCESS_TOKEN_SECRET"],
    )
    resp = session.get(_USERS_ME_URL, params={"user.fields": "public_metrics"}, timeout=15)
    resp.raise_for_status()
    metrics: dict[str, Any] = resp.json().get("data", {}).get("public_metrics", {})
    count = int(metrics.get("followers_count", 0))
    logger.info("Fetched followers_count=%d", count)
    return count


def _week_label(today: date) -> str:
    delta = (today - _PROJECT_START).days
    return f"W{delta // 7}"


def _read_rows() -> list[dict[str, str]]:
    if not _KPI_CSV.exists():
        return []
    with _KPI_CSV.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _write_rows(rows: list[dict[str, str]]) -> None:
    _KPI_CSV.parent.mkdir(parents=True, exist_ok=True)
    with _KPI_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def update_kpi(followers: int, *, dry_run: bool = False) -> None:
    """Upsert today's row in kpi.csv with the given follower count."""
    today_str = date.today().isoformat()
    rows = _read_rows()

    today_row = next((r for r in rows if r.get("date") == today_str), None)
    if today_row:
        today_row["followers"] = str(followers)
        logger.info("Updated existing row %s: followers=%d", today_str, followers)
    else:
        new_row: dict[str, str] = {
            "date": today_str,
            "week": _week_label(date.today()),
            "followers": str(followers),
            "impressions_7d": "0",
            "revenue_jpy": "0",
            "posts_7d": "0",
            "notes": "auto-updated",
        }
        rows.append(new_row)
        logger.info("Added new row %s: followers=%d", today_str, followers)

    if dry_run:
        logger.info("DRY-RUN: skipping file write (followers=%d)", followers)
        return

    _write_rows(rows)
    logger.info("kpi.csv saved.")


def main() -> None:
    from dotenv import load_dotenv

    env_path = _REPO_ROOT / ".env.x-growth"
    if env_path.exists():
        load_dotenv(env_path)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Update kpi.csv with current follower count")
    parser.add_argument("--dry-run", action="store_true", help="Fetch but do not write kpi.csv")
    args = parser.parse_args()

    followers = fetch_follower_count()
    update_kpi(followers, dry_run=args.dry_run)
    print(f"followers={followers}")


if __name__ == "__main__":
    main()
