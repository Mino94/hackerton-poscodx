"""추천 추진계획 방향 — 한 번 클릭으로 인터뷰 필드 채움 + 자동 생성 트리거."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from autopm.chat.interview_state import InterviewState
from autopm.chat.question_rules import FIELD_DEMO_SAMPLES


@dataclass(frozen=True)
class DirectionPreset:
    """UI 카드 + InterviewState 일괄 반영."""

    id: str
    label: str
    icon: str
    tagline: str
    highlights: tuple[str, ...]
    fields: dict[str, Any]
    bulk_preset: str = "to_ppt"  # Guided 시 guided_bulk 프리셋 ID


# ERP 데모를 베이스로 변형한 6가지 추천 방향
_ERP_BASE = dict(FIELD_DEMO_SAMPLES)

DIRECTION_PRESETS: tuple[DirectionPreset, ...] = (
    DirectionPreset(
        id="erp_validation",
        label="ERP 월마감 검증 자동화",
        icon="📊",
        tagline="수작업 검증·기준 불일치 → 룰 자동화·시간 절감",
        highlights=("월마감 ERP 검증", "4주·500만 원 이하", "실무 추진계획 톤"),
        fields=_ERP_BASE,
    ),
    DirectionPreset(
        id="cost_system",
        label="원가시스템·Mini ERP 개선",
        icon="🏭",
        tagline="원가 산정·데이터 정합성·경영 보고 연계",
        highlights=(
            "원가·BOM·단가 표준화",
            "경영진 보고형 PPT",
            "2개월·예산 협의",
        ),
        fields={
            **_ERP_BASE,
            "proposal_title": "Mini ERP 원가시스템 개선 추진계획서",
            "proposal_purpose": "경영진 보고용",
            "background_context": (
                "원가 산정 기준이 부서별로 달라 보고 신뢰도가 낮고, "
                "ERP·엑셀 병행으로 결산·원가 분석 리드타임이 길다."
            ),
            "current_problems": (
                "원가 데이터 불일치, 수작업 집계, 실시간 원가 분석·시뮬레이션 부재"
            ),
            "target_system": "Mini ERP · 원가시스템 · BOM/단가/수불",
            "business_scope": "원가 집계, 결산 검증, 단가·BOM 관리, 경영 리포트",
            "improvement_direction": "원가 데이터 표준화, 자동 검증 룰, 실시간 원가 모니터링",
            "target_audience": "경영진, 재무/원가팀, IT팀",
            "key_emphasis": "전략적 필요성·데이터 신뢰성·비용 절감",
            "presentation_tone": "경영진 보고형",
            "timeline": "2개월",
            "budget_range": "별도 예산 협의(가정)",
        },
    ),
    DirectionPreset(
        id="ai_quality",
        label="AI·룰 기반 품질 검증",
        icon="🤖",
        tagline="오류 사전 탐지·담당자 편차 제거·대시보드",
        highlights=("AI/룰 엔진", "기술 아키텍처 톤", "6주·중규모 예산"),
        fields={
            **_ERP_BASE,
            "proposal_title": "ERP 데이터 AI 품질 검증·오류 탐지 추진계획",
            "proposal_purpose": "시스템 구축 제안용",
            "improvement_direction": (
                "검증 룰 엔진 + 이상치 AI 탐지, 검증 결과 대시보드, 알림·워크플로"
            ),
            "key_emphasis": "오류 사전 탐지·자동화·확장성",
            "presentation_tone": "기술 아키텍처형",
            "timeline": "6주",
            "budget_range": "1,000만 원 이하(가정)",
        },
    ),
    DirectionPreset(
        id="process_rpa",
        label="프로세스 자동화·RPA",
        icon="⚙️",
        tagline="반복 업무 제거·표준 프로세스·현업 합의",
        highlights=("RPA·배치 검증", "컨설팅 제안서 톤", "4주·500만 원"),
        fields={
            **_ERP_BASE,
            "proposal_title": "월마감 검증 프로세스 자동화(RPA) 추진계획",
            "proposal_purpose": "고객 제안용",
            "improvement_direction": "엑셀 다운로드·검증·승인 워크플로 자동화, 표준 SOP 정립",
            "presentation_tone": "컨설팅 제안서형",
        },
    ),
    DirectionPreset(
        id="budget_approval",
        label="예산·투자 승인용",
        icon="💰",
        tagline="ROI·절감 효과·리스크·단계 투자",
        highlights=("ROI·KPI 강조", "투자/예산 승인 톤", "3개월·단계 예산"),
        fields={
            **_ERP_BASE,
            "proposal_title": "ERP 검증 자동화 투자 승인 추진계획서",
            "proposal_purpose": "예산 승인용",
            "key_emphasis": "비용 절감·ROI·리스크 감소·단계적 투자",
            "presentation_tone": "투자/예산 승인형",
            "timeline": "3개월(1단계 4주)",
            "budget_range": "500만 원(1단계) + 확장 협의(가정)",
        },
    ),
    DirectionPreset(
        id="exec_strategy",
        label="전략 과제·경영 보고",
        icon="🎯",
        tagline="미래전략 연계·의사결정 지원·거버넌스",
        highlights=("전략 KPI", "경영 보고", "분기 로드맵"),
        fields={
            **_ERP_BASE,
            "proposal_title": "2026 전략 과제 — 운영 데이터·ERP 거버넌스 강화",
            "proposal_purpose": "경영진 보고용",
            "background_context": "미래전략 실행을 위해 운영·재무 데이터 신뢰성과 보고 속도를 높여야 한다.",
            "key_emphasis": "전략 연계성·의사결정 속도·거버넌스",
            "presentation_tone": "경영진 보고형",
            "timeline": "2026년 상반기",
            "budget_range": "전략 과제 예산 내(가정)",
        },
    ),
)

_PRESET_BY_ID: dict[str, DirectionPreset] = {p.id: p for p in DIRECTION_PRESETS}


def get_direction_preset(preset_id: str) -> DirectionPreset | None:
    return _PRESET_BY_ID.get(preset_id)


def apply_direction_preset(
    preset_id: str,
    *,
    preset: DirectionPreset | None = None,
) -> InterviewState:
    """선택 방향으로 인터뷰 필드를 모두 채우고 완료 처리한다."""
    p = preset or _PRESET_BY_ID.get(preset_id)
    if p is None:
        raise ValueError(f"unknown direction preset: {preset_id}")

    state = InterviewState()
    f = p.fields

    state.proposal_title = str(f.get("proposal_title", ""))
    state.idea_title = state.proposal_title
    state.proposal_purpose = f.get("proposal_purpose")
    state.background_context = f.get("background_context")
    state.current_problems = f.get("current_problems")
    state.pain_points = state.current_problems
    state.target_system = f.get("target_system")
    state.business_scope = f.get("business_scope")
    state.improvement_direction = f.get("improvement_direction")
    state.goal = state.improvement_direction
    state.current_process = state.background_context
    state.target_audience = f.get("target_audience")
    state.key_emphasis = f.get("key_emphasis")
    state.presentation_tone = f.get("presentation_tone")
    state.timeline = f.get("timeline")
    state.budget_range = f.get("budget_range")
    state.related_departments = f.get("related_departments")

    mh = f.get("monthly_hours")
    if mh is not None:
        try:
            state.monthly_hours = int(str(mh).replace("시간", "").strip())
        except ValueError:
            state.monthly_hours = None
    pc = f.get("people_count")
    if pc is not None:
        try:
            state.people_count = int(str(pc).strip())
        except ValueError:
            state.people_count = None

    state._sync_title_aliases()
    state.completed = True
    state.chat_history = [
        {"role": "user", "content": f"[추천 방향 선택] {p.label}"},
        {
            "role": "assistant",
            "content": (
                f"**{p.icon} {p.label}** 방향으로 추진계획 맥락을 반영했습니다.\n"
                f"{p.tagline}\n\n"
                "이제 **PPT·문서 자동 생성**을 시작합니다. 진행 상황은 **수집·진행** 탭에서 확인하세요."
            ),
        },
    ]
    return state


__all__ = [
    "DirectionPreset",
    "DIRECTION_PRESETS",
    "apply_direction_preset",
    "get_direction_preset",
]
