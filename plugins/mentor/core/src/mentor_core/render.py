"""Lesson markdown -> self-contained HTML page (spec §6.10).

Supported fenced blocks: ``math``, ``mermaid``, ``plot`` (JSON spec for Observable Plot),
``jsxgraph`` (JS body run with a ``board`` variable), ``quiz`` (YAML self-check questions).
Inline/display math uses ``$...$`` / ``$$...$$``. Raw HTML in markdown is escaped.

Trust note: ``jsxgraph`` and plot ``fn`` blocks execute JavaScript. Lessons are written by
Mentor's own lesson-author agent; never paste web content into those blocks.
"""

from __future__ import annotations

import html
import json
from importlib import resources
from typing import Any

import yaml
from jinja2 import Environment
from markdown_it import MarkdownIt
from mdit_py_plugins.dollarmath import dollarmath_plugin

CDN = {
    "katex_css": "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css",
    "katex_js": "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js",
    "katex_auto": "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js",
    "mermaid": "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js",
    "d3": "https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js",
    "plot": "https://cdn.jsdelivr.net/npm/@observablehq/plot@0.6.16/dist/plot.umd.min.js",
    "jsxgraph_js": "https://cdn.jsdelivr.net/npm/jsxgraph@1.10.1/distrib/jsxgraphcore.js",
    "jsxgraph_css": "https://cdn.jsdelivr.net/npm/jsxgraph@1.10.1/distrib/jsxgraph.css",
}


def _math_renderer(content: str, options: dict[str, Any]) -> str:
    body = html.escape(content)
    if options.get("display_mode"):
        return f'<div class="math-display">\\[{body}\\]</div>\n'
    return f'<span class="math-inline">\\({body}\\)</span>'


class _Renderer:
    def __init__(self) -> None:
        self.md = MarkdownIt("commonmark", {"html": False, "linkify": False, "typographer": True})
        self.md.enable(["table", "strikethrough"])
        self.md.use(dollarmath_plugin, renderer=_math_renderer, double_inline=True)
        self.md.add_render_rule("fence", self._fence)
        self.used: set[str] = set()
        self.counter = 0

    def _fence(self, tokens, idx, options, env):  # noqa: ANN001 - markdown-it API
        token = tokens[idx]
        lang = (token.info or "").strip().split(" ")[0].lower()
        content = token.content
        self.counter += 1
        if lang in ("math", "latex", "tex"):
            self.used.add("math")
            return f'<div class="math-display">\\[{html.escape(content)}\\]</div>\n'
        if lang == "mermaid":
            self.used.add("mermaid")
            return f'<pre class="mermaid">{html.escape(content)}</pre>\n'
        if lang == "plot":
            self.used.add("plot")
            try:
                spec = json.loads(content)
            except ValueError as exc:
                return f'<div class="render-error">plot block: invalid JSON ({html.escape(str(exc))})</div>\n'
            return (f'<figure class="plot" id="plot-{self.counter}" '
                    f'data-spec="{html.escape(json.dumps(spec), quote=True)}"></figure>\n')
        if lang == "jsxgraph":
            self.used.add("jsxgraph")
            box = f"jxg-{self.counter}"
            code = content.replace("</script", "<\\/script")
            return (f'<div id="{box}" class="jxgbox"></div>\n<script>window.addEventListener("load",function(){{'
                    f'var board=JXG.JSXGraph.initBoard("{box}",{{boundingbox:[-5,5,5,-5],axis:true,'
                    f'showCopyright:false}});\n{code}\n}});</script>\n')
        if lang == "quiz":
            return self._quiz(content)
        cls = f' class="language-{html.escape(lang)}"' if lang else ""
        return f"<pre><code{cls}>{html.escape(content)}</code></pre>\n"

    def _quiz(self, content: str) -> str:
        try:
            questions = yaml.safe_load(content) or []
        except yaml.YAMLError as exc:
            return f'<div class="render-error">quiz block: invalid YAML ({html.escape(str(exc))})</div>\n'
        if isinstance(questions, dict):
            questions = [questions]
        parts = ['<section class="quiz">']
        for i, q in enumerate(questions, 1):
            if not isinstance(q, dict):
                continue
            parts.append(f'<div class="quiz-q"><p><b>Check {i}.</b> {self.md.renderInline(str(q.get("q", "")))}</p>')
            if q.get("options"):
                parts.append("<ol type='A'>" + "".join(
                    f"<li>{self.md.renderInline(str(o))}</li>" for o in q["options"]) + "</ol>")
            answer = self.md.renderInline(str(q.get("answer", "")))
            explain = self.md.renderInline(str(q.get("explain", ""))) if q.get("explain") else ""
            parts.append(f"<details><summary>Try it first, then reveal</summary><p><b>{answer}</b></p>"
                         f"{f'<p>{explain}</p>' if explain else ''}</details></div>")
        parts.append("</section>\n")
        self.used.update(("math", "quiz"))
        return "".join(parts)

    def render(self, markdown: str) -> str:
        out = self.md.render(markdown)
        if "math-inline" in out or "math-display" in out:
            self.used.add("math")
        return out


def _template() -> Any:
    text = resources.files("mentor_core").joinpath("templates/page.html.j2").read_text(encoding="utf-8")
    return Environment(autoescape=True).from_string(text)


def render_page(markdown: str, *, title: str, subtitle: str = "", sources: list[dict] | None = None,
                nav: dict[str, str] | None = None) -> dict[str, Any]:
    r = _Renderer()
    body = r.render(markdown)
    page = _template().render(title=title, subtitle=subtitle, body=body, sources=sources or [],
                              nav=nav or {}, used=sorted(r.used), cdn=CDN)
    return {"html": page, "features": sorted(r.used)}


def smoke_check(page_html: str) -> list[str]:
    """Cheap structural checks used by tests and the export step."""
    from html.parser import HTMLParser

    problems: list[str] = []

    class P(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.stack: list[str] = []

        def handle_starttag(self, tag, attrs):  # noqa: ANN001
            if tag not in ("meta", "link", "br", "hr", "img", "input", "source"):
                self.stack.append(tag)

        def handle_endtag(self, tag):  # noqa: ANN001
            if tag in self.stack:
                while self.stack and self.stack.pop() != tag:
                    pass
            else:
                problems.append(f"unexpected </{tag}>")

    p = P()
    p.feed(page_html)
    if p.stack:
        problems.append(f"unclosed tags: {p.stack[-5:]}")
    if 'class="render-error"' in page_html:
        problems.append("page contains render errors")
    return problems
