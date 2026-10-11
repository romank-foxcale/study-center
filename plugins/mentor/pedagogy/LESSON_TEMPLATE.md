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
- 4-6 practice items across at least 2 forms; at least one at the node's target Bloom level.
- One two-tier misconception item; every distractor maps to a named misconception.
- One explain-back rubric for concept and design nodes.
- One near-transfer item.
- Every worked solution and answer key is verified (`check_math`, executed code, or an
  independent re-derivation by the fact-checker). Record how in `verified`.

## B. Visible `lesson.md`: the learner's reference copy

Written for re-reading later, not to be dumped into chat. Sections:

1. `## Why this matters`: tie to the mission.
2. `## The intuition`: concrete example, analogy or picture (mermaid/plot/jsxgraph blocks welcome).
3. `## The idea, precisely`: definition / theorem / rule, each part tied back to the intuition.
4. `## Why it works`: derivation, mechanism, or what would break otherwise.
5. `## Worked example`: steps with a *why* for each.
6. `## Common traps`: the misconceptions and how to spot them.
7. `## Check yourself`: a `quiz` block with 2-3 self-check questions (different from the graded items).
8. `## Key takeaways`: three bullets at most.

Cite sources inline as `[1]`, `[2]` matching the `sources` list passed to `lesson_save`.

### Fenced blocks the renderer understands
- ```` ```math ```` display LaTeX; inline `$...$`, display `$$...$$`.
- ```` ```mermaid ```` diagrams.
- ```` ```plot ```` JSON for Observable Plot: `{"marks":[{"type":"line","fn":"Math.sin(x)","domain":[-6,6]}],"caption":"..."}`
  or data marks `{"type":"dot","data":[{"x":1,"y":2}],"options":{"x":"x","y":"y"}}`.
- ```` ```jsxgraph ```` JavaScript using a ready `board` variable (e.g. `board.create('point',[1,2])`).
- ```` ```quiz ```` YAML list of `{q, options?, answer, explain?}` with click-to-reveal answers.

## C. Teaching run (main conversation)

| Step | What happens | Engine call |
|---|---|---|
| 1 Warm-up | due review items if `next_activity` gave any | `evidence_record kind=review` |
| 2 Hook | why it matters for the mission; optional "guess first" question | none |
| 3 Activate | recall check on 1-2 key prereqs; fail → brief refresh or remediate | `evidence_record kind=check` on the prereq |
| 4 Intuition | concrete first, small steps, a picture if it helps | none |
| 5 Formal + why | statement plus why it works | none |
| 6 Worked example | with one "why does this step work?" prompt | none |
| 7 Faded example | learner completes the final step | `evidence_record kind=practice hinted=true` |
| 8 Practice | 2-5 items from the pack, adaptive, hint ladder | `evidence_record kind=practice` each |
| 9 Misconception | the two-tier item | `evidence_record kind=misconception` |
| 10 Explain-back | Feynman explanation (concept/design) or transfer item | `evidence_record kind=explain` |
| 11 Close | learner's own summary, confidence, "what would you check next time?" | none |
| 12 Wrap up | render, learning record if something notable happened, next activity | `lesson_render`, `next_activity` |

Stop early and follow `next_action` whenever the engine returns `halt_and_remediate`,
`suggest_insert_prereq` or `gate passed`.
