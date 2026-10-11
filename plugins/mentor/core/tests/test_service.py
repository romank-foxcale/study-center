import json
import zipfile
from pathlib import Path

import pytest

from mentor_core import paths
from mentor_core.render import render_page, smoke_check
from mentor_core.service import MentorError
from test_learner import _learn

LESSON_MD = r"""
## Why this matters
Every neural-network layer is a stack of dot products.

The dot product of $\mathbf{a}$ and $\mathbf{b}$ is

$$\mathbf{a}\cdot\mathbf{b} = \sum_i a_i b_i$$

```mermaid
flowchart LR
  a[vector a] --> p[projection] --> s[scalar]
```

```plot
{"marks": [{"type": "line", "fn": "Math.cos(x)", "domain": [0, 6.28]}], "caption": "cos θ"}
```

```jsxgraph
board.create('arrow', [[0,0],[3,1]]);
```

```quiz
- q: "Is $\\mathbf{a}\\cdot\\mathbf{b}$ a vector or a scalar?"
  options: ["vector", "scalar"]
  answer: "scalar"
  explain: "It sums products of components."
```

<script>alert('raw html must be escaped')</script>
"""

PACK = {
    "objective": "Compute dot products",
    "items": [
        {"prompt": "Compute (1,2)·(3,4)", "form": "numeric", "bloom": "apply",
         "answer_key": {"answer": "11", "explanation": "1*3 + 2*4"}},
        {"prompt": "Is the dot product a vector?", "form": "mcq", "bloom": "understand",
         "answer_key": {"answer": "No, a scalar"}, "misconception_map": {"yes": "dot-is-vector"},
         "purpose": "misconception"},
    ],
}


def test_course_lifecycle_and_status(mentor, graph_yaml):
    created = mentor.course_create("Linear Algebra for PCA!")
    slug = created["course"]
    assert slug == "linear-algebra-for-pca"
    assert mentor.course_create("Linear Algebra for PCA!")["course"] == "linear-algebra-for-pca-2"
    assert mentor.course_status(slug)["stage"] == "needs_intake"
    mentor.profile_write(slug, mission_md="# Mission\nFollow ML papers", profile_md="# Profile\nKnows Python")
    assert mentor.course_status(slug)["stage"] == "needs_graph"
    assert mentor.graph_propose(slug, graph_yaml)["saved"]
    status = mentor.course_status(slug)
    assert status["stage"] == "needs_diagnostic"
    assert Path(status["dir"], "graph.html").exists()


def test_invalid_graph_not_saved(mentor):
    slug = mentor.course_create("x")["course"]
    r = mentor.graph_propose(slug, "goal: x\nnodes: []\n")
    assert not r["saved"] and r["errors"]
    r = mentor.graph_propose(slug, "goal: [unclosed")
    assert not r["saved"]


def test_diagnostic_flow(mentor, course, clock):
    probe = mentor.diagnostic_next(course)
    assert not probe["done"]
    while not probe["done"]:
        clock.advance(seconds=20)
        probe = mentor.diagnostic_record(course, probe["node"], 1.0 if "vec" in probe["node"] else 0.0)["next"]
    out = mentor.diagnostic_finish(course)
    assert "vec.basics" in out["known"]
    assert mentor.course_status(course)["stage"] == "learning"


def test_items_hide_keys(mentor, course):
    item_id = mentor.item_save(course, "vec.dot", PACK["items"][0])["item_id"]
    assert "answer_key" not in mentor.item_get(course, item_id)
    assert mentor.item_get(course, item_id, include_key=True)["answer_key"]["answer"] == "11"
    with pytest.raises(MentorError):
        mentor.item_save(course, "vec.dot", {"prompt": "no key", "form": "short"})


def test_evidence_uses_item_metadata(mentor, course, clock):
    item_id = mentor.item_save(course, "vec.basics", PACK["items"][0])["item_id"]
    r = mentor.evidence_record(course, "vec.basics", "practice", score=1.0, item_id=item_id)
    ev = mentor.store.evidence(mentor._course(course)["id"], "vec.basics")[-1]
    assert ev["form"] == "numeric" and ev["bloom"] == "apply"
    assert r["state"] == "learning"
    with pytest.raises(MentorError):
        mentor.evidence_record(course, "vec.basics", "practice")  # no score
    with pytest.raises(MentorError):
        mentor.evidence_record(course, "vec.basics", "mastered", score=1)  # LLM can't set state


def test_lesson_save_render_and_navigation(mentor, course):
    a = mentor.lesson_save(course, "vec.basics", "# Vectors\nArrows.", {"items": []},
                           [{"id": 1, "title": "OpenStax", "url": "https://openstax.org"}])
    b = mentor.lesson_save(course, "vec.dot", LESSON_MD, PACK, title="Dot product")
    assert a["lesson_id"] == "0001-vec.basics" and b["lesson_id"] == "0002-vec.dot"
    assert len(b["items_saved"]) == 2
    assert b["problems"] == []
    assert set(b["features"]) == {"math", "mermaid", "plot", "jsxgraph"}
    page = Path(b["html"]).read_text(encoding="utf-8")
    assert "<script>alert" not in page and "&lt;script&gt;alert" in page
    assert "../0001-vec.basics/lesson.html" in page
    assert "katex@0.16.11" in page
    again = mentor.lesson_save(course, "vec.dot", LESSON_MD, PACK)
    assert again["lesson_id"] == "0002-vec.dot" and again["version"] == 2
    pack_on_disk = json.loads((Path(b["dir"]) / "pack.json").read_text(encoding="utf-8"))
    assert pack_on_disk["objective"] == "Compute dot products"


def test_render_errors_are_reported():
    page = render_page("```plot\n{not json\n```", title="t")
    assert any("render errors" in p for p in smoke_check(page["html"]))


def test_progress_and_anki(mentor, course, clock):
    with pytest.raises(MentorError):
        mentor.export_anki(course)
    mentor.item_save(course, "vec.basics", PACK["items"][0])
    _learn(mentor, course, "vec.basics", clock)
    prog = mentor.progress(course, fmt="html")
    assert prog["counts"]["learned"] == 1
    assert Path(prog["progress_html"]).exists()
    assert prog["streak_days"] == 1
    deck = mentor.export_anki(course)
    assert deck["notes"] == 1 and zipfile.is_zipfile(deck["path"])


def test_check_math(mentor):
    assert mentor.check_math("(x+1)**2", "x^2 + 2x + 1", ["x"])["equivalent"] is True
    assert mentor.check_math("sin(x)**2 + cos(x)**2", "1", ["x"])["equivalent"] is True
    assert mentor.check_math("2*x", "x + 2", ["x"])["equivalent"] is False
    assert mentor.check_math("y = 2*x", "y - 2*x = 0", ["x", "y"])["equivalent"] is True
    assert mentor.check_math("1/3", "0.333333333333333333", [])["equivalent"] is True
    assert mentor.check_math("((", "1")["equivalent"] is None


def test_review_queue_and_config(mentor, course, clock):
    _learn(mentor, course, "vec.basics", clock)
    assert mentor.review_queue() == []
    clock.advance(days=2)
    q = mentor.review_queue()
    assert q[0]["course"] == course and q[0]["due"] == 1
    assert mentor.config("review_budget", "3")["review_budget"] == 3
    with pytest.raises(MentorError):
        mentor.config("nope", "1")


def test_workspace_resolution(tmp_path, monkeypatch):
    monkeypatch.setenv("MENTOR_PLUGIN_DATA", str(tmp_path / "pd"))
    monkeypatch.setenv("MENTOR_WORKSPACE", "${user_config.workspace_dir}")  # unsubstituted
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    ws = paths.resolve_workspace()
    assert ws == (tmp_path / "home" / "Mentor").resolve()
    pointer = json.loads((tmp_path / "pd" / "pointer.json").read_text(encoding="utf-8"))
    assert Path(pointer["workspace"]) == ws
    monkeypatch.setenv("MENTOR_WORKSPACE", str(tmp_path / "with space" / "ws"))
    assert paths.resolve_workspace() == (tmp_path / "with space" / "ws").resolve()
    monkeypatch.setenv("MENTOR_WORKSPACE", "")
    assert paths.resolve_workspace() == (tmp_path / "with space" / "ws").resolve()  # via pointer
