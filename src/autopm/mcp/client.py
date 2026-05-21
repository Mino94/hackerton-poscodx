"""LangChain MCP Client — stdio 서버 연결 및 ReAct용 도구 로드."""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any

from autopm.mcp.policy import is_mcp_enabled, is_mcp_react_enabled

_tools_cache: list[Any] | None = None


def _stdio_connection() -> dict[str, Any]:
    """AutoPM 내장 MCP 서버 — langchain-mcp-adapters StdioConnection 형식."""
    return {
        "transport": "stdio",
        "command": sys.executable,
        "args": ["-m", "autopm.mcp"],
        "env": {**os.environ, "PYTHONPATH": os.pathsep.join(_pythonpath_entries())},
    }


def _pythonpath_entries() -> list[str]:
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    src = os.path.join(root, "src")
    entries = [p for p in (src, root) if os.path.isdir(p)]
    existing = os.environ.get("PYTHONPATH", "")
    if existing:
        entries.extend(existing.split(os.pathsep))
    return entries


async def _load_mcp_tools_async() -> list[Any]:
    from langchain_mcp_adapters.client import MultiServerMCPClient

    client = MultiServerMCPClient({"autopm": _stdio_connection()})
    return await client.get_tools(server_name="autopm")


def get_mcp_langchain_tools() -> list[Any]:
    """LangChain BaseTool 목록 — ReAct 루프용. 실패 시 빈 리스트."""
    global _tools_cache
    if not is_mcp_enabled() or not is_mcp_react_enabled():
        return []
    if _tools_cache is not None:
        return _tools_cache
    try:
        tools = asyncio.run(_load_mcp_tools_async())
        _tools_cache = list(tools)
        return _tools_cache
    except Exception:
        return []


def get_mcp_status() -> dict[str, Any]:
    """Streamlit·디버그용 MCP 상태."""
    tools = get_mcp_langchain_tools() if is_mcp_react_enabled() else []
    from autopm.mcp.registry import TOOL_HANDLERS

    return {
        "mcp_enabled": is_mcp_enabled(),
        "mcp_react": is_mcp_react_enabled(),
        "inprocess_tools": list(TOOL_HANDLERS.keys()),
        "stdio_tools_loaded": len(tools),
        "stdio_server": "python -m autopm.mcp.server",
    }


def reset_mcp_cache() -> None:
    """테스트·재연결용."""
    global _tools_cache
    _tools_cache = None
    get_mcp_langchain_tools.cache_clear() if hasattr(get_mcp_langchain_tools, "cache_clear") else None
