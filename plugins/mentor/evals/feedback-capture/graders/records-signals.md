---
type: llm
weight: 2
---

The tutor turns the learner's feedback into learner-model signals instead of just
acknowledging it:
- a negative reaction (valence below 0) to the analogy (`angle: analogy`), with a note that
  keeps the learner's reason (it hid that order matters / non-commutativity);
- a positive reaction or stated preference for the geometric / visual explanation (e.g.
  `angle: geometric`, `format: interactive` or `animation`);
- the game-development background or interest recorded (a `fact` and/or `domain: game-dev`);
- it confirms briefly what changed and does not invent anything the learner didn't say
  (no guessed age, job level, or other personal details);
- it does not argue with the learner's preference.
