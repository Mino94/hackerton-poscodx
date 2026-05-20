"""Deep Agents 파이프라인 — 순차 실행 + Agent 간 대화로 산출 고도화."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from autopm.agents.deep_runner import run_agent_task, run_agent_task_with_subagents
from autopm.orchestration.agent_dialogue import (
    dialogue_revise_enabled,
    dialogue_rounds_limit,
    format_dialogue_for_prompt,
    revise_output_after_dialogue,
    run_multi_turn_peer_dialogue,
)
from autopm.orchestration.state import AutoPMState
from autopm.orchestration.supervisor_manager import (
    get_supervisor_context_block,
    run_supervisor_checkpoint,
    supervisor_agent_complete,
    supervisor_agent_start,
    supervisor_record_dialogue,
)
from autopm.services.observability import agent_done


def _as_text(val: object) -> str:
    """Pydantic·Harness·PPT 경로가 str만 가정하므로 Agent 산출을 통일한다."""
    return val if isinstance(val, str) else str(val or "")


# flow.py와 동일한 매핑 — UI 진행 메시지·state 필드와 맞춘다.
PIPELINE_KEYS: list[str] = [
    "orchestrate_task",
    "requirement_task",
    "business_analysis_task",
    "solution_design_task",
    "development_scope_task",
    "wbs_task",
    "budget_roi_task",
    "risk_critic_task",
]
STATE_FIELDS: list[str] = [
    "orchestration_brief",
    "requirement_analysis",
    "business_analysis",
    "solution_direction",
    "development_scope",
    "wbs_plan",
    "budget_roi",
    "risk_management",
]
PIPELINE_AGENT_KEYS: list[str] = [
    "pm_orchestrator_agent",
    "requirement_interview_agent",
    "business_analyst_agent",
    "solution_architect_agent",
    "development_scope_agent",
    "wbs_planner_agent",
    "budget_roi_agent",
    "risk_critic_agent",
]
PIPELINE_USER_MSG: list[str] = [
    "[1/12] PM Orchestrator: 전체 추진계획 구조 설계",
    "[2/12] Requirement Interview: 요구사항 및 누락 정보 분석",
    "[3/12] Business Analyst: AS-IS / Pain Point 분석",
    "[4/12] Solution Architect: TO-BE / 개선 방향 설계",
    "[5/12] Development Scope: 개발 범위 정의",
    "[6/12] WBS Planner: 추진 일정 생성",
    "[7/12] Budget & ROI: 예산 및 기대효과 산출",
    "[8/12] Risk & Critic: 리스크 및 품질 검토",
]


def _enrich_with_prior(state: AutoPMState, enriched: dict[str, str], idx: int) -> dict[str, str]:
    """이전 단계 산출·Agent 대화를 placeholder에 주입한다."""
    ctx = dict(enriched)
    for j in range(idx):
        fld = STATE_FIELDS[j]
        val = getattr(state, fld, "") or ""
        ctx[fld] = val
        ctx[f"prior_{PIPELINE_KEYS[j]}"] = val
    ctx["agent_dialogue_summary"] = format_dialogue_for_prompt(state.agent_dialogue)
    sup_ctx = get_supervisor_context_block(state)
    if sup_ctx.strip():
        ctx["supervisor_context"] = sup_ctx
        base_fb = (ctx.get("feedback_block") or "").strip()
        ctx["feedback_block"] = f"{base_fb}\n\n{sup_ctx}".strip() if base_fb else sup_ctx
    return ctx


def execute_pipeline_step(
    state: AutoPMState,
    idx: int,
    agent_defs: dict[str, Any],
    task_defs: dict[str, Any],
    enriched: dict[str, str],
    feedback_acc: str,
    *,
    on_progress: Callable[[str], None] | None = None,
) -> str:
    """
    Core 파이프라인 1단계 실행 — Orchestrator–Worker 그래프·레거시 for-loop 공통.
    갱신된 feedback_acc 문자열을 반환한다.
    """
    task_key = PIPELINE_KEYS[idx]
    ag_key = PIPELINE_AGENT_KEYS[idx]
    field = STATE_FIELDS[idx]
    user_line = PIPELINE_USER_MSG[idx]
    spec = task_defs[task_key]

    ctx = _enrich_with_prior(state, enriched, idx)
    if feedback_acc.strip():
        ctx["feedback_block"] = feedback_acc

    dialogue_snip = format_dialogue_for_prompt(state.agent_dialogue, limit=3)
    supervisor_agent_start(state, task_key=task_key)

    if on_progress:
        on_progress(f"{user_line} → Worker 실행 (Send)… Deep Agent + Sub-Agent")

    def _sub_progress(msg: str) -> None:
        if on_progress:
            on_progress(f"{user_line} {msg}")

    out, sub_recs = run_agent_task_with_subagents(
        ag_key,
        agent_defs,
        task_defs,
        task_key,
        ctx,
        prior_dialogue=dialogue_snip,
        on_progress=_sub_progress,
    )
    out = _as_text(out)
    setattr(state, field, out)
    state.agent_outputs[task_key] = out
    if sub_recs:
        state.subagent_outputs[task_key] = sub_recs
    agent_done(state, ag_key, f"deep_{task_key}")

    dialogue_rounds = 0
    new_feedback = feedback_acc

    if idx < len(PIPELINE_KEYS) - 1:
        next_ag = PIPELINE_AGENT_KEYS[idx + 1]
        next_spec = agent_defs[next_ag]
        cur_spec = agent_defs[spec["agent"]]
        if on_progress:
            on_progress(f"{user_line} Agent 대화 ({dialogue_rounds_limit()}라운드)…")

        thread = run_multi_turn_peer_dialogue(
            from_agent_key=ag_key,
            to_agent_key=next_ag,
            from_role=cur_spec["role"],
            to_role=next_spec["role"],
            producer_output=out,
            task_key=task_key,
            enriched=ctx,
            agent_defs=agent_defs,
        )

        if dialogue_revise_enabled() and thread.get("revision_hint"):
            revised, rev_prov = revise_output_after_dialogue(
                from_agent_key=ag_key,
                task_key=task_key,
                task_defs=task_defs,
                agent_defs=agent_defs,
                original_output=out,
                dialogue_thread=thread,
                enriched=ctx,
            )
            if revised and revised != out:
                out = _as_text(revised)
                setattr(state, field, out)
                state.agent_outputs[task_key] = out
                thread["revised_after_dialogue"] = True
                thread["revise_provider"] = rev_prov
                if on_progress:
                    on_progress(f"{user_line} 대화 반영 산출 보완 ({rev_prov})")

        state.append_agent_dialogue(thread)
        dialogue_rounds = int(thread.get("round_count") or 0)
        supervisor_record_dialogue(state, task_key, dialogue_rounds)

        if thread.get("revision_hint"):
            new_feedback = (
                f"{new_feedback}\n\n### {cur_spec['role']}↔{next_spec['role']} "
                f"({thread.get('round_count', 0)}라운드)\n{thread['revision_hint']}"
            ).strip()

    supervisor_agent_complete(
        state,
        task_key=task_key,
        output=out,
        subagent_count=len(sub_recs),
        dialogue_rounds=dialogue_rounds,
    )
    run_supervisor_checkpoint(
        state,
        label=f"after_{task_key}",
        enriched=enriched,
        agent_defs=agent_defs,
        task_key=task_key,
    )

    if on_progress:
        on_progress(f"{user_line} → Worker 완료 ({ag_key})")

    return new_feedback


def _use_send_graph() -> bool:
    return os.getenv("AUTOPM_USE_SEND_GRAPH", "true").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def run_deep_pipeline(
    state: AutoPMState,
    agent_defs: dict[str, Any],
    task_defs: dict[str, Any],
    enriched: dict[str, str],
    on_progress: Callable[[str], None] | None,
) -> None:
    """8 Core PM — 기본은 LangGraph Orchestrator–Worker(Send), 레거시는 for-loop."""
    if _use_send_graph():
        from autopm.orchestration.orchestrator_worker_graph import run_deep_pipeline_graph

        run_deep_pipeline_graph(state, agent_defs, task_defs, enriched, on_progress)
        return

    feedback_acc = enriched.get("feedback_block", "")
    for idx in range(len(PIPELINE_KEYS)):
        feedback_acc = execute_pipeline_step(
            state,
            idx,
            agent_defs,
            task_defs,
            enriched,
            feedback_acc,
            on_progress=on_progress,
        )


def run_deep_single_task(
    state: AutoPMState,
    agent_defs: dict[str, Any],
    task_defs: dict[str, Any],
    ctx: dict[str, str],
    task_key: str,
    on_progress: Callable[[str], None] | None,
    progress_label: str,
) -> str:
    """PPT 3~4단계 등 단일 Deep Agent 태스크."""
    spec = task_defs[task_key]
    ag_key = spec["agent"]
    ctx = dict(ctx)
    ctx["agent_dialogue_summary"] = format_dialogue_for_prompt(state.agent_dialogue)
    supervisor_agent_start(state, task_key=task_key)
    if on_progress:
        on_progress(progress_label)
    out, sub_recs = run_agent_task_with_subagents(
        ag_key, agent_defs, task_defs, task_key, ctx, on_progress=on_progress
    )
    out = _as_text(out)
    state.agent_outputs[task_key] = out
    if sub_recs:
        state.subagent_outputs[task_key] = sub_recs
    agent_done(state, ag_key, f"deep_{task_key}")
    supervisor_agent_complete(
        state,
        task_key=task_key,
        output=out,
        subagent_count=len(sub_recs),
    )
    run_supervisor_checkpoint(
        state,
        label=f"after_{task_key}",
        enriched=ctx,
        agent_defs=agent_defs,
        task_key=task_key,
    )
    if on_progress:
        on_progress(f"{progress_label} 완료")
    return out


def run_deep_critic(
    state: AutoPMState,
    agent_defs: dict[str, Any],
    task_defs: dict[str, Any],
    enriched: dict[str, str],
    on_progress: Callable[[str], None] | None,
) -> str:
    spec = task_defs["critic_task"]
    ag_key = spec["agent"]
    ctx = {
        **enriched,
        "draft": state.snapshot_for_critic(),
        "agent_dialogue_summary": format_dialogue_for_prompt(state.agent_dialogue),
    }
    supervisor_agent_start(state, agent_id="critic_gate")
    if on_progress:
        on_progress("[Critic] 평가 중 (Deep Agent)")
    out = _as_text(run_agent_task(ag_key, agent_defs, task_defs, "critic_task", ctx))
    state.agent_outputs["critic_task"] = out
    state.critic_review = out
    supervisor_agent_complete(state, agent_id="critic_gate", output=out)
    run_supervisor_checkpoint(state, label="after_critic", enriched=enriched, agent_defs=agent_defs)
    if on_progress:
        on_progress("[Critic] 완료")
    return out.strip()


def run_deep_improvement(
    state: AutoPMState,
    agent_defs: dict[str, Any],
    task_defs: dict[str, Any],
    enriched: dict[str, str],
    target: str,
    feedback: str,
    improvement_map: dict[str, tuple[str, str]],
    on_progress: Callable[[str], None] | None,
) -> None:
    tkey, fld = improvement_map[target]
    spec = task_defs[tkey]
    ag_key = spec["agent"]
    block = (
        f"\n### Self-Correction ({target}, round {state.loop_count + 1})\n"
        f"{feedback}\n이전 본문을 보완·수정하라.\n"
    )
    local = {**enriched, "feedback_block": block, "agent_dialogue_summary": format_dialogue_for_prompt(state.agent_dialogue)}
    if on_progress:
        on_progress(f"[보완] {target} ({ag_key})")
    out = _as_text(run_agent_task(ag_key, agent_defs, task_defs, tkey, local))
    setattr(state, fld, out)
    state.agent_outputs[tkey] = out
    agent_done(state, ag_key, "improvement")


def run_deep_documentation(
    state: AutoPMState,
    agent_defs: dict[str, Any],
    task_defs: dict[str, Any],
    enriched: dict[str, str],
    loop_meta: str,
    on_progress: Callable[[str], None] | None,
) -> str:
    spec = task_defs["documentation_task"]
    ag_key = spec["agent"]
    ctx = {
        **enriched,
        "loop_meta": loop_meta,
        "agent_dialogue_summary": format_dialogue_for_prompt(state.agent_dialogue),
        "orchestration_brief": state.orchestration_brief,
        "requirement_analysis": state.requirement_analysis,
        "business_analysis": state.business_analysis,
        "solution_direction": state.solution_direction,
        "development_scope": state.development_scope,
        "wbs_plan": state.wbs_plan,
        "budget_roi": state.budget_roi,
        "risk_management": state.risk_management,
        "critic_review": state.critic_review,
    }
    supervisor_agent_start(state, agent_id="documentation")
    if on_progress:
        on_progress("[Documentation] 최종 문서 조립 (Deep Agent)")
    out = _as_text(run_agent_task(ag_key, agent_defs, task_defs, "documentation_task", ctx))
    state.agent_outputs["documentation_task"] = out
    state.document_output = out
    supervisor_agent_complete(state, agent_id="documentation", output=out)
    run_supervisor_checkpoint(
        state, label="after_documentation", enriched=enriched, agent_defs=agent_defs
    )
    if on_progress:
        on_progress("[문서화] 완료")
    return out.strip()


__all__ = [
    "PIPELINE_KEYS",
    "STATE_FIELDS",
    "PIPELINE_USER_MSG",
    "execute_pipeline_step",
    "run_deep_pipeline",
    "run_deep_single_task",
    "run_deep_critic",
    "run_deep_improvement",
    "run_deep_documentation",
]
