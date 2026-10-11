"""Retention scheduling behind a small protocol (spec §6.5).

Default implementation wraps py-fsrs with day-level scheduling (no intra-day learning
steps, no fuzzing, so replaying the evidence log is deterministic). A fallback
interval scheduler keeps the core working if ``fsrs`` cannot be imported.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Protocol

from .paths import iso, parse_ts

AGAIN, HARD, GOOD, EASY = 1, 2, 3, 4
RATING_NAMES = {AGAIN: "again", HARD: "hard", GOOD: "good", EASY: "easy"}

def rating_for(score: float, hinted: bool = False, confidence: int | None = None) -> int:
    """Map a graded attempt to an FSRS rating (spec §6.5 table)."""
    if score < 0.5:
        return AGAIN
    if hinted or score < 0.8:
        return HARD
    if score >= 0.95 and (confidence is None or confidence >= 4):
        return EASY
    return GOOD


class RetentionScheduler(Protocol):
    def new_card(self, now: datetime, first_due: datetime) -> str: ...
    def review(self, card_json: str, rating: int, now: datetime) -> str: ...
    def due(self, card_json: str) -> datetime: ...
    def interval_days(self, card_json: str) -> float: ...
    def shift_due(self, card_json: str, delta: timedelta) -> str: ...


class FsrsScheduler:
    def __init__(self, desired_retention: float = 0.9):
        from fsrs import Card, Rating, Scheduler  # imported lazily for the fallback path

        self._Card, self._Rating = Card, Rating
        self._s = Scheduler(desired_retention=desired_retention, learning_steps=(),
                            relearning_steps=(), enable_fuzzing=False)

    def new_card(self, now: datetime, first_due: datetime) -> str:
        card, _ = self._s.review_card(self._Card(card_id=1), self._Rating.Good, now)
        card.due = first_due
        return card.to_json()

    def review(self, card_json: str, rating: int, now: datetime) -> str:
        card = self._Card.from_json(card_json)
        card, _ = self._s.review_card(card, self._Rating(rating), now)
        return card.to_json()

    def due(self, card_json: str) -> datetime:
        return parse_ts(json.loads(card_json)["due"])

    def interval_days(self, card_json: str) -> float:
        d = json.loads(card_json)
        if not d.get("last_review"):
            return 1.0
        return max((parse_ts(d["due"]) - parse_ts(d["last_review"])).total_seconds() / 86400, 0.0)

    def shift_due(self, card_json: str, delta: timedelta) -> str:
        d = json.loads(card_json)
        d["due"] = iso(parse_ts(d["due"]) + delta)
        return json.dumps(d)


class FallbackScheduler:
    """Expanding-interval scheduler: x2.5 on success, reset to 1 day on failure."""

    def new_card(self, now: datetime, first_due: datetime) -> str:
        return json.dumps({"due": iso(first_due), "last_review": iso(now), "interval": 1.0})

    def review(self, card_json: str, rating: int, now: datetime) -> str:
        d = json.loads(card_json)
        factor = {AGAIN: 0.0, HARD: 1.2, GOOD: 2.5, EASY: 3.5}[rating]
        interval = 1.0 if rating == AGAIN else max(1.0, d.get("interval", 1.0) * factor)
        return json.dumps({"due": iso(now + timedelta(days=interval)), "last_review": iso(now),
                           "interval": interval})

    def due(self, card_json: str) -> datetime:
        return parse_ts(json.loads(card_json)["due"])

    def interval_days(self, card_json: str) -> float:
        return float(json.loads(card_json).get("interval", 1.0))

    def shift_due(self, card_json: str, delta: timedelta) -> str:
        d = json.loads(card_json)
        d["due"] = iso(parse_ts(d["due"]) + delta)
        return json.dumps(d)


def make_scheduler(desired_retention: float = 0.9) -> RetentionScheduler:
    try:
        return FsrsScheduler(desired_retention)
    except ImportError:  # pragma: no cover
        return FallbackScheduler()
