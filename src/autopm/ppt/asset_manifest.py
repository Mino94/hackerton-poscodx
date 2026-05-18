"""visual_assets.json 스키마 — 슬라이드·자산·render_mode 요약."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AssetRef(BaseModel):
    """단일 자산 참조 — Streamlit Visual Asset Plan 탭에 표시."""

    asset_id: str = ""
    asset_type: str = ""  # chart | diagram | table | image
    render_mode: str = ""  # ppt_shapes | matplotlib_png | fallback
    path: str = ""  # 프로젝트 기준 상대 경로 권장
    visual_type: str = ""
    notes: str = ""


class SlideVisualEntry(BaseModel):
    slide_no: int = 0
    title: str = ""
    visual_type: str = ""
    render_mode: str = ""
    graphics_spec_summary: str = ""
    assets: list[AssetRef] = Field(default_factory=list)


class VisualAssetsManifest(BaseModel):
    project_title: str = ""
    slides: list[SlideVisualEntry] = Field(default_factory=list)

    def to_json_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
