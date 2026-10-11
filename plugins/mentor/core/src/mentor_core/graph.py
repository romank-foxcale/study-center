"""Knowledge graph: schema, validation, traversal and Mermaid export (spec §6.1).

Edge semantics:
* ``prereq``      from -> to : ``from`` must be learned before ``to`` unlocks.
* ``encompasses`` from -> to : practicing ``from`` (advanced) implicitly practices ``to``
                               (simpler) with ``weight`` in (0, 1].
"""

from __future__ import annotations

import re
from typing import Any

import networkx as nx
import yaml

NODE_TYPES = ("memory", "procedure", "concept", "design")
TIERS = ("prereq", "core", "stretch")
BLOOM = ("remember", "understand", "apply", "analyze", "evaluate", "create")
EDGE_KINDS = ("prereq", "encompasses")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
MIN_MINUTES, MAX_MINUTES = 10, 45

REQUIRED_NODE_FIELDS = ("id", "title", "type", "tier", "objective", "bloom", "minutes")


def bloom_rank(level: str | None) -> int:
    return BLOOM.index(level) + 1 if level in BLOOM else 0


def parse(text: str) -> dict[str, Any]:
    data = yaml.safe_load(text) or {}
    if not isinstance(data, dict):
        raise ValueError("graph must be a YAML mapping")
    data.setdefault("capabilities", [])
    data.setdefault("nodes", [])
    data.setdefault("edges", [])
    return data


def dump(graph: dict[str, Any]) -> str:
    return yaml.safe_dump(graph, sort_keys=False, allow_unicode=True, width=100)


def prereq_digraph(nodes: list[dict], edges: list[dict]) -> nx.DiGraph:
    g = nx.DiGraph()
    g.add_nodes_from(n["id"] for n in nodes)
    g.add_edges_from((e["from"], e["to"]) for e in edges if e["kind"] == "prereq")
    return g


def validate(graph: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []
    caps = graph.get("capabilities") or []

    if not graph.get("goal"):
        errors.append("missing top-level 'goal'")
    if not nodes:
        errors.append("graph has no nodes")

    cap_ids = set()
    for i, cap in enumerate(caps):
        if not isinstance(cap, dict) or not cap.get("id") or not cap.get("statement"):
            errors.append(f"capabilities[{i}]: needs 'id' and 'statement'")
            continue
        cap_ids.add(cap["id"])
        if not cap.get("evidence"):
            warnings.append(f"capability {cap['id']}: no 'evidence' (how will we know it's achieved?)")
    if not caps:
        warnings.append("no capabilities defined (backward design: what should the learner be able to do?)")

    ids: list[str] = []
    for i, n in enumerate(nodes):
        if not isinstance(n, dict):
            errors.append(f"nodes[{i}]: not a mapping")
            continue
        where = f"node {n.get('id', f'#{i}')}"
        missing = [f for f in REQUIRED_NODE_FIELDS if n.get(f) in (None, "")]
        if missing:
            errors.append(f"{where}: missing {', '.join(missing)}")
            continue
        if not ID_RE.match(str(n["id"])):
            errors.append(f"{where}: id must match {ID_RE.pattern}")
        if n["type"] not in NODE_TYPES:
            errors.append(f"{where}: type must be one of {NODE_TYPES}")
        if n["tier"] not in TIERS:
            errors.append(f"{where}: tier must be one of {TIERS}")
        if n["bloom"] not in BLOOM:
            errors.append(f"{where}: bloom must be one of {BLOOM}")
        try:
            minutes = int(n["minutes"])
            if not MIN_MINUTES <= minutes <= MAX_MINUTES:
                warnings.append(f"{where}: {minutes} min is outside {MIN_MINUTES}-{MAX_MINUTES}; "
                                f"consider {'splitting' if minutes > MAX_MINUTES else 'merging'}")
        except (TypeError, ValueError):
            errors.append(f"{where}: minutes must be an integer")
        for cap in n.get("serves") or []:
            if cap not in cap_ids:
                errors.append(f"{where}: serves unknown capability '{cap}'")
        if not n.get("misconceptions"):
            warnings.append(f"{where}: no misconceptions listed")
        ids.append(n["id"])

    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        errors.append(f"duplicate node ids: {', '.join(dupes)}")
    id_set = set(ids)

    valid_nodes = [n for n in nodes if isinstance(n, dict) and n.get("id") in id_set]
    good_edges = []
    for i, e in enumerate(edges):
        if not isinstance(e, dict):
            errors.append(f"edges[{i}]: not a mapping")
            continue
        kind, src, dst = e.get("kind"), e.get("from"), e.get("to")
        if kind not in EDGE_KINDS:
            errors.append(f"edges[{i}]: kind must be one of {EDGE_KINDS}")
            continue
        unknown = [x for x in (src, dst) if x not in id_set]
        if unknown:
            errors.append(f"edges[{i}] ({src} -> {dst}): unknown node(s) {', '.join(map(str, unknown))}")
            continue
        if src == dst:
            errors.append(f"edges[{i}]: self-loop on {src}")
            continue
        if kind == "encompasses":
            w = e.get("weight")
            if not isinstance(w, (int, float)) or not 0 < w <= 1:
                errors.append(f"edges[{i}] ({src} encompasses {dst}): weight must be in (0, 1]")
                continue
        good_edges.append(e)

    g = prereq_digraph(valid_nodes, good_edges)
    if not nx.is_directed_acyclic_graph(g):
        try:
            cycle = nx.find_cycle(g)
            errors.append("prereq cycle: " + " -> ".join(f"{a}" for a, _ in cycle) + f" -> {cycle[0][0]}")
        except nx.NetworkXNoCycle:  # pragma: no cover
            errors.append("prereq graph is not acyclic")
    else:
        for e in good_edges:
            if e["kind"] == "encompasses" and not nx.has_path(g, e["to"], e["from"]):
                warnings.append(f"{e['from']} encompasses {e['to']} but is not downstream of it "
                                f"in the prereq graph")
        serves = {n["id"]: set(n.get("serves") or []) for n in valid_nodes}
        covered: set[str] = set()
        for nid in id_set:
            reach = serves[nid] | set().union(*(serves[d] for d in nx.descendants(g, nid)))
            covered |= reach
            if cap_ids and not reach:
                warnings.append(f"node {nid}: does not serve any capability (directly or via descendants)")
        for cap in sorted(cap_ids - covered):
            warnings.append(f"capability {cap}: no node serves it")

    if len(id_set) > 1:
        touched = {e["from"] for e in good_edges} | {e["to"] for e in good_edges}
        for nid in sorted(id_set - touched):
            warnings.append(f"node {nid}: has no edges (isolated)")

    stats = {
        "nodes": len(id_set),
        "prereq_edges": sum(1 for e in good_edges if e["kind"] == "prereq"),
        "encompasses_edges": sum(1 for e in good_edges if e["kind"] == "encompasses"),
        "capabilities": len(cap_ids),
        "by_tier": {t: sum(1 for n in valid_nodes if n.get("tier") == t) for t in TIERS},
        "total_minutes": sum(int(n["minutes"]) for n in valid_nodes
                             if str(n.get("minutes", "")).isdigit()),
    }
    if not errors and nx.is_directed_acyclic_graph(g) and len(g):
        stats["depth"] = nx.dag_longest_path_length(g) + 1
    return {"ok": not errors, "errors": errors, "warnings": warnings, "stats": stats}


class Graph:
    """Read-only view over a validated graph used by learner/planner/diagnostic."""

    def __init__(self, nodes: list[dict], edges: list[dict], capabilities: list[dict] | None = None):
        self.nodes = {n["id"]: n for n in nodes}
        self.capabilities = capabilities or []
        self.g = prereq_digraph(nodes, edges)
        # encompasses[x] = [(y, w)] : practicing x implicitly practices y
        self.encompasses: dict[str, list[tuple[str, float]]] = {}
        for e in edges:
            if e["kind"] == "encompasses":
                self.encompasses.setdefault(e["from"], []).append((e["to"], float(e["weight"])))

    def prereqs(self, nid: str) -> list[str]:
        return sorted(self.g.predecessors(nid))

    def dependents(self, nid: str) -> list[str]:
        return sorted(self.g.successors(nid))

    def ancestors(self, nid: str) -> set[str]:
        return nx.ancestors(self.g, nid)

    def descendants(self, nid: str) -> set[str]:
        return nx.descendants(self.g, nid)

    def depth(self, nid: str) -> int:
        anc = self.ancestors(nid)
        if not anc:
            return 0
        return max(nx.shortest_path_length(self.g, a, nid) for a in anc)

    def topo(self) -> list[str]:
        return list(nx.lexicographical_topological_sort(self.g))

    def encompassed_by(self, nid: str) -> list[tuple[str, float]]:
        return self.encompasses.get(nid, [])


STATE_STYLE = {
    "mastered": "fill:#2e7d32,color:#fff",
    "learned": "fill:#81c784,color:#000",
    "rusty": "fill:#ffb74d,color:#000",
    "learning": "fill:#64b5f6,color:#000",
    "ready": "fill:#fff,stroke:#1976d2,stroke-width:2px,color:#000",
    "deferred": "fill:#e0e0e0,color:#555",
    "locked": "fill:#f5f5f5,stroke:#bbb,color:#888",
}


def to_mermaid(graph: Graph, states: dict[str, str] | None = None, focus: str | None = None) -> str:
    states = states or {}
    ids = list(graph.nodes)
    if focus and focus in graph.nodes:
        keep = {focus} | set(graph.prereqs(focus)) | set(graph.dependents(focus))
        ids = [i for i in ids if i in keep]
    alias = {nid: f"n{i}" for i, nid in enumerate(ids)}
    lines = ["flowchart TD"]
    for nid in ids:
        title = str(graph.nodes[nid]["title"]).replace('"', "'")
        lines.append(f'  {alias[nid]}["{title}"]')
    for a, b in graph.g.edges:
        if a in alias and b in alias:
            lines.append(f"  {alias[a]} --> {alias[b]}")
    for state, style in STATE_STYLE.items():
        members = [alias[n] for n in ids if states.get(n) == state]
        if members:
            lines.append(f"  classDef {state} {style}")
            lines.append(f"  class {','.join(members)} {state}")
    return "\n".join(lines)
