from datetime import timedelta
from pathlib import Path

import pytest

from mentor_core import learner_model
from mentor_core.service import MentorError
from test_learner import _learn
from conftest import T0


def _sig(i, kind, dims=None, valence=None, adjust=None, note=None, days=0):
    ts = (T0 + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    return {"id": i, "ts": ts, "kind": kind, "dims": dims or {}, "valence": valence,
            "adjust": adjust or {}, "weight": 1.0, "note": note, "target": None}


def test_empty_model_asks_for_evidence():
    model = learner_model.build([], T0)
    assert model["works"] == [] and model["avoid"] == []
    assert any("Little evidence" in g for g in model["guidance"])
    assert "Nothing yet" in learner_model.to_markdown(model)


def test_repeated_reactions_become_works_and_avoid():
    sigs = [_sig(i, "reaction", {"angle": "geometric"}, 1.0) for i in range(2)]
    sigs += [_sig(10 + i, "reaction", {"angle": "formal"}, -1.0) for i in range(2)]
    model = learner_model.build(sigs, T0)
    assert [e["value"] for e in model["works"]] == ["geometric"]
    assert [e["value"] for e in model["avoid"]] == ["formal"]
    assert model["guidance"][0].startswith("Lead with: geometric")


def test_one_reaction_is_not_enough():
    model = learner_model.build([_sig(1, "reaction", {"angle": "story"}, 1.0)], T0)
    assert model["works"] == [] and model["unclear"][0]["value"] == "story"


def test_liked_but_not_worked_is_reported_as_conflict():
    sigs = [_sig(i, "reaction", {"angle": "story"}, 1.0) for i in range(2)]
    sigs += [_sig(10 + i, "outcome", {"angle": "story"}, -1.0) for i in range(3)]
    model = learner_model.build(sigs, T0)
    assert model["conflicts"][0]["pattern"] == "liked_not_worked"
    assert any("hook" in g for g in model["guidance"])


def test_old_signals_decay():
    old = [_sig(i, "reaction", {"angle": "algebraic"}, 1.0, days=0) for i in range(2)]
    fresh = learner_model.build(old, T0)
    stale = learner_model.build(old, T0 + timedelta(days=720))
    assert fresh["works"] and not stale["works"]


def test_adjustments_accumulate_and_clamp():
    sigs = [_sig(i, "stated", adjust={"pace": 1}) for i in range(5)] + [_sig(9, "stated", adjust={"depth": 0})]
    model = learner_model.build(sigs, T0)
    assert model["adjust"]["pace"]["offset"] == 3
    assert model["adjust"]["pace"]["text"] == "much faster"
    assert model["adjust"]["depth"]["text"] == "as default"


def test_explore_lists_untested_angles():
    model = learner_model.build([_sig(i, "reaction", {"angle": "geometric"}, 1.0) for i in range(2)], T0)
    explored = {e["value"] for e in model["explore"]}
    assert "geometric" not in explored and "algebraic" in explored


def test_dims_validation():
    assert learner_model.validate_dims({"Domain": "Game Dev"}) == {"domain": "game-dev"}
    with pytest.raises(ValueError, match="angle must be one of"):
        learner_model.validate_dims({"angle": "vibes"})
    with pytest.raises(ValueError, match="unknown dimension"):
        learner_model.validate_dims({"learning_style": "visual"})
    with pytest.raises(ValueError):
        learner_model.validate_adjust({"pace": 2})


# --- service ------------------------------------------------------------------
def test_signals_write_learner_md_and_survive_across_courses(mentor, course, clock):
    mentor.learner_signal("fact", note="Backend developer, writes Python daily")
    r = mentor.learner_signal("reaction", dims={"angle": "geometric", "domain": "game-dev"}, valence=1,
                              target="camera rotation analogy", note="the camera picture made it click",
                              course=course, node="vec.basics")
    mentor.learner_signal("reaction", dims={"angle": "geometric"}, valence=0.8, course=course)
    path = Path(r["learner_md"])
    text = path.read_text(encoding="utf-8")
    assert "Backend developer" in text and "camera picture" in text and "geometric" in text

    _learn(mentor, course, "vec.basics", clock)
    other = mentor.course_create("Machine learning basics")["course"]
    model = mentor.learner_model()
    assert model["known_elsewhere"][0]["node"] == "vec.basics"  # known in another course
    assert "game-dev" in model["interests"]
    assert any(e["value"] == "geometric" for e in model["works"])
    assert other  # the model is global: no course argument needed


def test_signal_validation_and_void(mentor):
    with pytest.raises(MentorError, match="outcomes come from evidence_record"):
        mentor.learner_signal("outcome", dims={"angle": "geometric"}, valence=1)
    with pytest.raises(MentorError, match="valence"):
        mentor.learner_signal("reaction", dims={"angle": "geometric"})
    with pytest.raises(MentorError, match="needs note"):
        mentor.learner_signal("fact")
    with pytest.raises(MentorError, match="angle must be one of"):
        mentor.learner_signal("reaction", dims={"angle": "kinesthetic"}, valence=1)
    sid = mentor.learner_signal("stated", dims={"format": "video"}, valence=1, weight=2)["signal_id"]
    sid2 = mentor.learner_signal("stated", dims={"format": "video"}, valence=1)["signal_id"]
    assert mentor.learner_model()["works"]
    mentor.learner_signal_void(sid, "learner: I said that about a different topic")
    mentor.learner_signal_void(sid2, "same")
    assert not mentor.learner_model()["works"]
    with pytest.raises(MentorError):
        mentor.learner_signal_void(sid, "again")


def test_evidence_with_taught_with_creates_relative_outcome(mentor, course, clock):
    for score in (0.5, 0.5, 0.5):  # baseline 0.5
        clock.advance(minutes=1)
        mentor.evidence_record(course, "vec.basics", "practice", score=score, form="short")
    clock.advance(minutes=1)
    mentor.evidence_record(course, "vec.basics", "practice", score=1.0, form="short",
                           taught_with={"angle": "geometric"})
    clock.advance(minutes=1)
    mentor.evidence_record(course, "vec.basics", "practice", score=0.0, form="short",
                           taught_with={"angle": "formal"})
    sigs = mentor.store.signals()
    by_angle = {s["dims"]["angle"]: s for s in sigs if s["kind"] == "outcome"}
    assert by_angle["geometric"]["valence"] > 0 > by_angle["formal"]["valence"]
    ev = mentor.store.evidence(mentor.store.course(course)["id"])[-1]
    assert ev["meta"]["taught_with"] == {"angle": "formal"}
    with pytest.raises(MentorError, match="taught_with"):
        mentor.evidence_record(course, "vec.basics", "practice", score=1, taught_with={"angle": "?"})


# --- explorables ---------------------------------------------------------------
GOOD_EXPLORABLE = """<!doctype html><html><head><meta charset="utf-8"><title>Grid transform</title>
<script src="https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js"></script></head>
<body><svg id="s"></svg><script>const m=[[1,1],[0,1]];</script></body></html>"""


def test_explorable_save_validates_and_triggers_html(mentor, course):
    with pytest.raises(MentorError, match="lesson_save"):
        mentor.explorable_save(course, "vec.basics", "grid", GOOD_EXPLORABLE, "what does a shear do?")
    saved = mentor.lesson_save(course, "vec.basics", "# Vectors\nPlain text.", {"items": []})
    assert saved["html"] is None

    bad = GOOD_EXPLORABLE.replace("cdn.jsdelivr.net/npm/d3@7.9.0", "evil.example.com/x").replace(
        "const m", "fetch('https://evil.example.com');const m")
    r = mentor.explorable_save(course, "vec.basics", "grid", bad, "what does a shear do?")
    assert not r["saved"]
    assert any("non-allowlisted" in p for p in r["problems"])
    assert any("network" in p for p in r["problems"])
    unpinned = GOOD_EXPLORABLE.replace("d3@7.9.0", "d3")
    assert any("unpinned" in p for p in mentor.explorable_save(
        course, "vec.basics", "grid", unpinned, "q")["problems"])

    ok = mentor.explorable_save(course, "vec.basics", "Grid Shear", GOOD_EXPLORABLE, "what does a shear do?")
    assert ok["saved"] and ok["path"].endswith("explore-grid-shear.html")
    again = mentor.lesson_save(course, "vec.basics", "# Vectors\nPlain text.\n\n" + ok["markdown_link"],
                               {"items": []})
    assert again["html"] and Path(again["html"]).exists()  # an explorable makes HTML worthwhile
    meta = (Path(again["dir"]) / "meta.json").read_text(encoding="utf-8")
    assert "explore-grid-shear.html" in meta  # survives re-saving the lesson


def test_detail_log_and_reset(mentor, course):
    mentor.learner_signal("fact", note="Physics teacher")
    mentor.learner_signal("stated", adjust={"pace": 1})
    log = mentor.learner_model(detail=True)["signal_log"]
    assert [s["kind"] for s in log] == ["stated", "fact"]  # newest first
    assert mentor.learner_reset("learner asked to start over")["voided"] == 2
    model = mentor.learner_model()
    assert model["signals"] == 0 and model["facts"] == []


def test_single_clear_signal_is_an_early_sign_not_a_verdict():
    model = learner_model.build([_sig(1, "reaction", {"angle": "analogy"}, -1.0),
                                 _sig(2, "outcome", {"angle": "formal"}, -1.0)], T0)
    assert model["avoid"] == []
    assert [e["value"] for e in model["early_signs"]] == ["analogy"]  # outcome alone is too weak
    assert any("analogy (angle) did not help" in g for g in model["guidance"])
    assert {"formal", "analogy"}.isdisjoint(e["value"] for e in model["explore"])  # tried, even if weakly
