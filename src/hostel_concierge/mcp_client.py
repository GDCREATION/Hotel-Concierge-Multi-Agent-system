"""Specialists call this client. Tool schemas do not include guest id or room."""

from __future__ import annotations

import asyncio

from hostel_concierge.runtime_state import cache_mcp_names, cached_mcp_names


def _server():
    from hostel_concierge.mcp_server.server import mcp

    return mcp


def _unwrap(result) -> dict:
    data = getattr(result, "data", None)
    if isinstance(data, dict):
        return data
    if isinstance(data, str):
        return {"status": "ok", "message": data}
    content = getattr(result, "content", None) or []
    if content:
        text = getattr(content[0], "text", str(content[0]))
        return {"status": "error" if getattr(result, "is_error", False) else "ok", "message": text}
    return {"status": "error", "message": "The tool returned an empty result."}


async def _list_names() -> list[str]:
    from fastmcp import Client

    async with Client(_server()) as client:
        tools = await client.list_tools()
        return [tool.name for tool in tools]


async def _call(name: str, arguments: dict) -> dict:
    from fastmcp import Client

    async with Client(_server()) as client:
        result = await client.call_tool(name, arguments, raise_on_error=False)
        return _unwrap(result)


def mcp_tool_names() -> set[str]:
    cached = cached_mcp_names()
    if cached is not None:
        return cached
    names = set(asyncio.run(_list_names()))
    cache_mcp_names(names)
    return names


def mcp_call(name: str, arguments: dict | None = None) -> dict:
    try:
        return asyncio.run(_call(name, arguments or {}))
    except Exception as exc:  # noqa: BLE001 - return a guest-safe payload
        return {
            "status": "error",
            "code": "tool_error",
            "message": f"The {name} tool failed. Please try again.",
            "detail": str(exc),
        }
