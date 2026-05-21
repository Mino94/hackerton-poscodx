"""Gamma API — 고품질 발표용 PPTX/PDF 생성 (선택)."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

GAMMA_API_BASE = "https://public-api.gamma.app/v1.0"


def is_gamma_configured() -> bool:
    load_dotenv()
    return bool(os.getenv("GAMMA_API_KEY", "").strip())


def _api_key() -> str:
    load_dotenv()
    key = os.getenv("GAMMA_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GAMMA_API_KEY가 없습니다.")
    return key


def _request(method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{GAMMA_API_BASE}{path}"
    headers = {
        "X-API-KEY": _api_key(),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")[:800]
        raise RuntimeError(f"Gamma API HTTP {exc.code}: {err_body}") from exc


def build_gamma_input_text(
    project_title: str,
    markdown: str,
    deck_dict: dict[str, Any] | None = None,
    *,
    presentation_tone: str = "",
) -> str:
    """
    Gamma inputText — Markdown + 슬라이드 카드 구분(---)으로 장표 구조를 전달한다.
    """
    tone = (presentation_tone or "실무 추진계획형").strip()
    parts = [
        f"# {project_title}\n",
        f"**발표 톤:** {tone}\n",
        "**요구:** 한국어 추진계획서 PPT. AS-IS/TO-BE, WBS, 예산·ROI, 리스크, 기대효과, 결론을 포함하라.",
        markdown[:48000],
    ]
    slides = (deck_dict or {}).get("slides") or []
    if slides:
        parts.append("\n---\n# 슬라이드 구성 (카드별)\n")
        for s in slides[:16]:
            if not isinstance(s, dict):
                continue
            title = s.get("title") or ""
            msg = s.get("key_message") or s.get("objective") or ""
            vt = s.get("visual_type") or ""
            parts.append(f"## {title}\n- 핵심: {msg}\n- 시각: {vt}\n")
            bullets = (s.get("content") or {}).get("bullets") if isinstance(s.get("content"), dict) else None
            if bullets:
                for b in bullets[:6]:
                    parts.append(f"- {b}")
            parts.append("\n---\n")
    return "\n".join(parts)[:95000]


def create_generation(
    input_text: str,
    *,
    title: str,
    num_cards: int = 11,
    export_as: str = "pptx",
    text_mode: str = "generate",
) -> str:
    """POST /generations — generationId 반환."""
    load_dotenv()
    payload: dict[str, Any] = {
        "inputText": input_text,
        "textMode": text_mode,
        "format": "presentation",
        "numCards": max(8, min(int(num_cards), 20)),
        "title": (title or "AutoPM 추진계획서")[:500],
        "exportAs": export_as,
        "textOptions": {
            "amount": "detailed",
            "tone": "professional, clear, executive-ready, Korean business",
            "language": os.getenv("GAMMA_OUTPUT_LANGUAGE", "ko"),
        },
        "additionalInstructions": "모든 슬라이드는 한국어로 작성한다. 추진계획서·PM 보고 스타일.",
    }
    data = _request("POST", "/generations", payload)
    gid = data.get("generationId") or data.get("id") or data.get("generation_id")
    if not gid:
        raise RuntimeError(f"Gamma generationId 없음: {data}")
    return str(gid)


def get_generation_status(generation_id: str) -> dict[str, Any]:
    return _request("GET", f"/generations/{generation_id}")


def poll_until_done(
    generation_id: str,
    *,
    poll_seconds: float | None = None,
    max_wait_seconds: float | None = None,
) -> dict[str, Any]:
    load_dotenv()
    interval = float(poll_seconds or os.getenv("GAMMA_POLL_SECONDS", "6"))
    max_wait = float(max_wait_seconds or os.getenv("GAMMA_POLL_MAX_SECONDS", "180"))
    deadline = time.time() + max_wait
    last: dict[str, Any] = {}
    while time.time() < deadline:
        last = get_generation_status(generation_id)
        status = str(last.get("status") or last.get("state") or "").lower()
        if status in ("completed", "complete", "succeeded", "success", "done"):
            return last
        if status in ("failed", "error", "cancelled", "canceled"):
            raise RuntimeError(f"Gamma 생성 실패: {last}")
        time.sleep(interval)
    raise TimeoutError(f"Gamma 생성 시간 초과 ({max_wait}s): {last}")


def _download_file(url: str, dest: Path) -> str:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=180) as resp:
        dest.write_bytes(resp.read())
    return str(dest.resolve())


def export_gamma_pptx(
    input_text: str,
    output_path: str | Path,
    *,
    title: str = "AutoPM 추진계획서",
    num_cards: int = 11,
) -> dict[str, str]:
    """
    Gamma로 PPTX 생성 후 로컬에 저장.
    반환: {pptx_path, gamma_url, generation_id}
    """
    out = Path(output_path)
    gid = create_generation(input_text, title=title, num_cards=num_cards, export_as="pptx")
    result = poll_until_done(gid)
    export_url = (
        result.get("exportUrl")
        or result.get("export_url")
        or (result.get("export") or {}).get("url")
        if isinstance(result.get("export"), dict)
        else None
    )
    gamma_url = result.get("gammaUrl") or result.get("gamma_url") or result.get("url") or ""

    if not export_url:
        raise RuntimeError(f"Gamma exportUrl 없음 — gammaUrl만 있을 수 있음: {gamma_url}")

    pptx_path = _download_file(str(export_url), out)
    return {
        "pptx_path": pptx_path,
        "gamma_url": str(gamma_url),
        "generation_id": gid,
    }
