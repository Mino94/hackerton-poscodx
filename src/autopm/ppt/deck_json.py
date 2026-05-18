"""LLM 출력에서 SlideDeck JSON을 추출하고, Markdown/입력으로 보조 덱을 만든다."""

from __future__ import annotations

import json
import re
from typing import Any

from autopm.ppt.ppt_composer import build_fallback_slide_deck
from autopm.ppt.slide_schema import SlideDeckSpec, SlideSpec


def extract_json_object(text: str) -> dict[str, Any] | None:
    """ fenced code 또는 본문 전체에서 JSON 객체를 찾는다 — 데모 안정성 우선."""
    if not text or not text.strip():
        return None
    s = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", s, re.DOTALL)
    if fence:
        try:
            return json.loads(fence.group(1))
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}", s)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    return None


def slide_deck_from_parsed(data: dict[str, Any]) -> SlideDeckSpec | None:
    """AGENTS.md structured output의 slide_deck 블록 또는 루트 덱을 파싱한다."""
    if not data:
        return None
    block = data.get("slide_deck")
    if isinstance(block, dict):
        data = block
    try:
        return SlideDeckSpec.model_validate(data)
    except Exception:
        return None


def merge_storyline_and_visual(storyline: dict[str, Any], visualization: dict[str, Any]) -> SlideDeckSpec:
    """스토리라인 슬라이드에 시각화 단계의 visual_type/content를 덮어쓴다."""
    base = (
        SlideDeckSpec.model_validate(storyline)
        if storyline.get("slides")
        else build_fallback_slide_deck("AutoPM", "")
    )
    vis_slides = visualization.get("slides") if isinstance(visualization.get("slides"), list) else []
    vis_by_no = {}
    for vs in vis_slides:
        if isinstance(vs, dict) and "slide_no" in vs:
            vis_by_no[int(vs["slide_no"])] = vs
    merged: list[SlideSpec] = []
    for s in base.slides:
        d = s.model_dump()
        extra = vis_by_no.get(s.slide_no)
        if extra:
            if extra.get("visual_type"):
                d["visual_type"] = extra["visual_type"]
            if extra.get("content"):
                d["content"] = extra["content"]
            if extra.get("key_message"):
                d["key_message"] = extra["key_message"]
        merged.append(SlideSpec.model_validate(d))
    return SlideDeckSpec(project_title=base.project_title, subtitle=base.subtitle, slides=merged)


def deck_from_llm_chain(
    storyline_text: str,
    visualization_text: str,
    composer_text: str,
    *,
    project_title: str,
    presentation_graphics_text: str = "",
) -> SlideDeckSpec:
    """Storyline·Visualization·Presentation Graphics·Composer 출력을 병합 — 실패 시 샘플 덱."""
    # 순환 import 방지: graphics_agent는 deck_json을 이미 import하므로 여기서만 지연 import한다.
    from autopm.ppt.graphics_agent import merge_graphics_json_into_deck, overlay_storyline_visual_on_deck

    s1 = extract_json_object(storyline_text) or {}
    s2 = extract_json_object(visualization_text) or {}
    s3 = extract_json_object(presentation_graphics_text) or {}
    s4 = extract_json_object(composer_text)

    deck: SlideDeckSpec | None = None
    if s4 and s4.get("slides"):
        try:
            deck = SlideDeckSpec.model_validate(s4)
        except Exception:
            deck = None
    if deck is None or not deck.slides:
        if s1.get("slides"):
            try:
                deck = merge_storyline_and_visual(s1, s2 if isinstance(s2, dict) else {})
            except Exception:
                deck = None
    if deck is None or not deck.slides:
        deck = build_fallback_slide_deck(project_title, "LLM JSON 파싱 실패 — fallback")

    deck.project_title = deck.project_title or project_title
    deck = overlay_storyline_visual_on_deck(deck, s1, s2 if isinstance(s2, dict) else {})
    deck = merge_graphics_json_into_deck(deck, s3)
    return deck
