"""Supervisor Agent — 전체 Agent 진행·산출물·게이트를 PM 관리자처럼 추적·지휘한다."""

from __future__ import annotations

import os
import time
from typing import Any

from autopm.orchestration.state import AutoPMState
from autopm.orchestration.supervisor_registry import (
    AGENT_REGISTRY,
    get_registry_entry_by_id,
    get_registry_entry_by_task,
)
from autopm.services.observability import log


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _clip(text: str, n: int = 200) -> str:
    t = (text or "").strip().replace("\n", " ")
    return t if len(t) <= n else t[: n - 1] + "…"


def _empty_supervisor() -> dict[str, Any]:
    return {
        "supervisor_agent": "PM Supervisor",
        "project_title": "",
        "overall_status": "init",
        "current_step_id": "",
        "progress_pct": 0,
        "agents": {},
        "checkpoints": [],
        "blockers": [],
        "next_actions": [],
        "last_brief": "",
    }


def init_supervisor(state: AutoPMState, enriched: dict[str, str]) -> None:
    """실행 시작 시 전 Agent를 pending으로 등록한다."""
    sup = _empty_supervisor()
    title = enriched.get("proposal_title") or enriched.get("idea_title") or "추진계획"
    sup["project_title"] = title
    sup["overall_status"] = "planning"
    sup["next_actions"] = [
        "8 Core Agent 순차 실행",
        "단계별 산출물·Agent 대화 검토",
        "Critic 게이트 후 문서화·PPT 생성",
    ]

    for entry in AGENT_REGISTRY:
        sup["agents"][entry["id"]] = {
            "id": entry["id"],
            "order": entry["order"],
            "dashboard_id": entry["dashboard_id"],
            "agent_key": entry["agent_key"],
            "task_key": entry["task_key"],
            "display_name": entry["display_name"],
            "deliverable_label": entry["deliverable_label"],
            "phase_group": entry["phase_group"],
            "status": "pending",
            "started_at": "",
            "completed_at": "",
            "output_chars": 0,
            "deliverable_preview": "",
            "dialogue_rounds": 0,
            "subagent_count": 0,
            "supervisor_note": "",
            "quality": "pending",
        }

    state.supervisor = sup
    state.current_phase = "supervisor_init"
    log(state, f"[Supervisor] 프로젝트 등록: {title} · Agent {len(AGENT_REGISTRY)}명")


def _recalc_progress(sup: dict[str, Any]) -> None:
    agents = sup.get("agents") or {}
    if not agents:
        sup["progress_pct"] = 0
        return
    done = sum(1 for a in agents.values() if a.get("status") == "complete")
    err = sum(1 for a in agents.values() if a.get("status") == "error")
    total = len(agents)
    sup["progress_pct"] = round(100.0 * done / total, 1)
    if err and done < total:
        sup["overall_status"] = "degraded"
    elif done == total:
        sup["overall_status"] = "complete"
    elif done > 0 or any(a.get("status") == "running" for a in agents.values()):
        sup["overall_status"] = "running"


def supervisor_agent_start(
    state: AutoPMState,
    *,
    task_key: str | None = None,
    agent_id: str | None = None,
) -> None:
    """Agent 실행 시작 — Supervisor가 현재 단계를 running으로 표시."""
    entry = get_registry_entry_by_task(task_key) if task_key else get_registry_entry_by_id(agent_id or "")
    if not entry:
        return
    sup = state.supervisor or _empty_supervisor()
    rec = sup["agents"].get(entry["id"])
    if not rec:
        return
    rec["status"] = "running"
    rec["started_at"] = _now_iso()
    sup["current_step_id"] = entry["id"]
    sup["overall_status"] = "running"
    state.supervisor = sup
    state.current_phase = f"agent_{entry['id']}"
    log(state, f"[Supervisor] ▶ {entry['display_name']} 시작")


def supervisor_agent_complete(
    state: AutoPMState,
    *,
    task_key: str | None = None,
    agent_id: str | None = None,
    output: str = "",
    subagent_count: int = 0,
    dialogue_rounds: int = 0,
    artifact_path: str = "",
) -> None:
    """Agent 완료 — 산출물 메타데이터를 Supervisor에 기록."""
    entry = get_registry_entry_by_task(task_key) if task_key else get_registry_entry_by_id(agent_id or "")
    if not entry:
        return
    sup = state.supervisor or _empty_supervisor()
    rec = sup["agents"].get(entry["id"])
    if not rec:
        return

    out = output if isinstance(output, str) else str(output or "")
    n = len(out.strip())
    rec["status"] = "complete"
    rec["completed_at"] = _now_iso()
    rec["output_chars"] = n
    rec["deliverable_preview"] = _clip(out, 220)
    rec["subagent_count"] = subagent_count
    rec["dialogue_rounds"] = dialogue_rounds
    if artifact_path:
        rec["artifact_path"] = artifact_path

    if n < 80:
        rec["quality"] = "weak"
        rec["supervisor_note"] = "산출이 짧음 — 표·bullet 보강 필요"
        sup["blockers"] = list(dict.fromkeys((sup.get("blockers") or []) + [f"{entry['display_name']}: 산출 부족"]))
    elif n < 300:
        rec["quality"] = "fair"
        rec["supervisor_note"] = "최소 분량 충족 — 다음 단계 연계 확인"
    else:
        rec["quality"] = "good"
        rec["supervisor_note"] = "게이트 통과 — 다음 Agent 진행"

    _recalc_progress(sup)
    state.supervisor = sup
    log(state, f"[Supervisor] ✓ {entry['display_name']} 완료 ({n}자, Q={rec['quality']})")


def supervisor_agent_error(
    state: AutoPMState,
    *,
    task_key: str | None = None,
    agent_id: str | None = None,
    error: str = "",
) -> None:
    entry = get_registry_entry_by_task(task_key) if task_key else get_registry_entry_by_id(agent_id or "")
    if not entry:
        return
    sup = state.supervisor or _empty_supervisor()
    rec = sup["agents"].get(entry["id"])
    if not rec:
        return
    rec["status"] = "error"
    rec["supervisor_note"] = _clip(error, 300)
    rec["quality"] = "fail"
    sup["blockers"] = list(dict.fromkeys((sup.get("blockers") or []) + [f"{entry['display_name']}: {error[:120]}"]))
    _recalc_progress(sup)
    sup["overall_status"] = "degraded"
    state.supervisor = sup
    log(state, f"[Supervisor] ✗ {entry['display_name']} 오류")


def supervisor_record_dialogue(state: AutoPMState, task_key: str, round_count: int) -> None:
    """Agent 간 대화 라운드 수를 해당 단계에 누적."""
    entry = get_registry_entry_by_task(task_key)
    if not entry:
        return
    sup = state.supervisor or {}
    rec = (sup.get("agents") or {}).get(entry["id"])
    if rec:
        rec["dialogue_rounds"] = int(round_count)


def _checkpoint_mode() -> str:
    return os.getenv("AUTOPM_SUPERVISOR_CHECKPOINT", "milestones").strip().lower()


def _should_checkpoint(task_key: str | None, checkpoint_label: str) -> bool:
    mode = _checkpoint_mode()
    if mode == "off" or mode == "false":
        return False
    if mode == "every":
        return bool(task_key)
    if mode == "end":
        return checkpoint_label in ("after_core", "after_ppt", "final")
    # milestones
    milestone_tasks = {
        "orchestrate_task",
        "business_analysis_task",
        "wbs_task",
        "risk_critic_task",
        "documentation_task",
        "ppt_composition_task",
    }
    milestone_labels = {
        "after_core",
        "after_critic",
        "after_documentation",
        "after_ppt",
        "final",
    }
    if checkpoint_label in milestone_labels:
        return True
    return task_key in milestone_tasks if task_key else False


def run_supervisor_checkpoint(
    state: AutoPMState,
    *,
    label: str,
    enriched: dict[str, str],
    agent_defs: dict[str, Any] | None = None,
    task_key: str | None = None,
) -> dict[str, Any]:
    """
    Supervisor(PM Orchestrator) 관점 진행 점검 — LLM 또는 rule-based.
    반환: decision, summary, next_actions, agent_status_table
    """
    if not _should_checkpoint(task_key, label):
        return {}

    sup = state.supervisor or _empty_supervisor()
    agents = sup.get("agents") or {}

    completed = [a for a in agents.values() if a.get("status") == "complete"]
    running = [a for a in agents.values() if a.get("status") == "running"]
    pending = [a for a in agents.values() if a.get("status") == "pending"]
    weak = [a for a in agents.values() if a.get("quality") == "weak"]
    errors = [a for a in agents.values() if a.get("status") == "error"]

    table_lines = []
    for entry in AGENT_REGISTRY:
        a = agents.get(entry["id"], {})
        st = a.get("status", "pending")
        q = a.get("quality", "-")
        table_lines.append(
            f"| {entry['order']} | {entry['display_name']} | {st} | {q} | {a.get('output_chars', 0)} | "
            f"{a.get('deliverable_label', '')} |"
        )
    status_table = (
        "| # | Agent | 상태 | 품질 | 글자수 | 산출물 |\n| --- | --- | --- | --- | --- | --- |\n"
        + "\n".join(table_lines)
    )

    decision = "proceed"
    if errors:
        decision = "degraded_proceed"
    if len(weak) >= 3:
        decision = "proceed_with_warnings"

    summary_parts = [
        f"**체크포인트:** {label}",
        f"완료 {len(completed)}/{len(agents)} · 실행 중 {len(running)} · 대기 {len(pending)}",
    ]
    if weak:
        summary_parts.append(f"약한 산출: {', '.join(a['display_name'] for a in weak[:4])}")
    if sup.get("blockers"):
        summary_parts.append(f"블로커: {'; '.join(sup['blockers'][:3])}")

    next_actions: list[str] = []
    if pending:
        nxt = sorted(pending, key=lambda x: x.get("order", 99))[0]
        next_actions.append(f"다음 실행: {nxt.get('display_name')} ({nxt.get('deliverable_label')})")
    if weak:
        next_actions.append("약한 산출 Agent는 feedback_block·대화 합의로 보강")
    if label == "after_core" and not errors:
        next_actions.append("Critic 게이트 → 문서화 → PPT 4단계 진행")
    if label == "after_ppt":
        next_actions.append("Streamlit에서 project_plan.pptx 다운로드·검토")

    brief = run_supervisor_brief_llm(state, enriched, agent_defs, status_table, label) if agent_defs else ""
    if not brief.strip():
        brief = "\n".join(summary_parts)

    checkpoint = {
        "at": _now_iso(),
        "label": label,
        "task_key": task_key or "",
        "decision": decision,
        "summary": brief,
        "status_table": status_table,
        "next_actions": next_actions,
        "stats": {
            "complete": len(completed),
            "running": len(running),
            "pending": len(pending),
            "weak": len(weak),
            "error": len(errors),
        },
    }

    sup["checkpoints"] = list(sup.get("checkpoints") or []) + [checkpoint]
    sup["last_brief"] = brief
    sup["next_actions"] = next_actions
    state.supervisor = sup
    log(state, f"[Supervisor] 체크포인트 {label}: {decision}")
    return checkpoint


def run_supervisor_brief_llm(
    state: AutoPMState,
    enriched: dict[str, str],
    agent_defs: dict[str, Any] | None,
    status_table: str,
    label: str,
) -> str:
    """PM Orchestrator Agent로 관리자 브리핑 생성."""
    if not agent_defs:
        return ""
    from autopm.services.llm_router import invoke_with_tier
    from autopm.services.prompt_manager import build_agent_system_prompt

    system = build_agent_system_prompt("pm_orchestrator_agent", agent_defs)
    user = (
        f"당신은 **Supervisor PM**이다. 전체 Agent 팀의 진행·산출을 관리한다.\n\n"
        f"## 프로젝트\n{enriched.get('proposal_title') or enriched.get('idea_title', '')}\n\n"
        f"## 체크포인트\n{label}\n\n"
        f"## Agent 현황 표\n{status_table}\n\n"
        f"## 블로커\n{'; '.join((state.supervisor or {}).get('blockers') or []) or '없음'}\n\n"
        "**출력 (Markdown):**\n"
        "1) 전체 진행 한 줄 2) 완료된 산출 요약 3) 리스크·블로커 4) 다음 Agent 지시 2~3개\n"
        "관리자 회의 톤. generic 한 줄 금지."
    )
    text, _prov = invoke_with_tier(
        system,
        user,
        tier="cloud",
        fallback_key="orchestrate_task",
        context=enriched,
    )
    return text.strip()


def get_supervisor_context_block(state: AutoPMState) -> str:
    """다음 Agent task placeholder에 넣을 Supervisor 지시 블록."""
    sup = state.supervisor or {}
    parts = []
    if sup.get("last_brief"):
        parts.append(f"### Supervisor PM 브리핑\n{sup['last_brief'][:2000]}")
    actions = sup.get("next_actions") or []
    if actions:
        parts.append("### Supervisor 다음 지시\n" + "\n".join(f"- {a}" for a in actions[:5]))
    blockers = sup.get("blockers") or []
    if blockers:
        parts.append("### 주의(블로커)\n" + "\n".join(f"- {b}" for b in blockers[:5]))
    return "\n\n".join(parts)


def sync_agent_steps_from_supervisor(steps: list[Any], state: AutoPMState) -> None:
    """Streamlit AgentStep 카드와 Supervisor 레지스트리 동기화."""
    from autopm.ui.agent_progress import update_agent_status

    sup = state.supervisor or {}
    agents = sup.get("agents") or {}
    dash_to_status: dict[str, str] = {}
    for rec in agents.values():
        did = rec.get("dashboard_id", "")
        st = rec.get("status", "pending")
        if did not in dash_to_status or st == "running":
            dash_to_status[did] = st
        if st == "error":
            dash_to_status[did] = "error"
        elif st == "complete" and dash_to_status.get(did) != "error":
            dash_to_status[did] = "complete"

    for i, step in enumerate(steps):
        st = dash_to_status.get(step.id, step.status)
        art = ""
        for rec in agents.values():
            if rec.get("dashboard_id") == step.id and rec.get("deliverable_preview"):
                art = rec["deliverable_preview"]
                break
        msg = ""
        for rec in agents.values():
            if rec.get("dashboard_id") == step.id and rec.get("supervisor_note"):
                msg = rec["supervisor_note"]
                break
        update_agent_status(
            steps,
            i,
            st if st in ("pending", "running", "complete", "error") else step.status,
            artifact=art or None,
            completion_message=msg or None,
        )


def supervisor_report_dict(state: AutoPMState) -> dict[str, Any]:
    """export·UI용 Supervisor 전체 리포트."""
    sup = dict(state.supervisor or {})
    sup["progress_summary"] = {
        "overall_status": sup.get("overall_status"),
        "progress_pct": sup.get("progress_pct"),
        "checkpoint_count": len(sup.get("checkpoints") or []),
        "blocker_count": len(sup.get("blockers") or []),
    }
    return sup


__all__ = [
    "init_supervisor",
    "supervisor_agent_start",
    "supervisor_agent_complete",
    "supervisor_agent_error",
    "supervisor_record_dialogue",
    "run_supervisor_checkpoint",
    "get_supervisor_context_block",
    "sync_agent_steps_from_supervisor",
    "supervisor_report_dict",
]
