"""Learner model: *who* the learner is and what kind of teaching works for them.

``learner.py`` tracks what the learner knows (per node). This module tracks how to teach them:
which explanation angles, formats and example domains help, what pace and depth they want, and
facts about their background. It spans all courses: a person is the same person in every course.

Like node state, the model is derived by replaying an append-only signal log, so a correction
is a voided signal, never an edited preference. Deterministic, no LLM calls.

Signal kinds (weights in ``KIND_WEIGHT``):
- ``fact``: background the learner stated ("backend developer, Python daily"). Not scored.
- ``stated``: an explicit preference ("I prefer pictures before formulas", "I like chess").
- ``reaction``: feedback on something specific that was taught ("the camera analogy clicked").
- ``outcome``: implicit; how practice went right after a given angle, relative to the
  learner's own baseline. Weighted low because item difficulty confounds it.

We keep "liked" (stated + reaction) and "worked" (outcome) apart and report disagreements:
learners' preferences and what actually helps them often differ, and the tutor should know.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from .paths import parse_ts

SIGNAL_KINDS = ("fact", "stated", "reaction", "outcome")

# Categorical dimensions. ``None`` means free text (normalized to lowercase-hyphenated).
DIMENSIONS: dict[str, tuple[str, ...] | None] = {
    "angle": ("geometric", "algebraic", "computational", "physical", "story", "historical",
              "formal", "analogy", "intuitive"),
    "format": ("prose", "worked-example", "diagram", "plot", "interactive", "animation", "code",
               "table", "video"),
    "abstraction": ("concrete-first", "abstract-first"),
    "domain": None,  # where examples come from: the learner's interests (chess, game-dev, ...)
}
# Ordinal settings the learner nudges: +1 "more of it", -1 "less of it", 0 "about right".
ADJUST_DIMS = ("pace", "depth", "length", "rigor", "challenge")
ADJUST_WORDS = {"pace": ("slower", "faster"), "depth": ("lighter", "deeper"),
                "length": ("shorter", "longer"), "rigor": ("less formal", "more formal"),
                "challenge": ("easier", "harder")}

KIND_WEIGHT = {"stated": 1.5, "reaction": 1.0, "outcome": 0.5}
HALF_LIFE_DAYS = 120.0
WORKS, AVOID, MIN_EVIDENCE = 0.65, 0.35, 1.5


def normalize_value(value: Any) -> str:
    return "-".join(str(value).strip().lower().replace("_", " ").split())


def validate_dims(dims: dict | None) -> dict[str, str]:
    """Normalize ``dims``; raise ValueError listing the allowed values on bad input."""
    out: dict[str, str] = {}
    for key, value in (dims or {}).items():
        key = normalize_value(key)
        if key not in DIMENSIONS:
            raise ValueError(f"unknown dimension '{key}'; use one of {sorted(DIMENSIONS)}")
        val = normalize_value(value)
        allowed = DIMENSIONS[key]
        if not val or (allowed is not None and val not in allowed):
            raise ValueError(f"{key} must be one of {list(allowed or [])}" if allowed
                             else f"{key} needs a value")
        out[key] = val
    return out


def validate_adjust(adjust: dict | None) -> dict[str, int]:
    out: dict[str, int] = {}
    for key, value in (adjust or {}).items():
        key = normalize_value(key)
        if key not in ADJUST_DIMS:
            raise ValueError(f"unknown adjustment '{key}'; use one of {list(ADJUST_DIMS)}")
        if value not in (-1, 0, 1):
            raise ValueError(f"adjust.{key} must be -1 (less), 0 (about right) or 1 (more)")
        out[key] = int(value)
    return out


class _Tally:
    __slots__ = ("pos", "neg", "n")

    def __init__(self) -> None:
        self.pos = self.neg = 0.0
        self.n = 0

    def add(self, valence: float, weight: float) -> None:
        self.pos += weight * max(valence, 0.0)
        self.neg += weight * max(-valence, 0.0)
        self.n += 1

    @property
    def evidence(self) -> float:
        return self.pos + self.neg

    @property
    def mean(self) -> float:  # Beta(1, 1) prior: 0.5 with no evidence
        return (1 + self.pos) / (2 + self.pos + self.neg)


def build(signals: list[dict], now: datetime,
          known_elsewhere: list[dict] | None = None) -> dict[str, Any]:
    """Derive the learner model from (non-voided) signals in chronological order."""
    facts: list[dict] = []
    liked: dict[tuple[str, str], _Tally] = defaultdict(_Tally)
    worked: dict[tuple[str, str], _Tally] = defaultdict(_Tally)
    offsets: dict[str, int] = defaultdict(int)
    adjust_n: dict[str, int] = defaultdict(int)
    notes: list[dict] = []

    for s in signals:
        if s["kind"] == "fact":
            if s.get("note") and all(f["text"] != s["note"] for f in facts):
                facts.append({"text": s["note"], "since": s["ts"][:10], "signal_id": s["id"]})
            continue
        age = max((now - parse_ts(s["ts"])).total_seconds() / 86400, 0.0)
        w = float(s.get("weight") or 1.0) * KIND_WEIGHT[s["kind"]] * 0.5 ** (age / HALF_LIFE_DAYS)
        valence = max(-1.0, min(1.0, float(s["valence"] or 0.0)))
        bucket = worked if s["kind"] == "outcome" else liked
        for dim, val in (s.get("dims") or {}).items():
            bucket[(dim, val)].add(valence, w)
        for dim, step in (s.get("adjust") or {}).items():
            # Cumulative and undecayed: "faster, please" stays true until they say otherwise.
            offsets[dim] = max(-3, min(3, offsets[dim] + int(step)))
            adjust_n[dim] += 1
        if s.get("note") and s["kind"] != "outcome":
            notes.append({"date": s["ts"][:10], "kind": s["kind"], "target": s.get("target"),
                          "valence": valence, "note": s["note"], "signal_id": s["id"]})

    prefs = []
    for key in sorted(set(liked) | set(worked)):
        both = _Tally()
        for src in (liked.get(key), worked.get(key)):
            if src:
                both.pos, both.neg, both.n = both.pos + src.pos, both.neg + src.neg, both.n + src.n
        entry = {"dim": key[0], "value": key[1], "score": round(both.mean, 2),
                 "evidence": round(both.evidence, 2), "signals": both.n,
                 "liked": round(liked[key].mean, 2) if key in liked else None,
                 "worked": round(worked[key].mean, 2) if key in worked else None}
        if both.evidence >= MIN_EVIDENCE and both.mean >= WORKS:
            entry["verdict"] = "works"
        elif both.evidence >= MIN_EVIDENCE and both.mean <= AVOID:
            entry["verdict"] = "avoid"
        else:
            entry["verdict"] = "unclear"
        prefs.append(entry)
    prefs.sort(key=lambda e: (-e["evidence"] * abs(e["score"] - 0.5), e["dim"], e["value"]))

    conflicts = []
    for key in sorted(set(liked) & set(worked)):
        lk, wk = liked[key], worked[key]
        if lk.evidence < 1 or wk.evidence < 1:
            continue
        if lk.mean >= WORKS and wk.mean <= 0.4:
            conflicts.append({"dim": key[0], "value": key[1], "pattern": "liked_not_worked",
                              "advice": "the learner enjoys it but practice after it is weak: "
                                        "use it as a hook, then teach the core with an angle that works"})
        elif lk.mean <= AVOID and wk.mean >= 0.6:
            conflicts.append({"dim": key[0], "value": key[1], "pattern": "worked_not_liked",
                              "advice": "it helps even though the learner dislikes it: keep it short, "
                                        "say why you use it, and pair it with an angle they enjoy"})

    tested = set(liked) | set(worked)
    explore = [{"dim": d, "value": v} for d in ("angle", "format")
               for v in DIMENSIONS[d] or () if (d, v) not in tested][:6]

    adjustments = {}
    for dim in ADJUST_DIMS:
        if adjust_n.get(dim):
            off = offsets[dim]
            less, more = ADJUST_WORDS[dim]
            word = "as default" if off == 0 else (more if off > 0 else less)
            strength = {1: "a bit ", 2: "", 3: "much "}.get(abs(off), "")
            adjustments[dim] = {"offset": off, "signals": adjust_n[dim],
                                "text": word if off == 0 else f"{strength}{word}"}

    model = {
        "signals": len(signals),
        "facts": facts,
        "interests": [e["value"] for e in prefs if e["dim"] == "domain" and e["score"] > 0.5],
        "works": [e for e in prefs if e["verdict"] == "works"],
        "avoid": [e for e in prefs if e["verdict"] == "avoid"],
        "unclear": [e for e in prefs if e["verdict"] == "unclear"],
        # Too little evidence for a verdict, but already leaning one way: worth acting on gently.
        "early_signs": [e for e in prefs if e["verdict"] == "unclear" and e["evidence"] >= 0.75
                        and abs(e["score"] - 0.5) >= 0.15],
        "conflicts": conflicts,
        "adjust": adjustments,
        "explore": explore,
        "known_elsewhere": known_elsewhere or [],
        "recent_feedback": notes[-8:][::-1],
    }
    model["guidance"] = guidance(model)
    return model


def _label(e: dict) -> str:
    return f"{e['value']} ({e['dim']})"


def guidance(model: dict) -> list[str]:
    """Plain-language directives for lesson authors and the tutor."""
    out: list[str] = []
    works = [e for e in model["works"] if e["dim"] != "domain"]
    if works:
        out.append("Lead with: " + ", ".join(_label(e) for e in works[:4]) + ".")
    if model["interests"]:
        out.append("Draw examples from: " + ", ".join(model["interests"][:5])
                   + ". Say where an analogy breaks.")
    if model["avoid"]:
        out.append("Avoid as the main explanation: " + ", ".join(_label(e) for e in model["avoid"][:4])
                   + " (fine as a brief secondary view).")
    early = [e for e in model["early_signs"] if e["dim"] != "domain" or e["score"] < 0.5]
    if early:
        out.append("Early signs (not settled): " + ", ".join(
            f"{_label(e)} {'helped' if e['score'] > 0.5 else 'did not help'}" for e in early[:4]) + ".")
    for c in model["conflicts"]:
        out.append(f"{c['value']} ({c['dim']}): {c['advice']}.")
    for dim, a in model["adjust"].items():
        if a["offset"]:
            out.append(f"{dim.capitalize()}: {a['text']} than the default.")
    if model["explore"]:
        untested = ", ".join(e["value"] for e in model["explore"][:3])
        out.append(f"Still untested: {untested}. Try one as a secondary angle now and then; "
                   "early preferences are noisy.")
    if model["signals"] < 5:
        out.append("Little evidence yet: vary angles and ask one short feedback question per lesson.")
    return out


def _word(mean: float, high: str, low: str, mid: str) -> str:
    return high if mean >= 0.6 else low if mean <= 0.4 else mid


def to_markdown(model: dict) -> str:
    """LEARNER.md: the open learner model, readable (and challengeable) by the learner."""
    lines = ["# What Mentor knows about you", "",
             "Built from your feedback and how practice went, across all courses. If something is",
             "wrong, say so, or run `/mentor:me`: corrections take effect immediately.", ""]

    def pref_line(e: dict) -> str:
        basis = []
        if e["liked"] is not None:
            basis.append("your feedback: " + _word(e["liked"], "positive", "negative", "mixed"))
        if e["worked"] is not None:
            basis.append("practice afterwards: " + _word(e["worked"], "better than usual",
                                                          "worse than usual", "about usual"))
        return f"- **{e['value']}** ({e['dim']}): {'; '.join(basis)} ({e['signals']} signal(s))"

    sections = [
        ("About you", [f"- {f['text']} _(since {f['since']})_" for f in model["facts"]]),
        ("What works for you", [pref_line(e) for e in model["works"]]),
        ("What doesn't", [pref_line(e) for e in model["avoid"]]),
        ("Early signs", [pref_line(e) for e in model["early_signs"]]),
        ("Mixed signals", [f"- **{c['value']}** ({c['dim']}): {c['advice']}" for c in model["conflicts"]]),
        ("Pace and depth", [f"- {d}: {a['text']}" for d, a in model["adjust"].items()]),
        ("Interests used for examples", [f"- {i}" for i in model["interests"]]),
        ("Already learned in other courses", [
            f"- {k['title']} ({k['course']}, {k['state']})" for k in model["known_elsewhere"][:30]]),
        ("Not tried yet", [f"- {e['value']} ({e['dim']})" for e in model["explore"]]),
        ("Recent feedback", [
            f"- {n['date']}: {'+' if n['valence'] > 0 else '-' if n['valence'] < 0 else '~'} "
            f"{(n['target'] + ': ') if n['target'] else ''}\"{n['note']}\"" for n in model["recent_feedback"]]),
    ]
    for title, body in sections:
        if body:
            lines += [f"## {title}", *body, ""]
    if model["signals"] == 0:
        lines += ["_Nothing yet. This fills in as you learn._", ""]
    lines.append(f"_Derived from {model['signals']} signal(s)._")
    return "\n".join(lines) + "\n"
