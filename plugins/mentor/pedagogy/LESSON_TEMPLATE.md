# Lesson anatomy (one knowledge node)

A lesson has two artifacts written *before* teaching, then an interactive run-through.

## A. Hidden lesson pack (`pack`, JSON), written by the lesson-author agent

```json
{
  "node": "vec.dot",
  "objective": "Compute dot products and interpret them as projection",
  "bloom": "apply",
  "key_ideas": ["k1: sum of component products", "k2: |a||b|cos θ", "k3: projection / similarity"],
  "misconceptions": [
    {"id": "m1", "text": "the dot product is a vector", "contrast": "it collapses two vectors to one number"}
  ],
  "personalization": "learner_model said: geometric first, game-dev examples, a bit faster; knows vectors from course ml-basics",
  "explanations": [
    {"id": "e1", "role": "primary", "dims": {"angle": "geometric", "format": "diagram"},
     "summary": "shadow of a onto b, scaled by |b|", "source": "r2"},
    {"id": "e2", "role": "alternate", "dims": {"angle": "computational", "format": "code"},
     "summary": "np.dot as a weighted sum; similarity score of two embeddings", "source": "r5"}
  ],
  "examples": [
    {"id": "x1", "label": "enemy in the field of view", "dims": {"domain": "game-dev", "angle": "geometric"},
     "breaks_where": "game engines normalize vectors first; the general dot product doesn't"}
  ],
  "visuals": [
    {"level": 2, "question": "how does a·b change as the angle between them grows?", "block": "plot"},
    {"level": 4, "question": "dot product as projection", "link": "https://www.3blue1brown.com/lessons/dot-products"}
  ],
  "worked_examples": [
    {"problem": "...", "steps": [{"step": "...", "why": "..."}], "answer": "...", "verified": "check_math: a·b = 11"}
  ],
  "faded_example": {"problem": "...", "given_steps": ["..."], "learner_completes": "final step", "answer": "..."},
  "explain_back_rubric": {"criteria": [{"id": "k1", "text": "mentions summing component products"},
                                       {"id": "k3", "text": "connects to projection or similarity"}],
                          "pass": "all criteria"},
  "items": [
    {"prompt": "...", "form": "numeric", "bloom": "apply", "purpose": "practice",
     "answer_key": {"answer": "11", "explanation": "1*3 + 2*4"},
     "rubric": {"criteria": [{"id": "c1", "text": "correct value", "points": 1}]}},
    {"prompt": "... (two-tier: answer + why)", "form": "two-tier", "bloom": "understand",
     "purpose": "misconception", "answer_key": {"answer": "B", "why": "..."},
     "misconception_map": {"A": "m1"}},
    {"prompt": "... new context ...", "form": "short", "bloom": "analyze", "purpose": "transfer",
     "answer_key": {"answer": "..."}}
  ]
}
```

Rules for the pack:
- `explanations`: one `primary` angle chosen from the learner model's guidance, and one
  `alternate` from a *different* angle, ready for when the primary doesn't land. About one
  lesson in four, make the alternate an untested angle from the model's `explore` list.
- `examples`: each tagged with `dims` (`domain` = the interest it draws on) and where the
  analogy breaks, so the learner's reaction to it can be recorded precisely.
- `visuals`: every visual above level 0 with its level and the question it answers
  (VISUALS.md). An empty list is normal.
- 4-6 practice items across at least 2 forms; at least one at the node's target Bloom level.
- One two-tier misconception item; every distractor maps to a named misconception.
- One explain-back rubric for concept and design nodes.
- One near-transfer item.
- Every worked solution and answer key is verified (`check_math`, executed code, or an
  independent re-derivation by the fact-checker). Record how in `verified`.

## B. Visible `lesson.md`: the learner's reference copy

Written for re-reading later, not to be dumped into chat. Sections:

1. `## Why this matters`: tie to the mission.
2. `## The intuition`: the primary explanation, concrete first, from the learner's world.
   Plain text unless VISUALS.md's test says a picture earns its place.
3. `## The idea, precisely`: definition / theorem / rule, each part tied back to the intuition.
4. `## Why it works`: derivation, mechanism, or what would break otherwise.
5. `## Worked example`: steps with a *why* for each.
6. `## Common traps`: the misconceptions and how to spot them.
7. `## Check yourself`: 2-3 numbered self-check questions (different from the graded items),
   with answers under a final `### Answers` heading. Use a `quiz` block only if the lesson already
   has an HTML page for other reasons: a quiz block alone forces one.
8. `## Key takeaways`: three bullets at most.
9. `## Another way to see it` (optional): the alternate explanation, briefly, for re-reading later.

Keep it short. A lesson is not a textbook chapter: if a paragraph restates something the
learner already knows (`known_elsewhere`, PROFILE.md) or something already said, cut it.

Cite sources inline as `[1]`, `[2]` matching the `sources` list passed to `lesson_save`.

### Fenced blocks the renderer understands
- ```` ```math ```` display LaTeX; inline `$...$`, display `$$...$$`.
- ```` ```mermaid ```` diagrams.
- ```` ```plot ```` JSON for Observable Plot: `{"marks":[{"type":"line","fn":"Math.sin(x)","domain":[-6,6]}],"caption":"..."}`
  or data marks `{"type":"dot","data":[{"x":1,"y":2}],"options":{"x":"x","y":"y"}}`.
- ```` ```jsxgraph ```` JavaScript using a ready `board` variable (e.g. `board.create('point',[1,2])`).
- ```` ```quiz ```` YAML list of `{q, options?, answer, explain?}` with click-to-reveal answers.

`lesson_save(render="auto")` writes `lesson.html` only when the lesson contains `plot`,
`jsxgraph` or `quiz` blocks or has an explorable; otherwise `lesson.md` is the reference copy.

## C. Teaching run (main conversation)

| Step | What happens | Engine call |
|---|---|---|
| 1 Warm-up | due review items if `next_activity` gave any | `evidence_record kind=review` |
| 2 Hook | why it matters for the mission; optional "guess first" question | none |
| 3 Activate | recall check on 1-2 key prereqs; fail → brief refresh or remediate | `evidence_record kind=check` on the prereq |
| 4 Intuition | the pack's primary explanation, concrete first, small steps; a visual only if the pack lists one | none |
| 5 Formal + why | statement plus why it works | none |
| 6 Worked example | with one "why does this step work?" prompt | none |
| 7 Faded example | learner completes the final step | `evidence_record kind=practice hinted=true taught_with=<primary dims>` |
| 8 Practice | 2-5 items from the pack, adaptive, hint ladder. Stuck after rung 2? Switch to the alternate explanation | `evidence_record kind=practice` each (`taught_with` on the first item after any explanation) |
| 9 Misconception | the two-tier item | `evidence_record kind=misconception` |
| 10 Explain-back | Feynman explanation (concept/design) or transfer item | `evidence_record kind=explain` |
| 11 Close | learner's own summary, confidence, "what would you check next time?", then one optional feedback question naming the actual examples/visuals (PERSONALIZATION.md) | `learner_signal` for each reaction |
| 12 Wrap up | point to lesson.md (or lesson.html if one was made), learning record if something notable happened, next activity | `next_activity` |

Throughout: whenever the learner comments on the teaching itself, record a `learner_signal`
right then (PERSONALIZATION.md).

Stop early and follow `next_action` whenever the engine returns `halt_and_remediate`,
`suggest_insert_prereq` or `gate passed`.
