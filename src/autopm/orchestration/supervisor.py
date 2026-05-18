"""Supervisor — State·Phase·Critic Loop·최종 산출 통합을 책임진다(Code-only 역할)."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from autopm.run_result import AutoPMRunResult


class Supervisor:
    """YAML에 없는 오케스트레이션 두뇌 — CrewAI Crew 호출은 Flow에 위임한다."""

    def execute(
        self,
        inputs: dict[str, str],
        *,
        on_progress: Callable[[str], None] | None = None,
        phased: str | None = None,
        autopm_state_json: dict | None = None,
        ppt_gen_json: dict | None = None,
    ) -> "AutoPMRunResult":
        from autopm.orchestration.flow import AutoPMFlow
        from autopm.state.ppt_generation_state import PPTGenerationState

        flow = AutoPMFlow()
        ppt = PPTGenerationState.from_dict(ppt_gen_json) if ppt_gen_json else None
        if phased:
            return flow.run_phased(
                phased,
                inputs,
                autopm_state_json=autopm_state_json,
                ppt_gen=ppt,
                on_progress=on_progress,
            )
        return flow.run(inputs, on_progress=on_progress, ppt_gen=ppt)
