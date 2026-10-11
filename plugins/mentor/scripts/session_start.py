"""SessionStart hook: tell Claude about due reviews and the active course.

Standard library only, read-only, and silent on any problem: a broken hook must never
get in the way of a session. Prints the hook JSON (or nothing) and exits 0.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


def _now() -> datetime:
    override = os.environ.get("MENTOR_NOW")
    if override:
        ts = datetime.fromisoformat(override.replace("Z", "+00:00"))
        return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def _workspace(plugin_data: str | None) -> Path | None:
    candidates = [os.environ.get("MENTOR_WORKSPACE"), os.environ.get("CLAUDE_PLUGIN_OPTION_WORKSPACE_DIR")]
    for value in candidates:
        if value and "${" not in value:
            return Path(value).expanduser()
    data_dir = plugin_data or os.environ.get("CLAUDE_PLUGIN_DATA")
    if data_dir and "${" not in data_dir:
        try:
            pointer = json.loads((Path(data_dir) / "pointer.json").read_text(encoding="utf-8"))
            if pointer.get("workspace"):
                return Path(pointer["workspace"])
        except (OSError, ValueError):
            pass
    default = Path("~/Mentor").expanduser()
    return default if default.exists() else None


def summarize(db: Path, now: datetime) -> str | None:
    conn = sqlite3.connect(f"{db.as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT c.slug, c.goal, s.state, s.due_at FROM courses c "
            "JOIN node_state s ON s.course_id = c.id WHERE c.status = 'active'"
        ).fetchall()
        last = conn.execute(
            "SELECT c.slug FROM evidence e JOIN courses c ON c.id = e.course_id "
            "ORDER BY e.ts DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    if not rows:
        return None
    courses: dict[str, dict] = {}
    for r in rows:
        c = courses.setdefault(r["slug"], {"goal": r["goal"], "total": 0, "learned": 0, "mastered": 0,
                                           "due": 0, "oldest": None})
        c["total"] += 1
        if r["state"] in ("learned", "mastered"):
            c["learned"] += 1
            if r["state"] == "mastered":
                c["mastered"] += 1
            if r["due_at"]:
                due = datetime.fromisoformat(r["due_at"])
                if due <= now:
                    c["due"] += 1
                    c["oldest"] = min(c["oldest"] or due, due)
    active = last["slug"] if last and last["slug"] in courses else next(iter(courses))
    parts = []
    for slug, c in sorted(courses.items(), key=lambda kv: kv[0] != active):
        line = f"{c['goal']} [{slug}]: {c['learned']}/{c['total']} learned, {c['mastered']} mastered"
        if c["due"]:
            days = (now - c["oldest"]).days
            line += f"; {c['due']} review(s) due" + (f" (oldest {days}d overdue)" if days >= 1 else "")
        parts.append(line)
    total_due = sum(c["due"] for c in courses.values())
    hint = (f" Suggest /mentor:review before new material ({total_due} due)." if total_due
            else " Nothing due; /mentor:next continues the active course.")
    return "[mentor] " + " | ".join(parts) + "." + hint


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plugin-data")
    args, _ = parser.parse_known_args()
    try:
        ws = _workspace(args.plugin_data)
        db = ws / "mentor.db" if ws else None
        if not db or not db.exists():
            return 0
        text = summarize(db, _now())
        if text:
            json.dump({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}},
                      sys.stdout)
    except Exception:  # noqa: BLE001 - never break the session
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
