"""AGENTS.md에 적힌 Agent별 Tool 이름을 코드로 맞춰 둔 MVP 훅 — 실제 CrewAI Tool 바인딩 전 단계.

향후 각 함수를 CrewAI @tool / BaseTool로 감싸 Agent.tools에 붙이면 된다.
"""

from __future__ import annotations

from pathlib import Path

from autopm.tools.calculation_engine import estimate_rough_cost, fp_placeholder
from autopm.tools.rag_engine import keyword_search
from autopm.tools.visualization_generator import markdown_gantt_placeholder


def clarify_gen(summary: str, max_questions: int = 5) -> list[str]:
    """요건분석 Agent용 — 짧은 요약에서 확인 질문 bullet을 생성한다."""
    seeds = [
        "데이터 정의(키/컬럼)가 월별로 동일한가?",
        "오류 심각도(블로킹 vs 경고) 기준이 합의됐는가?",
        "보안·반출 정책은?",
        "성공 지표(시간/건수)는 무엇인가?",
        "파일럿 일정과 책임(RACI)은?",
    ]
    return seeds[:max_questions]


def arch_rag(query: str, knowledge_md: Path) -> str:
    """구축방향 Agent용 — 아키텍처 관점 키워드 RAG(키워드 매칭)."""
    return keyword_search(query, knowledge_md)


def tech_reco(constraints: str) -> str:
    """구축방향 Agent용 — 제약을 기술 스택 후보 문장으로 정리(MVP 텍스트)."""
    return (
        f"[tech_reco] 제약 요약: {constraints[:200]}"
        " → 후보: 규칙엔진+스크립트, 경량 RPA, 배치 검증 파이프라인 (실연동 단계적)"
    )


def module_decomp(scope_hint: str) -> list[str]:
    """개발범위 Agent용 — 모듈 후보 목록(MVP 고정 분해)."""
    _ = scope_hint
    return [
        "검증 규칙 정의",
        "데이터 수집/스냅샷",
        "자동 검증 엔진",
        "예외/승인 워크플로",
        "리포트·대시보드",
    ]


def fp_calc(monthly_hours: str, headcount: str) -> str:
    """FP/COCOMO 자리 — 시간·인원 기반 힌트만 반환."""
    return fp_placeholder(None) + " | " + estimate_rough_cost(monthly_hours, headcount, "")


def ui_counter(feature_bullets: str) -> int:
    """화면/기능 개수 휴리스틱 — bullet 줄 수 기반."""
    return max(3, min(40, feature_bullets.count("\n") + 1))


def gantt_gen(title: str, weeks: int = 4) -> str:
    """일정·예산 Agent용 — Mermaid Gantt 문자열."""
    return markdown_gantt_placeholder(title, weeks=weeks)


def cost_calc(monthly_hours: str, headcount: str, budget_cap: str) -> str:
    return estimate_rough_cost(monthly_hours, headcount, budget_cap)


def risk_matcher(domain: str) -> list[str]:
    """리스크 Agent용 — 도메인 키워드별 상위 리스크 힌트."""
    low = domain.lower()
    base = ["데이터 품질", "규칙 불완전", "변경 저항", "보안/권한"]
    if "erp" in low or "월마감" in low:
        base.append("마감 일정 압박")
    return base


def mitigation(risk: str) -> str:
    return f"대응 초안: {risk} → 파일럿·샘플 데이터·롤백 계획(가정)"


def prob_impact(score_hint: str) -> str:
    """가능성/영향 매핑 힌트 — LLM이 표를 채울 때 참고."""
    return f"(힌트) {score_hint} 기준으로 중/고 조합을 우선 검토"
