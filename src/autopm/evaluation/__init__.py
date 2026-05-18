"""Evaluation Harness — Agent·PPT 산출 품질을 휴리스틱으로 평가하고 개선 루프에 연결한다."""

# regression_suite는 CrewAI 의존 flow를 끌어오므로 패키지 로드 시점에는 넣지 않는다 — 필요 시 서브모듈에서 import한다.

from autopm.evaluation.harness import CombinedHarnessReport, EvaluationHarness, run_harness_improvement_loop

__all__ = [
    "EvaluationHarness",
    "CombinedHarnessReport",
    "run_harness_improvement_loop",
]
