"""Generate tweet text for each pillar using Anthropic API (Haiku).

Falls back to a template tweet when the API is overloaded or unavailable.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import date
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts" / "x_growth"
_MODEL = "claude-haiku-4-5-20251001"
_MAX_CHARS = 280


def _load_prompt(filename: str) -> str:
    path = _PROMPTS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Prompt not found: {path}")
    return path.read_text(encoding="utf-8")


def _call_anthropic(system: str, user: str) -> str:
    import anthropic

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")

    client = anthropic.Anthropic(api_key=api_key, max_retries=5)
    message = client.messages.create(
        model=_MODEL,
        max_tokens=512,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    block = message.content[0]
    if not hasattr(block, "text"):
        raise ValueError(f"Unexpected content block: {type(block).__name__}")
    return block.text.strip()  # type: ignore[attr-defined]


def _extract_tweet(raw: str) -> str:
    match = re.search(r"```(?:tweet)?\s*(.*?)\s*```", raw, re.DOTALL)
    if match:
        return match.group(1).strip()
    return raw.strip()


def _trim(text: str) -> str:
    if len(text) > _MAX_CHARS:
        logger.warning("Tweet too long (%d), truncating.", len(text))
        return text[:_MAX_CHARS]
    return text


def _fallback_tweet(pillar: str, source_data: dict[str, Any], hashtags: str) -> str:
    """Simple template tweet used when Anthropic API is unavailable."""
    today = date.today().strftime("%m/%d")
    tag = hashtags or "#ClaudeCode #AI副業"

    if pillar == "trend":
        return _trim(f"【{today} AIトレンド】Claude Codeで最新AI動向をキャッチアップ中。今日も自動化の精度を上げていきます。{tag}")

    if pillar == "devlog":
        commits = source_data.get("git_commits", [])
        if commits:
            subject = commits[0][:40]
            return _trim(f"【本日の開発】{subject}... Claude Codeで実装中。build in publicで全公開。{tag}")
        return _trim(f"【{today} devlog】今日もClaude Codeで自動化パイプラインを改善中。進捗は全公開。{tag}")

    # revenue
    kpi = source_data.get("kpi_lines", [])
    followers_line = next((l for l in kpi if "followers" in l.lower() or "フォロワー" in l), "")
    if followers_line:
        return _trim(f"【KPI報告】{followers_line[:60]}... 全力で1万フォロワー目指し中。{tag}")
    return _trim(f"【{today} 収益報告】Day1。まだ0円スタート。Claude Code全自動で3ヶ月1万フォロワー&月50万チャレンジ開始。{tag}")


def generate_tweet(pillar: str, source_data: dict[str, Any], hashtags: str = "") -> str:
    """Generate a tweet for the given pillar from source_data.

    Tries Anthropic API first; falls back to template on overload/API error.
    """
    if pillar == "trend":
        system = _load_prompt("tier1_trend.md")
        headlines = source_data.get("headlines", [])
        block = "\n".join(f"- {h}" for h in headlines) if headlines else "（最新AIニュース）"
        user = f"以下のニュースから1つ選び、ぱうう型ツイートを生成:\n\n{block}"
    elif pillar == "devlog":
        system = _load_prompt("tier2_devlog.md")
        commits = source_data.get("git_commits", [])
        adrs = source_data.get("adr_excerpts", [])
        commit_block = "\n".join(f"- {c}" for c in commits[:10]) if commits else "（本日コミットなし）"
        adr_block = "\n\n".join(adrs) if adrs else ""
        user = f"本日の開発ログ:\n\n{commit_block}"
        if adr_block:
            user += f"\n\n最近のADR:\n{adr_block}"
    elif pillar == "revenue":
        system = _load_prompt("tier3_revenue.md")
        kpi_lines = source_data.get("kpi_lines", [])
        kpi_block = "\n".join(kpi_lines) if kpi_lines else "KPI計測開始前"
        user = f"最新KPI:\n\n{kpi_block}"
    else:
        raise ValueError(f"Unknown pillar: {pillar!r}")

    if hashtags:
        user += f"\n\n末尾ハッシュタグ: {hashtags}"

    try:
        raw = _call_anthropic(system, user)
        return _trim(_extract_tweet(raw))
    except Exception as exc:
        logger.warning("Anthropic API unavailable (%s) — using fallback template.", exc)
        return _fallback_tweet(pillar, source_data, hashtags)
