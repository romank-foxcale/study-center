# Study Center: Mentor, a teach-me-anything tutor for Claude Code

Tell it what you want to learn. Mentor:

1. **interviews you** briefly (what you know, why, time, a bit about you), or, if you've
   learned with Mentor before, just confirms what it already knows about you,
2. **researches** the topic from several expert perspectives, then **curates** hard: it drops
   the paraphrases and keeps the few sources that are genuinely the best (the canonical
   explanation of each idea, the distinct angles, existing great visualizations),
3. **builds a prerequisite knowledge graph** of small, testable concepts,
4. **places you** with a short adaptive diagnostic (≤ 20 questions),
5. **teaches one concept at a time**, *for you*: examples from your world, the explanation
   angle that works for you first (with a different one ready when it doesn't land), why it
   matters, the precise idea, *why it works*, worked examples, practice with hints (not
   answers), misconception checks, explain-back,
6. **decides mastery with an engine, not vibes**: Bayesian knowledge tracing, a mastery gate,
   and confirmation at a delayed review,
7. **schedules spaced reviews** (FSRS) with credit propagation between related concepts, and
   reminds you at session start,
8. **gets to know you as you go**: every reaction ("that analogy confused me", "the moving
   grid made it click", "slower please") and how practice went after each kind of explanation
   feeds a learner model shared by all your courses. You can read it (`LEARNER.md`) and
   correct it (`/mentor:me`) at any time,
9. leaves you **notes, not noise**: Markdown lessons by default, and an interactive page only
   when seeing something move is the point (in the spirit of 3Blue1Brown or the Transformer
   Explainer), plus a course map, progress dashboard and an Anki deck.

The design follows the evidence: tutors that hand out answers make students worse once the AI
is gone, while tutors that scaffold, sequence and verify help (see
[`MENTOR_BUILD_SPEC.md`](MENTOR_BUILD_SPEC.md) §1 and §15).

## Install

Prerequisites: [Claude Code](https://code.claude.com) and [`uv`](https://docs.astral.sh/uv/) **on your PATH**
(the plugin's hook and core server are launched with `uv`; Python is fetched automatically if needed).

```bash
claude plugin marketplace add romank-foxcale/study-center
claude plugin install mentor@study-center
```

Or, for development from a clone:

```bash
claude --plugin-dir ./plugins/mentor
```

Your courses live in a workspace folder (default `~/Mentor`), set at enable time or with
`/mentor:config workspace <path>`. It is kept outside the plugin on purpose: plugin data is
deleted on uninstall, your learning history is not.

## Use

| Command | What it does |
|---|---|
| `/mentor:learn <goal>` | Start a course: intake → research → knowledge graph → placement |
| `/mentor:next` | Continue: reviews first, then the next lesson, quiz or remediation |
| `/mentor:review` | Due spaced reviews (free recall, confidence first) |
| `/mentor:quiz` | Mixed, interleaved quiz across recent topics |
| `/mentor:why <question>` | Deep "why does this work?" explanation |
| `/mentor:tutor <question>` | One-off help with a problem or concept, Mentor-style, no course needed |
| `/mentor:progress` | Mastery, capabilities, due forecast, calibration, course map |
| `/mentor:plan` | View or edit the knowledge graph |
| `/mentor:me` | What Mentor has learned about you; correct it or give feedback |
| `/mentor:config` | Workspace, review budget, retention target, teaching preferences |
| `/mentor:export` | Anki deck, JSON, or the HTML lesson set |

Optional: `/output-style mentor` makes Claude behave as a Socratic tutor everywhere.

## Troubleshooting

**"plugin:mentor:core" timed out / the mentor tools are missing on first use.** Claude Code gives
an MCP server 30 seconds to start. The very first start of Mentor's engine can take longer:
`uv` downloads its Python packages and Python compiles them. Mentor's session-start hook does
this setup in the background, so it usually fixes itself:

1. wait a minute, then reconnect `plugin:mentor:core` from `/mcp` (or start a new session);
2. if it keeps timing out (slow network, antivirus scanning new files), give servers more
   time to start by launching Claude Code with `MCP_TIMEOUT` set in milliseconds, e.g. 2 minutes:

```bash
MCP_TIMEOUT=120000 claude
```

On Windows PowerShell, set it for the session first:

```powershell
$env:MCP_TIMEOUT = "120000"; claude
```

To make it permanent, add `MCP_TIMEOUT` to your user environment variables (or your shell
profile). Once the engine has started once, later starts take a few seconds.

## Repository layout

```
.claude-plugin/marketplace.json   this repo is a one-plugin marketplace
plugins/mentor/
  .claude-plugin/plugin.json      manifest (+ workspace userConfig)
  .mcp.json                       launches the core MCP server with uv
  skills/                         /mentor:* commands
  agents/                         researcher, source-curator, curriculum-architect,
                                  graph-critic, lesson-author, fact-checker, visualizer, grader
  hooks/ + scripts/               SessionStart due-review reminder (stdlib only)
  output-styles/mentor.md         optional Socratic style
  pedagogy/                       the tutor constitution, personalization, visuals policy,
                                  lesson template, rubrics, formats
  evals/                          `claude plugin eval` behaviour cases
  core/                           mentor_core: provider-agnostic Python engine + MCP server + CLI
evals/                            simulated-learner scenarios, personas and judge rubric
docs/                             architecture, decisions, user guide
```

## Develop

```bash
cd plugins/mentor/core
uv sync
uv run pytest
uv run mentor --help
```

The core has no LLM calls. Scheduling, mastery and graph logic are deterministic and tested,
including a synthetic-learner check that the diagnostic places 90%+ of learners correctly
within 20 questions. Run the behaviour evals (they need the standalone CLI logged in with
`claude auth login`; the desktop app's sign-in doesn't carry over). The eval harness rejects
hard links, so move `core/.venv` aside first, and point the engine at a throwaway workspace so
your real courses aren't touched:

```bash
mv plugins/mentor/core/.venv plugins/mentor/core/.venv.bak
cd plugins/mentor
MENTOR_FORCE_WORKSPACE=~/mentor-eval-ws claude plugin eval . --mocks off --allow-tools mcp__plugin_mentor_core
```

Afterwards, move `core/.venv.bak` back to `core/.venv`.

## License

Apache-2.0. See [NOTICE](NOTICE) for the projects whose ideas this builds on.
