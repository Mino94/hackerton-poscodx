"""슬라이드 스펙 Pydantic 모델 — LLM·fallback·Composer가 동일 계약을 쓴다."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SlideSpec(BaseModel):
    """한 장의 슬라이드 설계 — visual_type에 따라 content dict 형태가 달라질 수 있다."""

    model_config = ConfigDict(extra="ignore")

    slide_no: int = 0
    title: str = ""
    objective: str = ""
    key_message: str = ""
    layout_type: str = "title_content"
    visual_type: str = "summary_cards"
    content: dict[str, Any] = Field(default_factory=dict)
    # Presentation Graphics Agent 산출 — PPT Composer가 도형/이미지 우선 배치에 사용한다.
    graphics_spec: dict[str, Any] | None = None
    notes: str | None = None


class SlideDeckSpec(BaseModel):
    """전체 덱 — python-pptx Composer의 입력."""

    model_config = ConfigDict(extra="ignore")

    project_title: str = "AutoPM"
    subtitle: str = ""
    slides: list[SlideSpec] = Field(default_factory=list)
