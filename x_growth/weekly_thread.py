"""Generate and post the weekly build-in-public summary thread.

Usage:
    python -m x_growth.weekly_thread [--live]
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import subprocess
from datetime import date, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_KPI_CSV = _REPO_ROOT / "docs" / "x-growth" / "kpi.csv"
_PROMPTS_DIR = _REPO_ROOT / "prompts" / "x_growth"
_OUT_DIR = _REPO_ROOT / "out" / "x-growth"
_MODEL = "claude-haiku-4-5-20251001"
_MAX_CHARS = 280
_PROJECT_START = date(2026, 5, 18)

JST = timezone(timedelta(hours=9))


# ---------------------------------------------------------------------------
# Data collection
# ---------------------------------------------------------------------------

def _week_number(today: date | None = None) -> int:
    d = today or date.today()
    return (d - _PROJECT_START).days // 7


def _read_kpi_delta() -> dict[str, Any]:
    """Return current and previous-week follower counts from kpi.csv."""
    if not _KPI_CSV.exists():
        return {"followers_now": 0, "followers_prev": 0, "posts_week": 0}

    import csv
    with _KPI_CSV.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        return {"followers_now": 0, "followers_prev": 0, "posts_week": 0}

    latest = rows[-1]
    prev = rows[-8] if len(rows) >= 8 else rows[0]

    def _int(row: dict, key: str) -> int:
        try:
            return int(row.get(key) or 0)
        except ValueError:
            return 0

    posts_week = sum(_int(r, "posts_7d") for r in rows[-7:]) or _int(latest, "posts_7d")
    return {
        "followers_now": _int(latest, "followers"),
        "followers_prev": _int(prev, "followers"),
        "posts_week": posts_week,
        "week_number": _week_number(),
    }


def _git_log_7d() -> list[str]:
    since = (date.today() - timedelta(days=7)).isoformat()
    try:
        result = subprocess.run(
            ["git", "log", f"--since={since}", "--pretty=format:%s", "--no-merges"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            cwd=_REPO_ROOT,
        )
        if result.returncode != 0:
            return []
        return [l.strip() for l in result.stdout.splitlines() if l.strip()][:10]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def collect_weekly() -> dict[str, Any]:
    kpi = _read_kpi_delta()
    commits = _git_log_7d()
    return {
        "week_number": kpi.get("week_number", _week_number()),
        "followers_now": kpi["followers_now"],
        "followers_prev": kpi["followers_prev"],
        "posts_week": kpi["posts_week"],
        "commits": commits,
    }


# ---------------------------------------------------------------------------
# Thread generation
# ---------------------------------------------------------------------------

def _load_prompt() -> str:
    path = _PROMPTS_DIR / "weekly_thread.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt not found: {path}")
    return path.read_text(encoding="utf-8")


def generate_thread(data: dict[str, Any]) -> list[str]:
    """Generate 5-7 tweet texts for the weekly thread via Anthropic API."""
    import anthropic

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")

    system = _load_prompt()
    commit_block = "\n".join(f"- {c}" for c in data["commits"]) if data["commits"] else "（今週コミットなし）"
    user = (
        f"週番号: W{data['week_number']}\n"
        f"フォロワー数 (週初): {data['followers_prev']}\n"
        f"フォロワー数 (現在): {data['followers_now']}\n"
        f"今週の投稿数: {data['posts_week']}\n\n"
        f"今週のコミット:\n{commit_block}"
    )

    client = anthropic.Anthropic(api_key=api_key, max_retries=5)
    message = client.messages.create(
        model=_MODEL,
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    raw = message.content[0].text.strip()  # type: ignore[union-attr]
    tweets = [t.strip() for t in re.split(r"\n---\n", raw) if t.strip()]
    return [t[:_MAX_CHARS] for t in tweets]


# ---------------------------------------------------------------------------
# Posting
# ---------------------------------------------------------------------------

def _save_drafts(tweets: list[str]) -> Path:
    today = date.today().isoformat()
    out_dir = _OUT_DIR / today
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "tweet_weekly_thread.md"
    path.write_text("\n---\n".join(tweets), encoding="utf-8")
    logger.info("Thread draft saved: %s (%d tweets)", path, len(tweets))
    return path


def post_thread(tweets: list[str]) -> list[dict[str, Any]]:
    """Post tweets as a reply chain. Returns list of post results."""
    from x_growth.publisher import post_tweet

    results: list[dict[str, Any]] = []
    prev_id: str | None = None
    for i, text in enumerate(tweets):
        result = post_tweet(text, reply_to_id=prev_id)  # type: ignore[call-arg]
        prev_id = result["id"]
        results.append(result)
        logger.info("Thread [%d/%d] posted: %s", i + 1, len(tweets), result["url"])
    return results


def run(*, dry_run: bool = True) -> dict[str, Any]:
    data = collect_weekly()
    tweets = generate_thread(data)
    draft_path = _save_drafts(tweets)

    if dry_run:
        logger.info("DRY-RUN complete: %d tweets, draft at %s", len(tweets), draft_path)
        return {"status": "dry_run", "tweet_count": len(tweets), "draft": str(draft_path), "tweets": tweets}

    results = post_thread(tweets)
    return {"status": "published", "tweet_count": len(tweets), "results": results}


def main() -> None:
    from dotenv import load_dotenv

    env_path = _REPO_ROOT / ".env.x-growth"
    if env_path.exists():
        load_dotenv(env_path)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Post weekly build-in-public thread")
    parser.add_argument("--live", action="store_true", help="Actually post (default: dry-run)")
    args = parser.parse_args()

    result = run(dry_run=not args.live)

    print(f"\nStatus: {result['status']} | Tweets: {result['tweet_count']}")
    if "tweets" in result:
        for i, t in enumerate(result["tweets"], 1):
            print(f"\n[{i}] ({len(t)} chars)\n{t}")


if __name__ == "__main__":
    main()
