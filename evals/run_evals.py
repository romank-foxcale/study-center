"""Simulated-learner eval harness (spec §11.3-11.4).

Drives multi-turn sessions: tutor = Claude Code with the Mentor plugin (headless, resumed
session); learner = a persona-playing `claude -p` call; judge = `claude -p` with the rubric.
Each scenario gets its own throwaway workspace (MENTOR_FORCE_WORKSPACE).

    uv run --project plugins/mentor/core python evals/run_evals.py [--only ID] [--turns N]

Requires a logged-in `claude` CLI. Writes evals/results/<timestamp>/{results.jsonl,summary.md}.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
EVALS = ROOT / "evals"
PLUGIN = ROOT / "plugins" / "mentor"
TUTOR_TOOLS = "mcp__plugin_mentor_core,Read,Write,Edit,Glob,Agent,WebSearch,WebFetch"


def claude(prompt: str, *, extra: list[str], env: dict[str, str], timeout: int = 900) -> dict:
    cmd = ["claude", "-p", prompt, "--output-format", "json", *extra]
    out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", env=env, timeout=timeout)
    if out.returncode != 0:
        raise RuntimeError(f"claude failed ({out.returncode}): {out.stderr.strip()[:500]}")
    return json.loads(out.stdout)


def learner_reply(persona: str, scenario: dict, transcript: list[dict], env: dict[str, str]) -> str:
    history = "\n\n".join(f"{t['role'].upper()}: {t['text']}" for t in transcript)
    prompt = (
        f"You are role-playing a LEARNER talking to an AI tutor. Stay in character.\n\n{persona}\n\n"
        f"Facts about you: {scenario.get('context', '')}\n"
        f"{'Your misconception: ' + scenario['misconception'] if scenario.get('misconception') else ''}\n\n"
        f"Conversation so far:\n{history}\n\n"
        "Write ONLY your next message to the tutor (no quotes, no stage directions)."
    )
    return claude(prompt, extra=["--model", "haiku", "--tools", ""], env=env)["result"].strip()


def judge(rubric: str, scenario: dict, transcript: list[dict], env: dict[str, str]) -> dict:
    history = "\n\n".join(f"{t['role'].upper()}: {t['text']}" for t in transcript)
    criteria = "\n".join(f"- {c}" for c in scenario.get("criteria", []))
    prompt = (f"{rubric}\n\n## Scenario criteria\n{criteria}\n\n## Transcript\n{history}\n\n"
              "Return the JSON only.")
    raw = claude(prompt, extra=["--model", "opus", "--tools", ""], env=env)["result"]
    match = re.search(r"\{.*\}", raw, re.S)
    try:
        return json.loads(match.group(0)) if match else {"error": "no JSON", "raw": raw[:2000]}
    except ValueError:
        return {"error": "bad JSON", "raw": raw[:2000]}


def run_scenario(scenario: dict, turns: int | None, rubric: str) -> dict:
    persona = (EVALS / "personas" / f"{scenario['persona']}.md").read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="mentor-eval-") as tmp:
        env = {**os.environ, "MENTOR_FORCE_WORKSPACE": str(Path(tmp) / "ws")}
        transcript: list[dict] = []
        session_id = None
        message = scenario["opening"]
        for _ in range(turns or scenario.get("turns", 6)):
            transcript.append({"role": "learner", "text": message})
            extra = ["--plugin-dir", str(PLUGIN), "--allowedTools", TUTOR_TOOLS]
            if session_id:
                extra += ["--resume", session_id]
            res = claude(message, extra=extra, env=env)
            session_id = res.get("session_id", session_id)
            transcript.append({"role": "tutor", "text": res.get("result", "")})
            message = learner_reply(persona, scenario, transcript, env)
        verdict = judge(rubric, scenario, transcript, env)
    return {"id": scenario["id"], "persona": scenario["persona"], "transcript": transcript, "verdict": verdict}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="scenario id")
    parser.add_argument("--turns", type=int)
    args = parser.parse_args()
    scenarios = yaml.safe_load((EVALS / "scenarios" / "scenarios.yaml").read_text(encoding="utf-8"))
    if args.only:
        scenarios = [s for s in scenarios if s["id"] == args.only]
    rubric = (EVALS / "judge" / "RUBRIC.md").read_text(encoding="utf-8")
    out_dir = EVALS / "results" / datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True)
    rows = []
    with (out_dir / "results.jsonl").open("w", encoding="utf-8") as fh:
        for sc in scenarios:
            print(f"running {sc['id']} ...", flush=True)
            try:
                row = run_scenario(sc, args.turns, rubric)
            except Exception as exc:  # noqa: BLE001 - record and continue
                row = {"id": sc["id"], "error": str(exc)}
            rows.append(row)
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    lines = ["| scenario | overall | criteria met | integrity |", "|---|---|---|---|"]
    for r in rows:
        v = r.get("verdict") or {}
        crit = v.get("criteria") or []
        met = f"{sum(1 for c in crit if c.get('met'))}/{len(crit)}" if crit else "-"
        integ = "ok" if v.get("integrity") and all(v["integrity"].values()) else "FAIL" if v.get("integrity") else "-"
        lines.append(f"| {r['id']} | {v.get('overall', r.get('error', '-'))} | {met} | {integ} |")
    (out_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nresults: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
