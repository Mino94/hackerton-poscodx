"""Agent Workflow 시각화 — 전체 파이프라인·Sub-Agent·실행 상태."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st
import yaml

from autopm.orchestration.deep_pipeline import PIPELINE_KEYS, PIPELINE_USER_MSG
from autopm.orchestration.supervisor_registry import AGENT_REGISTRY

_PHASE_LABELS = {
    "input": "① 입력·인터뷰",
    "supervisor": "Supervisor PM",
    "core": "② Core PM (8)",
    "quality": "③ 품질·문서화",
    "ppt": "④ PPT 생성 (4)",
    "dialogue": "Agent 간 대화",
}

_STATUS_ICON = {
    "pending": "⏳",
    "running": "🔄",
    "complete": "✅",
    "error": "❌",
    "init": "○",
    "planning": "📋",
}


def _load_subagents() -> dict[str, list[dict[str, str]]]:
    """subagents.yaml — Parent별 Sub-Agent 팀."""
    path = Path(__file__).resolve().parents[1] / "config" / "subagents.yaml"
    if not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    out: dict[str, list[dict[str, str]]] = {}
    for parent, items in data.items():
        if isinstance(items, list):
            out[str(parent)] = [
                {
                    "id": str(x.get("id", "")),
                    "role": str(x.get("role", "")),
                    "tier": str(x.get("llm_tier", "auto")),
                }
                for x in items
                if isinstance(x, dict)
            ]
    return out


def _status_for_entry(entry: dict[str, Any], supervisor: dict[str, Any] | None, steps_map: dict[str, str]) -> str:
    """Supervisor 레지스트리 또는 Agent Progress 카드에서 상태 조회."""
    if supervisor:
        agents = supervisor.get("agents") or {}
        sid = entry.get("id") or ""
        if sid in agents:
            return str(agents[sid].get("status") or "pending")
    dash = entry.get("dashboard_id") or entry.get("id")
    if dash and dash in steps_map:
        return steps_map[dash]
    return "pending"


def _mermaid_workflow() -> str:
    """전체 워크플로 — Mermaid flowchart (Streamlit st.mermaid)."""
    return """
flowchart TB
    subgraph IN["① 입력"]
        IV["Rule-based 인터뷰"]
        INP["to_autopm_inputs()"]
        IV --> INP
    end

    subgraph SUP["Supervisor PM"]
        SV["진행·산출·체크포인트 관리"]
    end

    subgraph OW["Orchestrator–Worker (LangGraph Send)"]
        ORCH["Orchestrator dispatch"]
        WRK["Worker × N 동적 생성"]
        ORCH -->|Send task| WRK
        WRK --> ORCH
    end

    subgraph CORE["② Core PM Agents"]
        direction TB
        O["PM Orchestrator"] --> R["Requirement Interview"]
        R --> B["Business Analyst"]
        B --> S["Solution Architect"]
        S --> D["Development Scope"]
        D --> W["WBS Planner"]
        W --> BU["Budget & ROI"]
        BU --> RK["Risk & Critic"]
    end

    subgraph Q["③ 품질·문서"]
        CR["Critic 게이트"]
        DOC["Documentation"]
    end

    subgraph PPT["④ PPT Production"]
        ST["Storyline"] --> VI["Visualization"]
        VI --> PG["Presentation Graphics"]
        PG --> PC["PPT Composer"]
    end

    OUT["project_plan.pptx"]

    INP --> SV
    SV --> ORCH
    WRK --> O
    RK --> CR
    CR --> DOC
    DOC --> ST
    PC --> OUT

    O -.->|Sub-Agent 팀| O
    R -.->|3라운드 대화| B
    B -.->|3라운드 대화| S
    S -.->|…| D
"""


def render_agent_workflow_tab(
    agent_steps: list[Any] | None,
    last_result: Any | None,
) -> None:
    """Agent Workflow 탭 — 구조도 + 단계표 + Sub-Agent + (선택) 실시간 상태."""
    st.markdown("#### AutoPM Agent Workflow")
    st.caption(
        "인터뷰 → **Supervisor PM** → **LangGraph Orchestrator–Worker**(`Send()`로 단계별 Worker 동적 생성) → "
        "Core 8 → Critic·문서화 → PPT 4단계. `AUTOPM_USE_SEND_GRAPH=false` 이면 레거시 for-loop."
    )

    with st.expander("구조도 (Mermaid — GitHub/Notion에 붙여넣기)", expanded=False):
        st.code(_mermaid_workflow().strip(), language="mermaid")

    supervisor = None
    steps_map: dict[str, str] = {}
    if agent_steps:
        for s in agent_steps:
            steps_map[getattr(s, "id", "")] = getattr(s, "status", "pending")
    if last_result and getattr(last_result, "state", None):
        supervisor = getattr(last_result.state, "supervisor", None) or {}

    t_flow, t_table, t_sub = st.tabs(["단계 흐름", "Agent 목록", "Sub-Agent 팀"])

    with t_flow:
        _render_phase_flow(supervisor, steps_map)

    with t_table:
        _render_registry_table(supervisor, steps_map, last_result)

    with t_sub:
        _render_subagent_teams(last_result)


def _render_phase_flow(supervisor: dict[str, Any] | None, steps_map: dict[str, str]) -> None:
    """단계별 카드 + 화살표."""
    st.markdown("##### 파이프라인 단계 (실행 순서)")

    # 인터뷰
    st.markdown(f"**{_PHASE_LABELS['input']}**")
    st.caption("Streamlit 인터뷰 탭 → 주제·목적·배경·문제·범위·톤 수집")
    st.markdown("⬇")

    if supervisor:
        sup_st = supervisor.get("overall_status", "—")
        pct = supervisor.get("progress_pct", 0)
        st.markdown(
            f"**{_PHASE_LABELS['supervisor']}** · `{sup_st}` · 진행 **{pct}%**"
        )
        if supervisor.get("last_brief"):
            with st.expander("Supervisor 최신 브리핑", expanded=False):
                st.markdown(supervisor["last_brief"][:1200])
    else:
        st.markdown(f"**{_PHASE_LABELS['supervisor']}** · _(실행 후 상태 표시)_")
    st.markdown("⬇")

    groups = ("core", "quality", "ppt")
    for g in groups:
        entries = [e for e in AGENT_REGISTRY if e.get("phase_group") == g]
        if not entries:
            continue
        st.markdown(f"**{_PHASE_LABELS.get(g, g)}**")
        cols = st.columns(min(len(entries), 4))
        for i, entry in enumerate(entries):
            stt = _status_for_entry(entry, supervisor, steps_map)
            icon = _STATUS_ICON.get(stt, "○")
            with cols[i % len(cols)]:
                st.markdown(
                    f"{icon} **{entry.get('order')}. {entry.get('display_name', '')[:22]}**"
                )
                st.caption(entry.get("deliverable_label", "")[:36])
        if g == "core":
            st.caption("↳ 각 단계 직후 **다음 Agent**와 3라운드 피어 대화 (AUTOPM_DIALOGUE_ROUNDS)")
        st.markdown("⬇")

    st.success("최종 산출: `outputs/project_plan.pptx`")


def _render_registry_table(
    supervisor: dict[str, Any] | None,
    steps_map: dict[str, str],
    last_result: Any | None,
) -> None:
    """전 Agent 레지스트리 표."""
    rows = []
    for entry in sorted(AGENT_REGISTRY, key=lambda x: x.get("order", 99)):
        stt = _status_for_entry(entry, supervisor, steps_map)
        dialogue_n = 0
        if last_result and getattr(last_result.state, "supervisor", None):
            ag = (supervisor or {}).get("agents", {}).get(entry.get("id", ""), {})
            dialogue_n = int(ag.get("dialogue_rounds") or 0)
        rows.append(
            {
                "순서": entry.get("order"),
                "단계": _PHASE_LABELS.get(entry.get("phase_group", ""), entry.get("phase_group")),
                "Agent": entry.get("display_name"),
                "Task": entry.get("task_key"),
                "산출물": entry.get("deliverable_label"),
                "상태": stt,
                "대화": dialogue_n if dialogue_n else "—",
            }
        )

    # Deep pipeline task 순서 보조
    st.markdown("##### Deep Pipeline 태스크 순서")
    pipe_rows = []
    for i, tk in enumerate(PIPELINE_KEYS):
        msg = PIPELINE_USER_MSG[i] if i < len(PIPELINE_USER_MSG) else ""
        pipe_rows.append({"#": i + 1, "task_key": tk, "진행 메시지": msg[:50]})
    st.dataframe(pipe_rows, hide_index=True, use_container_width=True)

    st.markdown("##### Supervisor 레지스트리 (전체 Agent)")
    st.dataframe(rows, hide_index=True, use_container_width=True)


def _render_subagent_teams(last_result: Any | None) -> None:
    """Parent Agent별 Sub-Agent 구성."""
    teams = _load_subagents()
    if not teams:
        st.caption("subagents.yaml 을 찾지 못했습니다.")
        return

    st.caption("각 Parent Agent 실행 시 Sub-Agent 팀(로컬 LLM → cloud synthesizer)이 병렬·순차 실행됩니다.")

    sub_out = {}
    if last_result and getattr(last_result.state, "subagent_outputs", None):
        sub_out = last_result.state.subagent_outputs or {}

    for parent, members in teams.items():
        n_run = len(sub_out.get(_parent_task_key(parent), []) or [])
        label = f"`{parent}` — Sub-Agent {len(members)}명"
        if n_run:
            label += f" · 최근 실행 {n_run}건"
        with st.expander(label, expanded=False):
            for m in members:
                st.markdown(f"- **{m['id']}** · {m['role']} · tier `{m['tier']}`")


def _parent_task_key(parent_agent_key: str) -> str:
    """subagents.yaml 키 → task_key 매핑 (일부만)."""
    mapping = {
        "pm_orchestrator_agent": "orchestrate_task",
        "requirement_interview_agent": "requirement_task",
        "business_analyst_agent": "business_analysis_task",
        "solution_architect_agent": "solution_design_task",
        "development_scope_agent": "development_scope_task",
        "wbs_planner_agent": "wbs_task",
        "budget_roi_agent": "budget_roi_task",
        "risk_critic_agent": "risk_critic_task",
        "storyline_slide_planning_agent": "slide_storyline_task",
        "visualization_agent": "visualization_design_task",
        "presentation_graphics_agent": "presentation_graphics_task",
        "ppt_composer_agent": "ppt_composition_task",
    }
    return mapping.get(parent_agent_key, "")


__all__ = ["render_agent_workflow_tab"]
