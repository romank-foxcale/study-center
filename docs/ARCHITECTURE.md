# Architecture

```
Claude Code session
 ├─ skills (/mentor:*) ── orchestrate the flow, load pedagogy/*.md
 ├─ agents ─────────────── researcher ×5 (parallel, incl. explainer-scout), source-curator,
 │                         curriculum-architect, graph-critic, lesson-author, fact-checker,
 │                         visualizer (rare), grader (independent of the chat)
 ├─ SessionStart hook ──── scripts/session_start.py (stdlib, read-only) → due-review reminder
 └─ MCP stdio ──────────── mentor_core.mcp_server  ⇄  mentor_core.service.Mentor
                                                      ├─ store      SQLite (WAL)
                                                      ├─ graph      schema, validation, Mermaid
                                                      ├─ learner    BKT + state machine + gate
                                                      ├─ learner_model  who the learner is (signals → LEARNER.md)
                                                      ├─ fsrs_adapter / fire   scheduling, implicit credit
                                                      ├─ diagnostic / planner  placement, what-next
                                                      ├─ render     lesson.md → HTML
                                                      └─ export_anki, verify_math
Workspace (~/Mentor by default)
 ├─ mentor.db             evidence + signals (append-only) + derived node_state, items, lessons
 ├─ LEARNER.md            the learner model, generated, shared by all courses
 └─ courses/<slug>/       MISSION, PROFILE, APPROACH, RESOURCES, research/ (incl. ANGLES.md),
                          graph.yaml, graph.html,
                          lessons/NNNN-node/{lesson.md, pack.json, sources.json,
                                             lesson.html and explore-*.html only when needed},
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
5. **Two learner models.** Knowledge (per node, per course, from evidence) and the learner model
   (how to teach this person, all courses, from signals). Both are derived by replay; corrections
   void rows. The learner model only changes the *choice and order* of explanations, examples,
   pace and depth, never what counts as mastery.
6. **Text first.** `lesson.md` is the reference copy; HTML is written only when the lesson has
   plots, boards, quizzes or an explorable. Explorables pass `explorable_save` checks
   (pinned CDNs only, no network calls, balanced markup, ≤ 2 MB).
7. **Provider-agnostic core.** `mentor_core` has no LLM calls. Any MCP client, the `mentor`
   CLI, or a future non-Claude front end drives the same state.

## Mastery gate (learning → learned)
- BKT estimate ≥ 0.95 (soft-evidence update, hint damping, MCQ guess = 1/n)
- ≥ 3 unhinted correct answers in ≥ 2 item forms, one at the node's Bloom level
- misconception item passed (if the node lists misconceptions)
- explain-back passed (concept and design nodes)

**learned → mastered**: a passing spaced review at least 20 h after learning.
**→ rusty**: a review rated *Again*. Re-practice returns the node to learned.

## Learner model (pedagogy/PERSONALIZATION.md)
- Signals: `fact` (background), `stated` (preference, ×1.5), `reaction` (feedback on something
  taught, ×1), `outcome` (automatic from `evidence_record(taught_with=...)`, score relative to
  the learner's own baseline, ×0.5). Half-life 120 days.
- Per (dimension, value): Beta(1,1) posterior over "helps". `works` ≥ 0.65 and `avoid` ≤ 0.35
  with evidence ≥ 1.5. "Liked" and "worked" are kept apart and disagreements reported.
- `adjust` offsets (pace, depth, length, rigor, challenge) accumulate without decay, clamped ±3.
- `explore` lists never-tried angles/formats so the tutor keeps sampling (about 1 lesson in 4).

## Research pipeline
researchers (5 perspectives, each tags source angle and original/derivative) → source-curator
(clusters paraphrases, keeps the canonical exposition per idea, maps angles and existing
visuals → RESOURCES.md, research/ANGLES.md) → curriculum-architect (chooses the teaching
approach for this learner → APPROACH.md, graph) → lesson-author (primary + alternate angle,
tagged examples, visuals decision) → fact-checker.

## Planner priority
due reviews (greedy set cover over encompasses edges) → check flags (from failed encompassing
nodes) → rusty remediation → halted lessons (remediate the weakest prereq, or suggest a missing
one) → resume the in-progress lesson → mixed quiz every 3 learned nodes → the best ready node
(tier, capability value, layering, non-interference) → done.
