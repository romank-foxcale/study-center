# Decisions and verified platform facts

The build follows `MENTOR_BUILD_SPEC.md`. This file records where we resolved a [VERIFY]
item or deviated from the spec. Newest entries go at the bottom.

## 2026-10-11: Phase 0 verification (Claude Code 2.1.293, Windows 11)

Verified against code.claude.com docs and the local CLI:

| Topic | Finding | Consequence |
|---|---|---|
| `userConfig` types | `string, number, boolean, directory, file`; needs `type, title, description`; prompted when the plugin is enabled via `/plugin` (re-open with `/plugin configure mentor`) | `workspace_dir` uses `type: directory`, `required: false` |
| `~` expansion in userConfig | not documented | core calls `expanduser()` itself |
| `${user_config.KEY}` | substituted in MCP server config (incl. `env`), exec-form hook args, skill/agent content. Hooks also get `CLAUDE_PLUGIN_OPTION_<KEY>`; MCP servers do not | `.mcp.json` passes `MENTOR_WORKSPACE=${user_config.workspace_dir}`; the core ignores unsubstituted `${...}` values; the hook reads `CLAUDE_PLUGIN_OPTION_WORKSPACE_DIR`, then `pointer.json` |
| Exec-form hooks | supported; `${CLAUDE_PLUGIN_ROOT}`/`${CLAUDE_PLUGIN_DATA}` substitute in args; **on Windows the command must be a real `.exe`** (no `.cmd` shims) | `uv.exe` qualifies; documented that uv must be on PATH |
| `hooks.json` | must wrap events in a top-level `"hooks"` key | done |
| Skills | `skills/<name>/SKILL.md` → `/mentor:<name>`; `${CLAUDE_PLUGIN_ROOT}` substituted in the body; `allowed-tools` pre-approves for the turn | skills reference `${CLAUDE_PLUGIN_ROOT}/pedagogy/...` |
| Plugin MCP tool names | `mcp__plugin_mentor_core__<tool>`; server-level rule `mcp__plugin_mentor_core` | used in `allowed-tools` and agent `tools` |
| Agents | plugin agents ignore `hooks`, `mcpServers`, `permissionMode`; substitution of `${CLAUDE_PLUGIN_ROOT}` in agent bodies not confirmed | skills pass the pedagogy folder path to agents explicitly in the spawn prompt |
| Marketplace | `claude plugin marketplace add <path or owner/repo>`, `claude plugin install mentor@study-center`; entry `name` must match the manifest `name` | marketplace is named `study-center` (the repo), plugin `mentor` |
| Plugin evals | `evals/<case>/prompt.md` + `graders/*.md` (`type: llm`, `type: tool_used`); run `claude plugin eval .` from the plugin root | 5 behaviour cases in `plugins/mentor/evals/` |
| `claude plugin validate` | passes for plugin and marketplace | n/a |

## Deviations from the spec
- **MCP SDK 2.x**: `FastMCP` was renamed `MCPServer` (`mcp.server.mcpserver`). Unexpected
  exceptions are masked as "Error executing tool", so `MentorError` is mapped to `ToolError`
  to keep messages visible to the model.
- **Renderer template** lives inside the package (`mentor_core/templates/page.html.j2`) so the
  core is self-contained, not in `plugins/mentor/templates/`.
- **FSRS**: day-level scheduling (`learning_steps=()`, `relearning_steps=()`, no fuzzing) so that
  replaying the evidence log is deterministic. Every node's first review is +1 day (the
  learned → mastered confirmation), then FSRS takes over. DeepTutor's per-type cold-start
  intervals were dropped as redundant.
- **State is derived by replay**: every write appends evidence and then re-derives node state
  from the full log. `rebuild-state` is identical to incremental updates by construction
  (there's a test). Diagnostic inferences, FIRe credit and check flags are evidence rows too.
- **Gate details**: the misconception check is required only when the node lists
  misconceptions, and explain-back only for `concept`/`design` nodes.
- **CDN versions** pinned to long-established releases verified to exist: KaTeX 0.16.11,
  Mermaid 11.4.1, D3 7.9.0, Observable Plot 0.6.16, JSXGraph 1.10.1.
- **Lesson pack items** passed to `lesson_save` are stored in the item bank automatically.

## Known gaps / next steps
- A live headless `claude -p --plugin-dir` smoke test was blocked (CLI OAuth session
  expired). The MCP server is verified end to end over stdio by `tests/test_mcp_stdio.py`.
- Phase 6 simulated-learner harness (`evals/`) is scaffolded; calibration labels still to collect.
- Phase 7 extras (Manim visualizer, marimo lessons, AnkiConnect, provider-agnostic `mentor chat`)
  are not started.

## 2026-10-13: Learner model, source curation, text-first visuals

| Decision | Why |
|---|---|
| A **global learner model** (`signals` table → `LEARNER.md`), separate from per-course PROFILE.md | A person is the same person in every course. Background, interests and what works carry over; known concepts from other courses become bridges. |
| Signals are append-only and the model is replayed (like evidence) | Same correction story as node state: void, never edit. Deterministic and testable. |
| Separate "liked" (stated, reaction) from "worked" (outcome) and report conflicts | What learners prefer and what helps them often differ. The tutor should use liked-but-ineffective things as hooks, not as the core explanation. |
| Outcome signals are relative to the learner's own recent score, weighted 0.5 | Item difficulty confounds raw scores; one hard item shouldn't condemn an angle. |
| Fixed vocabularies for `angle`, `format`, `abstraction`; free text for `domain` | Aggregation needs shared keys; interests are open-ended. No "learning style" dimension on purpose (Pashler et al. 2008). |
| Preference adjustments (pace, depth...) accumulate without decay | "Go faster" stays true until the learner says otherwise; categorical evidence decays (half-life 120 days) so the model follows the learner's growth. |
| `explore` list plus "about one lesson in four uses an untested angle as the alternate" | Avoids locking in on noisy early preferences. |
| New agents: `source-curator` (dedupe paraphrases, pick canonical sources, map angles) and `visualizer` (rare level-3 explorables); new researcher persona `explainer-scout` | Most material restates a few originals. Curating for distinct contribution saves the learner's time; linking the best existing explanation beats paraphrasing it. |
| `APPROACH.md` per course, written by the curriculum-architect | The teaching approach (e.g. geometry first) is chosen explicitly from evidence + learner model and is reviewable. Kept out of graph.yaml so the validated schema doesn't change. |
| `lesson_save(render="auto")` writes HTML only for plots, JSXGraph, quiz blocks or explorables | Text first: most lessons read fine as Markdown (VS Code, GitHub and Obsidian render math and Mermaid). The template's self-check moved from a `quiz` block to plain Markdown so it doesn't force a page. |
| `explorable_save` validates bespoke pages (pinned allowlisted CDNs, no network calls, balanced markup, `<title>`, ≤ 2 MB) | Generated JavaScript runs in the learner's browser; keep it self-contained and reviewable. |
| `/mentor:me` shows and corrects the model; `learner_reset` voids everything | Open learner model: the learner sees everything inferred about them and can correct it. |

Not done yet: tuning the thresholds (0.65 / 0.35 / 1.5) and outcome weight against simulated
learners (`evals/scenarios.yaml` has a `la-feedback-loop` scenario to start from).

## 2026-10-13: First real `claude plugin eval` run (Claude Code 2.1.293)

| Finding | Consequence |
|---|---|
| `${CLAUDE_PLUGIN_ROOT}` is **not** substituted in eval `prompt.md`; runs work in an empty temp folder, so plugin files are unreachable by path (probe case confirmed) | Behaviour cases go through the new `/mentor:tutor` skill, whose body *is* substituted and loads the pedagogy files |
| Eval grader `type: tool_used` takes `tool:`, not `tool_used:` | Fixed in `learn-intake` and `feedback-capture` |
| The harness rejects a plugin folder containing hard links; `core/.venv` (built by uv from its cache) has thousands | Run evals on a copy without `core/.venv`, or move it aside first |
| The MCP server must start within 30 s. A cold first start took 45 s, mostly importing SymPy | SymPy (`check_math`) and genanki (`export_anki`) are imported on first use; a fresh-environment start now takes about 5 s |
| Eval runs need the standalone CLI logged in (`claude auth login`); the desktop app's sign-in doesn't carry over | Documented in the eval instructions |
