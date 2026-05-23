"""Main runner — one posting cycle: collect → generate → guard → post (or dry-run).

Usage:
    python -m x_growth.runner --pillar trend [--live]
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_OUT_DIR = Path(__file__).resolve().parents[1] / "out" / "x-growth"


def _save_draft(tweet: str, pillar: str) -> Path:
    today = date.today().isoformat()
    out_dir = _OUT_DIR / today
    out_dir.mkdir(parents=True, exist_ok=True)
    idx = 0
    while True:
        suffix = f"_{idx}" if idx > 0 else ""
        path = out_dir / f"tweet_{pillar}{suffix}.md"
        if not path.exists():
            break
        idx += 1
    path.write_text(tweet, encoding="utf-8")
    logger.info("Draft saved: %s", path)
    return path


def run(
    *,
    dry_run: bool = True,
    pillar_override: str | None = None,
) -> dict[str, Any]:
    """Run one posting cycle."""
    from x_growth.pillar_router import resolve_pillar
    from x_growth.publish_guard import check_tweet
    from x_growth.source_collector import (
        collect_devlog,
        collect_opinion,
        collect_revenue,
        collect_trend,
        collect_utility,
    )
    from x_growth.tweet_generator import generate_tweet

    hashtags = os.getenv("X_HASHTAGS_DEFAULT", "#ClaudeCode #AI副業").strip()

    pillar = resolve_pillar(override=pillar_override)
    logger.info("Pillar: %s | dry_run: %s", pillar, dry_run)

    if pillar == "trend":
        src = collect_trend()
        source_data: dict[str, Any] = {"headlines": src.headlines}
    elif pillar == "devlog":
        src = collect_devlog()
        source_data = {"git_commits": src.git_commits, "adr_excerpts": src.adr_excerpts}
    elif pillar == "opinion":
        src = collect_opinion()
        source_data = {"headlines": src.headlines, "commits": src.commits, "template_hint": src.template_hint}
    elif pillar == "utility":
        src = collect_utility()
        source_data = {"topic_hint": src.topic_hint, "commits": src.commits}
    else:
        src = collect_revenue()
        source_data = {"kpi_lines": src.kpi_lines}

    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        if dry_run:
            items = next(iter(source_data.values()), [])
            tweet = f"[DRY-RUN] pillar={pillar} items={len(items)} {hashtags}"
            logger.warning("ANTHROPIC_API_KEY not set — placeholder tweet")
        else:
            raise ValueError("ANTHROPIC_API_KEY required for live posting")
    else:
        tweet = generate_tweet(pillar, source_data, hashtags)

    guard = check_tweet(tweet)
    if not guard.allowed:
        logger.error("Blocked by publish_guard: %s | %r", guard.reason, tweet[:80])
        return {"pillar": pillar, "tweet": tweet, "status": "blocked", "reason": guard.reason}

    draft_path = _save_draft(tweet, pillar)

    if dry_run:
        logger.info("DRY-RUN complete: %s", draft_path)
        return {"pillar": pillar, "tweet": tweet, "status": "dry_run", "draft": str(draft_path)}

    from x_growth.publisher import post_tweet
    result = post_tweet(tweet)
    return {"pillar": pillar, "tweet": tweet, **result}


def main() -> None:
    from dotenv import load_dotenv

    env_path = Path(__file__).resolve().parents[1] / ".env.x-growth"
    if env_path.exists():
        load_dotenv(env_path)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    parser = argparse.ArgumentParser(description="x_growth runner — one tweet per run")
    parser.add_argument("--pillar", choices=["trend", "devlog", "revenue", "opinion", "utility"])
    parser.add_argument("--live", action="store_true", help="Actually post (default: dry-run)")
    args = parser.parse_args()

    result = run(dry_run=not args.live, pillar_override=args.pillar)

    print("\n--- Result ---")
    for k, v in result.items():
        if k == "tweet":
            continue
        print(f"  {k}: {v}")
    tweet = result.get("tweet", "")
    print(f"  tweet ({len(tweet)} chars):\n    {tweet}")

    status = result.get("status", "")
    sys.exit(0 if status in ("published", "dry_run") else 1)


if __name__ == "__main__":
    main()
