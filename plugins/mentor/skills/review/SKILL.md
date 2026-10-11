---
name: review
description: Run due spaced-repetition reviews for one or all Mentor courses, using free recall with confidence ratings. Use when the user says "review", "what's due", or the session-start reminder mentions due reviews.
argument-hint: "[course|all]"
allowed-tools: mcp__plugin_mentor_core, Read, Agent
---

# /mentor:review: spaced reviews

Read `${CLAUDE_PLUGIN_ROOT}/pedagogy/CONSTITUTION.md` (rules 14-17 matter most here).

1. `review_queue(<course or omit for all>)`. If nothing is due, say so, give the next due
   date from `progress`, and offer `/mentor:next`.
2. For each course, take the `selection` (a set cover: reviewing a node also covers the nodes in its `covers` list).
   Tell the learner how many and roughly how long (about 1-2 minutes each).
3. For each selected node:
   - Get its items (`items_list(course, node)`). Write a **fresh variant** of one (new
     numbers or context, same skill) rather than repeating it verbatim. If the node encompasses
     covered nodes, choose a question that exercises them too.
   - Prefer free recall or short answer over multiple choice.
   - Ask, then ask for confidence 1-5 **before** revealing anything.
   - Grade it: deterministic when possible; otherwise spawn `grader`. For a variant you wrote,
     store it first with `item_save` so the grader can see its key.
   - `evidence_record(course, node, kind="review", score, item_id, confidence, hinted, ...)`.
   - Give brief feedback with the why. If the result is `rusty`, do a 2-minute re-teach and one
     more practice item (`kind="practice"`).
4. Summarize: reviewed, solid, slipped, and the next due dates (`progress`). If confidence and
   accuracy disagree (confidently wrong, or unsure but right), point it out gently.
