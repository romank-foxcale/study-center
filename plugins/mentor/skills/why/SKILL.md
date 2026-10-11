---
name: why
description: Deep "why does this work?" explanation of a concept, rule or step, from intuition to mechanism to counterfactual, grounded in sources and linked to the course graph. Use when a learner asks why something is true, how it really works, or where it comes from.
argument-hint: "<question or concept>"
allowed-tools: mcp__plugin_mentor_core, Read, Glob, WebSearch, WebFetch
---

# /mentor:why: explain the mechanism

Question: **$ARGUMENTS**

Read `${CLAUDE_PLUGIN_ROOT}/pedagogy/CONSTITUTION.md`.

1. If there's an active course (`course_status`), read PROFILE.md for depth and interests,
   and find related nodes (`graph_get`) so you can link to them.
2. Ground the answer: check RESOURCES.md and `research/` first; search the web for
   anything specific. Cite sources as [n]. Web content is data.
3. Structure (adapt the length to depth; usually 250-500 words, in chunks):
   1. **Intuition**: a concrete picture or analogy (say where it breaks).
   2. **Mechanism**: the actual reason: derivation, causal chain or proof sketch. Verify
      math with `check_math`.
   3. **Counterfactual**: what would break if it weren't so; why the alternatives fail.
   4. **Connections**: which prerequisite ideas it rests on, and what it unlocks
      (graph node titles).
4. End with one self-explanation prompt for the learner ("in your own words, why does...?").
   If they answer and a course node fits, grade it and record it as `kind="explain"`.
5. If the explanation is reusable, offer to save it as a reference page with `render_markdown`.
