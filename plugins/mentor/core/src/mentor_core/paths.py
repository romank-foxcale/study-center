"""Workspace resolution and the clock.

Workspace resolution order (spec §4.4):
0. env MENTOR_FORCE_WORKSPACE (eval harnesses and sandboxes only)
1. env MENTOR_WORKSPACE (ignored if empty or an unsubstituted ``${...}`` placeholder)
2. pointer.json in the plugin data dir (env MENTOR_PLUGIN_DATA / CLAUDE_PLUGIN_DATA)
3. ~/Mentor

The resolved path is always written back to pointer.json so the stdlib-only
SessionStart hook can find the database without importing this package.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_WORKSPACE = "~/Mentor"
POINTER_FILE = "pointer.json"
DB_FILE = "mentor.db"

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _usable(value: str | None) -> bool:
    return bool(value) and "${" not in value  # type: ignore[operator]


def plugin_data_dir() -> Path | None:
    for var in ("MENTOR_PLUGIN_DATA", "CLAUDE_PLUGIN_DATA"):
        value = os.environ.get(var)
        if _usable(value):
            return Path(value).expanduser()  # type: ignore[arg-type]
    return None


def read_pointer() -> Path | None:
    data_dir = plugin_data_dir()
    if not data_dir:
        return None
    try:
        raw = json.loads((data_dir / POINTER_FILE).read_text(encoding="utf-8"))
        return Path(raw["workspace"]).expanduser() if raw.get("workspace") else None
    except (OSError, ValueError, KeyError):
        return None


def write_pointer(workspace: Path) -> None:
    data_dir = plugin_data_dir()
    if not data_dir:
        return
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / POINTER_FILE).write_text(
            json.dumps({"workspace": str(workspace)}, indent=2), encoding="utf-8"
        )
    except OSError:
        pass


def resolve_workspace(explicit: str | Path | None = None) -> Path:
    if explicit:
        workspace = Path(explicit).expanduser()
    elif _usable(os.environ.get("MENTOR_FORCE_WORKSPACE")):  # evals/sandboxes; beats plugin config
        workspace = Path(os.environ["MENTOR_FORCE_WORKSPACE"]).expanduser()
    elif _usable(os.environ.get("MENTOR_WORKSPACE")):
        workspace = Path(os.environ["MENTOR_WORKSPACE"]).expanduser()
    else:
        workspace = read_pointer() or Path(DEFAULT_WORKSPACE).expanduser()
    workspace = workspace.resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "courses").mkdir(exist_ok=True)
    write_pointer(workspace)
    return workspace


def now() -> datetime:
    """Current UTC time. ``MENTOR_NOW`` (ISO 8601) overrides it for tests and simulations."""
    override = os.environ.get("MENTOR_NOW")
    if override:
        return parse_ts(override)
    return datetime.now(timezone.utc)


def parse_ts(value: str) -> datetime:
    ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def iso(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).isoformat(timespec="seconds")


def slugify(text: str, max_len: int = 40) -> str:
    slug = _SLUG_RE.sub("-", text.lower()).strip("-")
    return (slug[:max_len].rstrip("-")) or "course"
