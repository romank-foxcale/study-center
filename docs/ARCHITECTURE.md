# Architecture

```
Claude Code session
 ├─ skills (/mentor:*) ── orchestrate the flow, load pedagogy/*.md
 ├─ agents ─────────────── researcher ×N (parallel), curriculum-architect, graph-critic,
 │                         lesson-author, fact-checker, grader (independent of the chat)
 ├─ SessionStart hook ──── scripts/session_start.py (stdlib, read-only) → due-review reminder
 └─ MCP stdio ──────────── mentor_core.mcp_server  ⇄  mentor_core.service.Mentor
                                                      ├─ store      SQLite (WAL)
                                                      ├─ graph      schema, validation, Mermaid
                                                      ├─ learner    BKT + state machine + gate
                                                      ├─ fsrs_adapter / fire   scheduling, implicit credit
                                                      ├─ diagnostic / planner  placement, what-next
                                                      ├─ render     lesson.md → HTML
                                                      └─ export_anki, verify_math
Workspace (~/Mentor by default)
 ├─ mentor.db             evidence log (append-only) + derived node_state, items, lessons
 └─ courses/<slug>/       MISSION, PROFILE, RESOURCES, research/, graph.yaml, graph.html,
                          lessons/NNNN-node/{lesson.md, lesson.html, pack.json, sources.json},
                          reference/, records/, exports/
```

## Invariants
1. **The engine decides.** The LLM records graded evidence; state (`ready → learning → learned
   → mastered`, `rusty`, `deferred`) is computed by `learner.derive_states`.
2. **Evidence is the source of truth.** `node_state` is a cache rebuilt by replaying evidence in
   timestamp order. Corrections are made by voiding evidence, never by editing state.
3. **Deterministic scheduling.** FSRS without fuzzing; `MENTOR_NOW` overrides the clock for
   tests and simulations.
4. **Answer keys stay hidden.** `item_get` withholds keys unless `include_key=true` (grader only);
   `pack.json` is never shown to the learner.
5. **Provider-agnostic core.** `mentor_core` has no LLM calls. Any MCP client, the `mentor`
   CLI, or a future non-Claude front end drives the same state.

## Mastery gate (learning → learned)
- BKT estimate ≥ 0.95 (soft-evidence update, hint damping, MCQ guess = 1/n)
- ≥ 3 unhinted correct answers in ≥ 2 item forms, one at the node's Bloom level
- misconception item passed (if the node lists misconceptions)
- explain-back passed (concept and design nodes)

**learned → mastered**: a passing spaced review at least 20 h after learning.
**→ rusty**: a review rated *Again*. Re-practice returns the node to learned.

## Planner priority
due reviews (greedy set cover over encompasses edges) → check flags (from failed encompassing
nodes) → rusty remediation → halted lessons (remediate the weakest prereq, or suggest a missing
one) → resume the in-progress lesson → mixed quiz every 3 learned nodes → the best ready node
(tier, capability value, layering, non-interference) → done.
