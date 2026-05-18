"""Golden 입력·기대 품질 메타 — 회귀 스위트가 Crew 없이 휴리스틱을 검증한다."""

from __future__ import annotations

# ERP 월마감 시나리오 — 스펙 문서의 기본 데모와 동일한 축을 유지한다.
GOLDEN_ERP_CASE_NAME = "ERP 월마감 데이터 검증 자동화"

GOLDEN_ERP_INPUTS: dict[str, str] = {
    "proposal_title": "ERP 월마감 데이터 검증 자동화",
    "proposal_purpose": "내부 개선안",
    "background_context": "ERP 데이터를 엑셀로 다운로드하여 수작업 검증",
    "current_problems": "시간이 오래 걸리고 담당자별 기준이 달라 오류 누락 가능",
    "target_system": "ERP",
    "business_scope": "월마감 검증",
    "improvement_direction": "검증 자동화",
    "target_audience": "회계팀, IT팀",
    "key_emphasis": "업무 효율화",
    "presentation_tone": "실무 추진계획형",
    "related_departments": "회계팀, 생산관리팀, IT팀",
    "timeline": "4주",
    "budget_range": "500만 원 이하",
    "idea_title": "ERP 월마감 데이터 검증 자동화",
    "current_process": "ERP 데이터를 엑셀로 다운로드하여 수작업 검증",
    "pain_points": "시간이 오래 걸리고 담당자별 기준이 달라 오류 누락 가능",
    "departments": "회계팀, 생산관리팀, IT팀",
    "monthly_hours": "40",
    "headcount": "3",
    "goals": "검증 시간 단축 및 오류 사전 탐지",
    "target_timeline": "4주",
}

# 기대 산출(휴리스틱/파일) — regression_suite에서 assert.
GOLDEN_EXPECTATIONS: dict[str, object] = {
    "min_slides": 10,
    "require_slides_markdown_topics": (
        "AS-IS",
        "TO-BE",
        "WBS",
        "예산",
        "리스크",
        "Critic",
    ),
    "require_pptx": True,
    "interview_must_pass": True,
}
