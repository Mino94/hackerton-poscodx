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


def _presenton_http_connection() -> dict[str, Any] | None:
    try:
        from autopm.mcp.presenton_client import (
            _presenton_http_connection as _conn,
            is_presenton_mcp_enabled,
        )

        if is_presenton_mcp_enabled():
            return _conn()
    except Exception:
        return None
    return None


async def _load_mcp_tools_async() -> list[Any]:
    from langchain_mcp_adapters.client import MultiServerMCPClient

    servers: dict[str, Any] = {"autopm": _stdio_connection()}
    pres = _presenton_http_connection()
    if pres:
        servers["presenton"] = pres
    client = MultiServerMCPClient(servers)
    tools: list[Any] = []
    for name in servers:
        tools.extend(await client.get_tools(server_name=name))
    return tools


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

    presenton_mcp: dict[str, Any] = {"enabled": False}
    try:
        from autopm.mcp.presenton_client import (
            check_presenton_mcp_health,
            is_presenton_mcp_enabled,
            presenton_mcp_url,
        )

        if is_presenton_mcp_enabled():
            ok, msg = check_presenton_mcp_health()
            presenton_mcp = {
                "enabled": True,
                "url": presenton_mcp_url(),
                "healthy": ok,
                "detail": msg,
            }
    except Exception as exc:  # noqa: BLE001
        presenton_mcp = {"enabled": False, "error": str(exc)[:120]}

    return {
        "mcp_enabled": is_mcp_enabled(),
        "mcp_react": is_mcp_react_enabled(),
        "inprocess_tools": list(TOOL_HANDLERS.keys()),
        "stdio_tools_loaded": len(tools),
        "stdio_server": "python -m autopm.mcp.server",
        "presenton_mcp": presenton_mcp,
    }


def reset_mcp_cache() -> None:
    """테스트·재연결용."""
    global _tools_cache
    _tools_cache = None
    get_mcp_langchain_tools.cache_clear() if hasattr(get_mcp_langchain_tools, "cache_clear") else None
