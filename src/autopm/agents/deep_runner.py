"""Deep Agents / LangChain 기반 Parent Agent + Sub-Agent 팀 실행."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from autopm.services.llm_router import get_langchain_chat_model_or_none, invoke_chat_or_fallback
from autopm.services.prompt_manager import (
    build_agent_system_prompt,
    build_task_user_prompt,
)


def _subagents_enabled() -> bool:
    """Sub-Agent 체인 사용 여부 — 기본 켜짐, AUTOPM_ENABLE_SUBAGENTS=false 로 끌 수 있다."""
    return os.getenv("AUTOPM_ENABLE_SUBAGENTS", "true").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def run_flat_agent_task(
    agent_key: str,
    agent_defs: dict[str, Any],
    task_defs: dict[str, Any],
    task_key: str,
    context: dict[str, str],
    *,
    prior_dialogue: str = "",
) -> str:
    """Sub-Agent 없이 Parent 단일 호출 — 순환 import·빈 체인 폴백용."""
    spec = task_defs[task_key]
    ag_key = spec["agent"]
    system = build_agent_system_prompt(ag_key, agent_defs)
    user = build_task_user_prompt(
        task_key,
        spec["description"],
        spec["expected_output"],
        context,
        prior_dialogue=prior_dialogue,
    )

    model = get_langchain_chat_model_or_none()
    return invoke_chat_or_fallback(
        system,
        user,
        fallback_key=task_key,
        context=context,
        model=model,
    )


def run_agent_task(
    agent_key: str,
    agent_defs: dict[str, Any],
    task_defs: dict[str, Any],
    task_key: str,
    context: dict[str, str],
    *,
    prior_dialogue: str = "",
    on_progress: Callable[[str], None] | None = None,
) -> str:
    """tasks.yaml 한 건 실행 — Sub-Agent 팀이 있으면 세분화 후 Parent가 통합한다."""
    if _subagents_enabled():
        from autopm.agents.subagent_runner import run_subagents_then_task

        final, _records = run_subagents_then_task(
            agent_key,
            agent_defs,
            task_defs,
            task_key,
            context,
            prior_dialogue=prior_dialogue,
            on_progress=on_progress,
        )
        return final

    return run_flat_agent_task(
        agent_key,
        agent_defs,
        task_defs,
        task_key,
        context,
        prior_dialogue=prior_dialogue,
    )


def run_agent_task_with_subagents(
    agent_key: str,
    agent_defs: dict[str, Any],
    task_defs: dict[str, Any],
    task_key: str,
    context: dict[str, str],
    *,
    prior_dialogue: str = "",
    on_progress: Callable[[str], None] | None = None,
) -> tuple[str, list[dict[str, str]]]:
    """Sub-Agent 기록까지 반환 — state.subagent_outputs 저장용."""
    from autopm.agents.subagent_runner import run_subagents_then_task

    final, records = run_subagents_then_task(
        agent_key,
        agent_defs,
        task_defs,
        task_key,
        context,
        prior_dialogue=prior_dialogue,
        on_progress=on_progress,
    )
    return final, [r.to_dict() for r in records]


__all__ = [
    "build_agent_system_prompt",
    "run_flat_agent_task",
    "run_agent_task",
    "run_agent_task_with_subagents",
]
