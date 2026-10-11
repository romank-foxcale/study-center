from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from mentor_core.paths import iso
from mentor_core.service import Mentor

FIXTURES = Path(__file__).parent / "fixtures"
T0 = datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc)


@pytest.fixture
def graph_yaml() -> str:
    return (FIXTURES / "mini_la.yaml").read_text(encoding="utf-8")


class Clock:
    def __init__(self, monkeypatch: pytest.MonkeyPatch):
        self.mp = monkeypatch
        self.t = T0
        self.set(T0)

    def set(self, t: datetime) -> None:
        self.t = t
        self.mp.setenv("MENTOR_NOW", iso(t))

    def advance(self, **kw: float) -> datetime:
        self.set(self.t + timedelta(**kw))
        return self.t


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    return Clock(monkeypatch)


@pytest.fixture
def mentor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clock: Clock) -> Mentor:
    monkeypatch.delenv("MENTOR_WORKSPACE", raising=False)
    monkeypatch.delenv("CLAUDE_PLUGIN_DATA", raising=False)
    monkeypatch.setenv("MENTOR_PLUGIN_DATA", str(tmp_path / "plugin data"))
    m = Mentor(tmp_path / "My Workspace")  # space in path on purpose
    yield m
    m.close()


@pytest.fixture
def course(mentor: Mentor, graph_yaml: str) -> str:
    slug = mentor.course_create("Linear algebra for PCA")["course"]
    result = mentor.graph_propose(slug, graph_yaml)
    assert result["saved"], result
    return slug
