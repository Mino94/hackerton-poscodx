"""MCP ReAct — bind_tools + tool_calls 루프로 LLM Agent가 MCP 도구를 직접 호출."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from autopm.mcp.client import get_mcp_langchain_tools
from autopm.mcp.policy import is_mcp_react_enabled, resolve_tool_names
from autopm.services.llm_router import _coerce_llm_text, _content_to_text, _fallback_for_key


def invoke_with_mcp_react(
    system: str,
    user: str,
    *,
    model: Any,
    agent_key: str,
    task_key: str = "",
    fallback_key: str = "generic",
    context: dict[str, str] | None = None,
    max_rounds: int = 4,
) -> tuple[str, str]:
    """
    OpenAI 등 tool-calling 지원 모델 + MCP LangChain tools.
    실패·도구 없음 시 일반 invoke 폴백은 호출측에서 처리.
    """
    ctx = context or {}
    if not is_mcp_react_enabled():
        raise RuntimeError("mcp_react_disabled")

    all_tools = get_mcp_langchain_tools()
    allowed = set(resolve_tool_names(agent_key, task_key))
    tools = [t for t in all_tools if getattr(t, "name", "") in allowed]
    if not tools:
        raise RuntimeError("no_mcp_tools_for_agent")

    bound = model.bind_tools(tools)
    messages: list[Any] = [
        SystemMessage(content=system),
        HumanMessage(content=user),
    ]

    for _ in range(max_rounds):
        resp = bound.invoke(messages)
        tool_calls = getattr(resp, "tool_calls", None) or []
        if not tool_calls:
            text = _content_to_text(getattr(resp, "content", ""))
            return _coerce_llm_text(text), "openai+mcp"

        messages.append(resp)
        tool_map = {getattr(t, "name", ""): t for t in tools}
        for tc in tool_calls:
            name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", "")
            args = tc.get("args") if isinstance(tc, dict) else getattr(tc, "args", {}) or {}
            tid = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", "")
            tool = tool_map.get(name)
            if tool is None:
                result = f"(MCP) unknown tool {name}"
            else:
                try:
                    result = tool.invoke(args)
                except Exception as exc:  # noqa: BLE001
                    result = f"(MCP) {name} error: {exc}"
            messages.append(
                ToolMessage(content=_coerce_llm_text(result), tool_call_id=tid or name)
            )

    last = messages[-1]
    if isinstance(last, AIMessage):
        return _coerce_llm_text(_content_to_text(last.content)), "openai+mcp"
    return _fallback_for_key(fallback_key, ctx), "fallback"
