"""Presentation Graphics 파이프라인 — LLM 산출 병합 + 결정론적 보강 + 자산 기록."""

from __future__ import annotations

import json
import traceback
from pathlib import Path
from typing import Any

from autopm.ppt.asset_manifest import AssetRef, SlideVisualEntry, VisualAssetsManifest
from autopm.ppt.asset_store import asset_path_for_slide, ensure_assets_dir
from autopm.ppt.deck_json import extract_json_object
from autopm.ppt.slide_schema import SlideDeckSpec, SlideSpec
from autopm.ppt.visual_registry import (
    default_graphics_spec_for_slide,
    normalize_visual_type,
    try_render_asset_png,
)

_KIND_FOR_VT: dict[str, str] = {
    "process_flow": "process_flow",
    "budget_table": "budget_chart",
    "kpi_cards": "kpi_chart",
    "architecture_block_diagram": "architecture",
    "swimlane_process": "swimlane",
    "risk_matrix": "risk_matrix",
}


def merge_graphics_json_into_deck(deck: SlideDeckSpec, graphics_obj: dict[str, Any]) -> SlideDeckSpec:
    """LLM presentation_graphics JSON의 slides[*].graphics_spec을 슬라이드에 병합한다."""
    slides_in = graphics_obj.get("slides") if isinstance(graphics_obj.get("slides"), list) else []
    by_no: dict[int, dict[str, Any]] = {}
    for item in slides_in:
        if isinstance(item, dict) and "slide_no" in item:
            by_no[int(item["slide_no"])] = item
    new_slides: list[SlideSpec] = []
    for s in deck.slides:
        d = s.model_dump()
        ex = by_no.get(s.slide_no)
        if ex and isinstance(ex.get("graphics_spec"), dict):
            d["graphics_spec"] = ex["graphics_spec"]
        if ex and ex.get("visual_type"):
            d["visual_type"] = str(ex["visual_type"])
        if ex and isinstance(ex.get("content"), dict) and ex["content"]:
            # LLM이 그래픽 단계에서 content 미세조정을 준 경우만 덮어쓴다.
            merged = dict(d.get("content") or {})
            merged.update(ex["content"])
            d["content"] = merged
        new_slides.append(SlideSpec.model_validate(d))
    return SlideDeckSpec(project_title=deck.project_title, subtitle=deck.subtitle, slides=new_slides)


def overlay_storyline_visual_on_deck(deck: SlideDeckSpec, storyline: dict[str, Any], visualization: dict[str, Any]) -> SlideDeckSpec:
    """Composer가 얇은 슬라이드를 줄 때 story+vis 병합본으로 content/visual을 보강한다."""
    from autopm.ppt.deck_json import merge_storyline_and_visual

    if not storyline.get("slides"):
        return deck
    try:
        ref = merge_storyline_and_visual(storyline, visualization if isinstance(visualization, dict) else {})
    except Exception:
        return deck
    ref_by = {x.slide_no: x for x in ref.slides}
    out: list[SlideSpec] = []
    for s in deck.slides:
        d = s.model_dump()
        r = ref_by.get(s.slide_no)
        if r:
            if not d.get("content"):
                d["content"] = r.content
            vt_cur = d.get("visual_type")
            vt_str = vt_cur if isinstance(vt_cur, str) else str(vt_cur or "")
            if not vt_str.strip():
                d["visual_type"] = r.visual_type
            km_cur = d.get("key_message")
            km_str = km_cur if isinstance(km_cur, str) else str(km_cur or "")
            if not km_str.strip():
                d["key_message"] = r.key_message or ""
        out.append(SlideSpec.model_validate(d))
    return SlideDeckSpec(project_title=deck.project_title, subtitle=deck.subtitle, slides=out)


def enrich_graphics_pipeline(deck: SlideDeckSpec, project_root: Path) -> tuple[SlideDeckSpec, VisualAssetsManifest]:
    """
    graphics_spec 기본값 보장 + 선택적 PNG + manifest — 내부 예외는 삼키고 원본 deck을 가능한 보존한다.
    """
    manifest = VisualAssetsManifest(project_title=deck.project_title)
    assets_dir = ensure_assets_dir(project_root)
    new_slides: list[SlideSpec] = []

    for slide in deck.slides:
        try:
            d = slide.model_dump()
            vt = normalize_visual_type(str(d.get("visual_type", "")))
            d["visual_type"] = vt
            gs = d.get("graphics_spec")
            if not isinstance(gs, dict) or not gs:
                gs = default_graphics_spec_for_slide(SlideSpec.model_validate(d))
            d["graphics_spec"] = gs

            slide_obj = SlideSpec.model_validate(d)
            rel: str | None = None
            mode_used = str(gs.get("render_mode") or "ppt_shapes")
            kind = _KIND_FOR_VT.get(vt, vt.replace(" ", "_")[:24])
            png_path = asset_path_for_slide(assets_dir, slide_obj.slide_no, "png", kind)
            rpath, mode_hint = try_render_asset_png(slide_obj.slide_no, slide_obj, png_path)
            if rpath:
                gs = dict(slide_obj.graphics_spec or {})
                gs["image_path"] = rpath
                gs["render_mode"] = mode_hint
                slide_obj = SlideSpec.model_validate({**slide_obj.model_dump(), "graphics_spec": gs})
                rel = rpath
                mode_used = mode_hint

            assets_list: list[AssetRef] = []
            if rel:
                assets_list.append(
                    AssetRef(
                        asset_id=f"{kind}_{slide_obj.slide_no}",
                        asset_type="image",
                        render_mode=mode_used,
                        path=rel,
                        visual_type=vt,
                        notes="PNG 렌더",
                    )
                )
            else:
                assets_list.append(
                    AssetRef(
                        asset_id=f"ppt_shapes_{slide_obj.slide_no}",
                        asset_type=gs.get("asset_type", "diagram") or "diagram",
                        render_mode=mode_used,
                        path="",
                        visual_type=vt,
                        notes="python-pptx 도형",
                    )
                )

            summary = json.dumps(slide_obj.graphics_spec or {}, ensure_ascii=False)[:220]
            manifest.slides.append(
                SlideVisualEntry(
                    slide_no=slide_obj.slide_no,
                    title=slide_obj.title,
                    visual_type=vt,
                    render_mode=mode_used,
                    graphics_spec_summary=summary,
                    assets=assets_list,
                )
            )
            new_slides.append(slide_obj)
        except Exception:
            traceback.print_exc()
            new_slides.append(slide)

    return SlideDeckSpec(project_title=deck.project_title, subtitle=deck.subtitle, slides=new_slides), manifest


def presentation_graphics_from_llm_text(deck: SlideDeckSpec, raw_text: str) -> SlideDeckSpec:
    """LLM 원문에서 JSON만 추출해 병합 — 외부 도구/테스트용 엔트리포인트."""
    obj = extract_json_object(raw_text) or {}
    if not obj:
        return deck
    try:
        return merge_graphics_json_into_deck(deck, obj)
    except Exception:
        return deck
