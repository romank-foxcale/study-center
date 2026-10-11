"""MCP (stdio) server exposing the Mentor core. Thin wrappers over ``service.Mentor``.

Tool descriptions are kept short on purpose: each one costs context in every session.
"""

from __future__ import annotations

import functools
from typing import Any, Callable

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from .service import Mentor, MentorError

INSTRUCTIONS = (
    "Mentor tutor core. It owns the knowledge graph, mastery state, and review schedule. "
    "Never declare mastery yourself: record every graded answer with evidence_record and "
    "report what it returns. Item answer keys are hidden unless include_key=true (graders only)."
)

server = MCPServer("mentor-core", instructions=INSTRUCTIONS, version="0.1.0")
_mentor: Mentor | None = None


def tool(fn: Callable) -> Callable:
    """Register ``fn`` as a tool; MentorError messages reach the model as tool errors."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except MentorError as exc:
            raise ToolError(str(exc)) from exc

    return server.tool()(wrapper)


def m() -> Mentor:
    global _mentor
    if _mentor is None:
        _mentor = Mentor()
    return _mentor


# --- courses -------------------------------------------------------------------
@tool
def course_create(goal: str, slug: str | None = None) -> dict:
    """Create a course for a learning goal. Returns its slug and folder."""
    return m().course_create(goal, slug)


@tool
def course_list() -> list[dict]:
    """List courses with progress counts."""
    return m().course_list()


@tool
def course_status(course: str | None = None) -> dict:
    """Stage, counts, due reviews, files present and the next activity for a course."""
    return m().course_status(course)


@tool
def profile_write(course: str, mission_md: str | None = None, profile_md: str | None = None,
                  notes_md: str | None = None) -> dict:
    """Write MISSION.md / PROFILE.md / NOTES.md for a course (only the ones given)."""
    return m().profile_write(course, mission_md, profile_md, notes_md)


@tool
def resources_write(course: str, resources_md: str) -> dict:
    """Write the course's vetted RESOURCES.md."""
    return m().resources_write(course, resources_md)


# --- graph ---------------------------------------------------------------------
@tool
def graph_propose(course: str, graph_yaml: str) -> dict:
    """Validate and (if valid) save the knowledge graph YAML. Returns errors/warnings/stats."""
    return m().graph_propose(course, graph_yaml)


@tool
def graph_get(course: str, view: str = "frontier", node: str | None = None) -> Any:
    """Read the graph: view=frontier|full|mermaid, or one node's detail (state, gate, edges)."""
    return m().graph_get(course, view, node)


@tool
def graph_insert_node(course: str, node_yaml: str, edges_yaml: str = "[]") -> dict:
    """Insert a missing prerequisite node plus its edges (validated like graph_propose)."""
    return m().graph_insert_node(course, node_yaml, edges_yaml)


# --- diagnostic ----------------------------------------------------------------
@tool
def diagnostic_next(course: str) -> dict:
    """Next placement probe (node + item request), or done=true."""
    return m().diagnostic_next(course)


@tool
def diagnostic_record(course: str, node: str, score: float, item_id: str | None = None,
                      idk: bool = False, confidence: int | None = None) -> dict:
    """Record a placement answer (score 0..1) and get the next probe."""
    return m().diagnostic_record(course, node, score, item_id, idk, confidence)


@tool
def diagnostic_finish(course: str) -> dict:
    """Conclude placement: mark known nodes and return the starting frontier."""
    return m().diagnostic_finish(course)


# --- items & evidence ----------------------------------------------------------
@tool
def item_save(course: str, node: str, item: dict) -> dict:
    """Store a question: {prompt, form, bloom?, answer_key, rubric?, misconception_map?, purpose?}."""
    return m().item_save(course, node, item)


@tool
def item_get(course: str, item_id: str, include_key: bool = False) -> dict:
    """Fetch a stored item. include_key=true only for grading."""
    return m().item_get(course, item_id, include_key)


@tool
def items_list(course: str, node: str | None = None) -> list[dict]:
    """List stored items (no answer keys)."""
    return m().items_list(course, node)


@tool
def evidence_record(course: str, node: str, kind: str, score: float | None = None,
                    item_id: str | None = None, form: str | None = None, bloom: str | None = None,
                    hinted: bool = False, hint_level: int = 0, idk: bool = False,
                    confidence: int | None = None, misconceptions: list[str] | None = None,
                    grader_version: str | None = None, rationale: str | None = None,
                    n_options: int | None = None) -> dict:
    """Record a graded answer. kind=practice|quiz|review|explain|misconception|check|told.
    Returns the engine's verdict: state, gate_missing, mastered, next_action."""
    return m().evidence_record(course, node, kind, score, item_id, form, bloom, hinted, hint_level,
                               idk, confidence, None, misconceptions, grader_version, rationale, n_options)


@tool
def evidence_void(course: str, evidence_id: int, reason: str) -> dict:
    """Void a mis-graded answer (learner challenged the grade); state is recomputed."""
    return m().evidence_void(course, evidence_id, reason)


@tool
def node_defer(course: str, node: str, days: float = 3, reason: str = "") -> dict:
    """Park a stuck node for some days (explicit escape hatch)."""
    return m().node_defer(course, node, days, reason)


# --- planning ------------------------------------------------------------------
@tool
def next_activity(course: str | None = None) -> dict:
    """What to do next: review | check | remediate | lesson | quiz | suggest_insert_prereq | done."""
    return m().next_activity(course)


@tool
def review_queue(course: str | None = None) -> list[dict]:
    """Due reviews (set-cover selection) for one or all courses."""
    return m().review_queue(course)


# --- lessons & rendering -------------------------------------------------------
@tool
def lesson_save(course: str, node: str, lesson_md: str, pack: dict,
                sources: list[dict] | None = None, title: str | None = None) -> dict:
    """Save a lesson (visible markdown + hidden pack with items) and render its HTML."""
    return m().lesson_save(course, node, lesson_md, pack, sources, title)


@tool
def lesson_render(course: str, lesson_id: str | None = None, node: str | None = None,
                  open_browser: bool = False) -> dict:
    """Re-render a lesson's HTML (optionally open it in the browser)."""
    return m().lesson_render(course, lesson_id, node, open_browser)


@tool
def render_markdown(course: str, markdown: str, title: str, filename: str,
                    open_browser: bool = False) -> dict:
    """Render a reference page (cheat sheet, explainer) to reference/<filename>.html."""
    return m().render_markdown(course, markdown, title, filename, open_browser)


# --- utilities -----------------------------------------------------------------
@tool
def check_math(expr_a: str, expr_b: str, variables: list[str] | None = None) -> dict:
    """Check two math expressions/equations for equivalence (SymPy syntax, e.g. 2*x**2)."""
    return m().check_math(expr_a, expr_b, variables)


@tool
def progress(course: str | None = None, format: str = "md", open_browser: bool = False) -> dict:
    """Progress summary; format=html also writes progress.html."""
    return m().progress(course, format, open_browser)


@tool
def export_anki(course: str | None = None) -> dict:
    """Export learned items as an Anki .apkg deck."""
    return m().export_anki(course)


@tool
def config(key: str | None = None, value: str | None = None) -> dict:
    """Read or set config: workspace, review_budget, desired_retention, diagnostic_max_questions."""
    return m().config(key, value)


def main() -> None:
    server.run("stdio")


if __name__ == "__main__":
    main()
