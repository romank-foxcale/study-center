# Question design

## Forms by Bloom level
| Level | Good item forms |
|---|---|
| remember | recall, cloze |
| understand | explain in own words, give a new example, classify ("which of these is an X?") |
| apply | solve a novel problem, write or modify code |
| analyze | spot the error in a worked solution, compare two methods, "why does this fail when..." |
| evaluate | judge which approach is better and justify, critique an argument |
| create | design something under constraints, build a proof or program |

Use the `form` names: `mcq`, `two-tier`, `short`, `numeric`, `explain`, `code`, `proof`,
`error-spot`, `cloze`.

## Rules for every item
- One skill per item. If two things can go wrong, split it.
- Vary surface features (numbers, context, wording) so recognition can't stand in for understanding.
- Always allow "I don't know". Say it is a good answer: it beats guessing and gives better data.
  Record it with `idk=true`.
- Prefer free recall and short answers in reviews; multiple choice is for diagnosing misconceptions.

## Multiple choice
- Every distractor encodes exactly one named misconception, recorded in `misconception_map`.
  A wrong answer then tells you *which* misconception the learner holds.
- Options have similar length and grammar; vary the position of the correct answer.
- Prefer **two-tier** items: the answer plus "why?". This removes most lucky guesses.
- Pass `n_options` to `evidence_record` so the engine accounts for guessing.

## Diagnostic items (placement)
- Mostly Apply level: they carry the most information per minute.
- Quick (under 2 minutes), one skill, and the learner is told it's fine not to know.
- Score 1.0 for a correct answer, 0 for wrong, `idk=true` for "I don't know"; partial
  credit (0.5) only for clearly partial understanding.

## Scoring conventions for evidence_record
| Situation | score | flags |
|---|---|---|
| fully correct, unaided | 1.0 | |
| correct but with a hint | rubric score | `hinted=true, hint_level=n` |
| partially correct | rubric fraction | |
| wrong | 0-0.3 | `misconceptions=[...]` if identified |
| "I don't know" | omit | `idk=true` |
| learner asked to be told | omit | `kind="told"` |
| confidence asked first | | `confidence=1..5` |
