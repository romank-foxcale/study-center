from mentor_core.learner import Params, bkt_update

P = Params()


def test_three_unhinted_correct_reach_gate_threshold():
    p = P.p_init
    for _ in range(3):
        p = bkt_update(p, 1.0, P)
    assert p >= P.gate_p


def test_wrong_answers_lower_estimate_and_hints_damp():
    p = bkt_update(0.6, 0.0, P)
    assert p < 0.6
    full = bkt_update(0.3, 1.0, P)
    hinted = bkt_update(0.3, 1.0, P, weight=0.5)
    assert 0.3 < hinted < full


def _practice(mentor, course, node, form, kind="practice", score=1.0, **kw):
    return mentor.evidence_record(course, node, kind, score=score, form=form, **kw)


def test_gate_requires_forms_misconception_and_explain(mentor, course, clock):
    node = "vec.basics"  # concept -> needs explain-back; has misconceptions
    r = None
    for _ in range(3):
        clock.advance(minutes=2)
        r = _practice(mentor, course, node, "short")
    assert r["state"] == "learning"
    assert any("different item forms" in m for m in r["gate_missing"])
    clock.advance(minutes=2)
    r = _practice(mentor, course, node, "mcq", kind="misconception", n_options=4)
    assert r["state"] == "learning"
    assert r["gate_missing"] == ["explain-back"]
    clock.advance(minutes=2)
    r = _practice(mentor, course, node, "explain", kind="explain")
    assert r["state"] == "learned"
    assert r["next_action"].startswith("gate passed")


def _learn(mentor, course, node, clock):
    for form, kind in (("short", "practice"), ("numeric", "practice"), ("short", "practice"),
                       ("mcq", "misconception"), ("explain", "explain")):
        clock.advance(minutes=2)
        r = mentor.evidence_record(course, node, kind, score=1.0, form=form, bloom="analyze")
    assert r["state"] == "learned", r
    return r


def test_learned_to_mastered_needs_delayed_review(mentor, course, clock):
    _learn(mentor, course, "vec.basics", clock)
    clock.advance(hours=1)  # too soon: not spaced
    r = mentor.evidence_record(course, "vec.basics", "review", score=1.0, form="short")
    assert r["state"] == "learned"
    clock.advance(hours=23)
    r = mentor.evidence_record(course, "vec.basics", "review", score=1.0, form="short", confidence=4)
    assert r["state"] == "mastered" and r["mastered"]


def test_failed_review_makes_rusty_then_relearn(mentor, course, clock):
    _learn(mentor, course, "vec.basics", clock)
    clock.advance(days=2)
    r = mentor.evidence_record(course, "vec.basics", "review", score=0.1, form="short")
    assert r["state"] == "rusty"
    clock.advance(minutes=5)
    r = mentor.evidence_record(course, "vec.basics", "practice", score=1.0, form="short")
    assert r["state"] == "learned"


def test_told_gives_no_credit(mentor, course, clock):
    before = mentor.graph_get(course, node="vec.basics")["p_learned"]
    r = mentor.evidence_record(course, "vec.basics", "told")
    assert r["p_learned"] == before
    assert "isomorphic" in r["next_action"]


def test_rebuild_reproduces_incremental_state(mentor, course, clock):
    _learn(mentor, course, "vec.basics", clock)
    _learn(mentor, course, "vec.dot", clock)
    clock.advance(days=3)
    mentor.evidence_record(course, "vec.dot", "review", score=0.9, form="short", confidence=3)
    cid = mentor._course(course)["id"]
    before = mentor.store.states(cid)
    mentor.rebuild_state(course)
    assert mentor.store.states(cid) == before


def test_void_recomputes(mentor, course, clock):
    r = mentor.evidence_record(course, "vec.basics", "practice", score=0.0, form="short")
    after_fail = r["p_learned"]
    v = mentor.evidence_void(course, r["evidence_id"], "grader misread the answer")
    assert v["p_learned"] > after_fail


def test_unlocking_follows_prereqs(mentor, course, clock):
    states = {n["id"]: n["state"] for n in mentor.graph_get(course)["frontier"]}
    assert set(states) == {"vec.basics", "stats.cov"}
    _learn(mentor, course, "vec.basics", clock)
    frontier = {n["id"] for n in mentor.graph_get(course)["frontier"]}
    assert {"vec.dot", "mat.basics"} <= frontier


def test_defer(mentor, course, clock):
    r = mentor.node_defer(course, "stats.cov", days=2)
    assert r["state"] == "deferred"
    clock.advance(days=3)
    assert mentor.graph_get(course, node="stats.cov")["state"] == "ready"
