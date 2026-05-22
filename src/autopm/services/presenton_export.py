"""Presenton API — AutoPM 최종 JSON/Markdown → 고품질 PPTX (https://github.com/presenton/presenton)."""

from __future__ import annotations

import base64
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from autopm.ppt.deck_json import extract_json_object

# Docker 기본 포트 — README: docker run -p 5000:80 ...
DEFAULT_PRESENTON_BASE = "http://127.0.0.1:5000"


def is_presenton_configured() -> bool:
    """API 키 또는 self-hosted Basic 인증이 있으면 Presenton 사용 가능."""
    load_dotenv()
    if os.getenv("PRESENTON_API_KEY", "").strip():
        return True
    user = os.getenv("PRESENTON_USERNAME", "").strip()
    pwd = os.getenv("PRESENTON_PASSWORD", "").strip()
    return bool(user and pwd)


def _base_url() -> str:
    load_dotenv()
    return (os.getenv("PRESENTON_BASE_URL") or DEFAULT_PRESENTON_BASE).rstrip("/")


def _auth_header() -> dict[str, str]:
    """클라우드 Bearer 또는 self-hosted HTTP Basic."""
    load_dotenv()
    api_key = os.getenv("PRESENTON_API_KEY", "").strip()
    if api_key:
        token = api_key if api_key.lower().startswith("bearer ") else f"Bearer {api_key}"
        return {"Authorization": token}
    user = os.getenv("PRESENTON_USERNAME", "").strip()
    pwd = os.getenv("PRESENTON_PASSWORD", "").strip()
    if user and pwd:
        raw = base64.b64encode(f"{user}:{pwd}".encode("utf-8")).decode("ascii")
        return {"Authorization": f"Basic {raw}"}
    raise RuntimeError("Presenton 인증 정보가 없습니다 (PRESENTON_API_KEY 또는 USERNAME/PASSWORD).")


def _request(
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    *,
    timeout: float = 300.0,
) -> dict[str, Any]:
    url = f"{_base_url()}{path}"
    headers = {
        **_auth_header(),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")[:1200]
        raise RuntimeError(f"Presenton API HTTP {exc.code} {path}: {err_body}") from exc


def _download_bytes(url: str, dest: Path, *, timeout: float = 180.0) -> str:
    dest.parent.mkdir(parents=True, exist_ok=True)
    headers = _auth_header()
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            dest.write_bytes(resp.read())
    except urllib.error.HTTPError:
        # 공개 URL이면 인증 없이 재시도
        req2 = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req2, timeout=timeout) as resp:
            dest.write_bytes(resp.read())
    return str(dest.resolve())


def _tone_from_context(presentation_tone: str) -> str:
    t = (presentation_tone or "").strip()
    if "컨설팅" in t or "제안" in t:
        return "professional"
    if "경영" in t or "투자" in t or "예산" in t:
        return "professional"
    if "기술" in t or "아키텍처" in t:
        return "educational"
    return "professional"


def _content_dict_to_bullets(content: dict[str, Any]) -> list[str]:
    """visual_type별 content dict → 마크다운 불릿."""
    lines: list[str] = []
    if not content:
        return lines
    for key in (
        "bullets",
        "items",
        "problems",
        "steps",
        "before",
        "after",
        "included",
        "excluded",
        "highlights",
        "rows",
        "kpis",
        "risks",
        "cards",
    ):
        val = content.get(key)
        if isinstance(val, list):
            for item in val[:12]:
                if isinstance(item, str):
                    lines.append(item)
                elif isinstance(item, dict):
                    parts = [str(v) for v in item.values() if v]
                    lines.append(" · ".join(parts[:6]))
        elif isinstance(val, str) and val.strip():
            lines.append(val.strip())
    summary = content.get("summary") or content.get("text") or content.get("conclusion")
    if isinstance(summary, str) and summary.strip():
        lines.append(summary.strip())
    return lines


def slide_dict_to_markdown(slide: dict[str, Any]) -> str:
    """슬라이드 1장 → Presenton slides_markdown 항목."""
    title = (slide.get("title") or f"슬라이드 {slide.get('slide_no', '')}").strip()
    parts = [f"# {title}"]
    km = (slide.get("key_message") or "").strip()
    if km:
        parts.append(f"\n**핵심 메시지:** {km}")
    obj = (slide.get("objective") or "").strip()
    if obj:
        parts.append(f"\n*목적:* {obj}")
    vt = (slide.get("visual_type") or "").strip()
    if vt:
        parts.append(f"\n*시각 유형:* `{vt}`")
    content = slide.get("content") if isinstance(slide.get("content"), dict) else {}
    bullets = _content_dict_to_bullets(content)
    if bullets:
        parts.append("")
        for b in bullets:
            parts.append(f"- {b}")
    notes = (slide.get("notes") or "").strip()
    if notes:
        parts.append(f"\n> {notes}")
    return "\n".join(parts).strip()


def deck_dict_to_slides_markdown(deck_dict: dict[str, Any]) -> list[str]:
    """SlideDeckSpec JSON → Presenton slides_markdown 배열."""
    slides = deck_dict.get("slides") or []
    out: list[str] = []
    for s in slides:
        if isinstance(s, dict):
            md = slide_dict_to_markdown(s)
            if md:
                out.append(md)
    return out


def prefer_composer_deck(
    deck_dict: dict[str, Any],
    composer_raw: str = "",
) -> dict[str, Any]:
    """PPT Composer Agent 최종 JSON을 우선 사용 — 없으면 병합된 deck_dict."""
    parsed = extract_json_object(composer_raw or "")
    if not parsed:
        return deck_dict
    if parsed.get("slides"):
        merged = dict(deck_dict)
        merged["project_title"] = parsed.get("project_title") or merged.get("project_title")
        merged["subtitle"] = parsed.get("subtitle") or merged.get("subtitle")
        merged["slides"] = parsed["slides"]
        return merged
    block = parsed.get("slide_deck")
    if isinstance(block, dict) and block.get("slides"):
        merged = dict(deck_dict)
        merged.update({k: block[k] for k in ("project_title", "subtitle", "slides") if k in block})
        return merged
    return deck_dict


def build_presenton_content(
    project_title: str,
    markdown: str,
    deck_dict: dict[str, Any],
    *,
    business_plan: dict[str, Any] | None = None,
) -> str:
    """Presenton `content` 필드 — 전체 맥락(에이전트 Markdown + business_plan 요약)."""
    parts = [
        f"# {project_title}",
        "",
        "다음은 Multi-Agent PM이 작성한 **추진계획서** 초안이다. 한국어 비즈니스 PPT로 작성하라.",
        "",
        markdown[:45000],
    ]
    if business_plan:
        try:
            bp_excerpt = json.dumps(business_plan, ensure_ascii=False, indent=0)[:12000]
            parts.extend(["", "## 구조화 데이터 (business_plan)", "", "```json", bp_excerpt, "```"])
        except (TypeError, ValueError):
            pass
    slides = deck_dict.get("slides") or []
    if slides:
        parts.append("\n## 슬라이드 개요\n")
        for s in slides[:14]:
            if not isinstance(s, dict):
                continue
            parts.append(f"- **{s.get('title', '')}**: {s.get('key_message', '')}")
    return "\n".join(parts)[:95000]


def build_presenton_generate_payload(
    *,
    project_title: str,
    markdown: str,
    deck_dict: dict[str, Any],
    context: dict[str, str],
    business_plan: dict[str, Any] | None = None,
    composer_raw: str = "",
) -> dict[str, Any]:
    """POST /api/v1/ppt/presentation/generate 요청 본문."""
    load_dotenv()
    deck = prefer_composer_deck(deck_dict, composer_raw)
    slides_md = deck_dict_to_slides_markdown(deck)
    n_slides = max(8, min(len(slides_md) or 10, 20))
    language = os.getenv("PRESENTON_LANGUAGE", "Korean").strip() or "Korean"
    template = os.getenv("PRESENTON_TEMPLATE", "general").strip() or "general"
    tone = _tone_from_context(str(context.get("presentation_tone") or ""))

    instructions = (
        "한국어 추진계획서(PM 보고) 스타일. "
        "Executive Summary, AS-IS, TO-BE, 개발 범위, WBS, 예산·ROI, 리스크, 기대효과, 결론을 포함. "
        "표·차트·아이콘을 활용한 전문 슬라이드. 수치는 '예상/가정'으로 표기."
    )

    payload: dict[str, Any] = {
        "content": build_presenton_content(project_title, markdown, deck, business_plan=business_plan),
        "instructions": instructions,
        "tone": tone,
        "verbosity": "standard",
        "web_search": False,
        "n_slides": n_slides,
        "language": language,
        "template": template,
        "include_title_slide": True,
        "include_table_of_contents": False,
        "export_as": "pptx",
    }
    # Composer/Storyline JSON이 있으면 구조 보존 생성
    if slides_md:
        payload["slides_markdown"] = slides_md
        payload["content_generation"] = "preserve"
        payload["markdown_emphasis"] = True
    return payload


def _resolve_download_url(resp: dict[str, Any]) -> str | None:
    """generate/export 응답에서 다운로드 URL 추출."""
    path = str(resp.get("path") or "").strip()
    if path.startswith("http://") or path.startswith("https://"):
        return path
    pid = str(resp.get("presentation_id") or "").strip()
    base = _base_url()
    if path.startswith("/"):
        return f"{base}{path}"
    if pid:
        return f"{base}/api/v1/ppt/files/download/{pid}"
    return None


def _export_pptx_by_id(presentation_id: str) -> dict[str, Any]:
    """생성 후 별도 export API 호출 (self-hosted 호환)."""
    body = {"id": presentation_id, "export_as": "pptx"}
    for path in (
        "/api/v1/ppt/presentation/export",
        "/api/v1/ppt/presentation/export/pptx",
    ):
        try:
            return _request("POST", path, body, timeout=300.0)
        except RuntimeError:
            continue
    raise RuntimeError(f"Presenton export 실패 (presentation_id={presentation_id})")


def download_presentation_file(
    generate_resp: dict[str, Any],
    dest: Path,
) -> str:
    """generate/export 응답 → 로컬 PPTX 저장."""
    url = _resolve_download_url(generate_resp)
    pid = str(generate_resp.get("presentation_id") or "").strip()

    if url:
        try:
            return _download_bytes(url, dest)
        except Exception:
            pass

    if pid:
        export_resp = _export_pptx_by_id(pid)
        url2 = _resolve_download_url(export_resp)
        if url2:
            return _download_bytes(url2, dest)
        # path가 컨테이너 내부일 때 — app_data 프록시 시도
        path2 = str(export_resp.get("path") or "")
        if path2.startswith("/app_data/"):
            base = _base_url()
            for candidate in (
                f"{base}{path2}",
                f"{base}/static{path2}",
                f"{base}/files{path2}",
            ):
                try:
                    return _download_bytes(candidate, dest)
                except Exception:
                    continue

    raise RuntimeError(
        f"Presenton PPTX 다운로드 URL을 찾지 못했습니다: {json.dumps(generate_resp, ensure_ascii=False)[:500]}"
    )


def generate_presentation_pptx(payload: dict[str, Any]) -> dict[str, Any]:
    """동기 생성 API — PPTX export 포함."""
    return _request("POST", "/api/v1/ppt/presentation/generate", payload, timeout=600.0)


def export_presenton_pptx(
    output_path: str | Path,
    *,
    project_title: str,
    markdown: str,
    deck_dict: dict[str, Any],
    context: dict[str, str],
    business_plan: dict[str, Any] | None = None,
    composer_raw: str = "",
) -> dict[str, str]:
    """
    Presenton으로 PPTX 생성 후 output_path에 저장.
    MCP(generate_presentation) 우선, 실패 시 REST /api/v1/ppt/presentation/generate.
    반환: {pptx_path, presentation_id, edit_path, presenton_base_url, presenton_via?}
    """
    if not is_presenton_configured():
        raise RuntimeError("Presenton이 설정되지 않았습니다.")

    out = Path(output_path)

    # Presenton 내장 MCP (Streamable HTTP) — 오픈소스 권장 경로
    try:
        from autopm.mcp.presenton_client import export_presenton_via_mcp, is_presenton_mcp_enabled

        if is_presenton_mcp_enabled():
            return export_presenton_via_mcp(
                out,
                project_title=project_title,
                markdown=markdown,
                deck_dict=deck_dict,
                context=context,
                business_plan=business_plan,
                composer_raw=composer_raw,
            )
    except Exception:
        pass  # REST 폴백

    payload = build_presenton_generate_payload(
        project_title=project_title,
        markdown=markdown,
        deck_dict=deck_dict,
        context=context,
        business_plan=business_plan,
        composer_raw=composer_raw,
    )
    resp = generate_presentation_pptx(payload)
    pptx_path = download_presentation_file(resp, out)
    base = _base_url()
    edit = str(resp.get("edit_path") or "")
    if edit and not edit.startswith("http"):
        edit = f"{base}{edit}"
    return {
        "pptx_path": pptx_path,
        "presentation_id": str(resp.get("presentation_id") or ""),
        "edit_path": edit,
        "presenton_base_url": base,
        "presenton_via": "rest",
    }


def check_presenton_health() -> tuple[bool, str]:
    """서버 응답 여부 — 설정만 있고 서버가 꺼져 있으면 False."""
    if not is_presenton_configured():
        return False, "not_configured"
    try:
        url = f"{_base_url()}/"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            return resp.status < 500, f"http_{resp.status}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)[:120]
