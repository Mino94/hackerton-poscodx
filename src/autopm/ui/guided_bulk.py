"""Guided — 프리셋으로 여러 단계를 한 번에 실행."""

from __future__ import annotations

from typing import Any

import streamlit as st

# 프리셋 메타 (실행 로직은 app.py _execute_guided_bulk)
BULK_PRESETS: dict[str, dict[str, str]] = {
    "to_draft": {
        "label": "①~④ 초안까지",
        "desc": "입력 확인 → 1차 초안 생성 (톤 선택 전)",
        "icon": "📝",
    },
    "to_core": {
        "label": "①~⑦ Core+문서",
        "desc": "초안(그대로) → Core Agent + 추진계획서 문서화",
        "icon": "📋",
    },
    "to_ppt": {
        "label": "①~⑪ PPT까지 (표준)",
        "desc": "초안·Core·10장·실무 톤·Storyline·Vis·Graphics·PPT 한 번에",
        "icon": "🚀",
    },
    "ppt_from_core": {
        "label": "⑧~⑪ PPT만",
        "desc": "Core 완료 후 — 10장·실무 톤·PPT 생성만 (현재 Core 이후 단계)",
        "icon": "📊",
    },
    "demo_to_ppt": {
        "label": "샘플 채우고 PPT까지",
        "desc": "미입력 항목 ERP 데모 샘플 → 표준 프리셋으로 PPT 생성",
        "icon": "⚡",
    },
}

# 프리셋별 적용 기본값 (사용자에게 표시) — demo_to_ppt는 to_ppt 기본값을 재사용
_TO_PPT_DEFAULTS: list[str] = [
    "슬라이드 10장",
    "장표 스타일: 실무 추진계획",
    "Visual: 그대로",
    "PPT Composer까지",
]

PRESET_DEFAULTS: dict[str, list[str]] = {
    "to_draft": ["입력 확인 승인", "초안 생성"],
    "to_core": ["초안 톤: 그대로", "Core 8 Agent + 문서"],
    "to_ppt": list(_TO_PPT_DEFAULTS),
    "ppt_from_core": ["슬라이드 10장", "실무 톤", "PPT까지"],
    "demo_to_ppt": ["데모 샘플 일괄 입력", *_TO_PPT_DEFAULTS],
}


def _preset_allowed(preset_id: str, guided_ui_step: str) -> bool:
    """현재 UI 단계에서 실행 가능한 프리셋인지."""
    early = {
        "input_confirm",
        "draft_generate",
        "draft_decide",
        "core_run",
        "slide_pick",
    }
    ppt_only = {
        "slide_pick",
        "slide_exec",
        "style_pick",
        "vap_options",
        "vis_run",
        "visual_ok",
        "gfx_run",
        "compose_run",
    }
    if preset_id in ("to_draft", "to_core", "to_ppt", "demo_to_ppt"):
        return guided_ui_step in early or guided_ui_step == "input_confirm"
    if preset_id == "ppt_from_core":
        return guided_ui_step in ppt_only or guided_ui_step == "core_run"
    return False


def render_guided_bulk_bar(
    guided_ui_step: str,
    *,
    interview_started: bool,
) -> str | None:
    """
    한번에 진행 선택 UI.
    Returns: 클릭된 preset_id (없으면 None). 실행은 호출 측에서 처리.
    """
    if guided_ui_step in ("done", "post_ppt"):
        st.caption("생성 완료 — **산출물** 탭에서 다운로드하거나 아래에서 세부 조정하세요.")
        return None

    st.markdown("##### ⚡ 한번에 진행")
    st.caption("단계별 버튼 대신 **프리셋**을 고르면 기본값으로 연속 실행됩니다.")

    if not interview_started:
        st.warning("먼저 **인터뷰** 탭에서 주제 입력 후 **인터뷰 시작**을 해 주세요.")
        if st.button("⚡ 샘플 채우고 PPT까지 (인터뷰 자동)", type="primary", key="bulk_demo_only"):
            return "demo_to_ppt"
        return None

    # 프리셋 카드 2열
    preset_ids = [k for k in BULK_PRESETS if _preset_allowed(k, guided_ui_step)]
    if not preset_ids:
        st.caption("현재 단계에서는 아래 **세부 실행** 버튼을 사용하세요.")
        return None

    cols = st.columns(min(len(preset_ids), 2))
    clicked: str | None = None
    for i, pid in enumerate(preset_ids):
        meta = BULK_PRESETS[pid]
        with cols[i % len(cols)]:
            st.markdown(
                f"**{meta['icon']} {meta['label']}**  \n"
                f"<span style='font-size:0.8rem;color:#64748b'>{meta['desc']}</span>",
                unsafe_allow_html=True,
            )
            defaults = PRESET_DEFAULTS.get(pid, [])
            if defaults:
                st.caption(" · ".join(defaults[:4]))
            if st.button(
                f"실행 — {meta['label']}",
                key=f"bulk_run_{pid}",
                type="primary" if pid in ("to_ppt", "demo_to_ppt") else "secondary",
                use_container_width=True,
            ):
                clicked = pid

    with st.expander("프리셋 기본값 안내", expanded=False):
        st.markdown(
            "| 프리셋 | 적용 내용 |\n| --- | --- |\n"
            "| **PPT까지 (표준)** | 초안 그대로 · Core+문서 · 10장 · 실무 톤 · Visual 그대로 · PPT |\n"
            "| **Core+문서** | 초안까지 + Core 8 Agent |\n"
            "| **초안까지** | 입력 확인 + 1차 초안 |\n"
            "| **PPT만** | (Core 이후) 10장 + 실무 톤 + PPT |\n"
            "| **샘플+PPT** | 미입력 데모 샘플 + 표준 PPT |\n"
        )

    st.divider()
    return clicked
