import asyncio

from mcp_server.server import mcp, mcp_app


def test_mcp_app_exports_http_surface():
    assert mcp_app is not None


def test_mcp_tools_registered():
    async def _names():
        tools = await mcp.list_tools(run_middleware=False)
        return sorted(tool.name for tool in tools)

    names = asyncio.run(_names())
    assert names == [
        "capture",
        "create_entity",
        "get_entity",
        "get_note",
        "link_notes",
        "list_recent",
        "review",
        "search",
        "search_entities",
        "update_entity",
        "update_note",
    ]
