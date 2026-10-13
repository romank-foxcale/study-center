---
name: next
description: 'Continue a Mentor course with whatever the engine says comes next: due reviews, a check, remediation, a mixed quiz, or the next lesson taught interactively. Use when the user says "next", "continue", "let''s keep going", or runs /mentor:next.'
argument-hint: "[course]"
allowed-tools: mcp__plugin_mentor_core, Read, Write, Glob, Agent
---

# /mentor:next: continue learning

Read `${CLAUDE_PLUGIN_ROOT}/pedagogy/CONSTITUTION.md` and follow it throughout. For feedback
capture read `${CLAUDE_PLUGIN_ROOT}/pedagogy/PERSONALIZATION.md`; for visuals,
`${CLAUDE_PLUGIN_ROOT}/pedagogy/VISUALS.md`.

1. `course_status($ARGUMENTS)`. If it errors because there are several courses, show
   `course_list` and ask which one. If the stage is `needs_intake`, `needs_graph` or
   `needs_diagnostic`, resume `/mentor:learn` from that step.
2. Read the course's MISSION.md, PROFILE.md and APPROACH.md (paths from `dir`), and call
   `learner_model()`. Keep its `guidance` in mind for everything you say this session.
3. `next_activity(course)` and dispatch on `type`:

| type | do |
|---|---|
| `review` | Run the review flow in `${CLAUDE_PLUGIN_ROOT}/skills/review/SKILL.md` for `items`, then call `next_activity` again |
| `check` | One quick question per flagged node (`evidence_record kind=check`), then continue |
| `remediate` | Short focused re-teach of `node` (intuition, then why, then 2 practice items). If `blocked` is set, explain that we're strengthening a foundation for it, then return to it |
| `quiz` | Run `${CLAUDE_PLUGIN_ROOT}/skills/quiz/SKILL.md` on `nodes` |
| `lesson` | Teach the lesson (below) |
| `suggest_insert_prereq` | Propose the missing prerequisite node to the learner; if they agree, `graph_insert_node`, then teach it |
| `done` / `waiting` | Celebrate briefly, show `progress`, suggest stretch nodes, a capstone project tied to MISSION.md, or a new goal |

Always tell the learner in one line *why* this is next (use the `why` field).

## Teaching a lesson
**Prepare (once per node).** If the node already has a lesson (`lesson_render(course, node=...)`
succeeds), reuse it: read its `lesson.md` and `pack.json` from the lesson dir. Otherwise:
1. Spawn `lesson-author` with: course slug, course dir, node id, the pedagogy folder
   (`${CLAUDE_PLUGIN_ROOT}/pedagogy`), draft dir `<dir>/lessons/_draft/<node>/`, and anything
   the learner said this session that isn't in the model yet.
2. Spawn `fact-checker` on the draft. If it says `needs author revision`, send the issues
   back to `lesson-author` once.
3. Read the draft files and call `lesson_save(course, node, lesson_md, pack, sources, title)`.
   This stores the pack items in the item bank (their `item_id`s are in `items_saved`, in pack
   order). It writes lesson.html only if the lesson has something markdown can't show.
4. If the author requested a level-3 explorable, check it against VISUALS.md's test yourself
   (is there an existing visual to link instead?). If it passes, spawn `visualizer` with the
   course slug, node, lesson dir, the request and the pedagogy folder, then call
   `lesson_render(course, node=...)`. Don't block teaching on it: start the lesson while it
   builds and point to the page when it's ready.

**Teach.** Follow `${CLAUDE_PLUGIN_ROOT}/pedagogy/LESSON_TEMPLATE.md` §C step by step,
interactively, in plain text. Never paste lesson.md into chat. Keep the pack's answer keys to
yourself.
- Explain with the pack's `primary` explanation and its examples. If the learner is stuck after
  the second hint rung, or says it isn't clicking, switch to the `alternate` explanation.
- Pass `taught_with` (the explanation's `dims`) on the first graded item after each explanation.
- Whenever the learner reacts to the teaching itself, record a `learner_signal` right away
  (PERSONALIZATION.md) and adapt: slower, a different example, less text.
- For every learner answer to a pack item:
  - deterministic forms (mcq, numeric, expression): grade yourself using the key and `check_math`;
  - free text (explain, short, proof, the "why" of two-tier items): spawn `grader` with
    `course`, `item_id` and the verbatim answer in `<answer>` tags; use its JSON.
  Then call `evidence_record(course, node, kind, score, item_id, hinted, hint_level, idk,
  confidence, misconceptions, grader_version, n_options)`.
- React to the returned `next_action`:
  - `continue`: keep going; use `gate_missing` to choose what to practice next (another
    form, a higher Bloom level, the misconception item, explain-back);
  - `halt_and_remediate`: stop the lesson kindly and switch to the `remediate` target;
  - `suggest_insert_prereq`: as in the table above;
  - `gate passed`: run the close-out (learner summary, confidence, "what would you check next
    time?"), then the optional feedback question naming the lesson's actual examples and
    visuals. Turn the answer into `learner_signal` reactions (target = the example's label,
    dims = its dims).
- If the grader returns `needs_followup`, ask its follow-up question before recording.
- If the learner disputes a grade and they're right, `evidence_void` it with the reason.

**Wrap up.**
- Point to the reference copy: lesson.md, or lesson.html if `lesson_save` made one (open it in
  the browser only if the learner wants). Mention the canonical source for going deeper if
  the lesson links one.
- **Tune-up** (PERSONALIZATION.md): about every 5 lessons, or when `learner_model()` reports
  `conflicts`, show 3-4 lines of what you believe works for them and ask what's wrong.
- If something notable happened (a misconception surfaced, a breakthrough, an explanation that
  failed and the one that worked), write `<dir>/records/NNNN-<slug>.md` (format in FORMATS.md).
  Preferences go into learner signals, not records.
- One-line progress from `course_status`, then offer the next activity.

Never claim a node is learned or mastered unless `evidence_record` said so.
