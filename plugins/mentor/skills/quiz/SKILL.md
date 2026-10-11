---
name: quiz
description: Mixed, interleaved quiz across recently learned Mentor nodes at three difficulty tiers, recording results with the engine. Use when the user asks to be quizzed or tested, or when next_activity returns a quiz.
argument-hint: "[course] [number of questions]"
allowed-tools: mcp__plugin_mentor_core, Read, Agent
---

# /mentor:quiz: interleaved practice

Read `${CLAUDE_PLUGIN_ROOT}/pedagogy/CONSTITUTION.md` and `${CLAUDE_PLUGIN_ROOT}/pedagogy/QUESTION_DESIGN.md`.

1. Find the course (`course_status`). Nodes: from `next_activity` if it returned a quiz,
   otherwise the most recently learned 4-6 nodes (`progress` / `graph_get`). Default 6
   questions, or the number the user gave.
2. **Interleave**: never two questions on the same node in a row. Mix three tiers:
   - familiar-simple (like practice items),
   - familiar-complex (combines two ideas),
   - unfamiliar-complex (new context; transfer).
   Target about 80% success. Include at least one question that makes the learner *choose* the
   method, not just execute it.
3. Store each question with `item_save` (purpose `quiz`) so grading has a key.
4. For each question: ask, get confidence 1-5, grade (deterministic or `grader`), then
   `evidence_record(kind="quiz", ...)`. **Never reveal the answer before the learner responds.**
5. Debrief: score, misconceptions found (with the correction and the why), and any node the
   engine flagged. Wrong answers get a short targeted explanation plus one retry item on the
   same skill (`kind="practice"`).
