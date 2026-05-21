"""LLM Agent 호출에 MCP prefetch·ReAct를 통합한다."""

from __future__ import annotations

from typing import Any

from autopm.mcp.policy import build_mcp_prefetch_block, is_mcp_react_enabled
from autopm.mcp.react import invoke_with_mcp_react
from autopm.services.llm_router import invoke_with_tier, resolve_model_for_tier


def append_mcp_context(
    user_prompt: str,
    agent_key: str,
    context: dict[str, str],
    *,
    task_key: str = "",
) -> str:
    """User 프롬프트 뒤에 MCP prefetch 블록을 붙인다."""
    block = build_mcp_prefetch_block(agent_key, context, task_key=task_key)
    if not block:
        return user_prompt
    return f"{user_prompt}\n\n{block}"


def invoke_for_agent(
    system: str,
    user: str,
    *,
    agent_key: str,
    task_key: str = "",
    tier: str = "auto",
    fallback_key: str = "generic",
    context: dict[str, str] | None = None,
) -> tuple[str, str]:
    """
    Parent/Sub-Agent 공통 LLM 호출 — MCP prefetch 항상(옵션), ReAct는 AUTOPM_MCP_REACT=true 시.
    반환: (text, provider_label)
    """
    ctx = context or {}
    user_full = append_mcp_context(user, agent_key, ctx, task_key=task_key)

    if is_mcp_react_enabled():
        model, base_provider = resolve_model_for_tier(tier)
        if model is not None:
            try:
                text, prov = invoke_with_mcp_react(
                    system,
                    user_full,
                    model=model,
                    agent_key=agent_key,
                    task_key=task_key,
                    fallback_key=fallback_key,
                    context=ctx,
                )
                return text, prov
            except Exception:
                pass

    return invoke_with_tier(
        system,
        user_full,
        tier=tier,
        fallback_key=fallback_key,
        context=ctx,
    )
