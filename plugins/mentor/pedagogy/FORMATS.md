# Course file formats

All course files live in `<workspace>/courses/<slug>/` and are plain, human-editable Markdown.
(The workspace layout is adapted from Matt Pocock's `/teach` skill, MIT.)

## MISSION.md: why the learner is doing this
```markdown
# Mission: <goal in the learner's words>

## Why
<the real reason: job, project, curiosity, exam...>

## Done looks like
- <capability 1, observable: "can derive X", "can build Y">
- <capability 2>

## Constraints
- Time: <e.g. 4 h/week for 6 weeks>
- Deadline: <date or none>
```
Change it only after asking the learner. Every lesson's "why this matters" points back here.

## PROFILE.md: who the learner is (record only what they said)
```markdown
# Profile

## Already knows
- <topics, tools, level; quote the learner where possible>

## Preferences
- Depth: <1-10> (default 5)
- Communication: socratic | textbook | storytelling | layman
- Tone: encouraging | neutral | friendly | humorous
- Language: <language>
- Likes: <interests to draw analogies from>

## Diagnostic summary
<filled in after diagnostic_finish: known areas, starting frontier>
```

## RESOURCES.md: vetted sources only (written by the source-curator agent)
```markdown
# Resources

| id | Tier | Title | URL | Angle | Distinct contribution | Good for | Time | License |
|---|---|---|---|---|---|---|---|---|
| r1 | canonical | 3Blue1Brown, Essence of Linear Algebra ch. 3 | https://www.3blue1brown.com/lessons/linear-transformations | geometric | the grid-transformation picture of matrices; the origin of the explanation most others copy | matrices as functions | 11 min video | proprietary, free to watch |
| r2 | solid | OpenStax Calculus Vol 3, 2.3 | https://openstax.org/... | algebraic | worked dot-product examples with figures | dot product practice | 30 min | CC BY 4.0 |

## Dropped (and why)
- <title>, <url>: restates r1 with no new example; SEO page with no author.
```
- **Tier**: `canonical` (the best exposition of an idea; at most one or two per idea),
  `solid` (good, adds something the canonical one lacks), `reference` (look-ups: docs, tables).
- **Distinct contribution** is mandatory: what this source gives that no other listed source
  does. If you can't name one, the source doesn't belong.
- Prefer the *origin* of an explanation over rewrites of it. Record the license. Never include
  a source you have not opened.

## research/ANGLES.md: distinct ways to explain each key idea (source-curator)
```markdown
# Angles

## <key idea, e.g. matrix multiplication>
| Angle | One-line version | Best source | Existing visual |
|---|---|---|---|
| geometric | composing two transformations of the plane | r1 | 3B1B ch. 4 (link) |
| computational | each output entry is a dot product of a row and a column | r2 | none |
| algebraic | composition of linear maps written in coordinates | r4 | none |
Proven teaching order: geometric → computational → algebraic (r1, r6). Pitfall: starting with
the row-times-column rule makes the "why" invisible (r6).
```

## APPROACH.md: how this course will teach (curriculum-architect)
```markdown
# Approach

## Chosen approach
<one paragraph: e.g. "geometry first, then computation in NumPy, proofs only for the three
theorems the mission needs">

## Why for this learner
- <learner-model guidance, background facts, mission constraints that drove the choice>

## Primary angles by area
- <area>: <angle> (alternate: <angle>)

## Considered and rejected
- <approach>: <why not, for this learner>
```

## LEARNER.md: the learner model (generated; workspace root, all courses)
Written by the core after every learner signal. Don't edit it by hand: corrections go through
`/mentor:me` (`learner_signal` / `learner_signal_void`) so they are kept as evidence.
Sections: About you, What works for you, What doesn't, Mixed signals, Pace and depth,
Interests used for examples, Already learned in other courses, Not tried yet, Recent feedback.

PROFILE.md holds per-course preferences and the diagnostic summary. Who the learner is
across courses (background, what works, interests) lives in LEARNER.md.

## records/NNNN-<slug>.md: learning records (ADR style)
Write one when something non-obvious happens: a misconception surfaced, a breakthrough, a
preference discovered, a node inserted.
```markdown
# NNNN. <short title>
Date: <YYYY-MM-DD> · Node: <node id>

## What happened
## What it tells us
## What we changed
```

## research/<persona>.md: researcher output
```markdown
# <Persona> perspective on <goal>

## Must know first
- <prerequisite> - why [n]

## Key ideas and how they connect
## Common misconceptions
## Sources
[n] <title>, <url>, <license>
```
