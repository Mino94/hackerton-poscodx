"""PPTGenerationState — Guided/Auto 모드에서 사용자 결정·단계 진행을 보관한다."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

# Streamlit·Flow가 동일한 문자열로 단계를 맞추기 위한 상태값 — UI progress와 매핑된다.
StepStatus = Literal[
    "pending",
    "active",
    "waiting_user",
    "approved",
    "revised",
    "complete",
    "error",
]

# 사용자 안내 12단계(AGENTS 요구) — current_step·step_statuses 키로 사용한다.
STEP_ORDER: list[str] = [
    "idea_input",
    "interview",
    "confirm_input",
    "draft_generate",
    "draft_approve",
    "slide_plan_generate",
    "slide_plan_approve",
    "visual_style_pick",
    "visual_asset_generate",
    "visual_plan_approve",
    "ppt_generate",
    "post_ppt_review",
]

GUIDED_STEP_LABELS: dict[str, str] = {
    "idea_input": "1) 아이디어 입력",
    "interview": "2) 대화형 정보 수집",
    "confirm_input": "3) 입력 정보 확인",
    "draft_generate": "4) 1차 초안 생성",
    "draft_approve": "5) 초안 승인/수정",
    "slide_plan_generate": "6) 슬라이드 구성 생성",
    "slide_plan_approve": "7) 슬라이드 구성 승인/수정",
    "visual_style_pick": "8) 장표 스타일 선택",
    "visual_asset_generate": "9) Visual Asset Plan 생성",
    "visual_plan_approve": "10) Visual Plan 승인/수정",
    "ppt_generate": "11) PPT 생성",
    "post_ppt_review": "12) 최종 개선 요청 또는 다운로드",
}

# AutoPMFlow.run_phased() 분기 키 — Gateway·Streamlit이 동일 문자열을 사용한다.
PHASE_DRAFT_ONLY = "draft_only"
PHASE_REFINE_DRAFT = "refine_draft"
PHASE_CORE_DOC = "core_doc"
PHASE_STORYLINE = "storyline"
PHASE_VISUALIZATION = "visualization"
PHASE_GRAPHICS = "graphics"
PHASE_COMPOSER = "composer"
PHASE_FULL_AUTO = "full_auto"
PHASE_IMPROVE_CHAIN = "improve_chain"


@dataclass
class PPTGenerationState:
    """PPT 품질을 위해 단계별 사용자 승인·선택을 누적한다 — Crew 프롬프트에 문자열로 합성된다."""

    interview_completed: bool = False
    draft_generated: bool = False
    draft_approved: bool = False
    slide_plan_generated: bool = False
    slide_plan_approved: bool = False
    visual_plan_generated: bool = False
    visual_plan_approved: bool = False
    ppt_generated: bool = False

    current_step: str = "idea_input"
    user_decisions: dict[str, str] = field(default_factory=dict)
    revision_requests: list[str] = field(default_factory=list)
    selected_options: dict[str, str] = field(default_factory=dict)

    # 각 단계별 상태 — UI stepper와 동기화한다.
    step_statuses: dict[str, str] = field(default_factory=dict)

    # Guided에서 초안·슬라이드 JSON 미리보기를 세션에 넣기 위한 스냅샷(선택)
    last_draft_markdown: str = ""
    last_storyline_json: str = ""
    last_visualization_json: str = ""
    last_graphics_json: str = ""

    # Evaluation Harness — PPT·Agent 품질 게이트와 개선 루프 상태를 UI/세션에 보존한다.
    evaluation_score: float = 0.0
    pass_threshold: float = 85.0
    failed_criteria: list[str] = field(default_factory=list)
    feedback_target: str = ""
    improvement_attempts: int = 0
    max_improvement_attempts: int = 3
    final_passed: bool = False

    def __post_init__(self) -> None:
        if not self.step_statuses:
            self.step_statuses = {sid: "pending" for sid in STEP_ORDER}

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> PPTGenerationState:
        if not data:
            return cls()
        st = cls(
            interview_completed=bool(data.get("interview_completed")),
            draft_generated=bool(data.get("draft_generated")),
            draft_approved=bool(data.get("draft_approved")),
            slide_plan_generated=bool(data.get("slide_plan_generated")),
            slide_plan_approved=bool(data.get("slide_plan_approved")),
            visual_plan_generated=bool(data.get("visual_plan_generated")),
            visual_plan_approved=bool(data.get("visual_plan_approved")),
            ppt_generated=bool(data.get("ppt_generated")),
            current_step=str(data.get("current_step") or "idea_input"),
            user_decisions=dict(data.get("user_decisions") or {}),
            revision_requests=list(data.get("revision_requests") or []),
            selected_options=dict(data.get("selected_options") or {}),
            step_statuses=dict(data.get("step_statuses") or {sid: "pending" for sid in STEP_ORDER}),
            last_draft_markdown=str(data.get("last_draft_markdown") or ""),
            last_storyline_json=str(data.get("last_storyline_json") or ""),
            last_visualization_json=str(data.get("last_visualization_json") or ""),
            last_graphics_json=str(data.get("last_graphics_json") or ""),
            evaluation_score=float(data.get("evaluation_score") or 0.0),
            pass_threshold=float(data.get("pass_threshold") or 85.0),
            failed_criteria=list(data.get("failed_criteria") or []),
            feedback_target=str(data.get("feedback_target") or ""),
            improvement_attempts=int(data.get("improvement_attempts") or 0),
            max_improvement_attempts=int(data.get("max_improvement_attempts") or 3),
            final_passed=bool(data.get("final_passed")),
        )
        for sid in STEP_ORDER:
            st.step_statuses.setdefault(sid, "pending")
        return st

    def set_step_status(self, step_id: str, status: str) -> None:
        """특정 단계의 상태만 갱신한다 — Streamlit rerun마다 호출된다."""
        if step_id in self.step_statuses:
            self.step_statuses[step_id] = status
        self.current_step = step_id

    def add_revision(self, text: str) -> None:
        """사용자 자유 수정 요청을 누적한다 — 다음 Agent 프롬프트에 붙인다."""
        t = (text or "").strip()
        if t:
            self.revision_requests.append(t)

    @classmethod
    def for_auto_mode(cls) -> PPTGenerationState:
        """Auto Mode — 승인 단계 없이 기본 선택으로 끝까지 실행할 때 쓰는 프리셋."""
        g = cls(
            interview_completed=True,
            draft_generated=True,
            draft_approved=True,
            slide_plan_generated=True,
            slide_plan_approved=True,
            visual_plan_generated=True,
            visual_plan_approved=True,
            ppt_generated=False,
            current_step="ppt_generate",
        )
        g.selected_options = {
            "input_confirm": "proceed",
            "draft_tone": "proceed",
            "slide_structure": "default_10",
            "visual_style": "execution_plan",
            "visual_asset_plan": "proceed",
            "post_ppt": "finalize",
        }
        g.step_statuses = {sid: "complete" for sid in STEP_ORDER}
        g.step_statuses["ppt_generate"] = "pending"
        g.step_statuses["post_ppt_review"] = "pending"
        return g

    def active_guidance_mode(self) -> bool:
        """Guided에서 사용자 입력을 기다리는지 여부(외부에서 mode 라디오와 함께 쓴다)."""
        return self.step_statuses.get(self.current_step, "pending") in (
            "waiting_user",
            "active",
        )
