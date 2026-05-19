"""AutoPMState — Supervisor가 들고 다니는 단일 진실 원천(SSOT) 역할을 한다."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AutoPMState(BaseModel):
    """워크플로 전 구간에서 갱신되는 상태 — Critic 루프/재실행 추적에 필요하다."""

    model_config = {"extra": "allow"}

    user_input: dict[str, str] = Field(default_factory=dict)
    parsed_input: str = ""

    orchestration_brief: str = ""
    requirement_analysis: str = ""
    business_analysis: str = ""
    solution_direction: str = ""
    development_scope: str = ""
    wbs_plan: str = ""
    budget_roi: str = ""
    risk_management: str = ""
    critic_review: str = ""
    document_output: str = ""
    # 문서화 Crew 출력(§12 슬라이드 표 부록 이전) — Guided 단계에서 PPT 체인만 재실행할 때 사용한다.
    workspace_markdown: str = ""

    slide_storyline_raw: str = ""
    visualization_raw: str = ""
    presentation_graphics_raw: str = ""
    ppt_composer_raw: str = ""

    # Deep Agents 파이프라인 — 태스크별 원문·Agent 간 대화 로그(UI·재실행용)
    agent_outputs: dict[str, str] = Field(default_factory=dict)
    # Parent Agent별 Sub-Agent 실행 기록 — task_key → [{subagent_id, role, provider, output}]
    subagent_outputs: dict[str, list[dict[str, str]]] = Field(default_factory=dict)
    agent_dialogue: list[dict[str, str]] = Field(default_factory=list)

    # Supervisor PM — 전 Agent 진행·산출·체크포인트 (supervisor_manager.py)
    supervisor: dict[str, Any] = Field(default_factory=dict)

    current_phase: str = "init"
    loop_count: int = 0
    max_loops: int = 3
    pass_quality_gate: bool = False

    critic_score: int | None = None
    critic_status: str = ""
    feedback_target: str = ""
    feedback_text: str = ""
    improvement_applied: list[str] = Field(default_factory=list)
    final_recommendation: str = ""

    # Harness가 파이프라인 중간 결과를 들고 최종 PPT 직전까지 이어 붙인다 — Pydantic 스키마에 두어 체크포인트에 포함된다.
    evaluation_harness_snapshot: dict[str, Any] = Field(default_factory=dict)

    logs: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    artifacts: dict[str, str] = Field(default_factory=dict)
    timings_ms: dict[str, float] = Field(default_factory=dict)

    def snapshot_for_critic(self) -> str:
        """Critic Agent에게 넘기는 요약 스냅샷 — 실패 시에도 일관된 입력을 만든다."""
        parts = [
            f"### orchestration_brief\n{self.orchestration_brief or '(비어 있음)'}",
            f"### requirement_analysis\n{self.requirement_analysis or '(비어 있음)'}",
            f"### business_analysis\n{self.business_analysis or '(비어 있음)'}",
            f"### solution_direction\n{self.solution_direction or '(비어 있음)'}",
            f"### development_scope\n{self.development_scope or '(비어 있음)'}",
            f"### wbs_plan\n{self.wbs_plan or '(비어 있음)'}",
            f"### budget_roi\n{self.budget_roi or '(비어 있음)'}",
            f"### risk_management\n{self.risk_management or '(비어 있음)'}",
        ]
        return "\n\n".join(parts)

    def structured_loop_summary(self) -> dict[str, Any]:
        """UI/JSON에 넣기 쉬운 Self-Correction 요약 — 발표·로그용."""
        return {
            "critic_score": self.critic_score,
            "critic_status": self.critic_status,
            "pass_quality_gate": self.pass_quality_gate,
            "loop_count": self.loop_count,
            "max_loops": self.max_loops,
            "feedback_target": self.feedback_target,
            "improvement_applied": list(self.improvement_applied),
            "final_recommendation": self.final_recommendation,
        }
