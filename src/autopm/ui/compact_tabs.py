"""컴팩트 3탭 레이아웃 — 인터뷰 / 수집·진행 / 산출물."""

from __future__ import annotations

from typing import Any, Callable

import streamlit as st

from autopm.chat import InterviewState
from autopm.state.ppt_generation_state import GUIDED_STEP_LABELS, STEP_ORDER
from autopm.ui.agent_progress import render_agent_progress
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
) -> tuple[Any, Any]:
    """탭 2: 수집 요약·12단계·Agent/Supervisor 진행."""
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

    # 수집 항목을 2열 칩 형태로 압축
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

    with st.expander("필드 직접 수정", expanded=False):
        m = get_iv()
        with st.form("manual_interview_form", border=False):
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

    st.markdown("##### 12단계 프로세스")
    step_cols = st.columns(6)
    for i, sid in enumerate(STEP_ORDER):
        stat = str(ppt_gen_dict.get("step_statuses", {}).get(sid, "pending"))
        label = GUIDED_STEP_LABELS.get(sid, sid)
        with step_cols[i % 6]:
            st.caption(f"`{stat[:4]}` {label[:10]}")

    st.markdown("##### Agent 진행")
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
            st.info("Auto 실행 또는 Guided 패널(인터뷰 탭)에서 생성을 시작하면 표시됩니다.")

    if last_result and getattr(last_result.state, "supervisor", None):
        with st.expander("Supervisor PM", expanded=False):
            render_supervisor_panel(last_result.state.supervisor)

    return overall_progress, dash_placeholder
