---
name: me
description: Show what Mentor has learned about the learner across all courses (background, which explanations and examples work, pace and depth, interests) and take corrections or new feedback. Use when the user asks what Mentor knows about them, wants to change how they're taught, or gives feedback like "stop using analogies" or "I prefer code examples", or runs /mentor:me.
argument-hint: "[feedback or correction]"
allowed-tools: mcp__plugin_mentor_core, Read
---

# /mentor:me: the learner model

Rules: `${CLAUDE_PLUGIN_ROOT}/pedagogy/PERSONALIZATION.md` (read it).

Input: **$ARGUMENTS**

1. `learner_model(detail=true)`.
2. **No input**: summarize it in plain language, at most ~12 lines, written to the learner:
   - what you know about them (facts),
   - what has worked and what hasn't, with the basis ("you said so twice" vs "practice went
     better after geometric explanations"), including any liked-vs-worked conflicts, stated kindly,
   - pace, depth and other adjustments, interests used for examples,
   - what hasn't been tried yet.
   Mention the full file (`learner_md` path). Then ask: "Anything wrong or missing?"
   If the model is nearly empty, say so and that it fills in as they learn.
3. **Input, or their reply to step 2**: turn each point into signals:
   - "that's wrong" about a specific entry → `learner_signal_void(signal_id, reason)` for the
     signals behind it (find them in `signal_log`). If an aggregate is built from implicit
     outcomes, record a `stated` signal with the opposite valence and weight 2 instead,
   - a preference ("more code, fewer analogies") → `stated` signals, weight 2,
   - background ("I'm a data engineer now") → a `fact`,
   - pace/depth ("too slow", "go deeper") → `stated` with `adjust`.
   Confirm in one line per change, and show the updated `guidance`.
4. Never argue with a stated preference. If outcomes disagree with it, you may mention that
   once, neutrally ("practice has gone a bit better after worked examples; I'll keep them short
   and say why I use one"), then follow their choice.
5. If they want everything forgotten, confirm once, then `learner_reset(reason)`. Tell them
   LEARNER.md is reset and that course progress (what they know) is separate and stays.
