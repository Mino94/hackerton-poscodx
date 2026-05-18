"""PPT 생성용 사용자 결정 상태 — Interview/AutoPMState와 분리해 Guided 워크플로를 지원한다."""

from autopm.state.decision_enrichment import apply_decisions_to_enriched
from autopm.state.ppt_generation_state import (
    GUIDED_STEP_LABELS,
    PHASE_COMPOSER,
    PHASE_CORE_DOC,
    PHASE_DRAFT_ONLY,
    PHASE_FULL_AUTO,
    PHASE_GRAPHICS,
    PHASE_IMPROVE_CHAIN,
    PHASE_REFINE_DRAFT,
    PHASE_STORYLINE,
    PHASE_VISUALIZATION,
    PPTGenerationState,
    STEP_ORDER,
    StepStatus,
)

__all__ = [
    "PPTGenerationState",
    "StepStatus",
    "STEP_ORDER",
    "GUIDED_STEP_LABELS",
    "apply_decisions_to_enriched",
    "PHASE_DRAFT_ONLY",
    "PHASE_REFINE_DRAFT",
    "PHASE_CORE_DOC",
    "PHASE_STORYLINE",
    "PHASE_VISUALIZATION",
    "PHASE_GRAPHICS",
    "PHASE_COMPOSER",
    "PHASE_FULL_AUTO",
    "PHASE_IMPROVE_CHAIN",
]
