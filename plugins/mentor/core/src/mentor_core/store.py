"""SQLite access layer. Thin on purpose: no pedagogy logic lives here."""

from __future__ import annotations

import json
import sqlite3
from importlib import resources
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = 1


class Store:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._migrate()

    def _migrate(self) -> None:
        schema = resources.files("mentor_core").joinpath("schema.sql").read_text(encoding="utf-8")
        with self.conn:
            self.conn.executescript(schema)
            self.conn.execute(
                "INSERT OR IGNORE INTO meta(key, value) VALUES('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )

    def close(self) -> None:
        self.conn.close()

    # -- generic helpers -------------------------------------------------
    def one(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
        return self.conn.execute(sql, tuple(params)).fetchone()

    def all(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        return self.conn.execute(sql, tuple(params)).fetchall()

    def execute(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        with self.conn:
            return self.conn.execute(sql, tuple(params))

    def get_meta(self, key: str, default: str | None = None) -> str | None:
        row = self.one("SELECT value FROM meta WHERE key=?", (key,))
        return row["value"] if row else default

    def set_meta(self, key: str, value: str) -> None:
        self.execute("INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)", (key, value))

    # -- courses ------------------------------------------------------------
    def course(self, ref: str | int) -> sqlite3.Row | None:
        if isinstance(ref, int) or (isinstance(ref, str) and ref.isdigit()):
            return self.one("SELECT * FROM courses WHERE id=?", (int(ref),))
        return self.one("SELECT * FROM courses WHERE slug=?", (ref,))

    # -- graph --------------------------------------------------------------
    def replace_graph(self, course_id: int, nodes: list[dict], edges: list[dict]) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM nodes WHERE course_id=?", (course_id,))
            self.conn.execute("DELETE FROM edges WHERE course_id=?", (course_id,))
            self.conn.executemany(
                "INSERT INTO nodes(course_id,node_id,title,type,tier,bloom,minutes,data) "
                "VALUES(?,?,?,?,?,?,?,?)",
                [
                    (course_id, n["id"], n["title"], n["type"], n["tier"], n["bloom"],
                     int(n["minutes"]), json.dumps(n, ensure_ascii=False))
                    for n in nodes
                ],
            )
            self.conn.executemany(
                "INSERT INTO edges(course_id,src,dst,kind,weight) VALUES(?,?,?,?,?)",
                [(course_id, e["from"], e["to"], e["kind"], e.get("weight")) for e in edges],
            )

    def nodes(self, course_id: int) -> list[dict]:
        return [json.loads(r["data"]) for r in
                self.all("SELECT data FROM nodes WHERE course_id=? ORDER BY node_id", (course_id,))]

    def edges(self, course_id: int) -> list[dict]:
        return [
            {"from": r["src"], "to": r["dst"], "kind": r["kind"], "weight": r["weight"]}
            for r in self.all("SELECT * FROM edges WHERE course_id=?", (course_id,))
        ]

    # -- evidence -----------------------------------------------------------
    def add_evidence(self, row: dict) -> int:
        row = dict(row)
        for key in ("misconceptions", "meta"):
            if key in row and not isinstance(row[key], (str, type(None))):
                row[key] = json.dumps(row[key], ensure_ascii=False)
        cols = ",".join(row)
        marks = ",".join("?" for _ in row)
        cur = self.execute(f"INSERT INTO evidence({cols}) VALUES({marks})", row.values())
        return int(cur.lastrowid)

    def evidence(self, course_id: int, node_id: str | None = None,
                 include_voided: bool = False) -> list[dict]:
        sql = "SELECT * FROM evidence WHERE course_id=?"
        params: list[Any] = [course_id]
        if node_id is not None:
            sql += " AND node_id=?"
            params.append(node_id)
        if not include_voided:
            sql += " AND voided=0"
        sql += " ORDER BY ts, id"
        out = []
        for r in self.all(sql, params):
            d = dict(r)
            d["misconceptions"] = json.loads(d["misconceptions"]) if d["misconceptions"] else []
            d["meta"] = json.loads(d["meta"]) if d["meta"] else {}
            out.append(d)
        return out

    # -- node state ---------------------------------------------------------
    def save_states(self, course_id: int, states: dict[str, dict]) -> None:
        cols = ["state", "p_learned", "indep_correct", "forms_seen", "bloom_reached",
                "misconception_passed", "explain_passed", "learned_at", "mastered_at",
                "last_retrieval", "fsrs_card", "due_at", "deferred_until", "check_flag"]
        with self.conn:
            for node_id, s in states.items():
                values = [s.get(c) for c in cols]
                values[cols.index("forms_seen")] = json.dumps(sorted(s.get("forms_seen") or []))
                self.conn.execute(
                    f"INSERT OR REPLACE INTO node_state(course_id,node_id,{','.join(cols)}) "
                    f"VALUES(?,?,{','.join('?' for _ in cols)})",
                    [course_id, node_id, *values],
                )

    def states(self, course_id: int) -> dict[str, dict]:
        out = {}
        for r in self.all("SELECT * FROM node_state WHERE course_id=?", (course_id,)):
            d = dict(r)
            d["forms_seen"] = json.loads(d["forms_seen"] or "[]")
            out[d["node_id"]] = d
        return out
