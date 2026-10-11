"""The stdlib-only SessionStart hook script reads the workspace via pointer.json."""

import json
import subprocess
import sys
from pathlib import Path

from test_learner import _learn

HOOK = Path(__file__).resolve().parents[2] / "scripts" / "session_start.py"


def run_hook(plugin_data: Path, now: str) -> str:
    env = {"MENTOR_NOW": now, "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", "")}
    out = subprocess.run([sys.executable, "-I", str(HOOK), "--plugin-data", str(plugin_data)],
                         capture_output=True, text=True, env=env, timeout=30)
    assert out.returncode == 0, out.stderr
    return out.stdout


def test_hook_reports_due_reviews(mentor, course, clock, tmp_path):
    plugin_data = tmp_path / "plugin data"
    assert json.loads((plugin_data / "pointer.json").read_text(encoding="utf-8"))["workspace"]
    _learn(mentor, course, "vec.basics", clock)
    assert "1/7 learned" in json.loads(run_hook(plugin_data, clock.t.isoformat()))[
        "hookSpecificOutput"]["additionalContext"]
    later = clock.advance(days=3).isoformat()
    ctx = json.loads(run_hook(plugin_data, later))["hookSpecificOutput"]["additionalContext"]
    assert "1 review(s) due" in ctx and "/mentor:review" in ctx


def test_hook_is_silent_without_workspace(tmp_path):
    assert run_hook(tmp_path / "nothing-here", "2026-01-01T00:00:00+00:00") == ""
