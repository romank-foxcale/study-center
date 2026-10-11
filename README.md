# Study Center: Mentor, a teach-me-anything tutor for Claude Code

Tell it what you want to learn. Mentor:

1. **interviews you** briefly (what you know, why, time, preferences),
2. **researches** the topic from several expert perspectives, with citations,
3. **builds a prerequisite knowledge graph** of small, testable concepts,
4. **places you** with a short adaptive diagnostic (≤ 20 questions),
5. **teaches one concept at a time**: why it matters, intuition, the precise idea, *why it
   works*, worked examples, practice with hints (not answers), misconception checks, explain-back,
6. **decides mastery with an engine, not vibes**: Bayesian knowledge tracing, a mastery gate,
   and confirmation at a delayed review,
7. **schedules spaced reviews** (FSRS) with credit propagation between related concepts, and
   reminds you at session start,
8. leaves you **artifacts**: lesson pages with math, diagrams and interactive plots, a course
   map, progress dashboard and an Anki deck.

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
| `/mentor:progress` | Mastery, capabilities, due forecast, calibration, course map |
| `/mentor:plan` | View or edit the knowledge graph |
| `/mentor:config` | Workspace, review budget, retention target, teaching preferences |
| `/mentor:export` | Anki deck, JSON, or the HTML lesson set |

Optional: `/output-style mentor` makes Claude behave as a Socratic tutor everywhere.

## Repository layout

```
.claude-plugin/marketplace.json   this repo is a one-plugin marketplace
plugins/mentor/
  .claude-plugin/plugin.json      manifest (+ workspace userConfig)
  .mcp.json                       launches the core MCP server with uv
  skills/                         /mentor:* commands
  agents/                         researcher, curriculum-architect, graph-critic,
                                  lesson-author, fact-checker, grader
  hooks/ + scripts/               SessionStart due-review reminder (stdlib only)
  output-styles/mentor.md         optional Socratic style
  pedagogy/                       the tutor constitution, lesson template, rubrics, formats
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
within 20 questions. Run the behaviour evals (they need a logged-in Claude Code):

```bash
cd plugins/mentor
claude plugin eval .
```

## License

Apache-2.0. See [NOTICE](NOTICE) for the projects whose ideas this builds on.
