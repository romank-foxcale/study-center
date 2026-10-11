---
name: export
description: Export a Mentor course - Anki deck (.apkg) of learned items, a JSON dump of state, or a self-contained HTML course of all lessons.
argument-hint: "[course] [anki|json|html-course]"
allowed-tools: mcp__plugin_mentor_core, Read, Write, Glob
---

# /mentor:export

- **anki** (default): `export_anki(course)` → path and note count. Tell the user to import
  it in Anki via File → Import. Only items on learned or mastered nodes are included.
- **json**: write `<dir>/exports/<slug>.json` containing `course_status`, `progress`,
  `graph_get(view="full")` and `items_list` (no answer keys) for portability.
- **html-course**: every lesson is already rendered at `<dir>/lessons/*/lesson.html`, linked
  with previous/next and to `graph.html`. Re-render them all with `lesson_render` for each
  lesson (from `Glob <dir>/lessons/*/meta.json`), then point the user to the first lesson and
  the map. Report any `problems` returned by the renderer.
