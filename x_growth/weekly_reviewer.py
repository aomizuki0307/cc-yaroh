"""Weekly engagement review generator for @cc_yaroh.

Reads posted_ids.json and kpi.csv for the past 7 days, fetches tweet
metrics, and generates a Haiku-powered review report.

Output: out/x-growth/weekly-review/YYYY-MM-DD.md
Usage:  python -m x_growth.weekly_reviewer [--dry-run]
"""

from __future__ import annotations

import argparse
import csv as csv_mod
import logging
import os
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_KPI_CSV = _REPO_ROOT / "docs" / "x-growth" / "kpi.csv"
_OUT_DIR = _REPO_ROOT / "out" / "x-growth" / "weekly-review"
_MODEL = "claude-haiku-4-5-20251001"


# ---------------------------------------------------------------------------
# Data collection
# ---------------------------------------------------------------------------

def _engagement_score(t: dict[str, Any]) -> int:
    pub = t.get("public_metrics", {})
    return pub.get("like_count", 0) + pub.get("reply_count", 0) * 2 + pub.get("retweet_count", 0)


def _kpi_follows_delta_since(since: date) -> int:
    """Sum of follows_delta from kpi.csv for dates >= since."""
    if not _KPI_CSV.exists():
        return 0
    total = 0
    with _KPI_CSV.open(encoding="utf-8", newline="") as f:
        for row in csv_mod.DictReader(f):
            if row.get("date", "") >= since.isoformat():
                try:
                    total += int(row.get("follows_delta", 0))
                except ValueError:
                    pass
    return total


def collect_review_data() -> dict[str, Any]:
    """Gather tweet metrics and KPI data for the past 7 days."""
    from x_growth.kpi_updater import fetch_tweet_details, load_posted_records_since

    since = date.today() - timedelta(days=7)
    records = load_posted_records_since(since)

    # Group IDs by pillar
    by_pillar: dict[str, list[str]] = defaultdict(list)
    all_ids: list[str] = []
    for r in records:
        by_pillar[r.get("pillar", "unknown")].append(r["id"])
        all_ids.append(r["id"])

    # Fetch per-tweet details
    tweet_map: dict[str, dict[str, Any]] = {
        t["id"]: t for t in fetch_tweet_details(all_ids)
    }

    # Pillar-level stats
    pillar_stats: dict[str, dict[str, Any]] = {}
    for pillar, ids in by_pillar.items():
        tweets = [tweet_map[tid] for tid in ids if tid in tweet_map]
        count = len(tweets) or 1  # avoid division by zero
        pub_list = [t.get("public_metrics", {}) for t in tweets]
        pillar_stats[pillar] = {
            "posts": len(ids),
            "avg_likes": round(sum(m.get("like_count", 0) for m in pub_list) / count, 1),
            "avg_replies": round(sum(m.get("reply_count", 0) for m in pub_list) / count, 1),
            "avg_reposts": round(sum(m.get("retweet_count", 0) for m in pub_list) / count, 1),
        }

    # Top 5 by engagement
    top5 = sorted(tweet_map.values(), key=_engagement_score, reverse=True)[:5]
    id_to_pillar = {tid: pillar for pillar, ids in by_pillar.items() for tid in ids}

    total_follows_delta = _kpi_follows_delta_since(since)

    return {
        "week_start": since.isoformat(),
        "week_end": date.today().isoformat(),
        "total_posts": len(all_ids),
        "total_follows_delta": total_follows_delta,
        "pillar_stats": pillar_stats,
        "top5": [
            {
                "id": t.get("id", ""),
                "text_preview": t.get("text", "")[:100],
                "likes": t.get("public_metrics", {}).get("like_count", 0),
                "replies": t.get("public_metrics", {}).get("reply_count", 0),
                "reposts": t.get("public_metrics", {}).get("retweet_count", 0),
                "pillar": id_to_pillar.get(t.get("id", ""), ""),
            }
            for t in top5
        ],
    }


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_review(data: dict[str, Any]) -> str:
    """Generate weekly review report using Haiku."""
    import anthropic

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set — using fallback report")
        return _format_fallback_review(data)

    system = """あなたは SNS 成長分析のエキスパートです。
@cc_yaroh（CCたろー）の週次エンゲージメントレポートを日本語で生成してください。

レポートの構成（必須）:
1. 今週のサマリー（フォロワー増減・投稿数）
2. エンゲージメントトップ5投稿（入力データの数字のみ使用）
3. ピラー別分析（続けるべき・改善すべき・停止すべき）
4. 来週の提案アクション（具体的に2〜3つ）

★ 数字・パーセンテージは入力データに明示された値のみ使用。推測・補完禁止。
出力形式: Markdown 形式のレポート本文のみ。前置き不要。"""

    top5_lines = "\n".join(
        f"- [{t['pillar']}] {t['text_preview'][:60]} | likes={t['likes']} replies={t['replies']} reposts={t['reposts']}"
        for t in data.get("top5", [])
    ) or "（データなし）"

    pillar_lines = "\n".join(
        f"- {p}: {s['posts']}本 avg_likes={s['avg_likes']} avg_replies={s['avg_replies']}"
        for p, s in data.get("pillar_stats", {}).items()
    ) or "（データなし）"

    user = (
        f"集計期間: {data['week_start']} ～ {data['week_end']}\n"
        f"総投稿数: {data['total_posts']}\n"
        f"フォロワー増減: {data['total_follows_delta']:+d}\n\n"
        f"エンゲージメントトップ5:\n{top5_lines}\n\n"
        f"ピラー別統計:\n{pillar_lines}"
    )

    try:
        client = anthropic.Anthropic(api_key=api_key, max_retries=3)
        message = client.messages.create(
            model=_MODEL, max_tokens=1024, system=system,
            messages=[{"role": "user", "content": user}],
        )
        return message.content[0].text.strip()  # type: ignore[union-attr]
    except Exception as exc:
        logger.warning("Haiku call failed: %s", exc)
        return _format_fallback_review(data)


def _format_fallback_review(data: dict[str, Any]) -> str:
    lines = [
        f"# 週次レビュー {data['week_start']} ～ {data['week_end']}",
        "",
        "## サマリー",
        f"- 総投稿数: {data['total_posts']}",
        f"- フォロワー増減: {data['total_follows_delta']:+d}",
        "",
        "## ピラー別統計",
    ]
    for p, s in data.get("pillar_stats", {}).items():
        lines.append(f"- {p}: {s['posts']}本 (avg likes={s['avg_likes']} replies={s['avg_replies']})")
    lines += ["", "## トップ5投稿"]
    for t in data.get("top5", []):
        lines.append(f"- [{t['pillar']}] likes={t['likes']} replies={t['replies']}: {t['text_preview'][:60]}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Save + CLI
# ---------------------------------------------------------------------------

def _save_report(report: str) -> Path:
    today = date.today().isoformat()
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = _OUT_DIR / f"{today}.md"
    path.write_text(report, encoding="utf-8")
    logger.info("Weekly review saved: %s", path)
    return path


def run(*, dry_run: bool = False) -> None:
    data = collect_review_data()
    report = generate_review(data)
    if dry_run:
        logger.info("DRY-RUN: report not saved (%d chars)", len(report))
        print(report[:800])
        return
    path = _save_report(report)
    print(f"Review saved: {path}")


def main() -> None:
    from dotenv import load_dotenv

    env_path = _REPO_ROOT / ".env.x-growth"
    if env_path.exists():
        load_dotenv(env_path)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Generate weekly engagement review")
    parser.add_argument("--dry-run", action="store_true", help="Generate but do not save report")
    args = parser.parse_args()

    run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
