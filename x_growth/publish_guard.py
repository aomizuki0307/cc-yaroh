"""X publish guard — blocks tweets with secrets, inflammatory, or spam content."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|token|password|passwd|auth)[=:]\s*\S{8,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9\-._~+/]+=*"),
    re.compile(r"ghp_[A-Za-z0-9]{36}"),
    re.compile(r"sk-[A-Za-z0-9]{48}"),
    re.compile(r"\d{10,}-[A-Za-z0-9]{20,}"),      # X OAuth access token
    re.compile(r"sk-ant-[A-Za-z0-9\-_]{20,}"),    # Anthropic API key
]

_INFLAMMATORY_PATTERNS = [
    re.compile(r"(?i)\b(hate|kill|die|racist|suicide|炎上|死ね|殺|差別|自殺)\b"),
]

_SALESY_PATTERNS = [
    re.compile(r"(?i)\b(buy now|act fast|limited offer|dm me|follow for follow|f4f|l4l)\b"),
    re.compile(r"(?i)(今すぐ購入|今だけ|相互フォロー|フォロバ)"),
]

_MIN_LENGTH = 10
_MAX_LENGTH = 280


@dataclass(frozen=True)
class GuardResult:
    allowed: bool
    reason: str


def check_tweet(text: str) -> GuardResult:
    if len(text) < _MIN_LENGTH:
        return GuardResult(allowed=False, reason=f"too_short ({len(text)} chars)")
    if len(text) > _MAX_LENGTH:
        return GuardResult(allowed=False, reason=f"too_long ({len(text)} chars)")
    for p in _SECRET_PATTERNS:
        if p.search(text):
            return GuardResult(allowed=False, reason="secret_pattern_detected")
    for p in _INFLAMMATORY_PATTERNS:
        if p.search(text):
            return GuardResult(allowed=False, reason="inflammatory_content")
    for p in _SALESY_PATTERNS:
        if p.search(text):
            return GuardResult(allowed=False, reason="salesy_spam")
    return GuardResult(allowed=True, reason="ok")
