"""Anki export via genanki: one note per stored item on learned/mastered nodes."""

from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path

import genanki

_CSS = ".card{font-family:system-ui,sans-serif;font-size:18px;text-align:left;max-width:40em;margin:auto}"


def _stable_id(text: str) -> int:
    return int(hashlib.sha1(text.encode()).hexdigest()[:8], 16) | 1 << 30


def _answer_text(answer_key: str) -> str:
    try:
        key = json.loads(answer_key)
    except ValueError:
        return html.escape(answer_key)
    if isinstance(key, dict):
        parts = [key.get("answer") or key.get("text") or ""]
        if key.get("explanation"):
            parts.append(f"<br><br><i>{html.escape(str(key['explanation']))}</i>")
        return html.escape(str(parts[0])) + "".join(parts[1:])
    return html.escape(str(key))


def build_deck(course_slug: str, course_goal: str, items: list[dict], out_path: Path) -> dict:
    model = genanki.Model(
        _stable_id("mentor-model-v1"), "Mentor Q/A",
        fields=[{"name": "Question"}, {"name": "Answer"}, {"name": "Node"}],
        templates=[{
            "name": "Card 1",
            "qfmt": "{{Question}}<br><small style='color:#888'>{{Node}}</small>",
            "afmt": "{{FrontSide}}<hr id=answer>{{Answer}}",
        }],
        css=_CSS,
    )
    deck = genanki.Deck(_stable_id(f"mentor-deck-{course_slug}"), f"Mentor::{course_goal[:60]}")
    for it in items:
        deck.add_note(genanki.Note(
            model=model,
            fields=[html.escape(it["prompt"]).replace("\n", "<br>"), _answer_text(it["answer_key"]),
                    html.escape(it["node_id"])],
            guid=genanki.guid_for(it["item_id"]),
        ))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    genanki.Package(deck).write_to_file(str(out_path))
    return {"path": str(out_path), "notes": len(items)}
