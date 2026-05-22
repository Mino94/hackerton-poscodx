"""OpenAI API로 SlideDeck·스토리라인 JSON 품질을 고도화한다 — python-pptx 출력 개선."""

from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv

from autopm.ppt.deck_json import extract_json_object
from autopm.ppt.slide_schema import SlideDeckSpec


def is_openai_ppt_enhance_enabled() -> bool:
    """OpenAI 키 + AUTOPM_OPENAI_ENHANCE_PPT=true(기본)일 때 슬라이드 고도화."""
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY", "").strip():
        return False
    return os.getenv("AUTOPM_OPENAI_ENHANCE_PPT", "true").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _openai_json_completion(system: str, user: str) -> dict[str, Any] | None:
    from autopm.services.llm_router import build_openai_client, get_openai_api_key, get_openai_model_name

    if not get_openai_api_key():
        return None
    model = get_openai_model_name()
    try:
        client = build_openai_client()
        r = client.chat.completions.create(
            model=model,
            temperature=0.25,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        text = (r.choices[0].message.content or "").strip()
        return extract_json_object(text) or json.loads(text)
    except Exception:
        return None


def enhance_slide_deck_dict(
    deck_dict: dict[str, Any],
    context: dict[str, str],
    markdown_excerpt: str = "",
) -> dict[str, Any]:
    """
    SlideDeckSpec JSON의 title/key_message/content/bullets를 OpenAI로 보강한다.
    실패 시 원본 deck_dict 반환.
    """
    if not is_openai_ppt_enhance_enabled():
        return deck_dict

    tone = context.get("presentation_tone") or "실무 추진계획형"
    title = deck_dict.get("project_title") or context.get("proposal_title") or "추진계획서"

    system = (
        "당신은 B2B 추진계획서 PPT 전문가다. 주어진 slide deck JSON을 한국어로 보강하라. "
        "반드시 유효한 JSON만 출력한다. slide_no·visual_type은 유지하고 "
        "key_message는 한 줄 핵심, content.bullets는 3~5개 구체 bullet로 채운다. "
        "수치는 (가정)을 붙인다. 환각으로 새로운 예산·일정 숫자를 만들지 말고 입력·원본을 우선한다."
    )
    user = json.dumps(
        {
            "presentation_tone": tone,
            "user_context": {k: str(v)[:500] for k, v in list(context.items())[:20]},
            "markdown_excerpt": (markdown_excerpt or "")[:6000],
            "deck": deck_dict,
        },
        ensure_ascii=False,
    )

    improved = _openai_json_completion(system, user)
    if not improved:
        return deck_dict
    try:
        if improved.get("slides"):
            SlideDeckSpec.model_validate(improved)
            return improved
        if improved.get("slide_deck"):
            nested = improved["slide_deck"]
            SlideDeckSpec.model_validate(nested)
            return nested
    except Exception:
        return deck_dict
    return deck_dict


def enhance_storyline_raw(storyline_text: str, context: dict[str, str]) -> str:
    """스토리라인 Agent 산출(JSON 문자열)을 OpenAI로 다듬는다 — 실패 시 원문."""
    if not is_openai_ppt_enhance_enabled() or not (storyline_text or "").strip():
        return storyline_text

    system = (
        "추진계획서 PPT 스토리라인 JSON을 보강하라. slides 배열에 slide_no, title, "
        "objective, key_message, layout_type, visual_type을 포함한다. 한국어, 발표용. JSON만 출력."
    )
    user = json.dumps(
        {"context": context, "storyline": storyline_text[:12000]},
        ensure_ascii=False,
    )
    data = _openai_json_completion(system, user)
    if not data:
        return storyline_text
    return json.dumps(data.get("slide_deck") or data, ensure_ascii=False, indent=2)
