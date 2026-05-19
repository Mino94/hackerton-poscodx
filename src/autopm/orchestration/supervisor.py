"""Supervisor — 전 Agent 진행·산출·체크포인트를 관리하는 PM Orchestrator 계층."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from autopm.run_result import AutoPMRunResult


class Supervisor:
    """
    AutoPM Supervisor PM.
    - 실행 전: 전 Agent 레지스트리 등록 (supervisor_manager.init_supervisor)
    - 실행 중: 단계별 start/complete·대화·체크포인트 (deep_pipeline 연동)
    - 실행 후: supervisor_report.json · UI 대시보드
    Flow 호출은 이 클래스를 통해서만 진입한다.
    """

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
