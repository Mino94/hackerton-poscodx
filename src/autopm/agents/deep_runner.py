"""Deep Agents SDK(`create_deep_agent`) 기반 Parent Agent 실행 — 폴백은 deep_agent_sdk."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from autopm.agents.deep_agent_sdk import run_task_via_deep_agent_or_fallback
from autopm.services.prompt_manager import build_agent_system_prompt  # re-export 호환


def run_flat_agent_task(
    agent_key: str,
    agent_defs: dict[str, Any],
    task_defs: dict[str, Any],
    task_key: str,
    context: dict[str, str],
    *,
    prior_dialogue: str = "",
    on_progress: Callable[[str], None] | None = None,
) -> str:
    """Sub-Agent 없이 Parent 1건 — SDK 우선, 실패 시 invoke_for_agent."""
    text, _prov, _recs = run_task_via_deep_agent_or_fallback(
        agent_key,
        agent_defs,
        task_defs,
        task_key,
        context,
        prior_dialogue=prior_dialogue,
        on_progress=on_progress,
        use_subagents=False,
    )
    return text


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
    """tasks.yaml 한 건 — Deep Agents SDK + subagents.yaml Sub-Agent 팀."""
    text, _prov, _recs = run_task_via_deep_agent_or_fallback(
        agent_key,
        agent_defs,
        task_defs,
        task_key,
        context,
        prior_dialogue=prior_dialogue,
        on_progress=on_progress,
        use_subagents=True,
    )
    return text


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
    text, provider, records = run_task_via_deep_agent_or_fallback(
        agent_key,
        agent_defs,
        task_defs,
        task_key,
        context,
        prior_dialogue=prior_dialogue,
        on_progress=on_progress,
        use_subagents=True,
    )
    if on_progress and provider.startswith("deep_agent_sdk"):
        on_progress(f"  ▸ Deep Agent SDK 완료 ({provider})")
    return text, [r.to_dict() for r in records]


__all__ = [
    "build_agent_system_prompt",
    "run_flat_agent_task",
    "run_agent_task",
    "run_agent_task_with_subagents",
]
