"""Adaptive placement diagnostic: knowledge-frontier search (spec §6.7).

Each question is asked on the untested node that best splits the remaining
uncertainty (balanced uncertain ancestors vs descendants). A pass lifts prereq
ancestors; a fail caps descendants. Inferences are stored as ``inferred`` evidence
so placement is replayable like everything else.
"""

from __future__ import annotations

from .graph import Graph

MAX_QUESTIONS = 20
PASS_FLOOR = 0.85   # ancestors of a passed node
FAIL_CEIL = 0.10    # descendants of a failed node
KNOWN_AT = 0.85


def settled_nodes(evidence_by_node: dict[str, list[dict]]) -> set[str]:
    return {nid for nid, evs in evidence_by_node.items()
            if any(ev["kind"] in ("diagnostic", "inferred", "placement") for ev in evs)}


def questions_asked(evidence_by_node: dict[str, list[dict]]) -> int:
    return sum(1 for evs in evidence_by_node.values() for ev in evs if ev["kind"] == "diagnostic")


def next_probe(graph: Graph, evidence_by_node: dict[str, list[dict]],
               max_questions: int = MAX_QUESTIONS) -> dict:
    asked = questions_asked(evidence_by_node)
    settled = settled_nodes(evidence_by_node)
    uncertain = [nid for nid in graph.nodes if nid not in settled]
    if asked >= max_questions or not uncertain:
        return {"done": True, "asked": asked,
                "reason": "question cap reached" if asked >= max_questions else "frontier located"}
    pool = set(uncertain)

    def split(nid: str) -> tuple[int, int, int, str]:
        up = len(graph.ancestors(nid) & pool)
        down = len(graph.descendants(nid) & pool)
        return (min(up, down), up + down, -abs(up - down), nid)

    node_id = max(sorted(uncertain), key=split)
    node = graph.nodes[node_id]
    return {
        "done": False,
        "asked": asked,
        "remaining_uncertain": len(uncertain),
        "node": node_id,
        "title": node["title"],
        "objective": node["objective"],
        "item_request": {
            "form": "short" if node["type"] in ("concept", "design") else "numeric-or-short",
            "bloom": "apply" if node["bloom"] not in ("remember", "understand") else node["bloom"],
            "guidance": "One skill, one quick question (<2 min). Always allow 'I don't know'.",
        },
    }


def inference_rows(graph: Graph, node_id: str, passed: bool, weak: bool) -> list[dict]:
    if passed and not weak:
        return [{"node_id": a, "kind": "inferred", "weight": PASS_FLOOR,
                 "meta": {"op": "floor", "source": node_id}} for a in sorted(graph.ancestors(node_id))]
    if not passed:
        return [{"node_id": d, "kind": "inferred", "weight": FAIL_CEIL,
                 "meta": {"op": "ceil", "source": node_id}} for d in sorted(graph.descendants(node_id))]
    return []


def placement_rows(graph: Graph, states: dict[str, dict]) -> list[dict]:
    """Nodes whose estimate is high enough to count as already known."""
    return [{"node_id": nid, "kind": "placement", "meta": {"p": round(s["p_learned"], 3)}}
            for nid in graph.topo()
            if (s := states[nid])["p_learned"] >= KNOWN_AT and s["state"] not in ("learned", "mastered")]
