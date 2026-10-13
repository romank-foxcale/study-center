# Personalization: getting to know the learner

Mentor keeps two models of the learner:

| | What it answers | Where it lives | Updated by |
|---|---|---|---|
| **Knowledge model** | what do they know, per concept? | `node_state` (per course) | `evidence_record` |
| **Learner model** | how should we teach *this person*? | `signals` → `LEARNER.md` (one per workspace, all courses) | `learner_signal`, plus `taught_with` on `evidence_record` |

The learner model is global: someone who learned with game-dev examples in Linear Algebra
should get game-dev examples in Machine Learning on day one, and "you already know eigenvectors
from the LA course" is a free bridge. Read it with `learner_model()` before intake, before
writing a lesson, and at the start of every `/mentor:next`.

## What we adapt, and what we don't

Adapt what has evidence behind it:
- **Prior knowledge** (the strongest predictor of learning). Skip what they know, bridge from
  what they know, and drop worked examples for experts (expertise reversal effect).
- **Example domains** from their interests and work. Personalizing a problem's context to a
  learner's interests improves engagement and performance (Walkington 2013; Bernacki &
  Walkington 2018). Always say where an analogy breaks.
- **Explanation angle and order**: which entry point to use first (geometric, algebraic,
  computational...). It's an *ordering* choice: every learner still gets more than one
  representation, because connecting representations is where understanding comes from.
- **Pace, depth, length, rigor, challenge**: within the 70-85% success band (CONSTITUTION 16).

Don't:
- Match "learning styles" (visual / auditory / kinesthetic). Matching instruction to a
  self-declared style doesn't improve learning (Pashler et al. 2008). A learner who says "I'm a
  visual learner" gets diagrams *first*, not diagrams *only*.
- Record anything the learner didn't say or do. No guessing age, gender, nationality,
  health or anything sensitive. Facts are what they told you, in their words.
- Treat early preferences as settled. Keep exploring (see below).

## Signals

| kind | when | example call |
|---|---|---|
| `fact` | they tell you about themselves | `learner_signal(kind="fact", note="Backend dev, Python daily; did calculus at uni 10 years ago")` |
| `stated` | an explicit preference or interest | `learner_signal(kind="stated", dims={"domain": "chess"}, valence=1, note="I play a lot of chess")` |
| `reaction` | feedback on something you taught | `learner_signal(kind="reaction", dims={"angle": "geometric", "format": "diagram"}, valence=1, target="grid-shear picture", note="seeing the grid lean made it click", course=..., node=...)` |
| `outcome` | **automatic** | pass `taught_with={"angle": "geometric"}` to `evidence_record` for the first items after an explanation |

- `dims` vocabulary: `angle` (geometric, algebraic, computational, physical, story, historical,
  formal, analogy, intuitive), `format` (prose, worked-example, diagram, plot, interactive,
  animation, code, table, video), `abstraction` (concrete-first, abstract-first), `domain` (free
  text: the interest an example drew on). Tag only the dimensions the feedback is about.
- `valence`: 1 clearly helped, 0.5 somewhat, 0 neutral, -0.5 not much, -1 confused or annoyed.
- `adjust`: `{pace|depth|length|rigor|challenge: +1 more / 0 about right / -1 less}`. "Too slow"
  is `{"pace": 1}`; "too much text" is `{"length": -1}`; "this is too easy" is `{"challenge": 1}`.
- `note`: their words (short quote) plus, after a dash, your reading of *why*, e.g.
  `"the pizza thing confused me" - analogy hid that the operation isn't commutative`.
  The *why* is what makes the next lesson better.
- `weight` (default 1): use 2 for strong, explicit statements ("please never do X").

## Capturing feedback without making it a chore

1. **Listen all the time.** Any comment about the teaching ("that example was weird",
   "oh, now I get it", "can we go faster?") gets a signal right away, without asking them to
   repeat or rate it. This is the most valuable data and it's free.
2. **Implicit outcomes.** Pass `taught_with` on the first 1-2 graded items after each
   explanation. The engine compares the score with the learner's own baseline, so a hard item
   doesn't count against an angle unfairly. It's weighted low.
3. **One question at lesson close, optional, concrete.** Not a 1-5 rating. Name the actual
   pieces: *"Quick one, skip if you like: which part did the work for you, the shear picture or
   the matrix-column example? Anything that felt like noise?"* Turn the answer into 1-3 signals.
   Skip the question when they're tired, frustrated or in a hurry.
4. **Switch angles when stuck.** If an explanation isn't landing, use the pack's alternate
   angle. When it works, record a reaction for the new angle (and a mild negative for the old
   one only if they said it didn't help).
5. **Tune-up** every ~5 lessons, or when the model reports a conflict: show 3-4 lines of what
   you believe ("pictures before formulas, examples from game dev, a bit faster than default;
   proofs only when asked") and ask what's wrong. Corrections become `stated` signals (weight 2)
   or `learner_signal_void` for anything they say is false.
6. **Returning learner.** At intake for a new course, read the model and *confirm* rather than
   re-ask: "Last time geometric pictures and game-dev examples worked well. Same here?"

## Reading the model

`learner_model()` returns `guidance` (plain-language directives) plus the evidence:
- `works` / `avoid`: dimension values with enough evidence (score ≥ 0.65 or ≤ 0.35).
- `liked` vs `worked`: what they enjoy vs how practice actually went. `conflicts` lists where
  they disagree. *Liked but didn't work* → use it as the hook and teach the core another way.
  *Worked but disliked* → keep it brief, say why you use it, pair it with something they enjoy.
- `adjust`: cumulative pace/depth/length/rigor/challenge offsets from the default.
- `known_elsewhere`: concepts learned in other courses. Bridge from them; don't re-teach.
- `explore`: angles and formats never tried. **Explore vs exploit:** lead with what works,
  but about one lesson in four, use an untested angle as the *secondary* view. Early signals are
  noisy, and a learner who only ever sees one angle can't tell you another would be better.
- `facts`: background to draw on and pitch difficulty against.

Old signals fade (half-life about four months) so the model follows the learner as they grow:
an expert-to-be shouldn't be taught like the novice they were in January.

## Transparency

LEARNER.md (in the workspace) is regenerated after every signal and is written *to* the
learner. They can read it any time, and `/mentor:me` shows it and takes corrections. Never
hide what you've inferred, and never use the model to flatter or manipulate.
