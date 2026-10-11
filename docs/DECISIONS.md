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
- Whether `${CLAUDE_PLUGIN_ROOT}` substitutes inside eval `prompt.md` is unverified. If not,
  change those prompts to relative paths.
- Phase 6 simulated-learner harness (`evals/`) is scaffolded; calibration labels still to collect.
- Phase 7 extras (Manim visualizer, marimo lessons, AnkiConnect, provider-agnostic `mentor chat`)
  are not started.
