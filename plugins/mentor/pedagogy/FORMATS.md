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

## RESOURCES.md: vetted sources only
```markdown
# Resources

| id | Title | URL | License | Good for | Notes |
|---|---|---|---|---|---|
| r1 | OpenStax Calculus Vol 3, ch 2 | https://openstax.org/... | CC BY 4.0 | vectors, dot product | clear figures |
```
Prefer openly licensed sources (OpenStax, Wikipedia, official docs, papers). Record the
license. Never include a source you have not opened.

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
