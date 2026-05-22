"""Presenton MCP (Streamable HTTP) — generate_presentation 도구 호출."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from autopm.services.presenton_export import (
    _base_url,
    _download_bytes,
    build_presenton_content,
    build_presenton_generate_payload,
    is_presenton_configured,
)


def is_presenton_mcp_enabled() -> bool:
    """MCP 경로 사용 — 기본 true, AUTOPM_PRESENTON_USE_MCP=false 로 REST만."""
    load_dotenv()
    if not is_presenton_configured():
        return False
    return os.getenv("AUTOPM_PRESENTON_USE_MCP", "true").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def presenton_mcp_url() -> str:
    load_dotenv()
    explicit = os.getenv("PRESENTON_MCP_URL", "").strip()
    if explicit:
        return explicit.rstrip("/")
    base = _base_url()
    return f"{base}/mcp"


def _mcp_auth_headers() -> dict[str, str]:
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
    return {}


def _presenton_http_connection() -> dict[str, Any]:
    return {
        "transport": "streamable_http",
        "url": presenton_mcp_url(),
        "headers": _mcp_auth_headers(),
    }


def _extract_text_from_tool_result(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        return json.dumps(result, ensure_ascii=False)
    if isinstance(result, list):
        parts: list[str] = []
        for block in result:
            if isinstance(block, dict):
                parts.append(str(block.get("text") or block.get("content") or block))
            else:
                parts.append(str(block))
        return "\n".join(parts)
    return str(result)


def _parse_path_from_mcp_text(text: str) -> dict[str, Any]:
    """MCP 도구 응답에서 presentation_id·path 추출."""
    text = (text or "").strip()
    if not text:
        return {}
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            data = json.loads(m.group(0))
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
    if text.startswith("http://") or text.startswith("https://"):
        return {"path": text}
    return {"raw": text}


async def _call_generate_presentation_async(content: str, instructions: str) -> dict[str, Any]:
    from langchain_mcp_adapters.client import MultiServerMCPClient

    client = MultiServerMCPClient({"presenton": _presenton_http_connection()})
    tools = await client.get_tools(server_name="presenton")
    if not tools:
        raise RuntimeError("Presenton MCP: 도구 목록이 비어 있습니다. Docker가 실행 중인지 확인하세요.")

    target = None
    for t in tools:
        name = (getattr(t, "name", None) or "").lower()
        if "generate_presentation" in name or name == "generate":
            target = t
            break
    if target is None:
        target = tools[0]

    args = {"content": content[:95000], "instructions": (instructions or "")[:8000]}
    # 스키마에 맞는 키만 전달
    schema_keys: set[str] = set()
    try:
        schema = getattr(target, "args_schema", None)
        if schema and hasattr(schema, "model_fields"):
            schema_keys = set(schema.model_fields.keys())
    except Exception:
        schema_keys = set()

    if schema_keys:
        args = {k: v for k, v in args.items() if k in schema_keys}

    if hasattr(target, "ainvoke"):
        raw = await target.ainvoke(args)
    else:
        raw = await asyncio.to_thread(target.invoke, args)

    text = _extract_text_from_tool_result(raw)
    parsed = _parse_path_from_mcp_text(text)
    if not parsed and text:
        parsed = {"path": text, "presentation_id": ""}
    return parsed


def call_generate_presentation_mcp(content: str, instructions: str) -> dict[str, Any]:
    """동기 래퍼 — Presenton MCP generate_presentation."""
    return asyncio.run(_call_generate_presentation_async(content, instructions))


async def check_presenton_mcp_health_async() -> tuple[bool, str]:
    if not is_presenton_mcp_enabled():
        return False, "mcp_disabled"
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient

        client = MultiServerMCPClient({"presenton": _presenton_http_connection()})
        tools = await client.get_tools(server_name="presenton")
        names = [getattr(t, "name", "?") for t in tools]
        return True, f"tools={names}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)[:200]


def check_presenton_mcp_health() -> tuple[bool, str]:
    try:
        return asyncio.run(check_presenton_mcp_health_async())
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)[:200]


def export_presenton_via_mcp(
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
    MCP generate_presentation → PPTX 다운로드.
    REST API와 동일한 반환 dict.
    """
    from autopm.services.presenton_export import download_presentation_file

    dest = Path(output_path)

    payload = build_presenton_generate_payload(
        project_title=project_title,
        markdown=markdown,
        deck_dict=deck_dict,
        context=context,
        business_plan=business_plan,
        composer_raw=composer_raw,
    )
    content = str(payload.get("content") or build_presenton_content(
        project_title, markdown, deck_dict, business_plan=business_plan
    ))
    instructions = str(payload.get("instructions") or "")

    resp = call_generate_presentation_mcp(content, instructions)
    pptx_path = download_presentation_file(resp, dest)
    base = _base_url()
    edit = str(resp.get("edit_path") or "")
    if edit and not edit.startswith("http"):
        edit = f"{base}{edit}"
    return {
        "pptx_path": pptx_path,
        "presentation_id": str(resp.get("presentation_id") or ""),
        "edit_path": edit,
        "presenton_base_url": base,
        "presenton_via": "mcp",
    }
