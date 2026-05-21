"""Rule-based 인터뷰 질문 정의 — 추진계획서 방향을 먼저 잡고 실행 정보는 후순위로 묻는다."""

from __future__ import annotations

# proposal_title은 첫 입력(시드)에서 채운 뒤, 아래 순서로만 추가 질문한다 — 월시간/인원은 기본 제외.
PRIMARY_FIELD_ORDER: list[str] = [
    "proposal_purpose",
    "background_context",
    "current_problems",
    "target_system",
    "business_scope",
    "improvement_direction",
    "target_audience",
    "key_emphasis",
    "presentation_tone",
    "timeline",
    "budget_range",
    "related_departments",
]

# 레거시 코드 호환 — 동일 순서
FIELD_ORDER: list[str] = list(PRIMARY_FIELD_ORDER)

FIELD_QUESTIONS: dict[str, str] = {
    "proposal_title": (
        "작성할 **추진계획서의 주제나 제목**을 한 줄로 입력해 주세요.\n"
        "예: 포스코 2026년 미래전략을 위한 Mini ERP 시스템 원가시스템 개선 제안 추진계획서"
    ),
    "proposal_purpose": (
        "이 추진계획서는 **어떤 목적**으로 작성하나요? 번호나 문장으로 답해 주세요.\n"
        "1. 경영진 보고용\n"
        "2. 고객 제안용\n"
        "3. 내부 개선안\n"
        "4. 예산 승인용\n"
        "5. 시스템 구축 제안용"
    ),
    "background_context": (
        "이 제안을 하게 된 **배경**은 무엇인가요?\n"
        "예: 2026년 미래전략 대응, 원가시스템 노후화, 수작업 업무 증가, ERP·현업 데이터 불일치, 의사결정 데이터 부족 등"
    ),
    "current_problems": (
        "현재 **가장 큰 문제**는 무엇인가요?\n"
        "예: 원가 산정 기준 불일치, 수작업 검증 과다, 데이터 정합성 부족, 실시간 원가 분석 어려움, 보고서 지연, 시스템 사용성 문제 등"
    ),
    "target_system": (
        "**개선 대상 시스템 또는 핵심 IT 대상**은 무엇인가요?\n"
        "예: Mini ERP, 원가시스템, 구매/재고/생산/회계 연계, BOM·라우팅·단가·수불·결산, 대시보드/리포트"
    ),
    "business_scope": (
        "**개선 대상 업무·기능 범위**는 어디까지인가요?\n"
        "예: 원가 집계, 결산 검증, 단가 관리, 수불·재고, 경영 보고용 리포트 전체"
    ),
    "improvement_direction": (
        "제안하는 **핵심 개선 방향**은 무엇인가요?\n"
        "예: 원가 데이터 표준화, 자동 검증 룰, 실시간 원가 모니터링, 시뮬레이션, AI 기반 오류 탐지, 프로세스 자동화"
    ),
    "target_audience": (
        "**보고 대상·의사결정자**는 누구인가요?\n"
        "예: 경영진, IT부서, 재무/원가팀, 생산관리팀, 고객사 담당자, 프로젝트 승인자"
    ),
    "key_emphasis": (
        "추진계획서에서 **가장 강조하고 싶은 포인트**는 무엇인가요?\n"
        "예: 전략적 필요성, 비용 절감, 업무 효율화, 데이터 신뢰성, 시스템 확장성, 리스크 감소, 미래전략 연계성"
    ),
    "presentation_tone": (
        "원하는 **PPT 톤**을 골라 주세요 (번호 또는 이름).\n"
        "1. 경영진 보고형\n"
        "2. 컨설팅 제안서형\n"
        "3. 실무 추진계획형\n"
        "4. 기술 아키텍처형\n"
        "5. 투자/예산 승인형"
    ),
    "timeline": (
        "**희망 추진 기간**이 있나요? (없으면 '미정'이라고 답해도 됩니다)\n"
        "예: 4주, 2개월, 2026년 상반기 내"
    ),
    "budget_range": (
        "**대략적인 예산 범위**가 있나요? (가정·범위만 적어 주세요)\n"
        "예: 500만 원 이하, 내부 과제·별도 예산 협의"
    ),
    "related_departments": (
        "**관련 부서**는 어디인가요?\n"
        "예: 회계팀, 생산관리팀, IT팀, 원가관리팀"
    ),
    "monthly_hours": (
        "효율·절감을 강조하셨으니, **월간으로 투입되는 업무 시간(대략 시간)**을 알려 주세요.\n"
        "숫자만 적어도 됩니다 (예: 40)."
    ),
    "people_count": (
        "같은 맥락에서 **관련 인원 수(대략 명)**도 알려 주세요.\n"
        "숫자만 적어도 됩니다 (예: 3)."
    ),
}

FIELD_LABELS_KR: dict[str, str] = {
    "proposal_title": "추진계획서 주제/제목",
    "proposal_purpose": "추진계획서 목적",
    "background_context": "제안 배경",
    "current_problems": "핵심 문제",
    "target_system": "대상 시스템·IT",
    "business_scope": "업무·기능 범위",
    "improvement_direction": "핵심 개선 방향",
    "target_audience": "보고 대상·의사결정자",
    "key_emphasis": "강조 포인트",
    "presentation_tone": "PPT 톤",
    "timeline": "희망 추진 기간",
    "budget_range": "예산 범위",
    "related_departments": "관련 부서",
    "monthly_hours": "월 소요 시간(선택)",
    "people_count": "관련 인원(선택)",
    "expected_effects": "기대 효과",
    "constraints": "제약·전제",
    "reference_materials": "참고 자료",
    "idea_title": "과제 제목(레거시)",
    "current_process": "현재 업무(레거시)",
    "pain_points": "문제점(레거시)",
    "goal": "목표(레거시)",
    "inferred_target_company": "제목에서 추출: 조직/회사",
    "inferred_strategy_context": "제목에서 추출: 전략 맥락",
    "inferred_output_type": "제목에서 추출: 산출물 유형",
    "inferred_likely_purpose": "제목에서 추출: 목적 힌트",
    "inferred_proposal_type": "제목에서 추출: 문서 유형",
    "inferred_likely_tone": "제목에서 추출: PPT 톤 힌트",
}

# to_autopm_inputs 시 비어 있을 때 붙이는 안내 — Crew가 멈추지 않게 한다.
ASSUMPTION_SUFFIX = " (AutoPM 가정·추후 확정 필요)"

# AGENTS.md ERP 월마감 데모 — 질문마다 「샘플 넣기」·「전체 채우기」에 사용한다.
DEMO_SCENARIO_SEED = (
    "ERP 월마감 데이터 검증 자동화\n\n"
    "월마감 시 ERP에서 품목 단가, 재고 수량, BOM 누락 여부를 엑셀로 다운로드하여 수작업 검증한다. "
    "검증 시간이 오래 걸리고 담당자별 기준이 달라 오류가 누락될 수 있다."
)

FIELD_DEMO_SAMPLES: dict[str, str] = {
    "proposal_title": "ERP 월마감 데이터 검증 자동화",
    "proposal_purpose": "내부 개선안",
    "background_context": (
        "월마감 시 ERP에서 품목 단가, 재고 수량, BOM 누락 여부를 엑셀로 다운로드하여 수작업 검증한다."
    ),
    "current_problems": "검증 시간이 오래 걸리고 담당자별 기준이 달라 오류가 누락될 수 있다.",
    "target_system": "ERP (품목 단가·재고·BOM)",
    "business_scope": "월마감 데이터 검증·정합성 점검·오류 사전 탐지",
    "improvement_direction": "검증 룰 자동화, 표준 검증 기준 적용, 월마감 검증 시간 단축",
    "target_audience": "회계팀, 생산관리팀, IT팀",
    "key_emphasis": "업무 효율화·검증 시간 절감·데이터 신뢰성",
    "presentation_tone": "실무 추진계획형",
    "timeline": "4주",
    "budget_range": "500만 원 이하",
    "related_departments": "회계팀, 생산관리팀, IT팀",
    "monthly_hours": "40",
    "people_count": "3",
}


def demo_sample_for_field(field: str | None) -> str:
    """현재 질문 필드에 맞는 데모 샘플 문자열 — 없으면 빈 문자열."""
    if not field:
        return ""
    return FIELD_DEMO_SAMPLES.get(field, FIELD_SKIP_DEFAULTS.get(field, ""))


# UI 빠른 선택 버튼 — 번호 대신 라벨을 그대로 답변으로 저장한다.
FIELD_QUICK_CHOICES: dict[str, list[str]] = {
    "proposal_purpose": [
        "경영진 보고용",
        "고객 제안용",
        "내부 개선안",
        "예산 승인용",
        "시스템 구축 제안용",
    ],
    "presentation_tone": [
        "경영진 보고형",
        "컨설팅 제안서형",
        "실무 추진계획형",
        "기술 아키텍처형",
        "투자/예산 승인형",
    ],
    "background_context": [
        "월마감 ERP 데이터를 엑셀로 받아 수작업 검증",
        "원가·재고 데이터 정합성 이슈로 보고 지연",
        "전략 과제 대응을 위한 시스템·프로세스 개선",
    ],
    "current_problems": [
        "검증 시간 과다·담당자별 기준 상이",
        "오류 누락·재작업 발생",
        "실시간 모니터링·표준 룰 부재",
    ],
    "target_system": [
        "ERP (원가·재고·BOM)",
        "Mini ERP / 원가시스템",
        "엑셀·ERP 연계 검증 도구",
    ],
    "business_scope": [
        "월마감 검증 전 구간",
        "단가·재고·BOM 검증",
        "경영 보고용 리포트까지",
    ],
    "improvement_direction": [
        "검증 자동화·룰 엔진",
        "데이터 표준화·실시간 모니터링",
        "AI 기반 이상 탐지(가정)",
    ],
    "target_audience": [
        "경영진·재무/원가팀",
        "IT·현업(회계·생산)",
        "고객사·프로젝트 승인자",
    ],
    "key_emphasis": [
        "업무 효율화·시간 절감",
        "비용 절감·ROI",
        "데이터 신뢰성·리스크 감소",
    ],
    "timeline": ["4주", "2개월", "2026년 상반기"],
    "budget_range": ["500만 원 이하", "1천만 원 내", "내부 과제·별도 협의"],
    "related_departments": [
        "회계팀, 생산관리팀, IT팀",
        "재무·원가·IT",
        "현업·PMO·IT",
    ],
    "monthly_hours": ["40", "80", "120"],
    "people_count": ["2", "3", "5"],
}

# 건너뛰기 시 채울 기본값
FIELD_SKIP_DEFAULTS: dict[str, str] = {
    "timeline": "미정 (추후 협의)",
    "budget_range": "내부 협의 범위 (가정)",
    "related_departments": "관련 부서 협의 예정",
    "monthly_hours": "40",
    "people_count": "3",
    "expected_effects": "업무 시간 절감·오류 감소 (가정)",
}

PURPOSE_BY_NUM: dict[str, str] = {
    "1": "경영진 보고용",
    "2": "고객 제안용",
    "3": "내부 개선안",
    "4": "예산 승인용",
    "5": "시스템 구축 제안용",
}

TONE_BY_NUM: dict[str, str] = {
    "1": "경영진 보고형",
    "2": "컨설팅 제안서형",
    "3": "실무 추진계획형",
    "4": "기술 아키텍처형",
    "5": "투자/예산 승인형",
}


def normalize_field_answer(field: str, answer: str) -> str:
    """번호만 입력해도 선택지 문구로 변환한다."""
    a = (answer or "").strip()
    if not a:
        return a
    if field == "proposal_purpose" and a in PURPOSE_BY_NUM:
        return PURPOSE_BY_NUM[a]
    if field == "presentation_tone" and a in TONE_BY_NUM:
        return TONE_BY_NUM[a]
    return a
