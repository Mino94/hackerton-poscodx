"""calculation_engine — FP/COCOMO 자리 확보, MVP는 시간·인원·예산 힌트."""

from __future__ import annotations


def estimate_rough_cost(monthly_hours: str, headcount: str, budget_cap: str) -> str:
    """가성비 있는 수치 힌트만 반환 — LLM이 과장하지 않도록 '(가정)' 문구를 붙인다."""
    try:
        h = float(monthly_hours)
        p = float(headcount)
    except ValueError:
        h, p = 0.0, 0.0
    saved = h * 0.35 * p
    return (
        f"(가정) 월 {h}h·{p}명 기준 절감 후보 시간 {saved:.1f}h/월 수준까지 타겟팅 가능 — 상한 {budget_cap}"
    )


def fp_placeholder(function_points: int | None = None) -> str:
    """FP 기반 산정 훅 — MVP에서는 입력이 없으면 설명만 반환한다."""
    if function_points is None:
        return "(MVP) FP 산정 미적용 — 향후 COCOMO/FP 테이블 연동"
    return f"(가정) FP={function_points} 기준 내부 환산치 참고"
