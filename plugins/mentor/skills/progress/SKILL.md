---
name: progress
description: Show Mentor learning progress for a course - mastery counts, capability progress, due-review forecast, confidence calibration, streak and the colored course map.
argument-hint: "[course]"
allowed-tools: mcp__plugin_mentor_core
---

# /mentor:progress

1. With several courses and none named, show `course_list` as a compact table and ask which
   one (or show all briefly).
2. `progress(course, format="html")`.
3. Report compactly:
   - one line: % learned, mastered count, reviews due now, streak
   - capabilities: `done/total` each, as a short list
   - reviews due over the next 7 days
   - calibration: if high-confidence answers are often wrong (or the reverse), say so in one sentence
   - the map: `graph_get(course, view="mermaid")` in a ```mermaid block
4. Mention the full pages: `progress_html` and `map_html`. Open them only if asked
   (`progress(course, format="html", open_browser=true)`).
5. End with the suggested next step from `next_activity`.
