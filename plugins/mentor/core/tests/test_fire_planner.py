from test_learner import _learn


def test_implicit_credit_reschedules_encompassed_node(mentor, course, clock):
    for node in ("vec.basics", "vec.dot", "mat.basics"):
        _learn(mentor, course, node, clock)
    due_before = mentor.graph_get(course, node="vec.dot")["due_at"]
    clock.advance(days=2)
    # Learning mat.mult (encompasses vec.dot, w=0.7) implicitly reviews vec.dot.
    mentor.evidence_record(course, "mat.mult", "practice", score=1.0, form="short")
    due_after = mentor.graph_get(course, node="vec.dot")["due_at"]
    assert due_after > due_before


def test_failure_flags_encompassed_node_for_check(mentor, course, clock):
    for node in ("vec.basics", "vec.dot", "mat.basics"):
        _learn(mentor, course, node, clock)
    clock.advance(hours=2)
    mentor.evidence_record(course, "mat.mult", "practice", score=0.0, form="short")
    act = mentor.next_activity(course)
    assert act["type"] == "check" and act["nodes"] == ["vec.dot"]


def test_reviews_come_first_and_use_set_cover(mentor, course, clock):
    for node in ("vec.basics", "vec.dot", "mat.basics", "mat.mult"):
        _learn(mentor, course, node, clock)
    clock.advance(days=2)
    act = mentor.next_activity(course)
    assert act["type"] == "review"
    covered = {n for pick in act["items"] for n in pick["covers"]}
    assert covered == {"vec.basics", "vec.dot", "mat.basics", "mat.mult"}
    # mat.mult covers vec.dot via encompasses, so fewer picks than due nodes.
    assert len(act["items"]) < 4


def test_halt_and_remediate(mentor, course, clock):
    _learn(mentor, course, "vec.basics", clock)
    r = None
    for _ in range(4):
        clock.advance(minutes=2)
        r = mentor.evidence_record(course, "vec.dot", "practice", score=0.1, form="short")
    assert r["next_action"].startswith("halt_and_remediate")
    act = mentor.next_activity(course)
    assert act["type"] == "remediate" and act["node"] == "vec.basics" and act["blocked"] == "vec.dot"


def test_quiz_after_three_lessons(mentor, course, clock):
    for node in ("vec.basics", "stats.cov", "vec.dot"):
        _learn(mentor, course, node, clock)
    act = mentor.next_activity(course)
    assert act["type"] == "quiz"
    for node in act["nodes"]:
        clock.advance(minutes=1)
        mentor.evidence_record(course, node, "quiz", score=1.0, form="short")
    assert mentor.next_activity(course)["type"] == "lesson"


def test_new_lesson_prefers_prereq_tier_and_layering(mentor, course, clock):
    act = mentor.next_activity(course)
    assert act["type"] == "lesson" and act["node"] in ("vec.basics", "stats.cov")
    _learn(mentor, course, "vec.basics", clock)
    act = mentor.next_activity(course)
    assert act["node"] in ("stats.cov", "vec.dot", "mat.basics")
