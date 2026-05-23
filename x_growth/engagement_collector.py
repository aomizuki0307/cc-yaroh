"""Search for trending Claude/AI tweets, generate reply drafts, and auto-post quote tweets.

Usage:
    python -m x_growth.engagement_collector            # reply drafts only (dry-run)
    python -m x_growth.engagement_collector --include-quotes --live
    python -m x_growth.engagement_collector --post TWEET_ID --reply-text TEXT --live

Output:
    out/x-growth/engagement/YYYY-MM-DD.md  — reply drafts
    out/x-growth/quotes/YYYY-MM-DD.md      — quote post log
"""

from __future__ import annotations

import argparse
import logging
import math
import os
from datetime import date, datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_OUT_DIR = _REPO_ROOT / "out" / "x-growth" / "engagement"
_QUOTES_DIR = _REPO_ROOT / "out" / "x-growth" / "quotes"
_SEARCH_URL = "https://api.x.com/2/tweets/search/recent"
_SEARCH_QUERY = '(#ClaudeCode OR "Claude Code") lang:ja -is:retweet -from:cc_yaroh'
_FETCH_MAX = 15
_MIN_LIKES_REPLY = 2
_MIN_LIKES_QUOTE = 10
_TOP_REPLY_N = 5
_TOP_QUOTE_N = 2
_MODEL = "claude-haiku-4-5-20251001"
_MAX_REPLY_CHARS = 200
_MAX_QUOTE_CHARS = 200


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _score_tweet(tweet: dict, followers: int) -> float:
    """Multi-factor engagement score for prioritizing tweets.

    Components: age + influence + opportunity + relevance (max ~4.0)
    """
    # age_score: 2h=1.0, 6h=0.6, 24h=0.2
    age_score = 0.2
    created_at = tweet.get("created_at", "")
    if created_at:
        try:
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            age_hours = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
            if age_hours <= 2:
                age_score = 1.0
            elif age_hours <= 6:
                age_score = 0.6
        except (ValueError, OverflowError) as exc:
            logger.debug("age_score parse skipped: %s", exc)

    # influence_score: log10(followers+1)/5, capped at 1.0
    influence_score = min(math.log10(followers + 1) / 5, 1.0)

    # opportunity_score: fewer replies = less competition
    replies = tweet.get("replies", 0)
    if replies <= 2:
        opportunity_score = 1.0
    elif replies <= 10:
        opportunity_score = 0.5
    else:
        opportunity_score = 0.1

    # relevance_score: keyword matches / 3, capped at 1.0
    text = tweet.get("text", "").lower()
    keywords = ["claudecode", "claude code", "cursor", "codex", "個人開発", "副業"]
    matches = sum(1 for kw in keywords if kw in text)
    relevance_score = min(matches / 3, 1.0)

    return age_score + influence_score + opportunity_score + relevance_score


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def _load_oauth_session():
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


def _fetch_tweets(min_likes: int, limit: int) -> list[dict]:
    """Fetch, filter by likes, score, and return top tweets."""
    session = _load_oauth_session()
    params = {
        "query": _SEARCH_QUERY,
        "max_results": _FETCH_MAX,
        "tweet.fields": "public_metrics,created_at,author_id",
        "expansions": "author_id",
        "user.fields": "username,public_metrics",
    }
    resp = session.get(_SEARCH_URL, params=params, timeout=15)
    resp.raise_for_status()
    body = resp.json()

    tweets = body.get("data", [])
    users_detail = {
        u["id"]: {
            "username": u.get("username", "unknown"),
            "followers": u.get("public_metrics", {}).get("followers_count", 0),
        }
        for u in body.get("includes", {}).get("users", [])
    }

    results = []
    for t in tweets:
        metrics = t.get("public_metrics", {})
        likes = metrics.get("like_count", 0)
        if likes < min_likes:
            continue
        author_id = t.get("author_id", "")
        detail = users_detail.get(author_id, {"username": "unknown", "followers": 0})
        tweet_data = {
            "id": t["id"],
            "text": t["text"],
            "username": detail["username"],
            "likes": likes,
            "replies": metrics.get("reply_count", 0),
            "created_at": t.get("created_at", ""),
        }
        tweet_data["score"] = _score_tweet(tweet_data, detail["followers"])
        results.append(tweet_data)

    results.sort(key=lambda x: x["score"], reverse=True)
    logger.info("Fetched %d tweets, %d pass filter (min_likes=%d), returning top %d",
                len(tweets), len(results), min_likes, limit)
    return results[:limit]


def _search_tweets() -> list[dict]:
    return _fetch_tweets(min_likes=_MIN_LIKES_REPLY, limit=_TOP_REPLY_N)


def _search_tweets_for_quote() -> list[dict]:
    return _fetch_tweets(min_likes=_MIN_LIKES_QUOTE, limit=_TOP_QUOTE_N)


# ---------------------------------------------------------------------------
# AI generation
# ---------------------------------------------------------------------------

def _call_haiku(system: str, user: str, max_chars: int, fallback: str) -> str:
    """Call Haiku with the given prompts; return fallback on any API error."""
    import anthropic

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return fallback

    try:
        client = anthropic.Anthropic(api_key=api_key, max_retries=3)
        message = client.messages.create(
            model=_MODEL, max_tokens=256, system=system,
            messages=[{"role": "user", "content": user}],
        )
        return message.content[0].text.strip()[:max_chars]  # type: ignore[union-attr]
    except Exception as exc:
        logger.warning("Haiku call failed: %s", exc)
        return fallback


_REPLY_SYSTEM = """あなたは @cc_yaroh (CCたろー) として返信文を書きます。
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

_QUOTE_SYSTEM = """あなたは @cc_yaroh (CCたろー) として引用ツイートのコメントを書きます。
キャラクター: Claude Code で副業を全自動化中のエンジニア。build in public スタイル。

引用コメントのルール:
- 200文字以内（ハッシュタグ含む）
- 意見・補足・反例のどれかで切り込む（文脈による）
- 冒頭15〜25字で「結論か違和感」を提示する
- 宣伝・フォローお願い禁止
- 絵文字は1つまで
- ★ 数字・固有名詞は入力データにないものは絶対に作らない
- 末尾に #ClaudeCode を1つ付ける

出力形式: コメント本文のみ。前置き不要。"""


def _generate_reply(tweet_text: str, username: str) -> str:
    user = f"@{username} のツイート:\n\n{tweet_text}\n\n返信文を生成してください。"
    return _call_haiku(_REPLY_SYSTEM, user, _MAX_REPLY_CHARS, "（生成失敗 — 手動で返信文を作成してください）")


def _generate_quote_text(tweet_text: str, username: str) -> str:
    user = f"@{username} のツイート:\n\n{tweet_text}\n\n引用コメントを生成してください。"
    return _call_haiku(_QUOTE_SYSTEM, user, _MAX_QUOTE_CHARS, "（生成失敗）")


# ---------------------------------------------------------------------------
# Formatting and saving
# ---------------------------------------------------------------------------

def _format_draft(tweets: list[dict], replies: list[str]) -> str:
    today = date.today().isoformat()
    lines = [f"# エンゲージメント下書き — {today}\n"]
    lines.append("使い方: 下書きを確認し、投稿したいものを `--live` フラグ付きで手動実行してください。\n")

    for i, (tweet, reply) in enumerate(zip(tweets, replies), 1):
        url = f"https://x.com/{tweet['username']}/status/{tweet['id']}"
        score = tweet.get("score", 0.0)
        lines.append(f"## 候補 {i}  (score={score:.2f} likes={tweet['likes']})")
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


def _format_quotes_md(quotes: list[dict], quote_texts: list[str], results: list[dict]) -> str:
    today = date.today().isoformat()
    lines = [f"# 引用ツイート投稿ログ — {today}\n"]
    for i, (quote, text, result) in enumerate(zip(quotes, quote_texts, results), 1):
        quote_url = f"https://x.com/{quote['username']}/status/{quote['id']}"
        lines.append(f"## [{i}]")
        lines.append(f"引用元: @{quote['username']} — \"{quote['text'][:80]}\"")
        lines.append(f"引用URL: {quote_url}")
        lines.append(f"投稿文: {text}")
        lines.append(f"投稿ID: {result.get('id', '')}")
        lines.append(f"投稿URL: {result.get('url', '')}")
        lines.append("")
    return "\n".join(lines)


def _save_draft(content: str) -> Path:
    today = date.today().isoformat()
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = _OUT_DIR / f"{today}.md"
    path.write_text(content, encoding="utf-8")
    logger.info("Engagement draft saved: %s", path)
    print(f"Draft saved: {path}")
    return path


def _save_quotes_draft(quotes: list[dict], quote_texts: list[str]) -> None:
    today = date.today().isoformat()
    _QUOTES_DIR.mkdir(parents=True, exist_ok=True)
    path = _QUOTES_DIR / f"{today}.md"
    lines = [f"# 引用ツイート下書き — {today}\n"]
    for i, (quote, text) in enumerate(zip(quotes, quote_texts), 1):
        quote_url = f"https://x.com/{quote['username']}/status/{quote['id']}"
        lines.append(f"## [{i}] DRY-RUN")
        lines.append(f"引用元: @{quote['username']} — \"{quote['text'][:80]}\"")
        lines.append(f"引用URL: {quote_url}")
        lines.append(f"投稿予定文: {text}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Quote draft saved: %s", path)
    print(f"Quote draft saved: {path}")


def _save_quotes_log(quotes: list[dict], quote_texts: list[str], results: list[dict]) -> None:
    today = date.today().isoformat()
    _QUOTES_DIR.mkdir(parents=True, exist_ok=True)
    path = _QUOTES_DIR / f"{today}.md"
    content = _format_quotes_md(quotes, quote_texts, results)
    path.write_text(content, encoding="utf-8")
    logger.info("Quote log saved: %s", path)
    print(f"Quote log saved: {path}")


# ---------------------------------------------------------------------------
# Core actions
# ---------------------------------------------------------------------------

def post_reply(tweet_id: str, reply_text: str) -> dict:
    from x_growth.publisher import post_tweet
    return post_tweet(reply_text, reply_to_id=tweet_id, pillar="reply")


def _post_quotes(quotes: list[dict], quote_texts: list[str]) -> None:
    from x_growth.publisher import post_tweet

    results = []
    for quote, text in zip(quotes, quote_texts):
        try:
            result = post_tweet(text, quote_tweet_id=quote["id"], pillar="quote")
            results.append(result)
            logger.info("Quote posted: %s", result.get("url", ""))
        except Exception as exc:
            logger.error("Quote post failed: %s", exc)
            results.append({"id": "", "url": "", "status": "failed"})
    _save_quotes_log(quotes, quote_texts, results)


def run(
    *,
    dry_run: bool = True,
    post_id: str | None = None,
    reply_text: str | None = None,
    include_quotes: bool = False,
) -> None:
    if post_id and reply_text:
        if not post_id.isdigit():
            raise ValueError(f"Invalid tweet ID (expected numeric Snowflake): {post_id!r}")
        if dry_run:
            logger.info("DRY-RUN: would reply to %s: %s", post_id, reply_text[:60])
            return
        result = post_reply(post_id, reply_text)
        logger.info("Reply posted: %s", result['url'])
        return

    tweets = _search_tweets()
    if not tweets:
        logger.warning("No qualifying tweets found for reply drafts")
        _save_draft("# エンゲージメント下書き\n\n対象ツイートが見つかりませんでした。")
    else:
        replies = [_generate_reply(t["text"], t["username"]) for t in tweets]
        _save_draft(_format_draft(tweets, replies))

    if include_quotes:
        quotes = _search_tweets_for_quote()
        if not quotes:
            logger.warning("No qualifying tweets found for quotes (min_likes=%d)", _MIN_LIKES_QUOTE)
            return
        quote_texts = [_generate_quote_text(q["text"], q["username"]) for q in quotes]
        if dry_run:
            _save_quotes_draft(quotes, quote_texts)
        else:
            _post_quotes(quotes, quote_texts)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    from dotenv import load_dotenv

    env_path = _REPO_ROOT / ".env.x-growth"
    if env_path.exists():
        load_dotenv(env_path)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Generate engagement reply drafts and post quote tweets")
    parser.add_argument("--dry-run", action="store_true", help="Generate drafts only (default)")
    parser.add_argument("--live", action="store_true", help="Actually post when using --post or --include-quotes")
    parser.add_argument("--post", metavar="TWEET_ID", help="Post a reply to this tweet ID")
    parser.add_argument("--reply-text", metavar="TEXT", help="Reply text when using --post")
    parser.add_argument("--include-quotes", action="store_true", help="Also generate/post quote tweets")
    args = parser.parse_args()

    run(
        dry_run=not args.live,
        post_id=args.post,
        reply_text=args.reply_text,
        include_quotes=args.include_quotes,
    )


if __name__ == "__main__":
    main()
