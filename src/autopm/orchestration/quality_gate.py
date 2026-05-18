"""Quality Gate — Critic 점수 기준(80점)으로 PASS/FAIL을 판정한다."""

from __future__ import annotations

# 승인/재작성 분기 기준 — AGENTS.md와 동일하게 80점 고정
PASS_THRESHOLD = 80


def evaluate_gate(score: int | None) -> bool:
    """점수가 없거나 임계값 미만이면 실패로 본다 — 보수적으로 데모 안정성을 유지."""
    if score is None:
        return False
    return score >= PASS_THRESHOLD
