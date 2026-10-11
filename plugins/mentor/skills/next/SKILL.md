---
name: next
description: Continue a Mentor course with whatever the engine says comes next: due reviews, a check, remediation, a mixed quiz, or the next lesson taught interactively. Use when the user says "next", "continue", "let's keep going", or runs /mentor:next.
argument-hint: "[course]"
allowed-tools: mcp__plugin_mentor_core, Read, Write, Glob, Agent
---

# /mentor:next: continue learning

Read `${CLAUDE_PLUGIN_ROOT}/pedagogy/CONSTITUTION.md` and follow it throughout.

1. `course_status($ARGUMENTS)`. If it errors because there are several courses, show
   `course_list` and ask which one. If the stage is `needs_intake`, `needs_graph` or
   `needs_diagnostic`, resume `/mentor:learn` from that step.
2. Read the course's MISSION.md and PROFILE.md (paths from `dir`).
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
   (`${CLAUDE_PLUGIN_ROOT}/pedagogy`), and draft dir `<dir>/lessons/_draft/<node>/`.
2. Spawn `fact-checker` on the draft. If it says `needs author revision`, send the issues
   back to `lesson-author` once.
3. Read the draft files and call `lesson_save(course, node, lesson_md, pack, sources, title)`.
   This stores the pack items in the item bank (their `item_id`s are in `items_saved`, in pack order).

**Teach.** Follow `${CLAUDE_PLUGIN_ROOT}/pedagogy/LESSON_TEMPLATE.md` §C step by step,
interactively. Never paste lesson.md into chat. Keep the pack's answer keys to yourself.
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
  - `gate passed`: run the close-out (learner summary, confidence, "what would you check next time?").
- If the grader returns `needs_followup`, ask its follow-up question before recording.
- If the learner disputes a grade and they're right, `evidence_void` it with the reason.

**Wrap up.**
- Mention the rendered page: `lesson_render(course, node=..., open_browser=false)` → html path.
  Open it in the browser only if the learner wants.
- If something notable happened (a misconception surfaced, a breakthrough, a preference
  discovered), write `<dir>/records/NNNN-<slug>.md` (format in FORMATS.md).
- One-line progress from `course_status`, then offer the next activity.

Never claim a node is learned or mastered unless `evidence_record` said so.
