"""Simulated learners for calibrating the learner model's thresholds (``learner_model.ModelParams``).

There is no labelled data on real learners yet, so we calibrate against synthetic ones whose
truth we know. Each learner has, per explanation angle:

- an **effect**: +1 the angle helps them, 0 neutral, -1 it hurts (what "worked" should find);
- a **taste**: whether they *like* it. Usually equal to the effect, sometimes not (the
  liked-but-ineffective and effective-but-disliked cases the model reports as conflicts).

A lesson-by-lesson loop then produces the signals Mentor would record: an outcome after each
explanation (scored against the learner's running baseline, like ``Mentor._score_baseline``),
spontaneous reactions, the optional end-of-lesson question, occasional misreports, an
intake statement, and the alternate angle when the primary doesn't land.

The noise levels below are assumptions, not measurements; calibration therefore checks that
the chosen thresholds hold up across a range of them. Run ``python -m mentor_core.learner_model_sim``
for the full grid search. Deterministic: same seeds, same numbers.
"""

from __future__ import annotations

import itertools
import random
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone

from . import learner_model
from .learner_model import DEFAULT_PARAMS, ModelParams

ANGLES = learner_model.DIMENSIONS["angle"]
T0 = datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc)
CHECKPOINTS = (10, 20, 30)


@dataclass(frozen=True)
class Noise:
    """How noisy a simulated learner's signals are."""
    item_sd: float = 0.25        # item difficulty noise on outcome scores (0..1 scale)
    effect_size: float = 0.12    # how much a helpful angle raises the expected score
    p_react: float = 0.3         # chance of a spontaneous reaction to an explanation
    p_answer: float = 0.5        # chance the end-of-lesson feedback question is answered
    p_misreport: float = 0.1     # chance a reaction has the wrong sign
    p_taste_differs: float = 0.25  # chance taste is not equal to the effect for an angle


NOISE_LEVELS = {
    "low": Noise(item_sd=0.15, p_misreport=0.05, p_taste_differs=0.15),
    "medium": Noise(),
    "high": Noise(item_sd=0.35, p_react=0.2, p_answer=0.35, p_misreport=0.15, p_taste_differs=0.35),
}


@dataclass
class Learner:
    effect: dict[str, int]
    taste: dict[str, int]


def make_learner(rng: random.Random, noise: Noise) -> Learner:
    effect = {a: rng.choices((1, 0, -1), weights=(0.25, 0.55, 0.2))[0] for a in ANGLES}
    taste = {a: (rng.choice((1, 0, -1)) if rng.random() < noise.p_taste_differs else e)
             for a, e in effect.items()}
    return Learner(effect, taste)


def _ts(day: int, minute: int) -> str:
    return (T0 + timedelta(days=day, minutes=minute)).isoformat()


def simulate(learner: Learner, rng: random.Random, noise: Noise, lessons: int,
             params: ModelParams = DEFAULT_PARAMS, closed_loop: bool = False):
    """Yield (lesson number, signals so far) after each lesson.

    Open loop: the primary angle is random (a fixed signal stream, so thresholds can be compared
    on identical data). Closed loop: the tutor follows the model like the skills do (lead with
    what works, never lead with "avoid", explore an untested angle about one lesson in four).
    """
    signals: list[dict] = []
    scores: list[float] = []
    ids = itertools.count(1)

    def add(kind: str, angle: str, valence: float, day: int, minute: int, weight: float = 1.0) -> None:
        signals.append({"id": next(ids), "ts": _ts(day, minute), "kind": kind, "dims": {"angle": angle},
                        "valence": max(-1.0, min(1.0, valence)), "adjust": {}, "weight": weight,
                        "note": None, "target": None})

    def react(angle: str, day: int, minute: int) -> None:
        t = learner.taste[angle]
        valence = t * rng.uniform(0.5, 1.0) if t else rng.choice((-0.5, 0.0, 0.5))
        if rng.random() < noise.p_misreport:
            valence = -valence
        if valence:
            add("reaction", angle, valence, day, minute)

    def explain(angle: str, day: int, minute: int) -> float:
        baseline = sum(scores[-30:]) / len(scores[-30:]) if len(scores) >= 3 else 0.7
        score = min(1.0, max(0.0, rng.gauss(0.7 + noise.effect_size * learner.effect[angle], noise.item_sd)))
        scores.append(score)
        add("outcome", angle, 2 * (score - baseline), day, minute)
        if rng.random() < noise.p_react:
            react(angle, day, minute + 1)
        return score

    favorite = max(ANGLES, key=lambda a: (learner.taste[a], rng.random()))
    if learner.taste[favorite] > 0 and rng.random() < 0.4:  # some learners state a preference at intake
        add("stated", favorite, 1.0, 0, 0)

    for lesson in range(1, lessons + 1):
        if closed_loop:
            model = learner_model.build(signals, T0 + timedelta(days=lesson), params=params)
            works = [e["value"] for e in model["works"] if e["dim"] == "angle"]
            avoid = {e["value"] for e in model["avoid"] if e["dim"] == "angle"}
            untested = [e["value"] for e in model["explore"] if e["dim"] == "angle"]
            if works and rng.random() < 0.75:
                primary = works[0]
            elif untested:
                primary = rng.choice(untested)
            else:
                primary = rng.choice([a for a in ANGLES if a not in avoid] or list(ANGLES))
            alternates = [a for a in ANGLES if a != primary and a not in avoid] or [a for a in ANGLES if a != primary]
        else:
            primary = rng.choice(ANGLES)
            alternates = [a for a in ANGLES if a != primary]
        score = explain(primary, lesson, 0)
        if score < 0.55:  # stuck: the tutor switches to the alternate explanation
            explain(rng.choice(alternates), lesson, 10)
        if rng.random() < noise.p_answer:  # the optional end-of-lesson question
            react(primary, lesson, 20)
        yield lesson, list(signals)


@dataclass
class Score:
    correct: int = 0
    harmful: int = 0      # "works" on an angle that hurts, or "avoid" on one that helps
    neutral: int = 0      # a verdict on an angle with no real effect
    conflicts_caught: int = 0
    targets: int = 0      # angles with a real effect (what we hope to get verdicts on)

    @property
    def verdicts(self) -> int:
        return self.correct + self.harmful + self.neutral

    @property
    def precision(self) -> float:
        return self.correct / self.verdicts if self.verdicts else 1.0

    @property
    def harmful_rate(self) -> float:
        return self.harmful / self.verdicts if self.verdicts else 0.0

    @property
    def coverage(self) -> float:
        return self.correct / self.targets if self.targets else 0.0


def score_model(model: dict, learner: Learner, s: Score) -> None:
    flagged = {c["value"] for c in model["conflicts"] if c["dim"] == "angle"}
    s.targets += sum(1 for e in learner.effect.values() if e)
    for verdict, sign in (("works", 1), ("avoid", -1)):
        for e in model[verdict]:
            if e["dim"] != "angle":
                continue
            truth = learner.effect[e["value"]]
            if truth == sign:
                s.correct += 1
            elif truth == -sign:
                if e["value"] in flagged:
                    s.conflicts_caught += 1  # wrong verdict, but the tutor is told about the conflict
                else:
                    s.harmful += 1
            else:
                s.neutral += 1


def evaluate(params: ModelParams, noise: Noise, learners: int = 150, lessons: int = 30,
             seed: int = 7, closed_loop: bool = False) -> dict[int, Score]:
    """Precision, harmful-error rate and coverage at each checkpoint, over many learners."""
    out = {c: Score() for c in CHECKPOINTS if c <= lessons}
    for i in range(learners):
        rng = random.Random(seed * 100_003 + i)
        learner = make_learner(rng, noise)
        for lesson, signals in simulate(learner, rng, noise, lessons, params, closed_loop):
            if lesson in out:
                model = learner_model.build(signals, T0 + timedelta(days=lesson + 1), params=params)
                score_model(model, learner, out[lesson])
    return out


def grid() -> list[ModelParams]:
    combos = []
    for margin, evidence, outcome_w in itertools.product(
            (0.6, 0.65, 0.7, 0.75), (1.0, 1.5, 2.0, 2.5, 3.0), (0.25, 0.5, 0.75, 1.0)):
        combos.append(replace(DEFAULT_PARAMS, works=margin, avoid=round(1 - margin, 2), min_evidence=evidence,
                              kind_weight={"stated": 1.5, "reaction": 1.0, "outcome": outcome_w}))
    return combos


def label(p: ModelParams) -> str:
    return f"works>={p.works} avoid<={p.avoid} evidence>={p.min_evidence} outcome_w={p.kind_weight['outcome']}"


def main() -> None:  # pragma: no cover - a calibration report, not part of the engine
    """Grid search. Ranking: worst-case harmful rate (any noise level, any checkpoint) must stay
    at or under 7%; among those, highest medium-noise coverage at lesson 20 first."""
    print("worst = worst harmful rate across noise levels and checkpoints; "
          "medium-noise columns are at lesson 20\n")
    print(f"{'params':62} {'worst':>6} {'harm':>6} {'cover':>6} {'prec':>6}")
    rows = []
    for p in grid() + [DEFAULT_PARAMS]:
        res = {name: evaluate(p, noise) for name, noise in NOISE_LEVELS.items()}
        worst = max(s.harmful_rate for r in res.values() for s in r.values())
        rows.append((p, worst, res["medium"][20]))
    ok = sorted((r for r in rows if r[1] <= 0.07), key=lambda r: (-r[2].coverage, r[1]))
    for p, worst, m in ok[:15]:
        mark = "  <- default" if p == DEFAULT_PARAMS else ""
        print(f"{label(p):62} {worst:6.3f} {m.harmful_rate:6.3f} {m.coverage:6.2f} {m.precision:6.2f}{mark}")
    print("\nClosed loop (the tutor follows the model) for the current defaults:")
    for name, noise in NOISE_LEVELS.items():
        r = evaluate(DEFAULT_PARAMS, noise, closed_loop=True)
        print(f"  {name:7}" + "  ".join(
            f"L{c}: harm {r[c].harmful_rate:.3f} cover {r[c].coverage:.2f} prec {r[c].precision:.2f}" for c in r))


if __name__ == "__main__":  # pragma: no cover
    main()
