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


# --- background warm-up ---------------------------------------------------------
def _hook_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("session_start", HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fake_plugin(tmp_path, lock="version = 1\n"):
    root = tmp_path / "plugin"
    (root / "core").mkdir(parents=True)
    (root / "core" / "uv.lock").write_text(lock, encoding="utf-8")
    data = tmp_path / "data"
    data.mkdir()
    return root, data


def test_warm_runs_once_per_lockfile(tmp_path, monkeypatch):
    hook = _hook_module()
    root, data = _fake_plugin(tmp_path)
    monkeypatch.setattr(hook.shutil, "which", lambda name: "/bin/uv")
    calls = []
    assert hook.start_warm(root, data, spawn=lambda cmd, **kw: calls.append((cmd, kw)))
    cmd, kw = calls[0]
    assert cmd[:6] == ["/bin/uv", "run", "--quiet", "--frozen", "--directory", str(root / "core")]
    assert kw["env"]["UV_PROJECT_ENVIRONMENT"] == str(data / "venv")
    assert kw["stdout"] is hook.subprocess.DEVNULL and kw["close_fds"]
    assert ("creationflags" in kw) if hook.os.name == "nt" else kw["start_new_session"]

    # what the warm-up child writes when it finishes: the server now starts warm
    (data / "venv").mkdir()
    (data / hook.WARM_MARKER).write_text(json.dumps({"lock": cmd[-1]}), encoding="utf-8")
    assert hook.needs_warm(root, data) is None
    assert not hook.start_warm(root, data, spawn=lambda *a, **k: calls.append(a))
    assert len(calls) == 1

    (root / "core" / "uv.lock").write_text("version = 2\n", encoding="utf-8")  # dependencies changed
    assert hook.needs_warm(root, data) is not None


def test_warm_skips_without_uv_or_lockfile(tmp_path, monkeypatch):
    hook = _hook_module()
    root, data = _fake_plugin(tmp_path)
    monkeypatch.setattr(hook.shutil, "which", lambda name: None)
    assert not hook.start_warm(root, data, spawn=lambda *a, **k: 1 / 0)
    (root / "core" / "uv.lock").unlink()
    monkeypatch.setattr(hook.shutil, "which", lambda name: "/bin/uv")
    assert not hook.start_warm(root, data, spawn=lambda *a, **k: 1 / 0)


def test_warm_code_writes_marker(tmp_path):
    hook = _hook_module()
    marker = tmp_path / "warm.json"
    subprocess.run([sys.executable, "-c", hook.WARM_CODE, str(marker), "abc123"], check=True, timeout=120)
    assert json.loads(marker.read_text(encoding="utf-8")) == {"lock": "abc123"}


def test_hook_ignores_unsubstituted_plugin_root(tmp_path):
    env = {"SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", "")}
    out = subprocess.run([sys.executable, "-I", str(HOOK), "--plugin-data", "${CLAUDE_PLUGIN_DATA}",
                          "--plugin-root", "${CLAUDE_PLUGIN_ROOT}"],
                         capture_output=True, text=True, env=env, timeout=30)
    assert out.returncode == 0 and out.stdout == ""
