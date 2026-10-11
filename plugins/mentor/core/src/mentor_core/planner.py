"""Decides what the learner should do next (spec §6.8).

Priority: due reviews -> check flags -> remediation -> resume in-progress lesson ->
mixed quiz (every few lessons) -> new lesson from the frontier -> done.
"""

from __future__ import annotations

from datetime import datetime

from .fire import select_reviews
from .graph import Graph
from .learner import Params, RETAINED, failure_count, should_halt
from .paths import parse_ts

QUIZ_EVERY = 3
QUIZ_SIZE = 5
TIER_BONUS = {"prereq": 2.0, "core": 1.0, "stretch": -2.0}


def weakest_prereq(graph: Graph, node_id: str, states: dict[str, dict]) -> str | None:
    """Lowest-confidence ancestor, preferring direct prereqs."""
    direct = graph.prereqs(node_id)
    pool = direct or sorted(graph.ancestors(node_id))
    if not pool:
        return None
    return min(pool, key=lambda p: (states[p]["p_learned"], p))


def _last_ts(evidence: list[dict]) -> datetime | None:
    return parse_ts(evidence[-1]["ts"]) if evidence else None


def _capability_value(graph: Graph, node_id: str, states: dict[str, dict]) -> int:
    """How many not-yet-retained capability-serving nodes this node helps unlock."""
    reach = {node_id} | graph.descendants(node_id)
    return sum(1 for n in reach
               if graph.nodes[n].get("serves") and states[n]["state"] not in RETAINED)


def rank_new_lessons(graph: Graph, states: dict[str, dict],
                     evidence_by_node: dict[str, list[dict]]) -> list[str]:
    ready = [nid for nid, s in states.items() if s["state"] == "ready"]
    if not ready:
        return []
    # Most recently learned node, for layering and non-interference.
    recent = max(
        (nid for nid, s in states.items() if s.get("learned_at")),
        key=lambda nid: states[nid]["learned_at"], default=None,
    )
    recent_confusables = set(graph.nodes[recent].get("confusable_with") or []) if recent else set()
    max_value = max((_capability_value(graph, n, states) for n in ready), default=1) or 1

    def score(nid: str) -> tuple[float, str]:
        node = graph.nodes[nid]
        s = TIER_BONUS.get(node.get("tier"), 0.0)
        s += 2.0 * _capability_value(graph, nid, states) / max_value
        if recent and recent in graph.prereqs(nid):
            s += 1.5  # layering: build on what was just learned
        if nid in recent_confusables or recent in (node.get("confusable_with") or []):
            s -= 3.0  # non-interference
        return (-s, nid)

    return sorted(ready, key=score)


def next_activity(graph: Graph, states: dict[str, dict], evidence_by_node: dict[str, list[dict]],
                  params: Params, now: datetime, review_budget: int = 5) -> dict:
    reviews = select_reviews(graph, states, now, review_budget)
    if reviews:
        return {"type": "review", "items": reviews,
                "why": f"{sum(len(r['covers']) for r in reviews)} due node(s); reviews come before new material"}

    flagged = sorted(nid for nid, s in states.items() if s.get("check_flag"))
    if flagged:
        return {"type": "check", "nodes": flagged,
                "why": "a related advanced topic was missed; quick check on these foundations"}

    rusty = sorted(nid for nid, s in states.items() if s["state"] == "rusty")
    if rusty:
        return {"type": "remediate", "node": rusty[0], "because": "forgotten at review (rusty)"}

    learning = [nid for nid, s in states.items() if s["state"] == "learning"]
    learning.sort(key=lambda n: _last_ts(evidence_by_node.get(n, [])) or now, reverse=True)
    for nid in learning:
        evs = evidence_by_node.get(nid, [])
        if should_halt(evs, params):
            target = weakest_prereq(graph, nid, states)
            if failure_count(evs, params) >= params.insert_prereq_failures:
                return {"type": "suggest_insert_prereq", "node": nid,
                        "why": "repeated failure even after remediation; a prerequisite is probably missing"}
            if target:
                return {"type": "remediate", "node": target, "blocked": nid,
                        "because": f"accuracy collapsed on {nid}; strengthen {target} first"}
        return {"type": "lesson", "node": nid, "resume": True}

    learned_recently = sorted(
        (nid for nid, s in states.items() if s.get("learned_at")),
        key=lambda n: states[n]["learned_at"], reverse=True,
    )
    last_quiz = max((ev["ts"] for evs in evidence_by_node.values() for ev in evs if ev["kind"] == "quiz"),
                    default=None)
    since_quiz = [n for n in learned_recently
                  if states[n]["state"] in ("learned", "mastered")
                  and (last_quiz is None or states[n]["learned_at"] > last_quiz)]
    if len(since_quiz) >= QUIZ_EVERY:
        return {"type": "quiz", "nodes": learned_recently[:QUIZ_SIZE],
                "why": f"{len(since_quiz)} lessons since the last mixed quiz; interleaved practice"}

    ranked = rank_new_lessons(graph, states, evidence_by_node)
    if ranked:
        return {"type": "lesson", "node": ranked[0], "resume": False, "alternatives": ranked[1:4]}

    if states and all(s["state"] in ("learned", "mastered") or graph.nodes[n].get("tier") == "stretch"
                      for n, s in states.items()):
        return {"type": "done", "why": "all non-stretch nodes learned; consider stretch nodes or a capstone"}
    deferred = sorted(n for n, s in states.items() if s["state"] == "deferred")
    if deferred:
        return {"type": "waiting", "deferred": deferred, "why": "remaining nodes are deferred"}
    return {"type": "done", "why": "nothing left to schedule"}
