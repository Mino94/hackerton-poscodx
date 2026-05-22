"""컴팩트 3탭 레이아웃 — 인터뷰 / 수집·진행 / 산출물."""

from __future__ import annotations

from typing import Any, Callable

import streamlit as st

from autopm.chat import InterviewState
from autopm.state.ppt_generation_state import STEP_ORDER
from autopm.ui.agent_progress import render_agent_progress
from autopm.ui.guided_panel import render_guided_stepper
from autopm.ui.supervisor_panel import render_supervisor_panel


def inject_compact_css() -> None:
    """탭·메트릭·채팅 영역 여백을 줄여 한 화면에 더 많이 보이게 한다."""
    st.markdown(
        """
        <style>
        .block-container { padding-top: 0.75rem; padding-bottom: 1rem; max-width: 1180px; }
        div[data-testid="stMetric"] { background: #f8f9fb; padding: 0.35rem 0.5rem; border-radius: 6px; }
        div[data-testid="stTabs"] [data-baseweb="tab-list"] { gap: 0.25rem; }
        div[data-testid="stTabs"] button { padding: 0.4rem 0.85rem; font-size: 0.88rem; }
        [data-testid="stChatMessage"] { padding: 0.35rem 0.5rem; }
        .autopm-chip { display:inline-block; padding:2px 8px; margin:2px 4px 2px 0;
          border-radius:999px; font-size:0.78rem; background:#eef2f7; color:#334155; }
        .guided-action-box {
          border: 1px solid #cbd5e1; border-left: 4px solid #05509c;
          border-radius: 8px; padding: 0.65rem 0.75rem; margin: 0.35rem 0 0.75rem;
          background: #f8fafc;
        }
        [data-testid="stChatMessage"] { font-size: 0.9rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_progress_tab(
    get_iv: Callable[[], InterviewState],
    save_iv: Callable[[InterviewState], None],
    agent_steps: list[Any] | None,
    last_result: Any | None,
    ppt_gen_dict: dict,
    *,
    run_mode: str = "Auto",
    guided_panel_fn: Callable[[], None] | None = None,
) -> tuple[Any, Any]:
    """탭 2: Guided 스테퍼·승인·수집 요약·Agent 진행."""
    if run_mode == "Guided":
        st.markdown("### Guided · 단계별 승인")
        render_guided_stepper(
            ppt_gen_dict.get("step_statuses") or {},
            st.session_state.get("guided_ui_step", "input_confirm"),
        )
        st.markdown('<div class="guided-action-box">', unsafe_allow_html=True)
        if guided_panel_fn:
            guided_panel_fn()
        st.markdown("</div>", unsafe_allow_html=True)
        st.divider()

    iv = get_iv()
    filled = iv.filled_count()
    total = iv.total_fields()
    pct = min(1.0, filled / max(1, total))

    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("필수 수집", f"{filled}/{total}")
    with m2:
        st.metric("수집률", f"{int(pct * 100)}%")
    with m3:
        done_agents = sum(1 for s in (agent_steps or []) if getattr(s, "status", "") == "complete")
        st.metric("Agent 완료", f"{done_agents}/12" if agent_steps else "—")

    st.progress(pct)

    if iv.has_assumptions():
        st.warning("일부 항목은 **가정값**으로 채워집니다. 인터뷰를 이어가거나 아래에서 수정하세요.")

    # Guided·입력 확인 단계에서는 표가 위 박스에 있으므로 요약만 짧게 표시
    gu = st.session_state.get("guided_ui_step", "")
    if not (run_mode == "Guided" and gu == "input_confirm"):
        rows = iv.summary_rows()
        half = (len(rows) + 1) // 2
        c_left, c_right = st.columns(2)
        with c_left:
            for label, disp, ok in rows[:half]:
                icon = "✅" if ok else "⏳"
                st.markdown(f"{icon} **{label}** — {disp}")
        with c_right:
            for label, disp, ok in rows[half:]:
                icon = "✅" if ok else "⏳"
                st.markdown(f"{icon} **{label}** — {disp}")
    else:
        st.caption("입력 확인 표는 위 **Guided** 박스에 있습니다. 수정은 아래 폼을 사용하세요.")

    with st.expander("필드 직접 수정", expanded=run_mode == "Guided" and gu == "input_confirm"):
        render_manual_interview_form_embed(get_iv, save_iv)

    return _render_progress_tab_tail(agent_steps, last_result, ppt_gen_dict, run_mode=run_mode)


def render_manual_interview_form_embed(
    get_iv: Callable[[], InterviewState],
    save_iv: Callable[[InterviewState], None],
) -> None:
    """Sources 패널·진행 탭 공용 — 인터뷰 필드 수동 편집."""
    m = get_iv()
    with st.form("manual_interview_form_nlm", border=False):
        c1, c2 = st.columns(2)
        with c1:
            pt = st.text_input("주제/제목", value=m.proposal_title or m.idea_title or "")
            ppur = st.text_input("목적", value=m.proposal_purpose or "")
            bg = st.text_area("배경", value=m.background_context or "", height=56)
            prob = st.text_area("핵심 문제", value=m.current_problems or m.pain_points or "", height=48)
            ts = st.text_input("대상 시스템", value=m.target_system or "")
        with c2:
            bs = st.text_area("업무·기능 범위", value=m.business_scope or "", height=48)
            imp = st.text_area("개선 방향", value=m.improvement_direction or m.goal or "", height=48)
            aud = st.text_input("보고 대상", value=m.target_audience or "")
            emph = st.text_input("강조 포인트", value=m.key_emphasis or "")
            tone = st.text_input("PPT 톤", value=m.presentation_tone or "")
        submitted = st.form_submit_button("반영", use_container_width=True)
    if submitted:
        m.proposal_title = pt.strip() or None
        m.idea_title = m.proposal_title
        m.proposal_purpose = ppur.strip() or None
        m.background_context = bg.strip() or None
        m.current_problems = prob.strip() or None
        m.pain_points = m.current_problems
        m.target_system = ts.strip() or None
        m.business_scope = bs.strip() or None
        m.improvement_direction = imp.strip() or None
        m.goal = m.improvement_direction
        m.target_audience = aud.strip() or None
        m.key_emphasis = emph.strip() or None
        m.presentation_tone = tone.strip() or None
        save_iv(m)
        st.success("반영됨")
        st.rerun()


def _render_progress_tab_tail(
    agent_steps: list[Any] | None,
    last_result: Any | None,
    ppt_gen_dict: dict,
    *,
    run_mode: str = "Auto",
) -> tuple[Any, Any]:
    """진행 탭 하단 — Agent/Supervisor (Guided는 상단 스테퍼 사용)."""
    if run_mode != "Guided":
        st.markdown("##### 12단계 프로세스")
        render_guided_stepper(
            ppt_gen_dict.get("step_statuses") or {},
            "input_confirm",
        )

    st.markdown("##### Agent 실행 현황")
    overall_progress = st.progress(0.0)
    dash_placeholder = st.empty()

    if agent_steps:
        with dash_placeholder.container():
            render_agent_progress(
                agent_steps,
                progress_callback=overall_progress.progress,
            )
        overall_progress.progress(1.0 if last_result else 0.0)
    else:
        with dash_placeholder.container():
            st.info(
                "생성을 시작하면 표시됩니다. Agent 간 검토 대화는 **🤝 Agent 대화** 탭에서 채팅 형태로 볼 수 있습니다."
            )

    if last_result and getattr(last_result.state, "supervisor", None):
        with st.expander("Supervisor PM", expanded=False):
            render_supervisor_panel(last_result.state.supervisor)

    return overall_progress, dash_placeholder
