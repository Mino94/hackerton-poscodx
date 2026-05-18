"""CrewAI 실행 진입점 — L3 Orchestration으로 위임한다(기존 import 경로 유지)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from autopm.api.gateway import run_generation_job
from autopm.run_result import AutoPMRunResult


def run_autopm(
    inputs: dict[str, str],
    *,
    on_progress: Callable[[str], None] | None = None,
    ppt_gen_json: dict[str, Any] | None = None,
) -> AutoPMRunResult:
    """외부(Streamlit)가 호출하는 단일 함수 — 구버전 str 반환은 중단되고 RunResult로 통일된다."""
    return run_generation_job(inputs, on_progress=on_progress, ppt_gen_json=ppt_gen_json)


def run_autopm_phased(
    phase: str,
    inputs: dict[str, str],
    autopm_state_json: dict[str, Any] | None,
    ppt_gen_json: dict[str, Any] | None,
    *,
    on_progress: Callable[[str], None] | None = None,
) -> AutoPMRunResult:
    """Guided Mode 단계별 실행 — phased 키는 ppt_generation_state.PHASE_* 와 일치해야 한다."""
    return run_generation_job(
        inputs,
        on_progress=on_progress,
        phased=phase,
        autopm_state_json=autopm_state_json,
        ppt_gen_json=ppt_gen_json,
    )
