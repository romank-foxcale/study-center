---
name: learn
description: Start a new Mentor course for a learning goal. Interviews the learner, researches the topic from several expert perspectives, builds a prerequisite knowledge graph, and runs a short adaptive placement diagnostic. Use when the user says "teach me X", "I want to learn X", or runs /mentor:learn.
argument-hint: "<what you want to learn>"
allowed-tools: mcp__plugin_mentor_core, Read, Write, Glob, Agent
---

# /mentor:learn: start a course

Goal from the user: **$ARGUMENTS**

Read `${CLAUDE_PLUGIN_ROOT}/pedagogy/CONSTITUTION.md` now and follow it for the whole session.
File formats: `${CLAUDE_PLUGIN_ROOT}/pedagogy/FORMATS.md`.

If the goal is empty, ask what they want to learn and stop.
If `course_list` shows an active course with a very similar goal, ask whether to resume it
(`/mentor:next`) or start fresh.

## 1. Create the course
Call `course_create(goal)`. Keep the returned `course` slug and `dir`.

## 2. Intake: one message, then listen
Ask everything in **one** short message (DeepTutor-style intake):
1. What do you already know that's related? (tools, math, prior courses; rough is fine)
2. Why do you want this, and what would "done" look like? (a project, a job task, an exam, curiosity)
3. How much time per week, and is there a deadline?
4. How do you like to be taught? (more intuition or more rigor; Socratic questions or explain-first;
   any interests to draw examples from; language)

Tell them they can skip any question. When they answer, write MISSION.md and PROFILE.md with
`profile_write`, recording **only what they said** (no invented details). If they skip, use
sensible defaults (depth 5, explain-first with checks, their language) and say you'll adapt.

## 3. Research in parallel
Spawn **4 `researcher` subagents in one message** so they run concurrently, one per persona:
`practitioner`, `theorist`, `educator`, `recent learner`. Add `skeptic/historian` for broad goals.
Give each: the goal, a 3-line summary of MISSION.md and PROFILE.md, its persona, and
`output_path = <dir>/research/<persona>.md`.

While they run, tell the learner what's happening (about 2-4 minutes).

When all return, consolidate a RESOURCES.md (format in FORMATS.md: the best 8-15 sources,
deduplicated, with licenses) and save it with `resources_write`.

## 4. Build the knowledge graph
1. Spawn `curriculum-architect` with: the course dir, the pedagogy folder
   (`${CLAUDE_PLUGIN_ROOT}/pedagogy`), and output path `<dir>/graph.draft.yaml`.
2. Spawn `graph-critic` on the draft (same folder paths).
3. Apply the critic's fixes yourself (Read/Write the draft), then `graph_propose(course, <yaml text>)`.
4. If `saved` is false, fix every error and resubmit. Address important warnings
   (capability not served, missing misconceptions) unless there's a good reason not to.

## 5. Show the plan
Present briefly:
- the capabilities ("by the end you'll be able to...")
- the graph size and estimated total time from `stats.total_minutes`
- the map: `graph_get(course, view="mermaid")` in a ```mermaid block, and mention
  `<dir>/graph.html` for a full-page view

Ask if anything should be added, removed or emphasized. Edits go through `graph_propose`.
This is outline mode: no quizzing yet.

## 6. Placement diagnostic
Say: "About 10-15 quick questions to find where to start. 'I don't know' is a great answer;
it's better than guessing."

Loop:
1. `diagnostic_next(course)`. If `done`, go to step 7.
2. Write one quick question for `node` that follows `item_request` (one skill, under 2
   minutes, mostly Apply level). Optionally store it with `item_save` (purpose `diagnostic`).
3. Ask it. Don't teach, and don't reveal the answer yet.
4. Score it: deterministically where possible (`check_math`, exact or numeric), otherwise
   judge against your key (1 / 0.5 / 0). Use `idk=true` for "I don't know".
5. `diagnostic_record(course, node, score, item_id?, idk, confidence?)`. Give a one-line
   acknowledgement without the full solution ("noted, we'll cover that"). Brief
   corrections are fine for quick facts.

## 7. Wrap up
Call `diagnostic_finish(course)`. Update PROFILE.md's "Diagnostic summary" with
`profile_write`. Tell the learner what they already know, where they'll start, and the
first lesson (`next` in the result). Offer to begin now with `/mentor:next`.
