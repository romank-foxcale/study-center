# mentor-core

The provider-agnostic engine behind the Mentor plugin. It contains no LLM calls. It owns:

- **store**: SQLite evidence log (append-only, authoritative) plus derived node state
- **graph**: knowledge-graph schema, validation, frontier, Mermaid export
- **learner**: BKT mastery estimate, node state machine, mastery gate
- **fsrs_adapter / fire**: spaced-repetition scheduling and implicit credit propagation
- **diagnostic / planner**: adaptive placement and "what next" decisions
- **render / export_anki**: lesson HTML and Anki decks
- **mcp_server / cli**: the same functions exposed over MCP and on the command line

```bash
uv run pytest
uv run mentor --help
```
