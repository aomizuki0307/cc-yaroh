"""Collect raw content for each pillar.

trend   — placeholder (real RSS integration is W2)
devlog  — git log (last 24 h) + docs/ai/decisions.md (last 2 ADRs)
revenue — kpi.csv snapshot
"""

from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
_REPO_ROOT = Path(__file__).resolve().parents[1]
_DECISIONS_MD = _REPO_ROOT / "docs" / "ai" / "decisions.md"
_KPI_CSV = _REPO_ROOT / "docs" / "x-growth" / "kpi.csv"


@dataclass
class TrendSource:
    headlines: list[str] = field(default_factory=list)


@dataclass
class DevlogSource:
    git_commits: list[str] = field(default_factory=list)
    adr_excerpts: list[str] = field(default_factory=list)


@dataclass
class RevenueSource:
    kpi_lines: list[str] = field(default_factory=list)


def collect_trend() -> TrendSource:
    return TrendSource(headlines=["Claude Code 最新動向 (RSS統合はW2実装予定)"])


def collect_devlog() -> DevlogSource:
    commits = _git_log_24h()
    adrs = _read_adr_excerpts(max_entries=2)
    logger.info("DevlogSource: %d commits, %d ADR entries", len(commits), len(adrs))
    return DevlogSource(git_commits=commits, adr_excerpts=adrs)


def collect_revenue() -> RevenueSource:
    if not _KPI_CSV.exists():
        return RevenueSource(kpi_lines=["KPI計測開始前"])

    lines = _KPI_CSV.read_text(encoding="utf-8").splitlines()
    if not lines:
        return RevenueSource(kpi_lines=["KPI計測開始前"])
    header = lines[0]
    tail = lines[1:][-3:]
    kpi_lines = [header] + tail
    logger.info("RevenueSource: %d KPI lines", len(kpi_lines))
    return RevenueSource(kpi_lines=kpi_lines)


def _git_log_24h() -> list[str]:
    since = (datetime.now(JST) - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M")
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
            logger.warning("git log failed: %s", (result.stderr or "").strip())
            return []
        stdout = result.stdout or ""
        return [line.strip() for line in stdout.splitlines() if line.strip()][:20]
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        logger.warning("git log error: %s", exc)
        return []


def _read_adr_excerpts(max_entries: int = 2) -> list[str]:
    if not _DECISIONS_MD.exists():
        return []
    text = _DECISIONS_MD.read_text(encoding="utf-8")
    blocks = re.split(r"(?=^#{2,3} ADR-)", text, flags=re.MULTILINE)
    adr_blocks = [b.strip() for b in blocks if re.match(r"^#{2,3} ADR-", b.strip())]
    return [b[:300] for b in adr_blocks[-max_entries:]]
