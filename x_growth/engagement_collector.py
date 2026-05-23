"""Search for trending Claude/AI tweets and generate reply drafts.

Searches X for recent #ClaudeCode tweets, generates a contextual reply
for each using Haiku, and saves the drafts for user review.

Output: out/x-growth/engagement/YYYY-MM-DD.md
Usage:  python -m x_growth.engagement_collector [--dry-run]
"""

from __future__ import annotations

import argparse
import logging
import os
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_OUT_DIR = _REPO_ROOT / "out" / "x-growth" / "engagement"
_SEARCH_URL = "https://api.x.com/2/tweets/search/recent"
_SEARCH_QUERY = '(#ClaudeCode OR "Claude Code") lang:ja -is:retweet -from:cc_yaroh'
_MAX_RESULTS = 10
_MIN_LIKES = 2
_MODEL = "claude-haiku-4-5-20251001"
_MAX_REPLY_CHARS = 200


def _search_tweets() -> list[dict]:
    """Fetch recent #ClaudeCode tweets from X API."""
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
    params = {
        "query": _SEARCH_QUERY,
        "max_results": _MAX_RESULTS,
        "tweet.fields": "public_metrics,created_at,author_id",
        "expansions": "author_id",
        "user.fields": "username",
    }
    resp = session.get(_SEARCH_URL, params=params, timeout=15)
    resp.raise_for_status()
    body = resp.json()

    tweets = body.get("data", [])
    users = {u["id"]: u["username"] for u in body.get("includes", {}).get("users", [])}

    results = []
    for t in tweets:
        metrics = t.get("public_metrics", {})
        likes = metrics.get("like_count", 0)
        if likes < _MIN_LIKES:
            continue
        results.append({
            "id": t["id"],
            "text": t["text"],
            "username": users.get(t.get("author_id", ""), "unknown"),
            "likes": likes,
            "replies": metrics.get("reply_count", 0),
        })

    results.sort(key=lambda x: x["likes"], reverse=True)
    logger.info("Found %d tweets (filtered from %d)", len(results), len(tweets))
    return results


def _generate_reply(tweet_text: str, username: str) -> str:
    """Generate a contextual reply as @cc_yaroh using Haiku."""
    import anthropic

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return f"（APIキー未設定 — 返信下書きは手動で作成してください）"

    system = """あなたは @cc_yaroh (CCたろー) として返信文を書きます。
キャラクター: Claude Code で副業を全自動化中のエンジニア。build in public スタイル。

返信のルール:
- 200文字以内
- 相手のツイートに共感・価値追加・経験談のどれかで応答する
- 「私も試しています」「同じ課題があり〜」など具体性を持たせる
- ハッシュタグ不要（返信なので）
- 絵文字は1つまで
- 宣伝・フォローお願い系の文言は禁止
- ★ 数字・パーセンテージは実体験から出てくる場合のみ使用

出力形式: 返信本文のみ。前置き不要。"""

    user = f"@{username} のツイート:\n\n{tweet_text}\n\n返信文を生成してください。"

    try:
        client = anthropic.Anthropic(api_key=api_key, max_retries=3)
        message = client.messages.create(
            model=_MODEL,
            max_tokens=256,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        reply = message.content[0].text.strip()  # type: ignore[union-attr]
        return reply[:_MAX_REPLY_CHARS]
    except Exception as exc:
        logger.warning("Reply generation failed: %s", exc)
        return "（生成失敗 — 手動で返信文を作成してください）"


def _format_draft(tweets: list[dict], replies: list[str]) -> str:
    today = date.today().isoformat()
    lines = [f"# エンゲージメント下書き — {today}\n"]
    lines.append("使い方: 下書きを確認し、投稿したいものを `--live` フラグ付きで手動実行してください。\n")

    for i, (tweet, reply) in enumerate(zip(tweets, replies), 1):
        url = f"https://x.com/{tweet['username']}/status/{tweet['id']}"
        lines.append(f"## 候補 {i}  (likes={tweet['likes']})")
        lines.append(f"**元ツイート**: @{tweet['username']}")
        lines.append(f"> {tweet['text'][:120]}{'...' if len(tweet['text']) > 120 else ''}")
        lines.append(f"URL: {url}\n")
        lines.append(f"**返信下書き** ({len(reply)}文字):")
        lines.append(f"> {reply}\n")
        lines.append(
            f"**投稿コマンド**: `python -m x_growth.engagement_collector --post {tweet['id']} --live`"
        )
        lines.append("---\n")

    return "\n".join(lines)


def post_reply(tweet_id: str, reply_text: str) -> dict:
    """Post a reply to a specific tweet."""
    from x_growth.publisher import post_tweet
    return post_tweet(reply_text, reply_to_id=tweet_id)  # type: ignore[call-arg]


def run(*, dry_run: bool = True, post_id: str | None = None, reply_text: str | None = None) -> None:
    if post_id and reply_text:
        if dry_run:
            logger.info("DRY-RUN: would reply to %s: %s", post_id, reply_text[:60])
            return
        result = post_reply(post_id, reply_text)
        print(f"Reply posted: {result['url']}")
        return

    tweets = _search_tweets()
    if not tweets:
        logger.warning("No qualifying tweets found")
        _save_draft("# エンゲージメント下書き\n\n対象ツイートが見つかりませんでした。")
        return

    replies = [_generate_reply(t["text"], t["username"]) for t in tweets]
    draft = _format_draft(tweets, replies)
    _save_draft(draft)


def _save_draft(content: str) -> Path:
    today = date.today().isoformat()
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = _OUT_DIR / f"{today}.md"
    path.write_text(content, encoding="utf-8")
    logger.info("Engagement draft saved: %s", path)
    print(f"Draft saved: {path}")
    return path


def main() -> None:
    from dotenv import load_dotenv

    env_path = _REPO_ROOT / ".env.x-growth"
    if env_path.exists():
        load_dotenv(env_path)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Generate engagement reply drafts")
    parser.add_argument("--dry-run", action="store_true", help="Generate drafts only (default)")
    parser.add_argument("--live", action="store_true", help="Actually post when using --post")
    parser.add_argument("--post", metavar="TWEET_ID", help="Post a reply to this tweet ID")
    parser.add_argument("--reply-text", metavar="TEXT", help="Reply text when using --post")
    args = parser.parse_args()

    run(
        dry_run=not args.live,
        post_id=args.post,
        reply_text=args.reply_text,
    )


if __name__ == "__main__":
    main()
