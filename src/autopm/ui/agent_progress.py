"""Agent Progress Dashboard — 단계·상태·산출 요약을 Streamlit 카드로 표시한다."""

from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass
from typing import Any, Callable

VALID_STATUSES = frozenset({"pending", "running", "complete", "error"})


@dataclass
class AgentStep:
    """한 명의 Agent에 대응하는 대시보드 행 — UI·상태 시뮬레이션에 공통 사용."""

    id: str
    display_name: str
    role_summary: str
    status: str = "pending"
    artifact: str = ""
    completion_message: str = ""


def get_agent_steps() -> list[AgentStep]:
    """AGENTS.md·파이프라인 순서와 동일한 12단계 — Core 8 + Storyline + Vis + Graphics + Composer."""
    return [
        AgentStep(
            "pm_orchestrator",
            "PM Orchestrator Agent",
            "추진계획 목차·산출물 구조 설계",
        ),
        AgentStep(
            "requirement_interview",
            "Requirement Interview Agent",
            "누락 정보·가정·추가 질문 정리",
        ),
        AgentStep(
            "business_analyst",
            "Business Analyst Agent",
            "AS-IS·Pain Point·이해관계자 영향",
        ),
        AgentStep(
            "solution_architect",
            "Solution Architect Agent",
            "TO-BE·자동화 범위·기술 방향",
        ),
        AgentStep(
            "development_scope",
            "Development Scope Agent",
            "개발 범위·포함/제외·모듈",
        ),
        AgentStep("wbs_planner", "WBS Planner Agent", "WBS·일정·마일스톤"),
        AgentStep("budget_roi", "Budget & ROI Agent", "예산·ROI·KPI (가정 명시)"),
        AgentStep(
            "risk_critic_doc",
            "Risk & Critic Agent",
            "리스크 매트릭스·Critic 루프·문서화 통합",
        ),
        AgentStep(
            "storyline",
            "Storyline / Slide Planning Agent",
            "PPT 슬라이드 스토리라인(JSON)",
        ),
        AgentStep(
            "visualization",
            "Visualization Agent",
            "슬라이드별 visual_type·content",
        ),
        AgentStep(
            "presentation_graphics",
            "Presentation Graphics Agent",
            "graphics_spec·장표 도형/PNG 에셋 설계",
        ),
        AgentStep("ppt_composer", "PPT Composer Agent", "SlideDeckSpec → project_plan.pptx"),
    ]


def update_agent_status(
    steps: list[AgentStep],
    index: int,
    status: str,
    *,
    artifact: str | None = None,
    completion_message: str | None = None,
) -> None:
    """단일 Agent 행 상태 갱신 — 잘못된 status는 pending으로 클램프하지 않고 무시."""
    if not (0 <= index < len(steps)) or status not in VALID_STATUSES:
        return
    steps[index].status = status
    if artifact is not None:
        steps[index].artifact = artifact
    if completion_message is not None:
        steps[index].completion_message = completion_message


def _status_emoji(status: str) -> str:
    return {
        "pending": "⏳",
        "running": "🔄",
        "complete": "✅",
        "error": "❌",
    }.get(status, "⏳")


def _count_complete(steps: list[AgentStep]) -> int:
    return sum(1 for s in steps if s.status == "complete")


def render_agent_progress(
    steps: list[AgentStep],
    *,
    progress_callback: Callable[[float], None] | None = None,
) -> None:
    """카드형 목록 + 선택적 progress(0.0~1.0) 콜백 — st.progress와 함께 쓰려면 콜백에서 갱신."""
    total = len(steps)
    done = _count_complete(steps)
    running = sum(1 for s in steps if s.status == "running")
    err = sum(1 for s in steps if s.status == "error")
    if progress_callback is not None and total:
        # running이 있으면 완료 비율 + 진행 중 한 칸의 일부로 시각적 중간값
        frac = (done + (0.5 if running else 0)) / total
        progress_callback(min(1.0, frac))
    import streamlit as st

    st.caption(f"완료 **{done}** / **{total}** · 실행 중 **{running}** · 오류 **{err}**")
    for s in steps:
        with st.container(border=True):
            c1, c2 = st.columns([0.12, 0.88])
            with c1:
                st.markdown(f"### {_status_emoji(s.status)}")
            with c2:
                st.markdown(f"**{s.display_name}**")
                st.caption(s.role_summary)
                status_kr = {"pending": "대기", "running": "실행 중", "complete": "완료", "error": "오류"}.get(
                    s.status, s.status
                )
                st.markdown(f"- **상태:** {status_kr}")
                if s.artifact:
                    st.markdown(f"- **산출물:** {s.artifact}")
                if s.completion_message:
                    st.markdown(f"- **완료 메시지:** {s.completion_message}")


def simulate_agent_progress(
    steps: list[AgentStep],
    *,
    delay_min: float = 0.3,
    delay_max: float = 0.7,
    render_fn: Callable[[list[AgentStep]], None],
) -> None:
    """
    Deep Agent 호출 전 가벼운 시뮬레이션 — 각 Agent가 순차로 '실행 중' 후 다시 대기로 돌아가 웨이브만 보여준다.
    (실제 완료는 run 이후 finalize에서 처리 — 요구사항 '실행 전 simulation'.)
    """
    for i, _s in enumerate(steps):
        update_agent_status(steps, i, "running")
        render_fn(steps)
        time.sleep(random.uniform(delay_min, delay_max))
        update_agent_status(steps, i, "pending")
        render_fn(steps)
    # 시뮬 종료 후 전부 대기
    for j in range(len(steps)):
        update_agent_status(steps, j, "pending")
    render_fn(steps)


def apply_progress_message(steps: list[AgentStep], message: str) -> None:
    """
    flow.py의 on_progress 문자열을 12단계 모델에 매핑한다.
    인덱스 7: 리스크 태스크 완료 후 ~ 문서화 완료까지 Critic/문서화 포함.
    """
    msg = message.strip()

    m_done = re.search(r"\[(\d+)/12\].*?완료", msg)
    if m_done:
        n = int(m_done.group(1))
        if 1 <= n <= 8:
            idx = n - 1
            for k in range(idx):
                if steps[k].status != "error":
                    update_agent_status(steps, k, "complete")
            if idx <= 6:
                update_agent_status(steps, idx, "complete")
            elif idx == 7:
                update_agent_status(steps, 7, "running")
        elif n == 9:
            for k in range(8):
                if steps[k].status != "error":
                    update_agent_status(steps, k, "complete")
            update_agent_status(steps, 8, "complete")
        elif n == 10:
            for k in range(9):
                if steps[k].status != "error":
                    update_agent_status(steps, k, "complete")
            update_agent_status(steps, 9, "complete")
        elif n == 11:
            for k in range(10):
                if steps[k].status != "error":
                    update_agent_status(steps, k, "complete")
            update_agent_status(steps, 10, "complete")
        elif n == 12:
            for k in range(11):
                if steps[k].status != "error":
                    update_agent_status(steps, k, "complete")
            update_agent_status(steps, 11, "complete")
        return

    if "[Documentation]" in msg:
        for k in range(7):
            if steps[k].status not in ("error",):
                update_agent_status(steps, k, "complete")
        update_agent_status(steps, 7, "running")
        return

    if "실행 중" in msg:
        m_run = re.search(r"\[(\d+)/12\]", msg)
        if m_run:
            n = int(m_run.group(1))
            if 1 <= n <= 8:
                idx = n - 1
                for k in range(idx):
                    if steps[k].status not in ("complete", "error"):
                        update_agent_status(steps, k, "complete")
                update_agent_status(steps, idx, "running")
            elif n == 9:
                for k in range(8):
                    if steps[k].status not in ("complete", "error"):
                        update_agent_status(steps, k, "complete")
                update_agent_status(steps, 8, "running")
            elif n == 10:
                for k in range(9):
                    if steps[k].status not in ("complete", "error"):
                        update_agent_status(steps, k, "complete")
                update_agent_status(steps, 9, "running")
            elif n == 11:
                for k in range(10):
                    if steps[k].status not in ("complete", "error"):
                        update_agent_status(steps, k, "complete")
                update_agent_status(steps, 10, "running")
            elif n == 12:
                for k in range(11):
                    if steps[k].status not in ("complete", "error"):
                        update_agent_status(steps, k, "complete")
                update_agent_status(steps, 11, "running")
        return

    if "[Critic]" in msg or "[보완]" in msg:
        for k in range(7):
            if steps[k].status not in ("error",):
                update_agent_status(steps, k, "complete")
        update_agent_status(steps, 7, "running")
        return

    if "[문서화] 완료" in msg:
        for k in range(7):
            if steps[k].status not in ("error",):
                update_agent_status(steps, k, "complete")
        update_agent_status(steps, 7, "complete")
        return

    if "Storyline" in msg:
        for k in range(8):
            if steps[k].status not in ("error",):
                update_agent_status(steps, k, "complete")
        if "완료" in msg:
            update_agent_status(steps, 8, "complete")
        else:
            update_agent_status(steps, 8, "running")
        return

    if "Visualization" in msg:
        for k in range(8):
            if steps[k].status not in ("error",):
                update_agent_status(steps, k, "complete")
        if "완료" in msg:
            update_agent_status(steps, 9, "complete")
        else:
            update_agent_status(steps, 9, "running")
        return

    if "Presentation Graphics" in msg:
        for k in range(9):
            if steps[k].status not in ("error",):
                update_agent_status(steps, k, "complete")
        if "완료" in msg:
            update_agent_status(steps, 10, "complete")
        else:
            update_agent_status(steps, 10, "running")
        return

    if "PPT Composer" in msg:
        for k in range(10):
            if steps[k].status not in ("error",):
                update_agent_status(steps, k, "complete")
        if "완료" in msg:
            update_agent_status(steps, 11, "complete")
        else:
            update_agent_status(steps, 11, "running")
        return


def mark_all_complete(steps: list[AgentStep]) -> None:
    for i in range(len(steps)):
        if steps[i].status != "error":
            update_agent_status(steps, i, "complete")


def mark_pipeline_error(steps: list[AgentStep], from_index: int, err: str) -> None:
    """from_index부터 오류 처리 — 이전 단계는 complete 유지."""
    if 0 <= from_index < len(steps):
        update_agent_status(
            steps,
            from_index,
            "error",
            artifact="",
            completion_message=err[:300],
        )
    for j in range(from_index + 1, len(steps)):
        if steps[j].status != "error":
            update_agent_status(steps, j, "pending")


def fill_summaries_from_state(steps: list[AgentStep], result: Any) -> None:
    """실행 후 산출물·완료 문구를 상태 필드에서 채운다 — PPT 경로는 artifacts 우선."""
    stt = result.state
    arts = stt.artifacts or {}

    def _clip(text: str, n: int = 160) -> str:
        t = (text or "").strip().replace("\n", " ")
        return t if len(t) <= n else t[: n - 1] + "…"

    summaries: list[tuple[str, str]] = [
        ("PM Orchestrator", "전체 추진계획 구조 설계 완료"),
        ("Requirement Interview", "누락 정보 및 추가 질문 생성 완료"),
        ("Business Analyst", "AS-IS / Pain Point 분석 완료"),
        ("Solution Architect", "TO-BE / 개선 방향 설계 완료"),
        ("Development Scope", "개발 범위·포함/제외 정의 완료"),
        ("WBS Planner", f"{stt.user_input.get('target_timeline', '일정')} 추진 일정·WBS 생성 완료"),
        ("Budget & ROI", "예산·ROI·KPI 표 초안 완료 (가정 기반)"),
        ("Risk & Critic", "리스크 매트릭스·Critic·문서화 통합 완료"),
        ("Storyline", "슬라이드 스토리라인 JSON 완료"),
        ("Visualization", "슬라이드 시각 유형·content 보강 완료"),
        ("Presentation Graphics", "graphics_spec·visual_assets 반영 완료"),
        ("PPT Composer", "project_plan.pptx 생성 완료"),
    ]

    outs = stt.agent_outputs or {}
    state_texts = [
        outs.get("orchestrate_task") or stt.orchestration_brief,
        outs.get("requirement_task") or stt.requirement_analysis,
        outs.get("business_analysis_task") or stt.business_analysis,
        outs.get("solution_design_task") or stt.solution_direction,
        outs.get("development_scope_task") or stt.development_scope,
        outs.get("wbs_task") or stt.wbs_plan,
        outs.get("budget_roi_task") or stt.budget_roi,
        _clip(outs.get("risk_critic_task") or stt.risk_management)
        + " | "
        + _clip(stt.critic_review),
        _clip(outs.get("slide_storyline_task") or stt.slide_storyline_raw),
        _clip(outs.get("visualization_design_task") or stt.visualization_raw),
        _clip(outs.get("presentation_graphics_task") or stt.presentation_graphics_raw),
        arts.get("project_plan.pptx", ""),
    ]

    for i, step in enumerate(steps):
        if step.status == "error":
            continue
        art = state_texts[i] if i < len(state_texts) else ""
        if i == 11 and arts.get("project_plan.pptx"):
            art = arts["project_plan.pptx"]
        if i == 8 and arts.get("slide_plan.json"):
            art = art or arts["slide_plan.json"]
        if i == 10 and arts.get("visual_assets.json"):
            art = art or arts["visual_assets.json"]
        step.artifact = _clip(str(art), 200) if i != 11 else (art or step.artifact)
        if i < len(summaries):
            _, done_msg = summaries[i]
            step.completion_message = done_msg

    if len(steps) > 11 and arts.get("project_plan.pptx"):
        steps[11].artifact = arts["project_plan.pptx"]
        steps[11].completion_message = "project_plan.pptx 생성 완료"


def finalize_agent_dashboard(steps: list[AgentStep], result: Any) -> None:
    """
    실행 종료 후 대시보드 정리 — 예외 응답에도 PPT fallback이 있으면 후단 Agent는 완료로 둔다.
    """
    structured = result.structured if isinstance(result.structured, dict) else {}
    err = structured.get("error")
    rate_limited = structured.get("rate_limited")

    if err and not rate_limited:
        running_idx = next((i for i in range(len(steps) - 1, -1, -1) if steps[i].status == "running"), None)
        if running_idx is not None:
            mark_pipeline_error(steps, running_idx, str(err))
        elif all(s.status != "error" for s in steps):
            mark_pipeline_error(steps, 7, str(err))
        arts = result.state.artifacts or {}
        if arts.get("project_plan.pptx"):
            for j in range(8, 12):
                update_agent_status(steps, j, "complete")
    else:
        mark_all_complete(steps)

    fill_summaries_from_state(steps, result)
    try:
        from autopm.orchestration.supervisor_manager import sync_agent_steps_from_supervisor

        sync_agent_steps_from_supervisor(steps, result.state)
    except Exception:
        pass


__all__ = [
    "AgentStep",
    "get_agent_steps",
    "update_agent_status",
    "render_agent_progress",
    "simulate_agent_progress",
    "apply_progress_message",
    "mark_all_complete",
    "mark_pipeline_error",
    "fill_summaries_from_state",
    "finalize_agent_dashboard",
]
