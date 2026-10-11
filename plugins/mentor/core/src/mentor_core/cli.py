"""Command-line access to the same functions the MCP server exposes.

    mentor status [course]          mentor next [course]       mentor due
    mentor progress [course]        mentor rebuild-state       mentor validate-graph FILE
    mentor call METHOD '{"json": "kwargs"}'   # any service method, e.g. evidence_record
    mentor call METHOD @kwargs.json           # same, kwargs read from a file
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import graph as graphmod
from .service import Mentor, MentorError


def _print(value: object) -> None:
    if isinstance(value, str):
        print(value)
    else:
        print(json.dumps(value, indent=2, ensure_ascii=False, default=str))


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="mentor", description="Mentor tutor core")
    parser.add_argument("--workspace", help="override the learner workspace folder")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("status", "next", "progress"):
        p = sub.add_parser(name)
        p.add_argument("course", nargs="?")
    sub.add_parser("list")
    sub.add_parser("due")
    p = sub.add_parser("rebuild-state")
    p.add_argument("course", nargs="?")
    p = sub.add_parser("validate-graph")
    p.add_argument("file", type=Path)
    p = sub.add_parser("call")
    p.add_argument("method")
    p.add_argument("kwargs", nargs="?", default="{}")
    args = parser.parse_args(argv)

    if args.cmd == "validate-graph":
        _print(graphmod.validate(graphmod.parse(args.file.read_text(encoding="utf-8"))))
        return 0

    mentor = Mentor(args.workspace)
    try:
        if args.cmd == "status":
            _print(mentor.course_status(args.course))
        elif args.cmd == "next":
            _print(mentor.next_activity(args.course))
        elif args.cmd == "progress":
            _print(mentor.progress(args.course))
        elif args.cmd == "list":
            _print(mentor.course_list())
        elif args.cmd == "due":
            _print(mentor.review_queue())
        elif args.cmd == "rebuild-state":
            _print(mentor.rebuild_state(args.course))
        elif args.cmd == "call":
            method = getattr(mentor, args.method, None)
            if method is None or args.method.startswith("_"):
                raise MentorError(f"unknown method '{args.method}'")
            raw = args.kwargs
            if raw.startswith("@"):  # mentor call graph_propose @args.json (avoids shell quoting)
                raw = Path(raw[1:]).read_text(encoding="utf-8")
            _print(method(**json.loads(raw)))
    except MentorError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    finally:
        mentor.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
