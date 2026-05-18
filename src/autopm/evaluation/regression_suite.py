"""간이 회귀 실행기 — pytest 없이 `python -m autopm.evaluation.regression_suite` 형태로 돌릴 수 있다."""

from __future__ import annotations

import json
import re
from pathlib import Path

from autopm.evaluation.harness import EvaluationHarness
from autopm.evaluation.test_cases import (
    GOLDEN_ERP_CASE_NAME,
    GOLDEN_ERP_INPUTS,
    GOLDEN_EXPECTATIONS,
)
from autopm.orchestration.state import AutoPMState


def run_regression_suite() -> dict:
    """
    Golden ERP 입력으로 Fallback Markdown·면접 휴리스틱을 검증한다.
    네트워크/Crew가 없어도 동작해야 해커톤 CI에서 안전하다.
    """
    # CrewAI가 설치된 환경에서만 Flow를 불러 폴백 Markdown과 동일한 품질 축을 재현한다.
    from autopm.orchestration.flow import AutoPMFlow

    flow = AutoPMFlow()
    state = AutoPMState(user_input=dict(GOLDEN_ERP_INPUTS))
    md = flow._fallback_markdown(state, reason="regression_fixture")
    topics = GOLDEN_EXPECTATIONS["require_slides_markdown_topics"]
    assert isinstance(topics, tuple)
    missing_topics = [t for t in topics if t not in md]
    h = EvaluationHarness()
    iv = h.evaluate_interview(dict(GOLDEN_ERP_INPUTS))
    draft = h.evaluate_draft(md)
    slide_hits = len(re.findall(r"^##\s+", md, re.MULTILINE))
    outp = {
        "case": GOLDEN_ERP_CASE_NAME,
        "interview_passed": iv.passed,
        "draft_passed": draft.passed,
        "markdown_topics_ok": len(missing_topics) == 0,
        "missing_topics": missing_topics,
        "heading_count": slide_hits,
    }
    outp["passed"] = (
        bool(outp["interview_passed"])
        and bool(outp["draft_passed"])
        and outp["markdown_topics_ok"]
        and slide_hits >= 8
    )
    if GOLDEN_EXPECTATIONS.get("require_pptx"):
        root = Path(__file__).resolve().parents[3]
        ppt = root / "outputs" / "project_plan.pptx"
        outp["pptx_exists_after_full_run_note"] = (
            "전체 Crew 실행 후 생성됨 — 이 스위트는 Markdown golden만 검증"
        )
        _ = ppt  # 경로만 문서화용 참조
    return outp


def main() -> None:
    r = run_regression_suite()
    print(json.dumps(r, ensure_ascii=False, indent=2))
    if not r.get("passed"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
