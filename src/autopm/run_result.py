"""실행 결과 DTO — models(IdeaInput)와 orchestration state 사이 순환 import를 피하기 위해 분리."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from autopm.orchestration.state import AutoPMState


class AutoPMRunResult(BaseModel):
    """Markdown + 구조화 결과 + Supervisor State — UI와 export가 동일 계약을 사용."""

    markdown: str
    structured: dict[str, Any] = Field(default_factory=dict)
    state: AutoPMState
