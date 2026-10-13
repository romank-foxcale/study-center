---
name: config
description: View or change Mentor settings - workspace folder, review budget per session, desired retention, diagnostic length - and per-course teaching preferences (depth, tone, communication mode, language).
argument-hint: "[setting] [value]"
allowed-tools: mcp__plugin_mentor_core, Read
---

# /mentor:config

Global settings (`config` tool):
| key | meaning | default |
|---|---|---|
| `workspace` | folder holding courses and `mentor.db` (survives plugin uninstall) | `~/Mentor` |
| `review_budget` | max review picks per session | 5 |
| `desired_retention` | target recall probability for scheduling (0.7-0.97) | 0.9 |
| `diagnostic_max_questions` | placement quiz cap | 20 |

1. No arguments: `config()` and show the table with current values, then the per-course
   preferences from PROFILE.md.
2. Setting a global key: `config(key, value)`. For `workspace`, warn that existing courses stay
   in the old folder (they can move the folder themselves) and that it takes effect after
   `/reload-plugins` or a new session.
3. Per-course preferences (depth 1-10, tone, communication mode, language, interests): update
   PROFILE.md via `profile_write(course, profile_md=...)`, keeping everything else intact.
4. How Mentor teaches *this person* across courses (angles, examples, pace) is learned from
   feedback rather than configured: point them to `/mentor:me` to see or correct it.
5. Tip: the optional Socratic output style can be enabled with `/output-style mentor`.
