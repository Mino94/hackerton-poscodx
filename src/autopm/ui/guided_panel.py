"""Guided 모드 — 12단계 스테퍼·입력 확인 표·진행 탭 전용 UI."""

from __future__ import annotations

import html
from typing import Callable

import streamlit as st

from autopm.chat import InterviewState
from autopm.state.ppt_generation_state import GUIDED_STEP_LABELS, STEP_ORDER

# guided_ui_step → 파이프라인 step_statuses 키 (스테퍼 하이라이트용)
GUIDED_UI_ACTIVE_STEP: dict[str, str] = {
    "input_confirm": "confirm_input",
    "draft_generate": "draft_generate",
    "draft_decide": "draft_approve",
    "core_run": "slide_plan_generate",
    "slide_pick": "slide_plan_approve",
    "slide_exec": "slide_plan_generate",
    "style_pick": "visual_style_pick",
    "vap_options": "visual_asset_generate",
    "vis_run": "visual_asset_generate",
    "visual_ok": "visual_plan_approve",
    "gfx_run": "ppt_generate",
    "compose_run": "ppt_generate",
    "post_ppt": "post_ppt_review",
    "done": "post_ppt_review",
}

GUIDED_UI_TITLE: dict[str, str] = {
    "input_confirm": "3) 입력 정보 확인",
    "draft_generate": "4) 1차 초안 생성",
    "draft_decide": "5) 초안 승인 / 톤 선택",
    "core_run": "6–7) Core Agent + 문서화",
    "slide_pick": "8) 슬라이드 구성 선택",
    "slide_exec": "슬라이드 스토리라인 생성",
    "style_pick": "9) 장표 스타일",
    "vap_options": "10) Visual Asset Plan",
    "vis_run": "Visualization Agent",
    "visual_ok": "Visual 계획 확인",
    "gfx_run": "Presentation Graphics",
    "compose_run": "11) PPT 생성",
    "post_ppt": "12) 최종 개선 / 다운로드",
    "done": "완료",
}

_STATUS_STYLE = {
    "complete": ("#dcfce7", "#166534", "✓"),
    "approved": ("#dcfce7", "#166534", "✓"),
    "active": ("#dbeafe", "#1d4ed8", "●"),
    "running": ("#dbeafe", "#1d4ed8", "●"),
    "waiting_user": ("#fef3c7", "#b45309", "!"),
    "revised": ("#fef3c7", "#b45309", "↻"),
    "error": ("#fee2e2", "#b91c1c", "✕"),
    "pending": ("#f1f5f9", "#64748b", "○"),
}


def render_guided_stepper(
    step_statuses: dict[str, str],
    guided_ui_step: str,
) -> None:
    """12단계 파이프라인 — 완료/진행/대기를 한눈에 표시."""
    active_id = GUIDED_UI_ACTIVE_STEP.get(guided_ui_step, "confirm_input")
    try:
        active_idx = STEP_ORDER.index(active_id)
    except ValueError:
        active_idx = 0

    done_n = sum(1 for sid in STEP_ORDER if step_statuses.get(sid) in ("complete", "approved"))
    st.caption(f"**{done_n}/{len(STEP_ORDER)}** 단계 완료 · 지금: **{GUIDED_UI_TITLE.get(guided_ui_step, guided_ui_step)}**")

    cells: list[str] = []
    for i, sid in enumerate(STEP_ORDER):
        stat = str(step_statuses.get(sid, "pending"))
        bg, fg, icon = _STATUS_STYLE.get(stat, _STATUS_STYLE["pending"])
        label = GUIDED_STEP_LABELS.get(sid, sid)
        short = label.split(")", 1)[-1].strip() if ")" in label else label
        border = "2px solid #1d4ed8" if sid == active_id or i == active_idx else "1px solid #e2e8f0"
        weight = "700" if sid == active_id else "500"
        cells.append(
            f'<div style="flex:1;min-width:72px;max-width:140px;text-align:center;padding:4px 2px;'
            f"background:{bg};color:{fg};border:{border};border-radius:6px;font-size:0.68rem;"
            f'font-weight:{weight};line-height:1.2;margin:2px;">'
            f'<div style="font-size:0.75rem;">{icon}</div>'
            f'<div>{html.escape(label.split(")")[0] + ")")}</div>'
            f'<div style="opacity:0.85;font-size:0.62rem;">{html.escape(short[:8])}</div></div>'
        )

    st.markdown(
        f'<div style="display:flex;flex-wrap:wrap;gap:2px;margin:0.25rem 0 0.5rem;">{"".join(cells)}</div>',
        unsafe_allow_html=True,
    )


def render_input_confirm_table(get_iv: Callable[[], InterviewState]) -> None:
    """3) 입력 정보 확인 — 표 형태로 핵심 필드만 정리."""
    iv = get_iv()
    rows = []
    for label, disp, ok in iv.summary_rows():
        if label.startswith("추론"):
            continue
        rows.append(
            {
                "상태": "✅" if ok else "⏳",
                "항목": label,
                "내용": (disp[:80] + "…") if len(str(disp)) > 80 else disp,
            }
        )
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True, height=min(420, 36 * len(rows) + 38))
    missing = iv.get_missing_fields()
    if missing:
        st.warning(f"미입력 **{len(missing)}**개 — 인터뷰 탭에서 채우거나 아래 **직접 수정**을 사용하세요.")


def render_guided_banner_in_interview() -> None:
    """인터뷰 탭 — 승인 UI는 수집·진행 탭으로 안내."""
    gu = st.session_state.get("guided_ui_step", "input_confirm")
    title = GUIDED_UI_TITLE.get(gu, gu)
    st.info(
        f"**Guided** · **{title}** — 인터뷰 탭에서 **추천 방향**을 고르면 자동으로 여기까지 이어집니다. "
        "또는 **📊 수집·진행** 탭 **⚡ 한번에 진행** / 단계별 세부."
    )
