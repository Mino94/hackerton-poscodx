"""AutoPM MCP 도구 구현 — 서버(stdio)와 Agent in-process 호출이 동일 로직을 공유한다."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from autopm.tools.calculation_engine import estimate_rough_cost, fp_placeholder
from autopm.tools.document_parser import parse_paste_text
from autopm.tools.rag_engine import keyword_search
from autopm.tools.visualization_generator import markdown_gantt_placeholder, mermaid_simple_flow

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_KNOWLEDGE = _PROJECT_ROOT / "src" / "autopm" / "knowledge" / "sample_project_template.md"
_OUTPUTS = _PROJECT_ROOT / "outputs"


def _ctx_get(context: dict[str, Any], *keys: str, default: str = "") -> str:
    for k in keys:
        v = context.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    return default


def tool_rag_search(query: str, context: dict[str, Any] | None = None) -> str:
    """조직 지식 템플릿에서 키워드 검색 — 요건·AS-IS 작성 시 참고."""
    q = query.strip() or _ctx_get(context or {}, "proposal_title", "idea_title", "pain_points")
    return keyword_search(q, _KNOWLEDGE, max_lines=35)


def tool_estimate_cost(
    monthly_hours: str = "",
    headcount: str = "",
    budget_cap: str = "",
    context: dict[str, Any] | None = None,
) -> str:
    """월 소요·인원·예산 상한으로 비용·절감 힌트(가정) 산출."""
    ctx = context or {}
    mh = monthly_hours or _ctx_get(ctx, "monthly_hours", default="0")
    hc = headcount or _ctx_get(ctx, "headcount", default="0")
    cap = budget_cap or _ctx_get(ctx, "budget_range", default="협의")
    return estimate_rough_cost(mh, hc, cap)


def tool_fp_estimate(function_points: int | None = None) -> str:
    """FP/COCOMO 자리표시자 — 향후 정식 산정 연동."""
    return fp_placeholder(function_points)


def tool_mermaid_process(steps_csv: str = "", context: dict[str, Any] | None = None) -> str:
    """쉼표 구분 단계로 AS-IS/TO-BE 흐름 Mermaid 생성."""
    raw = steps_csv.strip()
    if not raw:
        ctx = context or {}
        proc = _ctx_get(ctx, "current_process", "improvement_direction")
        raw = proc.replace("→", ",").replace(">", ",")
    steps = [s.strip() for s in raw.split(",") if s.strip()][:8]
    if len(steps) < 2:
        steps = ["현황", "검증", "승인", "마감"]
    return mermaid_simple_flow(steps)


def tool_gantt_outline(title: str = "", weeks: int = 4, context: dict[str, Any] | None = None) -> str:
    """WBS·일정 슬라이드용 Mermaid Gantt 템플릿."""
    t = title.strip() or _ctx_get(context or {}, "proposal_title", "idea_title", default="추진 일정")
    return markdown_gantt_placeholder(t, weeks=max(1, min(weeks, 12)))


def tool_normalize_input(text: str) -> str:
    """붙여넣기 텍스트 정규화."""
    return parse_paste_text(text)


def tool_read_slide_plan() -> str:
    """outputs/slide_plan.json 요약 — PPT Agent가 구조를 맞출 때 참고."""
    path = _OUTPUTS / "slide_plan.json"
    if not path.is_file():
        return "(MCP) slide_plan.json 없음 — Storyline 단계 이후 생성됩니다."
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        slides = data.get("slides") or []
        lines = [f"- 슬라이드 {s.get('slide_no', '?')}: {s.get('title', '')} ({s.get('visual_type', '')})" for s in slides[:14]]
        return f"프로젝트: {data.get('project_title', '')}\n" + "\n".join(lines)
    except (OSError, json.JSONDecodeError) as exc:
        return f"(MCP) slide_plan 읽기 실패: {exc}"


# MCP 서버·in-process 공용 핸들러 맵
TOOL_HANDLERS: dict[str, Any] = {
    "rag_search": tool_rag_search,
    "estimate_cost": tool_estimate_cost,
    "fp_estimate": tool_fp_estimate,
    "mermaid_process": tool_mermaid_process,
    "gantt_outline": tool_gantt_outline,
    "normalize_input": tool_normalize_input,
    "read_slide_plan": tool_read_slide_plan,
}


def call_tool_inprocess(name: str, arguments: dict[str, Any] | None = None) -> str:
    """stdio 없이 동일 MCP 도구 실행 — Streamlit·데모 fallback용."""
    fn = TOOL_HANDLERS.get(name)
    if fn is None:
        return f"(MCP) unknown tool: {name}"
    args = dict(arguments or {})
    ctx = args.pop("context", None)
    try:
        if ctx is not None and "context" in fn.__code__.co_varnames:
            out = fn(**args, context=ctx)
        else:
            out = fn(**args)
        return str(out).strip()
    except TypeError:
        try:
            return str(fn(**args)).strip()
        except Exception as exc:  # noqa: BLE001
            return f"(MCP) tool {name} error: {exc}"
    except Exception as exc:  # noqa: BLE001
        return f"(MCP) tool {name} error: {exc}"
