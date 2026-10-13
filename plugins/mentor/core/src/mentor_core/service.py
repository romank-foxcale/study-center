"""The Mentor facade: every MCP tool and CLI command is a method here.

Methods take and return plain JSON-able values so the same surface works over MCP,
the CLI, tests and any future provider-agnostic front end.
"""

from __future__ import annotations

import json
import re
import secrets
import webbrowser
from collections import Counter
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any

from . import diagnostic as diag
from . import fire, graph as graphmod, learner_model, planner
from .fsrs_adapter import make_scheduler
from .learner import (
    EVIDENCE_KINDS, RETAINED, SCORED_KINDS, Params, derive_states, failure_count,
    gate_missing, should_halt,
)
from .paths import DB_FILE, iso, now, parse_ts, resolve_workspace, slugify, write_pointer
from .render import render_page, smoke_check
from .store import Store

COURSE_SUBDIRS = ("research", "lessons", "reference", "records", "exports")
LEARNER_FILE = "LEARNER.md"
# Lesson features that markdown viewers can't show; only these make an HTML page worth writing.
INTERACTIVE_FEATURES = {"plot", "jsxgraph", "quiz"}
OUTCOME_KINDS = ("practice", "misconception", "explain", "check")
EXPLORABLE_HOSTS = ("cdn.jsdelivr.net", "cdnjs.cloudflare.com", "unpkg.com")
EXPLORABLE_MAX_BYTES = 2_000_000
CONFIG_KEYS = {
    "review_budget": int,
    "desired_retention": float,
    "diagnostic_max_questions": int,
}
CONFIG_DEFAULTS = {"review_budget": 5, "desired_retention": 0.9, "diagnostic_max_questions": 20}


class MentorError(ValueError):
    """User-facing error: the message is meant to be shown to the model/learner."""


class Mentor:
    def __init__(self, workspace: str | Path | None = None):
        self.workspace = resolve_workspace(workspace)
        self.store = Store(self.workspace / DB_FILE)
        retention = float(self.config_value("desired_retention"))
        self.params = replace(Params(), desired_retention=retention)
        self.scheduler = make_scheduler(retention)

    def close(self) -> None:
        self.store.close()

    # ------------------------------------------------------------------ helpers
    def config_value(self, key: str) -> Any:
        raw = self.store.get_meta(f"config:{key}")
        return CONFIG_KEYS[key](raw) if raw is not None else CONFIG_DEFAULTS[key]

    def _course(self, ref: str | int | None) -> dict:
        if ref in (None, ""):
            rows = self.store.all("SELECT * FROM courses WHERE status='active' ORDER BY id DESC")
            if len(rows) == 1:
                return dict(rows[0])
            raise MentorError("specify a course (slug); active courses: "
                              + ", ".join(r["slug"] for r in rows) if rows else "no courses yet")
        row = self.store.course(ref)
        if not row:
            raise MentorError(f"unknown course '{ref}'")
        return dict(row)

    def _dir(self, course: dict) -> Path:
        return self.workspace / "courses" / course["slug"]

    def _graph(self, course_id: int) -> graphmod.Graph:
        nodes = self.store.nodes(course_id)
        if not nodes:
            raise MentorError("this course has no knowledge graph yet; propose one with graph_propose")
        caps = json.loads(self.store.get_meta(f"capabilities:{course_id}") or "[]")
        return graphmod.Graph(nodes, self.store.edges(course_id), caps)

    def _evidence_by_node(self, course_id: int) -> dict[str, list[dict]]:
        out: dict[str, list[dict]] = {}
        for ev in self.store.evidence(course_id):
            out.setdefault(ev["node_id"], []).append(ev)
        return out

    def _refresh(self, course_id: int) -> dict[str, dict]:
        g = self._graph(course_id)
        states = derive_states(g, self._evidence_by_node(course_id), self.params, self.scheduler, now())
        self.store.save_states(course_id, states)
        return states

    def _states(self, course_id: int) -> dict[str, dict]:
        return self._refresh(course_id)  # cheap at this scale; always consistent with `now`

    def _node(self, g: graphmod.Graph, node_id: str) -> dict:
        if node_id not in g.nodes:
            raise MentorError(f"unknown node '{node_id}'")
        return g.nodes[node_id]

    def _add(self, course_id: int, node_id: str, kind: str, **fields: Any) -> int:
        if kind not in EVIDENCE_KINDS:
            raise MentorError(f"unknown evidence kind '{kind}'")
        row = {"course_id": course_id, "node_id": node_id, "kind": kind, "ts": iso(now())}
        row.update({k: v for k, v in fields.items() if v is not None})
        for flag in ("hinted", "idk"):
            if flag in row:
                row[flag] = int(bool(row[flag]))
        return self.store.add_evidence(row)

    def _write_map(self, course: dict, states: dict[str, dict]) -> str:
        g = self._graph(course["id"])
        mermaid = graphmod.to_mermaid(g, {n: s["state"] for n, s in states.items()})
        counts = Counter(s["state"] for s in states.values())
        legend = " · ".join(f"**{k}** {v}" for k, v in sorted(counts.items()))
        md = f"{legend}\n\n```mermaid\n{mermaid}\n```\n"
        page = render_page(md, title=f"Course map: {course['goal']}", subtitle=course["slug"])
        path = self._dir(course) / "graph.html"
        path.write_text(page["html"], encoding="utf-8")
        return str(path)

    # ------------------------------------------------------------------ courses
    def course_create(self, goal: str, slug: str | None = None) -> dict:
        if not goal or not goal.strip():
            raise MentorError("goal is required")
        base = slugify(slug or goal)
        candidate, n = base, 2
        while self.store.course(candidate):
            candidate, n = f"{base}-{n}", n + 1
        cur = self.store.execute("INSERT INTO courses(slug, goal, created_at) VALUES(?,?,?)",
                                 (candidate, goal.strip(), iso(now())))
        course = dict(self.store.course(int(cur.lastrowid)))
        d = self._dir(course)
        for sub in COURSE_SUBDIRS:
            (d / sub).mkdir(parents=True, exist_ok=True)
        return {"course": candidate, "dir": str(d),
                "next": "intake -> profile_write; research -> resources_write; graph_propose; diagnostic"}

    def course_list(self) -> list[dict]:
        out = []
        for r in self.store.all("SELECT * FROM courses ORDER BY id"):
            states = self.store.states(r["id"])
            counts = Counter(s["state"] for s in states.values())
            out.append({"course": r["slug"], "goal": r["goal"], "status": r["status"],
                        "nodes": len(states), "learned": counts["learned"] + counts["mastered"],
                        "mastered": counts["mastered"]})
        return out

    def course_status(self, course: str | None = None) -> dict:
        c = self._course(course)
        d = self._dir(c)
        files = {name: (d / name).exists() for name in
                 ("MISSION.md", "PROFILE.md", "RESOURCES.md", "graph.yaml", "NOTES.md")}
        out: dict[str, Any] = {"course": c["slug"], "goal": c["goal"], "dir": str(d), "files": files}
        if not self.store.nodes(c["id"]):
            out["stage"] = "needs_graph" if files["MISSION.md"] else "needs_intake"
            return out
        states = self._states(c["id"])
        evidence = self._evidence_by_node(c["id"])
        counts = Counter(s["state"] for s in states.values())
        diag_done = any(ev["kind"] == "placement" for evs in evidence.values() for ev in evs) or \
            self.store.get_meta(f"diagnostic_done:{c['id']}") == "1"
        out.update({
            "stage": "learning" if diag_done else "needs_diagnostic",
            "counts": dict(counts),
            "progress": f"{counts['learned'] + counts['mastered']}/{len(states)} learned, "
                        f"{counts['mastered']} mastered",
            "due_reviews": len(fire.due_nodes(states, now())),
            "next": self.next_activity(c["slug"]),
        })
        return out

    # ------------------------------------------------------------------ profile & resources
    def profile_write(self, course: str, mission_md: str | None = None, profile_md: str | None = None,
                      notes_md: str | None = None) -> dict:
        c = self._course(course)
        written = []
        for name, text in (("MISSION.md", mission_md), ("PROFILE.md", profile_md), ("NOTES.md", notes_md)):
            if text is not None:
                if not text.strip():
                    raise MentorError(f"{name} content is empty")
                (self._dir(c) / name).write_text(text.strip() + "\n", encoding="utf-8")
                written.append(name)
        return {"written": written, "dir": str(self._dir(c))}

    def resources_write(self, course: str, resources_md: str) -> dict:
        c = self._course(course)
        if not resources_md.strip():
            raise MentorError("RESOURCES.md content is empty")
        path = self._dir(c) / "RESOURCES.md"
        path.write_text(resources_md.strip() + "\n", encoding="utf-8")
        return {"written": str(path)}

    # ------------------------------------------------------------------ graph
    def _save_graph(self, c: dict, doc: dict) -> dict:
        result = graphmod.validate(doc)
        if not result["ok"]:
            return {"saved": False, **result}
        old_ids = {n["node_id"] for n in self.store.all("SELECT node_id FROM nodes WHERE course_id=?", (c["id"],))}
        self.store.replace_graph(c["id"], doc["nodes"], doc["edges"])
        self.store.set_meta(f"capabilities:{c['id']}", json.dumps(doc.get("capabilities") or []))
        (self._dir(c) / "graph.yaml").write_text(graphmod.dump(doc), encoding="utf-8")
        removed = sorted(old_ids - {n["id"] for n in doc["nodes"]})
        if removed:
            result["warnings"].append(f"removed nodes keep their evidence but are no longer scheduled: {removed}")
        states = self._refresh(c["id"])
        return {"saved": True, **result, "map": self._write_map(c, states)}

    def graph_propose(self, course: str, graph_yaml: str) -> dict:
        c = self._course(course)
        try:
            doc = graphmod.parse(graph_yaml)
        except Exception as exc:  # noqa: BLE001
            return {"saved": False, "ok": False, "errors": [f"YAML parse error: {exc}"], "warnings": []}
        doc.setdefault("goal", c["goal"])
        return self._save_graph(c, doc)

    def _graph_doc(self, c: dict) -> dict:
        path = self._dir(c) / "graph.yaml"
        if not path.exists():
            raise MentorError("no graph.yaml yet")
        return graphmod.parse(path.read_text(encoding="utf-8"))

    def graph_insert_node(self, course: str, node_yaml: str, edges_yaml: str = "[]") -> dict:
        c = self._course(course)
        doc = self._graph_doc(c)
        import yaml

        node = yaml.safe_load(node_yaml)
        edges = yaml.safe_load(edges_yaml) or []
        if not isinstance(node, dict):
            raise MentorError("node_yaml must be a mapping")
        doc["nodes"].append(node)
        doc["edges"].extend(edges if isinstance(edges, list) else [edges])
        return self._save_graph(c, doc)

    def graph_get(self, course: str, view: str = "frontier", node: str | None = None) -> Any:
        c = self._course(course)
        g = self._graph(c["id"])
        states = self._states(c["id"])
        if node:
            n = self._node(g, node)
            s = states[node]
            return {
                "node": n, "state": s["state"], "p_learned": round(s["p_learned"], 3),
                "gate_missing": gate_missing(n, s, self.params) if s["state"] == "learning" else [],
                "due_at": s["due_at"], "prereqs": g.prereqs(node), "dependents": g.dependents(node),
                "encompasses": g.encompassed_by(node),
            }
        if view == "full":
            return (self._dir(c) / "graph.yaml").read_text(encoding="utf-8")
        if view == "mermaid":
            return graphmod.to_mermaid(g, {n: s["state"] for n, s in states.items()})
        if view != "frontier":
            raise MentorError("view must be frontier, full or mermaid")
        frontier = [
            {"id": nid, "title": g.nodes[nid]["title"], "state": s["state"],
             "objective": g.nodes[nid]["objective"], "type": g.nodes[nid]["type"]}
            for nid in g.topo() if (s := states[nid])["state"] in ("ready", "learning", "rusty")
        ]
        return {"capabilities": g.capabilities, "frontier": frontier,
                "counts": dict(Counter(s["state"] for s in states.values()))}

    # ------------------------------------------------------------------ diagnostic
    def diagnostic_next(self, course: str) -> dict:
        c = self._course(course)
        g = self._graph(c["id"])
        return diag.next_probe(g, self._evidence_by_node(c["id"]),
                               self.config_value("diagnostic_max_questions"))

    def diagnostic_record(self, course: str, node: str, score: float, item_id: str | None = None,
                          idk: bool = False, confidence: int | None = None) -> dict:
        c = self._course(course)
        g = self._graph(c["id"])
        self._node(g, node)
        self._add(c["id"], node, "diagnostic", item_id=item_id, score=float(score), idk=idk,
                  confidence=confidence)
        passed = (not idk) and float(score) >= self.params.pass_score
        weak = confidence is not None and confidence <= 2
        for row in diag.inference_rows(g, node, passed, weak):
            self._add(c["id"], row.pop("node_id"), row.pop("kind"), **row)
        nxt = self.diagnostic_next(c["slug"])
        return {"recorded": {"node": node, "passed": passed}, "next": nxt}

    def diagnostic_finish(self, course: str) -> dict:
        c = self._course(course)
        g = self._graph(c["id"])
        states = self._refresh(c["id"])
        rows = diag.placement_rows(g, states)
        for row in rows:
            self._add(c["id"], row.pop("node_id"), row.pop("kind"), **row)
        self.store.set_meta(f"diagnostic_done:{c['id']}", "1")
        states = self._refresh(c["id"])
        self._write_map(c, states)
        counts = Counter(s["state"] for s in states.values())
        return {"known": [r for r in sorted(n for n, s in states.items() if s["state"] == "mastered")],
                "ready": sorted(n for n, s in states.items() if s["state"] == "ready"),
                "counts": dict(counts), "next": self.next_activity(c["slug"])}

    # ------------------------------------------------------------------ items
    def item_save(self, course: str, node: str, item: dict | str) -> dict:
        c = self._course(course)
        g = self._graph(c["id"])
        self._node(g, node)
        if isinstance(item, str):
            item = json.loads(item)
        for field in ("prompt", "form", "answer_key"):
            if not item.get(field):
                raise MentorError(f"item needs '{field}'")
        item_id = item.get("item_id") or f"{node}#{secrets.token_hex(3)}"
        self.store.execute(
            "INSERT OR REPLACE INTO items(item_id,course_id,node_id,form,bloom,prompt,answer_key,rubric,"
            "misconception_map,purpose,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (item_id, c["id"], node, item["form"], item.get("bloom") or g.nodes[node]["bloom"],
             item["prompt"], json.dumps(item["answer_key"], ensure_ascii=False),
             json.dumps(item.get("rubric"), ensure_ascii=False) if item.get("rubric") else None,
             json.dumps(item.get("misconception_map"), ensure_ascii=False) if item.get("misconception_map") else None,
             item.get("purpose", "practice"), iso(now())),
        )
        return {"item_id": item_id}

    def item_get(self, course: str, item_id: str, include_key: bool = False) -> dict:
        c = self._course(course)
        row = self.store.one("SELECT * FROM items WHERE item_id=? AND course_id=?", (item_id, c["id"]))
        if not row:
            raise MentorError(f"unknown item '{item_id}'")
        out = {k: row[k] for k in ("item_id", "node_id", "form", "bloom", "prompt", "purpose")}
        if include_key:
            for k in ("answer_key", "rubric", "misconception_map"):
                out[k] = json.loads(row[k]) if row[k] else None
        return out

    def items_list(self, course: str, node: str | None = None) -> list[dict]:
        c = self._course(course)
        sql = "SELECT item_id,node_id,form,bloom,purpose,prompt FROM items WHERE course_id=? AND retired=0"
        params: list[Any] = [c["id"]]
        if node:
            sql += " AND node_id=?"
            params.append(node)
        return [dict(r) for r in self.store.all(sql + " ORDER BY created_at", params)]

    # ------------------------------------------------------------------ evidence
    def evidence_record(self, course: str, node: str, kind: str, score: float | None = None,
                        item_id: str | None = None, form: str | None = None, bloom: str | None = None,
                        hinted: bool = False, hint_level: int = 0, idk: bool = False,
                        confidence: int | None = None, latency_s: float | None = None,
                        misconceptions: list[str] | None = None, grader_version: str | None = None,
                        rationale: str | None = None, n_options: int | None = None,
                        taught_with: dict | None = None) -> dict:
        """``taught_with`` names the explanation the learner just had (learner_model dims, e.g.
        ``{"angle": "geometric", "format": "interactive"}``); it feeds an outcome signal."""
        if kind not in SCORED_KINDS + ("told",):
            raise MentorError(f"kind must be one of {SCORED_KINDS + ('told',)}")
        if kind != "told" and score is None and not idk:
            raise MentorError("score (0..1) is required unless idk is true")
        if score is not None and not 0 <= float(score) <= 1:
            raise MentorError("score must be between 0 and 1")
        c = self._course(course)
        g = self._graph(c["id"])
        n = self._node(g, node)
        if item_id:
            item = self.store.one("SELECT form, bloom FROM items WHERE item_id=?", (item_id,))
            if item:
                form, bloom = form or item["form"], bloom or item["bloom"]
        try:
            taught = learner_model.validate_dims(taught_with) if taught_with else {}
        except ValueError as exc:
            raise MentorError(f"taught_with: {exc}") from exc
        before = self._states(c["id"])
        baseline = self._score_baseline(c["id"])
        meta = {k: v for k, v in (("n_options", n_options), ("taught_with", taught or None)) if v}
        ev_id = self._add(c["id"], node, kind, item_id=item_id, score=None if score is None else float(score),
                          form=form, bloom=bloom, hinted=hinted, hint_level=hint_level, idk=idk,
                          confidence=confidence, latency_s=latency_s, misconceptions=misconceptions,
                          grader_version=grader_version, rationale=rationale,
                          meta=meta or None)
        if taught and kind in OUTCOME_KINDS:
            effective = 0.0 if idk else float(score or 0) - (0.2 * max(1, hint_level) if hinted else 0)
            self._signal("outcome", course_id=c["id"], node_id=node, dims=taught,
                         valence=max(-1.0, min(1.0, 2 * (effective - baseline))),
                         target=f"evidence {ev_id}")
        if kind != "told":
            s = float(score or 0)
            passed = not idk and not hinted and s >= self.params.pass_score
            failed = idk or s < 0.5
            for row in fire.implicit_rows(g, node, passed, failed, before):
                self._add(c["id"], row.pop("node_id"), row.pop("kind"), **row)
        states = self._refresh(c["id"])
        s_new, s_old = states[node], before[node]
        evs = self._evidence_by_node(c["id"]).get(node, [])
        result: dict[str, Any] = {
            "evidence_id": ev_id, "node": node, "state": s_new["state"],
            "previous_state": s_old["state"], "p_learned": round(s_new["p_learned"], 3),
            "mastered": s_new["state"] == "mastered", "due_at": s_new["due_at"],
        }
        if s_new["state"] == "learning":
            result["gate_missing"] = gate_missing(n, s_new, self.params)
        if kind == "told":
            result["next_action"] = "explain the why, then give an isomorphic item for the learner to solve alone"
        elif s_old["state"] != s_new["state"] and s_new["state"] == "learned":
            result["next_action"] = "gate passed: run the close-out (learner summary, confidence, record, render)"
        elif s_new["state"] == "mastered" and s_old["state"] != "mastered":
            result["next_action"] = "confirmed at delayed review: node mastered"
        elif s_new["state"] == "rusty":
            result["next_action"] = "forgotten: re-teach briefly, then re-practice this node"
        elif s_new["state"] == "learning" and should_halt(evs, self.params):
            if failure_count(evs, self.params) >= self.params.insert_prereq_failures:
                result["next_action"] = "suggest_insert_prereq: propose a missing prerequisite via graph_insert_node"
            else:
                target = planner.weakest_prereq(g, node, states)
                result["next_action"] = (f"halt_and_remediate: stop this lesson and strengthen '{target}' first"
                                         if target else "halt: switch to a simpler worked example, then retry")
                result["remediate"] = target
        else:
            result["next_action"] = "continue"
        return result

    def evidence_void(self, course: str, evidence_id: int, reason: str) -> dict:
        c = self._course(course)
        row = self.store.one("SELECT node_id FROM evidence WHERE id=? AND course_id=?", (evidence_id, c["id"]))
        if not row:
            raise MentorError(f"unknown evidence id {evidence_id}")
        self.store.execute("UPDATE evidence SET voided=1, rationale=COALESCE(rationale,'') || ? WHERE id=?",
                           (f" [voided: {reason}]", evidence_id))
        states = self._refresh(c["id"])
        s = states[row["node_id"]]
        return {"voided": evidence_id, "node": row["node_id"], "state": s["state"],
                "p_learned": round(s["p_learned"], 3)}

    def node_defer(self, course: str, node: str, days: float = 3, reason: str = "") -> dict:
        c = self._course(course)
        self._node(self._graph(c["id"]), node)
        until = iso(now() + timedelta(days=float(days)))
        self._add(c["id"], node, "defer", meta={"until": until, "reason": reason})
        return {"node": node, "deferred_until": until, "state": self._refresh(c["id"])[node]["state"]}

    # ------------------------------------------------------------------ planning
    def next_activity(self, course: str | None = None) -> dict:
        c = self._course(course)
        g = self._graph(c["id"])
        states = self._states(c["id"])
        act = planner.next_activity(g, states, self._evidence_by_node(c["id"]), self.params, now(),
                                    self.config_value("review_budget"))
        for key in ("node", "blocked"):
            if act.get(key):
                act[f"{key}_title"] = g.nodes[act[key]]["title"]
        return act

    def review_queue(self, course: str | None = None) -> list[dict]:
        rows = [self._course(course)] if course else \
            [dict(r) for r in self.store.all("SELECT * FROM courses WHERE status='active'")]
        out = []
        for c in rows:
            if not self.store.nodes(c["id"]):
                continue
            g = self._graph(c["id"])
            states = self._states(c["id"])
            picks = fire.select_reviews(g, states, now(), self.config_value("review_budget"))
            due = fire.due_nodes(states, now())
            if due:
                out.append({"course": c["slug"], "due": len(due), "selection": picks,
                            "oldest_due": min(states[n]["due_at"] for n in due)})
        return out

    # ------------------------------------------------------------------ lessons
    def lesson_save(self, course: str, node: str, lesson_md: str, pack: dict | str,
                    sources: list[dict] | str | None = None, title: str | None = None,
                    render: str = "auto") -> dict:
        """``render``: auto (HTML only when the lesson has something markdown can't show:
        plots, JSXGraph boards, quiz blocks or explorables), always, or never."""
        if render not in ("auto", "always", "never"):
            raise MentorError("render must be auto, always or never")
        c = self._course(course)
        g = self._graph(c["id"])
        n = self._node(g, node)
        pack = json.loads(pack) if isinstance(pack, str) else pack
        sources = json.loads(sources) if isinstance(sources, str) else (sources or [])
        existing = self.store.one("SELECT * FROM lessons WHERE course_id=? AND node_id=?", (c["id"], node))
        if existing:
            lesson_id, version = existing["lesson_id"], existing["version"] + 1
        else:
            count = self.store.one("SELECT COUNT(*) AS k FROM lessons WHERE course_id=?", (c["id"],))["k"]
            lesson_id, version = f"{count + 1:04d}-{node}", 1
        d = self._dir(c) / "lessons" / lesson_id
        d.mkdir(parents=True, exist_ok=True)
        (d / "lesson.md").write_text(lesson_md.strip() + "\n", encoding="utf-8")
        (d / "pack.json").write_text(json.dumps(pack, indent=2, ensure_ascii=False), encoding="utf-8")
        (d / "sources.json").write_text(json.dumps(sources, indent=2, ensure_ascii=False), encoding="utf-8")
        meta_path = d / "meta.json"
        old_meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        meta_path.write_text(json.dumps({"title": title or n["title"], "node": node, "version": version,
                                         "explorables": old_meta.get("explorables", [])},
                                        indent=2, ensure_ascii=False), encoding="utf-8")
        self.store.execute(
            "INSERT OR REPLACE INTO lessons(lesson_id,course_id,node_id,dir,version,created_at) VALUES(?,?,?,?,?,?)",
            (lesson_id, c["id"], node, str(d), version, iso(now())),
        )
        saved_items = []
        for item in pack.get("items") or []:
            saved_items.append(self.item_save(c["slug"], node, item)["item_id"])
        out = {"lesson_id": lesson_id, "version": version, "dir": str(d), "lesson_md": str(d / "lesson.md"),
               "items_saved": saved_items}
        features = set(render_page(lesson_md, title="")["features"])
        if render == "always" or (render == "auto" and (features & INTERACTIVE_FEATURES
                                                        or any(d.glob("explore-*.html")))):
            return {**out, **self.lesson_render(c["slug"], lesson_id)}
        stale = d / "lesson.html"
        if stale.exists():
            stale.unlink()
        return {**out, "html": None, "features": sorted(features),
                "render_skipped": "plain-markdown lesson: lesson.md is the reference copy"}

    def lesson_render(self, course: str, lesson_id: str | None = None, node: str | None = None,
                      open_browser: bool = False) -> dict:
        c = self._course(course)
        rows = [dict(r) for r in self.store.all(
            "SELECT * FROM lessons WHERE course_id=? ORDER BY lesson_id", (c["id"],))]
        if node and not lesson_id:
            lesson_id = next((r["lesson_id"] for r in rows if r["node_id"] == node), None)
        idx = next((i for i, r in enumerate(rows) if r["lesson_id"] == lesson_id), None)
        if idx is None:
            raise MentorError(f"unknown lesson '{lesson_id or node}'")
        row = rows[idx]
        d = Path(row["dir"])
        meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        sources = json.loads((d / "sources.json").read_text(encoding="utf-8"))
        nav = {"map": "../../graph.html"}

        def link(r: dict) -> str:  # neighbours may be plain-markdown lessons without HTML
            name = "lesson.html" if (Path(r["dir"]) / "lesson.html").exists() else "lesson.md"
            return f"../{r['lesson_id']}/{name}"

        if idx > 0:
            nav["prev"] = link(rows[idx - 1])
        if idx + 1 < len(rows):
            nav["next"] = link(rows[idx + 1])
        page = render_page((d / "lesson.md").read_text(encoding="utf-8"), title=meta["title"],
                           subtitle=c["goal"], sources=sources, nav=nav)
        out = d / "lesson.html"
        out.write_text(page["html"], encoding="utf-8")
        if open_browser:
            webbrowser.open(out.as_uri())
        return {"html": str(out), "features": page["features"], "problems": smoke_check(page["html"])}

    def render_markdown(self, course: str, markdown: str, title: str, filename: str,
                        open_browser: bool = False) -> dict:
        """Render a reference page (cheat sheet, glossary, explainer) into reference/<filename>.html."""
        c = self._course(course)
        stem = slugify(Path(filename).stem, 60)
        d = self._dir(c) / "reference"
        d.mkdir(exist_ok=True)
        (d / f"{stem}.md").write_text(markdown.strip() + "\n", encoding="utf-8")
        page = render_page(markdown, title=title, subtitle=c["goal"], nav={"map": "../graph.html"})
        out = d / f"{stem}.html"
        out.write_text(page["html"], encoding="utf-8")
        if open_browser:
            webbrowser.open(out.as_uri())
        return {"html": str(out), "md": str(d / f"{stem}.md"), "problems": smoke_check(page["html"])}

    def explorable_save(self, course: str, node: str, name: str, html_text: str, question: str) -> dict:
        """Validate and store a bespoke interactive page next to a lesson (pedagogy/VISUALS.md, level 3).

        Not saved when it fails a check: unbalanced markup, resources from hosts other than the
        pinned CDNs, network calls, a missing <title>, or a size over 2 MB.
        """
        c = self._course(course)
        row = self.store.one("SELECT * FROM lessons WHERE course_id=? AND node_id=?", (c["id"], node))
        if not row:
            raise MentorError(f"save the lesson for '{node}' first (lesson_save)")
        if not question.strip():
            raise MentorError("question is required: the one thing this explorable lets the learner see")
        problems = smoke_check(html_text)
        if len(html_text.encode("utf-8")) > EXPLORABLE_MAX_BYTES:
            problems.append("larger than 2 MB")
        if not re.search(r"<title>[^<]+</title>", html_text, re.I):
            problems.append("missing <title>")
        for url in re.findall(r"""(?:src|href)\s*=\s*["'](https?://[^"']+)""", html_text, re.I):
            host = url.split("/")[2].lower()
            if host not in EXPLORABLE_HOSTS:
                problems.append(f"external resource from a non-allowlisted host: {host}")
            elif "@" not in url:
                problems.append(f"unpinned CDN version: {url}")
        if re.search(r"\b(fetch|XMLHttpRequest|WebSocket|sendBeacon)\s*\(", html_text):
            problems.append("makes network calls; explorables must be self-contained")
        if problems:
            return {"saved": False, "problems": problems}
        d = Path(row["dir"])
        filename = f"explore-{slugify(name, 40)}.html"
        (d / filename).write_text(html_text, encoding="utf-8")
        meta_path = d / "meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        entries = [e for e in meta.get("explorables", []) if e["file"] != filename]
        meta["explorables"] = entries + [{"file": filename, "question": question.strip()}]
        meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        return {"saved": True, "path": str(d / filename),
                "markdown_link": f"[Explore: {question.strip()}]({filename})",
                "next": "add markdown_link to lesson.md on disk, then lesson_render(course, node=...)"}

    # ------------------------------------------------------------------ learner model
    def _score_baseline(self, course_id: int) -> float:
        """The learner's recent typical score here, so outcome signals are relative to them."""
        scores = [0.0 if ev["idk"] else float(ev["score"] or 0) for ev in self.store.evidence(course_id)
                  if ev["kind"] in OUTCOME_KINDS and (ev["score"] is not None or ev["idk"])][-30:]
        return sum(scores) / len(scores) if len(scores) >= 3 else 0.7

    def _signal(self, kind: str, **fields: Any) -> int:
        row = {"kind": kind, "ts": iso(now())}
        row.update({k: v for k, v in fields.items() if v not in (None, {}, "")})
        sid = self.store.add_signal(row)
        self._write_learner_md()
        return sid

    def _known_elsewhere(self) -> list[dict]:
        rows = self.store.all(
            "SELECT c.slug, n.title, n.node_id, s.state FROM node_state s "
            "JOIN nodes n ON n.course_id=s.course_id AND n.node_id=s.node_id "
            "JOIN courses c ON c.id=s.course_id WHERE s.state IN ('learned','mastered','rusty') "
            "ORDER BY c.id, n.node_id")
        return [{"course": r["slug"], "node": r["node_id"], "title": r["title"], "state": r["state"]}
                for r in rows]

    def _model(self) -> dict:
        return learner_model.build(self.store.signals(), now(), self._known_elsewhere())

    def _write_learner_md(self) -> Path:
        path = self.workspace / LEARNER_FILE
        path.write_text(learner_model.to_markdown(self._model()), encoding="utf-8")
        return path

    def learner_signal(self, kind: str, dims: dict | None = None, valence: float | None = None,
                       adjust: dict | None = None, target: str | None = None, note: str | None = None,
                       course: str | None = None, node: str | None = None, weight: float = 1.0) -> dict:
        if kind not in learner_model.SIGNAL_KINDS or kind == "outcome":
            raise MentorError("kind must be fact, stated or reaction (outcomes come from evidence_record)")
        try:
            dims = learner_model.validate_dims(dims)
            adjust = learner_model.validate_adjust(adjust)
        except ValueError as exc:
            raise MentorError(str(exc)) from exc
        if kind == "fact" and not (note or "").strip():
            raise MentorError("a fact needs note: what the learner said about themselves")
        if kind != "fact" and not dims and not adjust:
            raise MentorError("give dims (what it was about) and/or adjust (pace, depth, ...)")
        if dims and valence is None:
            raise MentorError("valence (-1 did not help .. 1 helped) is required with dims")
        if valence is not None and not -1 <= float(valence) <= 1:
            raise MentorError("valence must be between -1 and 1")
        if not 0 < float(weight) <= 3:
            raise MentorError("weight must be in (0, 3]")
        course_id = self._course(course)["id"] if course else None
        sid = self._signal(kind, course_id=course_id, node_id=node, dims=dims,
                           valence=None if valence is None else float(valence), adjust=adjust,
                           target=target, note=(note or "").strip(), weight=float(weight))
        return {"signal_id": sid, "guidance": self._model()["guidance"],
                "learner_md": str(self.workspace / LEARNER_FILE)}

    def learner_signal_void(self, signal_id: int, reason: str) -> dict:
        if not self.store.one("SELECT id FROM signals WHERE id=? AND voided=0", (signal_id,)):
            raise MentorError(f"no active signal {signal_id}")
        self.store.execute("UPDATE signals SET voided=1, note=COALESCE(note,'') || ? WHERE id=?",
                           (f" [voided: {reason}]", signal_id))
        self._write_learner_md()
        return {"voided": signal_id, "guidance": self._model()["guidance"]}

    def learner_reset(self, reason: str) -> dict:
        """Forget the learner model (voids every signal; course knowledge is untouched)."""
        n = self.store.execute("UPDATE signals SET voided=1, note=COALESCE(note,'') || ? WHERE voided=0",
                               (f" [reset: {reason}]",)).rowcount
        self._write_learner_md()
        return {"voided": n}

    def learner_model(self, detail: bool = False) -> dict:
        """The learner model; without ``detail`` it is trimmed to what a lesson author needs.
        With ``detail`` it includes the latest signals (ids for corrections)."""
        model = self._model()
        path = self._write_learner_md()
        if detail:
            model["signal_log"] = [
                {k: s[k] for k in ("id", "ts", "kind", "target", "dims", "valence", "adjust", "note")}
                for s in self.store.signals()[-100:][::-1]]
        else:
            model["unclear"] = model["unclear"][:5]
            model["known_elsewhere"] = model["known_elsewhere"][:40]
        return {**model, "learner_md": str(path)}

    # ------------------------------------------------------------------ tools
    def check_math(self, expr_a: str, expr_b: str, variables: list[str] | None = None) -> dict:
        from .verify_math import check_math as _check_math  # SymPy is slow to import: load on first use

        return _check_math(expr_a, expr_b, variables)

    def progress(self, course: str | None = None, fmt: str = "md", open_browser: bool = False) -> dict:
        c = self._course(course)
        g = self._graph(c["id"])
        states = self._states(c["id"])
        evidence = self.store.evidence(c["id"])
        t = now()
        counts = Counter(s["state"] for s in states.values())
        total = len(states)
        retained = counts["learned"] + counts["mastered"]
        forecast = Counter()
        for s in states.values():
            if s["state"] in ("learned", "mastered") and s.get("due_at"):
                days = (parse_ts(s["due_at"]) - t).total_seconds() / 86400
                if days <= 7:
                    forecast[max(0, int(days + 0.999)) if days > 0 else 0] += 1
        calib: dict[int, list[float]] = {}
        for ev in evidence:
            if ev["kind"] in SCORED_KINDS and ev["confidence"] and not ev["idk"]:
                calib.setdefault(int(ev["confidence"]), []).append(1.0 if (ev["score"] or 0) >= 0.8 else 0.0)
        calibration = {k: {"n": len(v), "accuracy": round(sum(v) / len(v), 2)} for k, v in sorted(calib.items())}
        days_active = sorted({parse_ts(ev["ts"]).date() for ev in evidence if ev["kind"] in SCORED_KINDS},
                             reverse=True)
        streak, day = 0, t.date()
        for d in days_active:
            if d == day or (streak == 0 and d == day - timedelta(days=1)):
                streak, day = streak + 1, d - timedelta(days=1)
            elif d < day:
                break
        caps = []
        for cap in g.capabilities:
            serving = [n for n, node in g.nodes.items() if cap["id"] in (node.get("serves") or [])]
            needed = set(serving) | set().union(*(g.ancestors(n) for n in serving)) if serving else set()
            done = sum(1 for n in needed if states[n]["state"] in RETAINED)
            caps.append({"id": cap["id"], "statement": cap["statement"], "done": done, "total": len(needed)})
        summary = {
            "course": c["slug"], "goal": c["goal"], "counts": dict(counts),
            "percent_learned": round(100 * retained / total, 1) if total else 0.0,
            "due_now": len(fire.due_nodes(states, t)), "due_next_7_days": dict(sorted(forecast.items())),
            "calibration": calibration, "streak_days": streak, "capabilities": caps,
        }
        map_path = self._write_map(c, states)
        summary["map_html"] = map_path
        if fmt == "html":
            lines = [f"**{summary['percent_learned']}% learned** · {counts['mastered']} mastered · "
                     f"{summary['due_now']} reviews due · streak {streak} day(s)", "", "## Capabilities", ""]
            lines += [f"- {cp['statement']}: {cp['done']}/{cp['total']}" for cp in caps] or ["- (none defined)"]
            lines += ["", "## Map", "", "```mermaid",
                      graphmod.to_mermaid(g, {n: s["state"] for n, s in states.items()}), "```", "",
                      "## Calibration (confidence → accuracy)", "", "| confidence | answers | accuracy |",
                      "|---|---|---|"]
            lines += [f"| {k} | {v['n']} | {v['accuracy']:.0%} |" for k, v in calibration.items()]
            page = render_page("\n".join(lines), title=f"Progress: {c['goal']}", subtitle=iso(t)[:10])
            out = self._dir(c) / "progress.html"
            out.write_text(page["html"], encoding="utf-8")
            summary["progress_html"] = str(out)
            if open_browser:
                webbrowser.open(out.as_uri())
        return summary

    def export_anki(self, course: str | None = None) -> dict:
        c = self._course(course)
        states = self._states(c["id"])
        nodes = [n for n, s in states.items() if s["state"] in RETAINED]
        if not nodes:
            raise MentorError("nothing learned yet to export")
        marks = ",".join("?" for _ in nodes)
        items = [dict(r) for r in self.store.all(
            f"SELECT * FROM items WHERE course_id=? AND retired=0 AND node_id IN ({marks})", [c["id"], *nodes])]
        from .export_anki import build_deck  # genanki: load on first use

        return build_deck(c["slug"], c["goal"], items, self._dir(c) / "exports" / f"{c['slug']}.apkg")

    def rebuild_state(self, course: str | None = None) -> dict:
        rows = [self._course(course)] if course else [dict(r) for r in self.store.all("SELECT * FROM courses")]
        done = []
        for c in rows:
            if self.store.nodes(c["id"]):
                self.store.execute("DELETE FROM node_state WHERE course_id=?", (c["id"],))
                self._refresh(c["id"])
                done.append(c["slug"])
        return {"rebuilt": done}

    def config(self, key: str | None = None, value: str | None = None) -> dict:
        if key == "workspace":
            if value:
                write_pointer(Path(value).expanduser().resolve())
                return {"workspace": str(Path(value).expanduser().resolve()),
                        "note": "takes effect when the MCP server restarts (/reload-plugins or new session)"}
            return {"workspace": str(self.workspace)}
        if key is not None and key not in CONFIG_KEYS:
            raise MentorError(f"unknown config key '{key}'; known: workspace, {', '.join(CONFIG_KEYS)}")
        if key and value is not None:
            CONFIG_KEYS[key](value)  # validate type
            self.store.set_meta(f"config:{key}", str(value))
            if key == "desired_retention":
                self.params = replace(self.params, desired_retention=float(value))
                self.scheduler = make_scheduler(float(value))
        return {"workspace": str(self.workspace), **{k: self.config_value(k) for k in CONFIG_KEYS}}
