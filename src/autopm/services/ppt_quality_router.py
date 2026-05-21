"""PPT 품질 API 라우터 — python-pptx(기본) + OpenAI 고도화 + Gamma(선택)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv

from autopm.services.gamma_export import (
    build_gamma_input_text,
    export_gamma_pptx,
    is_gamma_configured,
)
from autopm.services.ppt_openai_enhancer import (
    enhance_slide_deck_dict,
    enhance_storyline_raw,
    is_openai_ppt_enhance_enabled,
)


def get_ppt_quality_config() -> dict[str, Any]:
    load_dotenv()
    api_mode = os.getenv("AUTOPM_PPT_API", "both").strip().lower()
    return {
        "ppt_api_mode": api_mode,
        "openai_enhance_ppt": is_openai_ppt_enhance_enabled(),
        "gamma_configured": is_gamma_configured(),
        "gamma_enabled": api_mode in ("gamma", "both") and is_gamma_configured(),
    }


def apply_openai_ppt_enhancements(
    state: Any,
    deck_dict: dict[str, Any],
    context: dict[str, str],
    markdown: str,
) -> dict[str, Any]:
    """스토리라인·덱 JSON OpenAI 보강 — state.slide_storyline_raw 갱신 가능."""
    if not is_openai_ppt_enhance_enabled():
        return deck_dict
    if getattr(state, "slide_storyline_raw", None):
        state.slide_storyline_raw = enhance_storyline_raw(state.slide_storyline_raw, context)
    return enhance_slide_deck_dict(deck_dict, context, markdown_excerpt=markdown)


def try_export_gamma_ppt(
    out_dir: Path,
    *,
    project_title: str,
    markdown: str,
    deck_dict: dict[str, Any],
    context: dict[str, str],
    on_progress: Callable[[str], None] | None = None,
) -> dict[str, str] | None:
    """
    Gamma API로 project_plan_gamma.pptx 생성.
    키 없거나 실패 시 None — 기본 python-pptx는 호출측에서 유지.
    """
    cfg = get_ppt_quality_config()
    if not cfg.get("gamma_enabled"):
        return None

    if on_progress:
        on_progress("[Gamma API] 고품질 PPT 생성 요청…")

    input_text = build_gamma_input_text(
        project_title,
        markdown,
        deck_dict,
        presentation_tone=str(context.get("presentation_tone") or ""),
    )
    dest = out_dir / "project_plan_gamma.pptx"
    try:
        meta = export_gamma_pptx(
            input_text,
            dest,
            title=project_title[:500],
            num_cards=len((deck_dict or {}).get("slides") or []) or 11,
        )
        if on_progress:
            on_progress(f"[Gamma API] PPTX 저장 완료 — {meta.get('gamma_url', '')[:60]}")
        return {
            "project_plan_gamma.pptx": meta["pptx_path"],
            "gamma_url": meta.get("gamma_url", ""),
            "gamma_generation_id": meta.get("generation_id", ""),
        }
    except Exception as exc:  # noqa: BLE001
        if on_progress:
            on_progress(f"[Gamma API] 실패(기본 PPT 유지): {exc}")
        return None
