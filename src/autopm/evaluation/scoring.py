"""checklist 통과 여부를 100점 만점으로 환산한다 — 기준 미달 항목은 감점 가중."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CriterionScore:
    """단일 기준 결과 — harness 리포트에 직렬화한다."""

    criterion_id: str
    passed: bool
    weight: float
    note: str = ""


@dataclass
class AgentScoreResult:
    agent_id: str
    display_name: str
    threshold: float
    score: float
    passed: bool
    criteria: list[CriterionScore] = field(default_factory=list)
    failed_ids: list[str] = field(default_factory=list)


def score_from_criteria(results: list[CriterionScore], threshold: float) -> AgentScoreResult:
    """동일 가중 평균으로 점수를 계산하고 threshold 대비 pass/fail을 정한다."""
    if not results:
        return AgentScoreResult("unknown", "Unknown", threshold, 0.0, False, [], [])
    total_w = sum(r.weight for r in results)
    if total_w <= 0:
        earned = 0.0
    else:
        earned = sum(r.weight for r in results if r.passed) / total_w * 100.0
    failed = [r.criterion_id for r in results if not r.passed]
    return AgentScoreResult(
        agent_id="",
        display_name="",
        threshold=threshold,
        score=round(earned, 2),
        passed=earned >= threshold - 1e-6,
        criteria=results,
        failed_ids=failed,
    )


def merge_agent_results(agent_id: str, display: str, threshold: float, r: AgentScoreResult) -> AgentScoreResult:
    """점수 블록에 agent 메타를 채운다."""
    return AgentScoreResult(
        agent_id=agent_id,
        display_name=display,
        threshold=threshold,
        score=r.score,
        passed=r.passed,
        criteria=r.criteria,
        failed_ids=r.failed_ids,
    )
