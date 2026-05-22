"""PPT 품질 API 라우터 — Presenton(권장) / python-pptx(폴백) / Gamma(선택)."""

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
from autopm.services.presenton_export import (
    export_presenton_pptx,
    is_presenton_configured,
)


def get_ppt_quality_config() -> dict[str, Any]:
    load_dotenv()
    api_mode = os.getenv("AUTOPM_PPT_API", "presenton").strip().lower()
    # 레거시: gamma만 켠 경우
    if api_mode == "gamma":
        api_mode = "both"
    presenton_on = api_mode in ("presenton", "both") and is_presenton_configured()
    use_python_fallback = api_mode in ("python-pptx", "both", "presenton")
    return {
        "ppt_api_mode": api_mode,
        "openai_enhance_ppt": is_openai_ppt_enhance_enabled(),
        "presenton_configured": is_presenton_configured(),
        "presenton_enabled": presenton_on,
        "python_pptx_fallback": use_python_fallback,
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


def try_export_presenton_ppt(
    out_dir: Path,
    *,
    project_title: str,
    markdown: str,
    deck_dict: dict[str, Any],
    context: dict[str, str],
    composer_raw: str = "",
    business_plan: dict[str, Any] | None = None,
    on_progress: Callable[[str], None] | None = None,
) -> dict[str, str] | None:
    """
    Presenton API로 project_plan.pptx 생성 (최종 Agent JSON 우선).
    실패 시 None — 호출측에서 python-pptx 폴백.
    """
    cfg = get_ppt_quality_config()
    if not cfg.get("presenton_enabled"):
        return None

    if on_progress:
        on_progress("[Presenton] 추진계획서 PPT 생성 요청 (Composer JSON → slides_markdown)…")

    dest = out_dir / "project_plan.pptx"
    try:
        meta = export_presenton_pptx(
            dest,
            project_title=project_title[:500],
            markdown=markdown,
            deck_dict=deck_dict,
            context=context,
            business_plan=business_plan,
            composer_raw=composer_raw,
        )
        if on_progress:
            on_progress(
                f"[Presenton] PPTX 저장 완료 — {meta.get('edit_path', '')[:80]}"
            )
        return {
            "project_plan.pptx": meta["pptx_path"],
            "presenton_presentation_id": meta.get("presentation_id", ""),
            "presenton_edit_path": meta.get("edit_path", ""),
            "presenton_base_url": meta.get("presenton_base_url", ""),
        }
    except Exception as exc:  # noqa: BLE001
        if on_progress:
            on_progress(f"[Presenton] 실패(python-pptx 폴백): {exc}")
        return None
