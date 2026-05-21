"""Agent별 MCP 도구 매핑·prefetch 컨텍스트 블록 생성."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from autopm.mcp.registry import TOOL_HANDLERS, call_tool_inprocess

_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "mcp_agent_tools.yaml"
_policy_cache: dict[str, Any] | None = None


def is_mcp_enabled() -> bool:
    """MCP 도구 연동 — 기본 켜짐, AUTOPM_ENABLE_MCP=false 로 비활성."""
    return os.getenv("AUTOPM_ENABLE_MCP", "true").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def is_mcp_react_enabled() -> bool:
    """LLM tool-calling(ReAct) — OpenAI 등 bind_tools 필요, 기본은 prefetch만."""
    if not is_mcp_enabled():
        return False
    return os.getenv("AUTOPM_MCP_REACT", "false").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _load_policy() -> dict[str, Any]:
    global _policy_cache
    if _policy_cache is not None:
        return _policy_cache
    if not _CONFIG_PATH.is_file():
        _policy_cache = {"default": ["rag_search"], "task_overrides": {}}
        return _policy_cache
    raw = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8")) or {}
    _policy_cache = raw
    return _policy_cache


def resolve_tool_names(agent_key: str, task_key: str = "") -> list[str]:
    """Agent·Task에 허용된 MCP 도구 이름 목록(중복 제거, 순서 유지)."""
    pol = _load_policy()
    names: list[str] = []
    seen: set[str] = set()

    def _add(items: list[str] | None) -> None:
        for n in items or []:
            if n in TOOL_HANDLERS and n not in seen:
                seen.add(n)
                names.append(n)

    _add(pol.get("default"))
    _add(pol.get(agent_key))
    overrides = pol.get("task_overrides") or {}
    if task_key:
        _add(overrides.get(task_key))
    return names


def _build_tool_args(tool_name: str, context: dict[str, str]) -> dict[str, Any]:
    """prefetch 시 도구별 기본 인자 — context는 핸들러가 받을 수 있을 때만 전달."""
    ctx = dict(context)
    if tool_name == "rag_search":
        q = (
            ctx.get("proposal_title")
            or ctx.get("idea_title")
            or ctx.get("pain_points")
            or ctx.get("current_problems")
            or ""
        )
        return {"query": str(q), "context": ctx}
    if tool_name == "estimate_cost":
        return {
            "monthly_hours": str(ctx.get("monthly_hours", "")),
            "headcount": str(ctx.get("headcount", "")),
            "budget_cap": str(ctx.get("budget_range", "")),
            "context": ctx,
        }
    if tool_name == "mermaid_process":
        proc = ctx.get("current_process") or ctx.get("improvement_direction") or ""
        return {"steps_csv": str(proc)[:500], "context": ctx}
    if tool_name == "gantt_outline":
        title = ctx.get("proposal_title") or ctx.get("idea_title") or "추진 일정"
        weeks = 4
        tl = str(ctx.get("timeline") or ctx.get("target_timeline") or "")
        if "주" in tl:
            try:
                weeks = max(1, int("".join(c for c in tl if c.isdigit())[:2] or "4"))
            except ValueError:
                weeks = 4
        return {"title": str(title), "weeks": weeks, "context": ctx}
    if tool_name in ("fp_estimate", "read_slide_plan", "normalize_input"):
        if tool_name == "normalize_input":
            raw = ctx.get("open_source_draft") or ctx.get("background_context") or ""
            return {"text": str(raw)[:4000]}
        return {}
    return {"context": ctx}


def build_mcp_prefetch_block(
    agent_key: str,
    context: dict[str, str],
    *,
    task_key: str = "",
) -> str:
    """
    Agent 호출 전 MCP 도구를 in-process 실행해 프롬프트에 붙인다.
    API·stdio 실패와 무관하게 데모가 끊기지 않게 한다.
    """
    if not is_mcp_enabled():
        return ""
    tools = resolve_tool_names(agent_key, task_key)
    if not tools:
        return ""
    parts = ["## MCP Tool Results (Model Context Protocol · prefetch)"]
    for name in tools:
        args = _build_tool_args(name, context)
        out = call_tool_inprocess(name, args)
        parts.append(f"### `{name}`\n{out[:3500]}")
    return "\n\n".join(parts) + "\n\n위 MCP 결과를 참고하되, 없는 수치는 (가정)으로 명시하라.\n"
