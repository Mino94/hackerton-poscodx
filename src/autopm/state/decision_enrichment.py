"""사용자 결정(PPTGenerationState)을 CrewAI Task placeholder 문자열로 변환한다."""

from __future__ import annotations

from autopm.state.ppt_generation_state import PPTGenerationState

# 스펙의 Decision Point별 키 — Streamlit 버튼과 동일한 값을 저장한다.
DP_INPUT = "input_confirm"
DP_DRAFT = "draft_tone"
DP_SLIDES = "slide_structure"
DP_STYLE = "visual_style"
DP_VAP = "visual_asset_plan"
DP_POST = "post_ppt"


def _revision_block(ppt: PPTGenerationState) -> str:
    if not ppt.revision_requests:
        return ""
    lines = "\n".join(f"- {r}" for r in ppt.revision_requests[-12:])
    return f"\n[사용자 수정 요청 누적]\n{lines}\n"


def _slide_instruction(ppt: PPTGenerationState) -> str:
    choice = ppt.selected_options.get(DP_SLIDES, "default_10")
    custom = ppt.user_decisions.get("slide_custom_notes", "")
    m = {
        "default_10": "정확히 **10장** 슬라이드. Executive→문제→AS-IS→TO-BE→범위→WBS→예산/ROI→리스크→KPI→결론 흐름.",
        "compact_6": "**6장** 요약형: Executive, 문제+AS-IS, TO-BE+범위, 일정/WBS, 예산·ROI+리스크, 결론.",
        "detailed_12": "**12장** 상세형: 각 주제를 분리해 깊게. 가능하면 마일스톤·RACI 슬라이드 포함.",
        "custom_add_remove": "사용자 지정: 슬라이드를 추가·삭제·병합. ",
        "reorder": "슬라이드 순서를 경영진 보고에 맞게 재배치. ",
    }
    base = m.get(choice, m["default_10"])
    if choice in ("custom_add_remove", "reorder") and custom:
        base += custom
    elif choice in ("custom_add_remove", "reorder"):
        base += "구체 요청은 user_decisions.slide_custom_notes 참고."
    return base + _revision_block(ppt)


def _style_instruction(ppt: PPTGenerationState) -> str:
    choice = ppt.selected_options.get(DP_STYLE, "execution_plan")
    return {
        "executive": "경영진 보고형: 큰 숫자·리스크·결론 강조, 말풍선 최소, summary_cards·kpi_cards·risk_matrix 우선.",
        "consulting": "컨설팅 제안서형: 프레임·before_after·scope_matrix, 톤은 논리·옵션 제시.",
        "execution_plan": "실무 추진계획형: WBS·일정·역할 중심, gantt_like_timeline·wbs_table 활용.",
        "architecture": "기술 아키텍처형: architecture_block_diagram·process_flow, 시스템 경계 명확히.",
        "minimal": "미니멀 요약형: bullet 최소, summary_cards·conclusion_box 위주, 장식 요소 절제.",
    }.get(
        choice,
        "실무 추진계획형 기본: 일정·역할·산출물이 드러나게.",
    ) + _revision_block(ppt)


def _visual_asset_instruction(ppt: PPTGenerationState) -> str:
    choice = ppt.selected_options.get(DP_VAP, "proceed")
    custom = ppt.user_decisions.get("visual_slide_edit", "")
    m = {
        "proceed": "현재 스토리라인·시각화 JSON을 존중하고 graphics_spec을 일관되게 채운다.",
        "more_graphics": "도형·다이어그램·아이콘형 요소를 **늘려** 슬라이드가 텍스트 치우치지 않게.",
        "table_focus": "표(budget_table·comparison_table·wbs_table) 비중을 높이고 차트는 보조.",
        "process_focus": "AS/IS·TO-BE·업무 흐름 슬라이드에 process_flow·swimlane_process를 **우선**.",
        "per_slide_edit": "슬라이드별 시각 수정: ",
    }
    base = m.get(choice, m["proceed"])
    if choice == "per_slide_edit":
        base += custom or "user_decisions.visual_slide_edit 참고."
    return base + _revision_block(ppt)


def _budget_risk_emphasis(ppt: PPTGenerationState) -> str:
    post = ppt.selected_options.get(DP_POST, "")
    extra = ""
    if post == "risk_roi_slides" or "risk" in " ".join(ppt.revision_requests).lower():
        extra += "예산·ROI 표는 **정량 근거·민감도**(가정 명시)를 두껍게. "
    if post == "risk_roi_slides" or "roi" in " ".join(ppt.revision_requests).lower():
        extra += "ROI·절감 시나리오를 표로 명확히. "
    if post == "exec_summary" or "경영" in " ".join(ppt.revision_requests):
        extra += "Executive 관점 KPI·의사결정 요청사항을 리스크 대응과 연결. "
    if not extra:
        extra = "(기본) 과장 없이 (가정) 표기 유지."
    return extra + _revision_block(ppt)


def _user_decision_summary(ppt: PPTGenerationState) -> str:
    lines = [
        f"[입력 확인] {ppt.selected_options.get(DP_INPUT, '')}",
        f"[초안 톤] {ppt.selected_options.get(DP_DRAFT, '')}",
        f"[슬라이드 구성] {ppt.selected_options.get(DP_SLIDES, '')}",
        f"[장표 스타일] {ppt.selected_options.get(DP_STYLE, '')}",
        f"[Visual Plan] {ppt.selected_options.get(DP_VAP, '')}",
        f"[사후 개선] {ppt.selected_options.get(DP_POST, '')}",
    ]
    return "\n".join(lines) + _revision_block(ppt)


def _composer_notes(ppt: PPTGenerationState) -> str:
    return (
        "최종 SlideDeckSpec은 사용자 선택을 반영해 slide 수·visual_type 일관성을 유지하라. "
        + _revision_block(ppt)
    )


def apply_decisions_to_enriched(
    enriched: dict[str, str],
    ppt: PPTGenerationState | dict | None,
) -> dict[str, str]:
    """tasks.yaml placeholder와 키를 맞춘다 — 키가 없어도 format()이 되도록 기본값을 채운다."""
    if ppt is None:
        p = PPTGenerationState()
    elif isinstance(ppt, dict):
        p = PPTGenerationState.from_dict(ppt)
    else:
        p = ppt

    payload: dict[str, str] = {
        "user_decision_context": _user_decision_summary(p),
        "slide_deck_instruction": _slide_instruction(p),
        "visual_style_instruction": _style_instruction(p),
        "visual_asset_instruction": _visual_asset_instruction(p),
        "budget_risk_emphasis": _budget_risk_emphasis(p),
        "composer_user_notes": _composer_notes(p),
        "ppt_revision_notes": _revision_block(p).strip(),
    }
    return {**enriched, **payload}
