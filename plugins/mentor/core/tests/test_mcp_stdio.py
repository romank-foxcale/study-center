"""End-to-end: launch the real stdio MCP server and call tools over the protocol."""

import json
import os
import sys

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def _text(result) -> object:
    return json.loads(result.content[0].text)


def test_stdio_server_lists_and_calls_tools(tmp_path, graph_yaml):
    env = {**os.environ, "MENTOR_WORKSPACE": str(tmp_path / "ws"),
           "MENTOR_PLUGIN_DATA": str(tmp_path / "pd"), "MENTOR_NOW": "2026-01-05T09:00:00+00:00"}
    params = StdioServerParameters(command=sys.executable, args=["-m", "mentor_core.mcp_server"], env=env)

    async def run():
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = {t.name for t in (await session.list_tools()).tools}
                assert {"course_create", "graph_propose", "evidence_record", "next_activity"} <= tools
                slug = _text(await session.call_tool("course_create", {"goal": "Linear algebra"}))["course"]
                saved = _text(await session.call_tool("graph_propose", {"course": slug, "graph_yaml": graph_yaml}))
                assert saved["saved"]
                nxt = _text(await session.call_tool("next_activity", {"course": slug}))
                assert nxt["type"] == "lesson"
                bad = await session.call_tool("evidence_record", {"course": slug, "node": "nope",
                                                                  "kind": "practice", "score": 1})
                assert bad.is_error
                assert "unknown node" in bad.content[0].text
                return tools

    tools = anyio.run(run)
    assert len(tools) >= 25
