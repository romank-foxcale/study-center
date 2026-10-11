"""Implicit credit propagation and review selection, inspired by Math Academy's
Fractional Implicit Repetition (spec §6.6). Our own parameters; FIRe's are proprietary.
"""

from __future__ import annotations

from datetime import datetime

from .graph import Graph
from .paths import parse_ts

STRONG = 0.5  # encompasses weight at/above which credit counts as a full implicit review


def implicit_rows(graph: Graph, node_id: str, passed: bool, failed: bool,
                  states: dict[str, dict]) -> list[dict]:
    """Evidence rows to append on encompassed nodes after an attempt on ``node_id``.

    Pass -> ``implicit`` credit on every encompassed node (replay decides whether it is a
    full review or a due-date push, and respects spacing). Fail -> ``check_flag`` on
    strongly encompassed nodes the learner has already learned.
    """
    rows = []
    for target, w in graph.encompassed_by(node_id):
        state = states.get(target, {})
        if passed and state.get("state") in ("learned", "mastered"):
            rows.append({"node_id": target, "kind": "implicit", "weight": w,
                         "meta": {"source": node_id}})
        elif failed and w >= STRONG and state.get("state") in ("learned", "mastered", "rusty") \
                and not state.get("check_flag"):
            rows.append({"node_id": target, "kind": "check_flag", "weight": w,
                         "meta": {"source": node_id}})
    return rows


def overdue_ratio(state: dict, now: datetime) -> float:
    if not state.get("due_at"):
        return 0.0
    due = parse_ts(state["due_at"])
    last = parse_ts(state["last_retrieval"]) if state.get("last_retrieval") else due
    interval = max((due - last).total_seconds(), 3600.0)
    return (now - due).total_seconds() / interval


def due_nodes(states: dict[str, dict], now: datetime) -> list[str]:
    return sorted(
        (nid for nid, s in states.items()
         if s["state"] in ("learned", "mastered") and s.get("due_at") and parse_ts(s["due_at"]) <= now),
        key=lambda nid: -overdue_ratio(states[nid], now),
    )


def select_reviews(graph: Graph, states: dict[str, dict], now: datetime, budget: int) -> list[dict]:
    """Greedy set cover: pick review nodes that knock out the most due nodes at once."""
    due = set(due_nodes(states, now))
    if not due:
        return []
    candidates = {nid for nid, s in states.items() if s["state"] in ("learned", "mastered")}

    def covers(c: str) -> set[str]:
        hit = {c} & due
        hit |= {y for y, w in graph.encompassed_by(c) if w >= STRONG and y in due}
        return hit

    uncovered, picks = set(due), []
    while uncovered and len(picks) < budget:
        best = max(
            sorted(candidates),
            key=lambda c: (len(covers(c) & uncovered),
                           sum(overdue_ratio(states[y], now) for y in covers(c) & uncovered),
                           c in due),
        )
        gained = covers(best) & uncovered
        if not gained:
            break
        picks.append({"node": best, "covers": sorted(gained)})
        uncovered -= gained
        candidates.discard(best)
    return picks
