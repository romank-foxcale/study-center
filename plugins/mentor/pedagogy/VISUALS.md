# Visuals: text by default, pictures when they earn it

Most explanations are best as plain Markdown. A visual helps only when it shows something
text makes the learner *imagine*: motion, change under a parameter, spatial structure, or
many numbers at once. Decorative or redundant visuals make learning worse: they split
attention and add load without adding meaning (Mayer's coherence and redundancy principles;
the "seductive details" effect). So every visual has to earn its place.

## The ladder: use the lowest rung that works

| Level | What | Use when | Cost |
|---|---|---|---|
| **0 Text** | prose, lists, inline math, small tables | definitions, arguments, procedures, short derivations, comparisons. **The default.** | none |
| **1 Static figure in Markdown** | ```` ```mermaid ````, a table, a small ASCII sketch | relationships and structure: flows, hierarchies, a state machine, a before/after table | low; renders in VS Code, GitHub, Obsidian |
| **2 Parametric plot** | ```` ```plot ```` or ```` ```jsxgraph ```` in lesson.md (gets an HTML page) | the idea is about *how something changes* with a parameter, or a geometric construction the learner should drag | medium |
| **3 Bespoke explorable** | a standalone page built by the `visualizer` agent, saved with `explorable_save` | a dynamic process or high-dimensional structure where **manipulating it is the insight**: a matrix acting on the whole grid, eigenvectors staying on their span, attention weights flowing between tokens, gradient descent on a loss surface | high; at most one per lesson, most lessons none |
| **4 Link an existing one** | a link in lesson.md to a great existing visual (3Blue1Brown chapter, Transformer Explainer, Setosa, Distill...) | someone already built the ideal explorable for this exact idea | none. **Check this before building level 3.** |

## The test (answer before adding anything above level 0)

1. **What question does it answer?** One sentence the learner could ask ("what happens to the
   grid when the determinant hits zero?"). No question, no visual.
2. **Would text force the learner to imagine motion, change or many values at once?** If not,
   stay at level 0 or 1.
3. **Does interacting reveal something that looking doesn't?** (an invariant, a threshold, a
   cause-and-effect link). If not, a static figure is enough; don't build level 3.
4. **Does a good one already exist?** (the source curator lists existing visuals in
   `research/ANGLES.md`). Link it rather than rebuild it.
5. **Does the learner model favor or disfavor visuals?** It decides order and emphasis, not
   whether a visual that passes 1-3 is used.

Record the decision in the pack's `visuals` list (LESSON_TEMPLATE.md) with the level and the
answer to question 1, so the choice can be reviewed and the learner's reaction attributed.

## What makes a great explorable (level 3)

Distilled from the references we aim at:

- **3Blue1Brown** (*Essence of Linear Algebra*): geometry first, and **continuous motion**, so
  the learner watches the invariant (grid lines stay parallel and evenly spaced) rather than
  being told it. **Consistent color coding** for the same object everywhere (î green, ĵ red).
  One idea per view, and the learner is led to *discover* the definition.
- **Transformer Explainer** (Georgia Tech Polo Club): runs a **real model on the learner's own
  input**. **Overview first, zoom on demand**: the whole pipeline at a glance, click a block to
  expand it into the actual computation with live numbers. One meaningful control
  (temperature) whose effect is immediately visible downstream.
- **LLM Visualization** (bbycroft.net/llm): a **guided narrative synced with the visual**: a
  step-by-step walkthrough on one side, while the view moves to the part being described. A
  **small but complete** real example (a tiny GPT sorting letters) so every number can be traced
  end to end.
- **Neuronpedia**: understanding through **many real examples**. Browse actual cases (texts
  where a feature fires) rather than a single idealized one.
- **Explorable Explanations** (Bret Victor) and **Distill**: the reader can change the author's
  numbers and assumptions inline and see the consequences. Text and visual are one argument,
  not a picture pasted after a paragraph.

### Checklist for every level-3 page
- [ ] Answers the one question it was built for; the title says it.
- [ ] Opens in a **guided mode** (3-6 steps with Next/Back and a one-line caption per step),
      then hands over free play.
- [ ] Uses the learner's numbers or a small real example, never "foo/bar" data. Shows actual
      values on hover or inline.
- [ ] Overview first; details on demand.
- [ ] Same colors for the same objects as lesson.md and the other explorables in the course.
- [ ] At most 2-3 controls; each visibly changes something within 100 ms.
- [ ] Every symbol is labeled; units and axes are named.
- [ ] Works on a phone-width screen, in light and dark mode, and with the keyboard.
- [ ] Self-contained: one HTML file; scripts only from pinned CDN versions
      (cdn.jsdelivr.net, cdnjs.cloudflare.com, unpkg.com); no network calls.
      `explorable_save` enforces this.
- [ ] Math in it is verified (`check_math`) like everything else.
- [ ] Ends with a question for the learner ("drag until the area is zero. What do the columns
      look like?"). The tutor follows up on it in chat.

## In chat

The tutor teaches in chat, in text. Point to a visual at the moment it helps ("open
explore-shear.html and drag ĵ until the grid flattens; what do you notice?") rather than
listing links at the end. Afterwards, ask about it like any other part of the lesson and record
the reaction (`format: interactive`).
