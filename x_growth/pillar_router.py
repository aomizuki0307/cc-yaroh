"""Map JST hour to content pillar for @cc_yaroh daily posting schedule.

New posting slots (JST) and their pillars:
  07:40 -> utility   12:10 -> opinion
  21:10 -> devlog    22:20 -> devlog or revenue (day-dependent)

Legacy slots kept for workflow_dispatch compatibility.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Literal

logger = logging.getLogger(__name__)

Pillar = Literal["trend", "devlog", "revenue", "opinion", "utility"]

JST = timezone(timedelta(hours=9))

_SLOT_PILLAR: dict[tuple[int, int], Pillar] = {
    (7, 40): "utility",
    (12, 10): "opinion",
    (21, 10): "devlog",
    (22, 20): "devlog",
    # Legacy slots (workflow_dispatch only)
    (6, 0): "trend",
    (7, 30): "trend",
    (9, 0): "trend",
    (11, 30): "trend",
    (12, 30): "devlog",
    (17, 30): "devlog",
    (19, 0): "devlog",
    (20, 30): "devlog",
    (22, 0): "revenue",
    (23, 30): "revenue",
}

_ALL_PILLARS = ("trend", "devlog", "revenue", "opinion", "utility")


def resolve_pillar(*, override: str | None = None) -> Pillar:
    """Return the pillar for the current time slot.

    Args:
        override: Force a specific pillar. Falls back to X_PILLAR_OVERRIDE env, then time.

    Returns:
        Pillar name.
    """
    candidate = override or os.getenv("X_PILLAR_OVERRIDE", "").strip().lower()
    if candidate in _ALL_PILLARS:
        logger.info("Pillar override: %s", candidate)
        return candidate  # type: ignore[return-value]

    now = datetime.now(JST)
    now_minutes = now.hour * 60 + now.minute

    best_slot: tuple[int, int] | None = None
    best_diff = float("inf")

    for (h, m) in _SLOT_PILLAR:
        slot_minutes = h * 60 + m
        diff = abs(now_minutes - slot_minutes)
        if diff < best_diff:
            best_diff = diff
            best_slot = (h, m)

    if best_slot:
        pillar = _SLOT_PILLAR[best_slot]
        logger.info("Time-based pillar: %s (slot %02d:%02d)", pillar, best_slot[0], best_slot[1])
        return pillar

    return "trend"
