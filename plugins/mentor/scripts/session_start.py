"""SessionStart hook: tell Claude about due reviews and the active course, and warm up the
engine's environment in the background.

Standard library only and silent on any problem: a broken hook must never get in the way of
a session. Prints the hook JSON (or nothing) and exits 0.

Warm-up: Claude Code gives an MCP server 30 s to start, and a plugin can't raise that. The very
first start of the Mentor engine can exceed it (uv downloads packages, Python compiles them).
So the hook starts a detached ``uv sync`` + one import of the server, which leaves the
environment ready, and records the uv.lock hash it warmed so later sessions skip the work.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
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


WARM_MARKER = "warm.json"
# Imports the server once (compiling it), then records which uv.lock it warmed.
WARM_CODE = ("import json, pathlib, sys, mentor_core.mcp_server; "
             "pathlib.Path(sys.argv[1]).write_text(json.dumps({'lock': sys.argv[2]}), encoding='utf-8')")


def _usable(path: str | None) -> bool:
    return bool(path) and "${" not in path


def lock_hash(plugin_root: Path) -> str | None:
    try:
        return hashlib.sha256((plugin_root / "core" / "uv.lock").read_bytes()).hexdigest()[:16]
    except OSError:
        return None


def needs_warm(plugin_root: Path, plugin_data: Path) -> str | None:
    """The uv.lock hash to warm, or None when the environment is already warm (or can't be)."""
    digest = lock_hash(plugin_root)
    if not digest:
        return None
    try:
        warmed = json.loads((plugin_data / WARM_MARKER).read_text(encoding="utf-8")).get("lock")
    except (OSError, ValueError):
        warmed = None
    return None if warmed == digest and (plugin_data / "venv").exists() else digest


def warm_command(uv: str, plugin_root: Path, plugin_data: Path, digest: str) -> tuple[list[str], dict]:
    """Same project dir and environment as .mcp.json, so the server finds it ready."""
    cmd = [uv, "run", "--quiet", "--frozen", "--directory", str(plugin_root / "core"),
           "python", "-c", WARM_CODE, str(plugin_data / WARM_MARKER), digest]
    env = {**os.environ, "UV_PROJECT_ENVIRONMENT": str(plugin_data / "venv")}
    return cmd, env


def start_warm(plugin_root: Path, plugin_data: Path, spawn=subprocess.Popen) -> bool:
    """Start the warm-up detached from this hook; True if one was started."""
    digest = needs_warm(plugin_root, plugin_data)
    uv = shutil.which("uv")
    if not digest or not uv:
        return False
    cmd, env = warm_command(uv, plugin_root, plugin_data, digest)
    detach = ({"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
               | subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True})
    spawn(cmd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
          stderr=subprocess.DEVNULL, close_fds=True, **detach)
    return True


WARMING_NOTE = ("[mentor] The Mentor engine is being set up in the background (first run). If the "
                "mentor tools are unavailable, ask the user to wait a minute and reconnect "
                "plugin:mentor:core from /mcp. If it keeps timing out, they can start Claude Code "
                "with MCP_TIMEOUT=120000 (see the Mentor README, Troubleshooting).")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plugin-data")
    parser.add_argument("--plugin-root")
    args, _ = parser.parse_known_args()
    notes = []
    try:
        if _usable(args.plugin_root) and _usable(args.plugin_data):
            if start_warm(Path(args.plugin_root), Path(args.plugin_data)):
                notes.append(WARMING_NOTE)
    except Exception:  # noqa: BLE001 - never break the session
        pass
    try:
        ws = _workspace(args.plugin_data)
        db = ws / "mentor.db" if ws else None
        if db and db.exists():
            text = summarize(db, _now())
            if text:
                notes.insert(0, text)
    except Exception:  # noqa: BLE001 - never break the session
        pass
    if notes:
        json.dump({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                          "additionalContext": "\n".join(notes)}}, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
