"""Supervisor PM 대시보드 — 전 Agent 진행·산출·체크포인트 UI."""

from __future__ import annotations

from typing import Any

import streamlit as st


def render_supervisor_panel(supervisor: dict[str, Any] | None) -> None:
    """Streamlit — Supervisor가 관리하는 전체 Agent 현황."""
    if not supervisor or not supervisor.get("agents"):
        st.caption("Supervisor: 파이프라인 실행 후 전 Agent 진행·산출이 여기에 표시됩니다.")
        return

    st.subheader("Supervisor PM — 전체 Agent 관리")
    c1, c2, c3, c4 = st.columns(4)
    stats = supervisor.get("progress_summary") or {}
    with c1:
        st.metric("전체 진행", f"{supervisor.get('progress_pct', 0)}%")
    with c2:
        st.metric("상태", supervisor.get("overall_status", "—"))
    with c3:
        st.metric("체크포인트", stats.get("checkpoint_count", len(supervisor.get("checkpoints") or [])))
    with c4:
        st.metric("블로커", stats.get("blocker_count", len(supervisor.get("blockers") or [])))

    if supervisor.get("last_brief"):
        with st.expander("Supervisor 최신 브리핑", expanded=True):
            st.markdown(supervisor["last_brief"])

    actions = supervisor.get("next_actions") or []
    if actions:
        st.markdown("**다음 지시**")
        for a in actions:
            st.markdown(f"- {a}")

    agents = supervisor.get("agents") or {}
    rows = []
    for entry in sorted(agents.values(), key=lambda x: x.get("order", 99)):
        rows.append(
            {
                "순서": entry.get("order"),
                "Agent": entry.get("display_name"),
                "상태": entry.get("status"),
                "품질": entry.get("quality"),
                "산출(자)": entry.get("output_chars", 0),
                "Sub": entry.get("subagent_count", 0),
                "대화": entry.get("dialogue_rounds", 0),
                "산출물": entry.get("deliverable_label"),
                "Supervisor 메모": (entry.get("supervisor_note") or "")[:80],
            }
        )
    st.dataframe(rows, hide_index=True, use_container_width=True)

    blockers = supervisor.get("blockers") or []
    if blockers:
        st.warning("블로커: " + " · ".join(blockers[:5]))

    checkpoints = supervisor.get("checkpoints") or []
    if checkpoints:
        with st.expander(f"체크포인트 이력 ({len(checkpoints)})", expanded=False):
            for cp in reversed(checkpoints[-5:]):
                st.markdown(f"**{cp.get('label')}** · `{cp.get('decision')}` · {cp.get('at', '')}")
                st.caption(cp.get("summary", "")[:500])
                if cp.get("status_table"):
                    st.markdown(cp["status_table"])


__all__ = ["render_supervisor_panel"]
