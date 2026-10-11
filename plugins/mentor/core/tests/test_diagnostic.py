"""Diagnostic convergence on synthetic learners (spec Phase 1 acceptance)."""

import random

import networkx as nx
import yaml

from mentor_core.service import Mentor


def random_dag_yaml(n: int, seed: int) -> str:
    rng = random.Random(seed)
    nodes = [{"id": f"n{i:02d}", "title": f"Node {i}", "type": "procedure", "tier": "core",
              "objective": f"skill {i}", "bloom": "apply", "minutes": 20,
              "misconceptions": ["m"]} for i in range(n)]
    edges = []
    for i in range(1, n):
        for j in rng.sample(range(i), k=min(i, rng.choice([1, 1, 2, 2, 3]))):
            if i - j <= 12:
                edges.append({"kind": "prereq", "from": f"n{j:02d}", "to": f"n{i:02d}"})
        if not any(e["to"] == f"n{i:02d}" for e in edges):
            edges.append({"kind": "prereq", "from": f"n{i - 1:02d}", "to": f"n{i:02d}"})
    return yaml.safe_dump({"goal": "synthetic", "capabilities": [], "nodes": nodes, "edges": edges})


def known_set(doc: dict, rng: random.Random) -> set[str]:
    """A downward-closed knowledge state: everything up to a random frontier."""
    g = nx.DiGraph()
    g.add_edges_from((e["from"], e["to"]) for e in doc["edges"])
    order = list(nx.topological_sort(g))
    cut = rng.randint(0, len(order))
    known: set[str] = set()
    for nid in order[:cut]:
        if all(p in known for p in g.predecessors(nid)) and rng.random() < 0.85:
            known.add(nid)
    return known


def test_placement_accuracy_on_synthetic_learners(tmp_path, monkeypatch, clock):
    monkeypatch.delenv("MENTOR_WORKSPACE", raising=False)
    monkeypatch.setenv("MENTOR_PLUGIN_DATA", str(tmp_path / "pd"))
    mentor = Mentor(tmp_path / "ws")
    trials, good, questions = 20, 0, []
    try:
        for t in range(trials):
            text = random_dag_yaml(40, seed=t)
            doc = yaml.safe_load(text)
            slug = mentor.course_create(f"synthetic {t}")["course"]
            assert mentor.graph_propose(slug, text)["saved"]
            known = known_set(doc, random.Random(100 + t))
            probe = mentor.diagnostic_next(slug)
            while not probe["done"]:
                clock.advance(seconds=30)
                score = 1.0 if probe["node"] in known else 0.0
                probe = mentor.diagnostic_record(slug, probe["node"], score)["next"]
            questions.append(probe["asked"])
            mentor.diagnostic_finish(slug)
            states = {n: s["state"] for n, s in mentor.store.states(mentor._course(slug)["id"]).items()}
            predicted = {n for n, s in states.items() if s == "mastered"}
            accuracy = sum((n in predicted) == (n in known) for n in states) / len(states)
            good += accuracy >= 0.9
    finally:
        mentor.close()
    assert max(questions) <= 20
    assert good / trials >= 0.9, f"only {good}/{trials} placements >= 90% accurate"
