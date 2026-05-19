"""Parent Agent별 Sub-Agent 순차 실행 — 로컬 LLM(Ollama)으로 세분화, synthesizer로 통합."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from autopm.services.llm_router import _coerce_llm_text, invoke_with_tier, merge_subagent_fallbacks
from autopm.services.prompt_manager import (
    build_agent_system_prompt,
    build_subagent_system_prompt,
    build_subagent_user_prompt,
    build_task_user_prompt,
    load_subagents,
)


@dataclass
class SubAgentRunRecord:
    """UI·export용 Sub-Agent 실행 기록."""

    subagent_id: str
    role: str
    llm_tier: str
    provider: str
    output: str

    def to_dict(self) -> dict[str, str]:
        return {
            "subagent_id": self.subagent_id,
            "role": self.role,
            "llm_tier": self.llm_tier,
            "provider": self.provider,
            "output": self.output[:8000],
        }


def _prior_subagent_block(records: list[SubAgentRunRecord]) -> str:
    if not records:
        return ""
    parts = []
    for r in records[-4:]:
        parts.append(f"### [{r.subagent_id}] {r.role} ({r.provider})\n{r.output[:2500]}")
    return "\n\n".join(parts)


def _run_one_subagent(
    spec: dict[str, Any],
    context: dict[str, str],
    prior: list[SubAgentRunRecord],
    parent_agent_key: str,
) -> SubAgentRunRecord:
    sid = str(spec["id"])
    role = str(spec.get("role", sid))
    goal = str(spec.get("goal", "")).strip()
    tier = str(spec.get("llm_tier", "local")).strip().lower()

    system = build_subagent_system_prompt(parent_agent_key, sid, role, goal)
    user = build_subagent_user_prompt(goal, context, _prior_subagent_block(prior))

    text, provider = invoke_with_tier(
        system,
        user,
        tier=tier,
        fallback_key=f"sub_{sid}",
        context=context,
    )
    return SubAgentRunRecord(
        subagent_id=sid,
        role=role,
        llm_tier=tier,
        provider=provider,
        output=_coerce_llm_text(text),
    )


def run_subagents_for_parent(
    parent_agent_key: str,
    context: dict[str, str],
    *,
    on_progress: Callable[[str], None] | None = None,
) -> tuple[list[SubAgentRunRecord], str]:
    """
    Parent Agent에 정의된 Sub-Agent를 순차 실행하고 최종 Markdown/JSON 문자열을 반환한다.
    """
    all_defs = load_subagents()
    chain: list[dict[str, Any]] = list(all_defs.get(parent_agent_key) or [])
    if not chain:
        return [], ""

    records: list[SubAgentRunRecord] = []
    ctx = dict(context)

    for i, spec in enumerate(chain):
        sid = spec.get("id", f"sub_{i}")
        if on_progress:
            on_progress(f"  ↳ Sub-Agent [{sid}] ({spec.get('llm_tier', 'local')}) 실행…")
        rec = _run_one_subagent(spec, ctx, records, parent_agent_key)
        records.append(rec)
        ctx[f"subagent_{sid}"] = rec.output
        if on_progress:
            on_progress(f"  ↳ Sub-Agent [{sid}] 완료 ({rec.provider})")

    last = records[-1] if records else None
    if last and "synthesizer" in last.subagent_id:
        final = last.output
    else:
        parent_label = parent_agent_key.replace("_agent", "").replace("_", " ").title()
        final = merge_subagent_fallbacks(records, parent_label)

    return records, final


def run_subagents_then_task(
    parent_agent_key: str,
    agent_defs: dict[str, Any],
    task_defs: dict[str, Any],
    task_key: str,
    context: dict[str, str],
    *,
    prior_dialogue: str = "",
    on_progress: Callable[[str], None] | None = None,
) -> tuple[str, list[SubAgentRunRecord]]:
    """
    Sub-Agent 체인 실행 후, tasks.yaml 기대 형식에 맞게 Parent가 한 번 더 다듬는다(cloud 우선).
    """
    all_defs = load_subagents()
    chain: list[dict[str, Any]] = list(all_defs.get(parent_agent_key) or [])
    if not chain:
        from autopm.agents.deep_runner import run_flat_agent_task

        return (
            run_flat_agent_task(
                parent_agent_key,
                agent_defs,
                task_defs,
                task_key,
                context,
                prior_dialogue=prior_dialogue,
            ),
            [],
        )

    if on_progress:
        on_progress(f"  ▸ Sub-Agent 팀 시작 ({parent_agent_key})")

    records, sub_merged = run_subagents_for_parent(
        parent_agent_key,
        context,
        on_progress=on_progress,
    )

    spec = task_defs[task_key]
    ag_key = spec["agent"]
    sub_block = _prior_subagent_block(records)
    extra = (
        f"## Sub-Agent 팀 산출(통합 전 초안)\n{_coerce_llm_text(sub_merged)[:10000]}\n\n"
        f"## Sub-Agent 상세\n{sub_block[:8000]}\n\n"
        "Sub-Agent 내용을 빠짐없이 반영하되 중복을 제거하고 **기대 산출 형식**으로 정리하라."
    )
    system = build_agent_system_prompt(ag_key, agent_defs)
    user = build_task_user_prompt(
        task_key,
        spec["description"],
        spec["expected_output"],
        context,
        prior_dialogue=prior_dialogue,
        extra_sections=extra,
    )

    polished, provider = invoke_with_tier(
        system,
        user,
        tier="cloud",
        fallback_key=task_key,
        context=context,
    )
    polished = _coerce_llm_text(polished)
    sub_merged = _coerce_llm_text(sub_merged)

    if on_progress:
        on_progress(f"  ▸ Parent 통합 완료 ({provider})")

    final = polished if len(polished) > 80 else sub_merged
    return final, records


__all__ = [
    "SubAgentRunRecord",
    "run_subagents_for_parent",
    "run_subagents_then_task",
]
