"""Learner model: BKT mastery estimate, node state machine and the mastery gate (spec §6.3-6.4).

Node state is *derived* by replaying the append-only evidence log in order. Every
write path appends evidence and then re-derives state, so ``rebuild`` is trivially
identical to incremental updates.

States: locked, ready, learning, learned, mastered, rusty, deferred.
The LLM never sets these directly: it records evidence and reads the result.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any

from .fsrs_adapter import AGAIN, RetentionScheduler, rating_for
from .graph import Graph, bloom_rank
from .paths import iso, parse_ts

SCORED_KINDS = ("practice", "quiz", "review", "explain", "misconception", "check")
EVIDENCE_KINDS = SCORED_KINDS + (
    "diagnostic",   # placement question answered directly on this node
    "inferred",     # placement inference propagated from another node (meta.op = floor|ceil)
    "placement",    # diagnostic concluded the node is already known
    "implicit",     # FIRe credit from practicing an encompassing node (weight = w)
    "check_flag",   # an encompassing node failed: ask a quick check question here
    "told",         # learner asked for the answer: no positive evidence
    "defer",        # learner/tutor parked the node (meta.until)
)
RETAINED = ("learned", "mastered", "rusty")


@dataclass(frozen=True)
class Params:
    p_init: float = 0.1
    p_init_prereq: float = 0.3
    p_transit: float = 0.15
    p_slip: float = 0.10
    p_guess: float = 0.20
    gate_p: float = 0.95
    gate_correct: int = 3
    gate_forms: int = 2
    pass_score: float = 0.8
    spacing_hours: float = 6.0
    confirm_hours: float = 20.0
    first_review_days: float = 1.0
    known_review_days: float = 7.0
    desired_retention: float = 0.9
    halt_window: int = 4
    halt_accuracy: float = 0.5
    insert_prereq_failures: int = 8

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def bkt_update(p: float, score: float, params: Params, weight: float = 1.0,
               guess: float | None = None) -> float:
    """Soft-evidence BKT step: mix the correct/incorrect posteriors by ``score``.

    ``weight`` (0..1] damps the update for hinted answers. Reference: OATutor BKT-brain (MIT).
    """
    slip, g = params.p_slip, params.p_guess if guess is None else guess
    p_correct = p * (1 - slip) / (p * (1 - slip) + (1 - p) * g)
    p_wrong = p * slip / (p * slip + (1 - p) * (1 - g))
    posterior = score * p_correct + (1 - score) * p_wrong
    posterior = p + weight * (posterior - p)
    posterior = posterior + (1 - posterior) * params.p_transit * weight
    return min(max(posterior, 0.0), 1.0)


def _initial_state(node: dict, params: Params) -> dict[str, Any]:
    return {
        "state": "unseen",
        "p_learned": params.p_init_prereq if node.get("tier") == "prereq" else params.p_init,
        "indep_correct": 0,
        "forms_seen": set(),
        "bloom_reached": 0,
        "misconception_passed": 0,
        "explain_passed": 0,
        "learned_at": None,
        "mastered_at": None,
        "last_retrieval": None,
        "fsrs_card": None,
        "due_at": None,
        "deferred_until": None,
        "check_flag": 0,
    }


def needs_explain(node: dict) -> bool:
    return node.get("type") in ("concept", "design")


def needs_misconception(node: dict) -> bool:
    return bool(node.get("misconceptions"))


def gate_missing(node: dict, s: dict, params: Params) -> list[str]:
    """What still blocks learning -> learned. Empty list means the gate passes."""
    missing = []
    if s["p_learned"] < params.gate_p:
        missing.append(f"mastery estimate {s['p_learned']:.2f} < {params.gate_p}")
    if s["indep_correct"] < params.gate_correct:
        missing.append(f"{params.gate_correct - s['indep_correct']} more unhinted correct answer(s)")
    if len(s["forms_seen"]) < params.gate_forms:
        missing.append(f"correct answers in {params.gate_forms} different item forms "
                       f"(have: {', '.join(sorted(s['forms_seen'])) or 'none'})")
    if s["bloom_reached"] < bloom_rank(node.get("bloom")):
        missing.append(f"a correct answer at Bloom level '{node.get('bloom')}'")
    if needs_misconception(node) and not s["misconception_passed"]:
        missing.append("misconception check")
    if needs_explain(node) and not s["explain_passed"]:
        missing.append("explain-back")
    return missing


def _passed(ev: dict, params: Params) -> bool:
    return (not ev["idk"]) and not ev["hinted"] and (ev["score"] or 0) >= params.pass_score


def replay_node(node: dict, evidence: list[dict], params: Params,
                scheduler: RetentionScheduler) -> dict[str, Any]:
    """Graph-independent state from this node's evidence, in chronological order."""
    s = _initial_state(node, params)
    spacing = timedelta(hours=params.spacing_hours)

    def spaced(ts: datetime) -> bool:
        return s["last_retrieval"] is None or ts - parse_ts(s["last_retrieval"]) >= spacing

    for ev in evidence:
        ts = parse_ts(ev["ts"])
        kind = ev["kind"]
        meta = ev.get("meta") or {}

        if kind == "defer":
            s["deferred_until"] = meta.get("until")
        elif kind == "check_flag":
            if s["state"] in RETAINED:
                s["check_flag"] = 1
        elif kind == "inferred":
            value = float(ev["weight"])
            s["p_learned"] = (max if meta.get("op") == "floor" else min)(s["p_learned"], value)
        elif kind == "diagnostic":
            if _passed(ev, params):
                weak = ev.get("confidence") is not None and ev["confidence"] <= 2
                s["p_learned"] = 0.7 if weak else 0.9
            else:
                s["p_learned"] = 0.05
        elif kind == "placement":
            s.update(state="mastered", p_learned=max(s["p_learned"], 0.9),
                     learned_at=iso(ts), mastered_at=iso(ts), last_retrieval=iso(ts),
                     fsrs_card=scheduler.new_card(ts, ts + timedelta(days=params.known_review_days)))
        elif kind == "implicit":
            if s["state"] in ("learned", "mastered") and s["fsrs_card"] and spaced(ts):
                w = float(ev["weight"])
                if w >= 0.5:
                    s["fsrs_card"] = scheduler.review(s["fsrs_card"], 3, ts)
                    s["last_retrieval"] = iso(ts)
                else:
                    interval = scheduler.interval_days(s["fsrs_card"])
                    s["fsrs_card"] = scheduler.shift_due(s["fsrs_card"], timedelta(days=w * interval))
        elif kind in SCORED_KINDS:
            _apply_scored(node, s, ev, ts, spaced(ts), params, scheduler)
        # "told" carries no positive evidence by design.

    if s["fsrs_card"]:
        s["due_at"] = iso(scheduler.due(s["fsrs_card"]))
    return s


def _apply_scored(node: dict, s: dict, ev: dict, ts: datetime, is_spaced: bool,
                  params: Params, scheduler: RetentionScheduler) -> None:
    s["check_flag"] = 0
    score = 0.0 if ev["idk"] else float(ev["score"] or 0.0)
    weight = max(0.25, 1 - 0.25 * max(1, ev["hint_level"] or 0)) if ev["hinted"] else 1.0
    n_options = (ev.get("meta") or {}).get("n_options")
    guess = 1 / n_options if ev.get("form") == "mcq" and n_options else None
    s["p_learned"] = bkt_update(s["p_learned"], score, params, weight, guess)

    passed = _passed(ev, params)
    if passed:
        s["indep_correct"] += 1
        s["forms_seen"].add(ev.get("form") or "unspecified")
        s["bloom_reached"] = max(s["bloom_reached"], bloom_rank(ev.get("bloom") or node.get("bloom")))
        if ev["kind"] == "misconception":
            s["misconception_passed"] = 1
        if ev["kind"] == "explain":
            s["explain_passed"] = 1

    if s["state"] in ("unseen", "learning"):
        s["state"] = "learning"
        if not gate_missing(node, s, params):
            s["state"] = "learned"
            s["learned_at"] = iso(ts)
            s["fsrs_card"] = scheduler.new_card(ts, ts + timedelta(days=params.first_review_days))
    elif s["fsrs_card"] and is_spaced:
        rating = rating_for(score, bool(ev["hinted"]), ev.get("confidence"))
        s["fsrs_card"] = scheduler.review(s["fsrs_card"], rating, ts)
        if rating == AGAIN:
            s["state"] = "rusty"
        elif score >= params.pass_score:
            confirm = timedelta(hours=params.confirm_hours)
            if s["state"] == "learned" and ts - parse_ts(s["learned_at"]) >= confirm:
                s["state"] = "mastered"
                s["mastered_at"] = iso(ts)
            elif s["state"] == "rusty":
                s["state"] = "learned"
    elif s["state"] == "rusty" and passed:
        s["state"] = "learned"
    s["last_retrieval"] = iso(ts)


def derive_states(graph: Graph, evidence_by_node: dict[str, list[dict]], params: Params,
                  scheduler: RetentionScheduler, now: datetime) -> dict[str, dict[str, Any]]:
    states = {nid: replay_node(node, evidence_by_node.get(nid, []), params, scheduler)
              for nid, node in graph.nodes.items()}
    for nid in graph.topo():
        s = states[nid]
        if s["state"] == "unseen":
            ok = all(states[p]["state"] in RETAINED for p in graph.prereqs(nid))
            s["state"] = "ready" if ok else "locked"
        if (s["deferred_until"] and s["state"] not in RETAINED
                and now < parse_ts(s["deferred_until"])):
            s["state"] = "deferred"
    return states


def recent_scores(evidence: list[dict], window: int) -> list[float]:
    scored = [ev for ev in evidence if ev["kind"] in SCORED_KINDS and not ev["idk"]]
    return [float(ev["score"] or 0) for ev in scored[-window:]]


def should_halt(evidence: list[dict], params: Params) -> bool:
    scores = recent_scores(evidence, params.halt_window)
    return len(scores) == params.halt_window and sum(scores) / len(scores) < params.halt_accuracy


def failure_count(evidence: list[dict], params: Params) -> int:
    return sum(1 for ev in evidence
               if ev["kind"] in SCORED_KINDS and (ev["idk"] or (ev["score"] or 0) < 0.5))
