"""Visualization Agent 결과를 layout_engine 호출로 연결하기 위한 얇은 어댑터."""

from __future__ import annotations

from pptx.slide import Slide
from pptx.util import Inches

from autopm.ppt import layout_engine
from autopm.ppt.slide_schema import SlideSpec
from autopm.ppt.visual_registry import normalize_visual_type


def apply_visual(slide: Slide, spec: SlideSpec) -> None:
    """SlideSpec.visual_type에 맞춰 시각요소를 한 번에 배치한다 — graphics_spec 없을 때 최종 fallback."""
    vt = normalize_visual_type((spec.visual_type or "summary_cards").strip())
    content = spec.content or {}

    if vt == "summary_cards":
        layout_engine.add_summary_cards(slide, list(content.get("cards", [])))
    elif vt == "problem_cards":
        items = content.get("problem_items")
        if isinstance(items, list) and items and isinstance(items[0], dict):
            layout_engine.add_problem_structured_cards(slide, list(items))
        else:
            layout_engine.add_problem_cards(slide, list(content.get("problems", [])))
    elif vt == "process_flow":
        layout_engine.add_process_flow(slide, list(content.get("steps", [])))
    elif vt == "before_after":
        layout_engine.add_before_after(
            slide,
            list(content.get("before", [])),
            list(content.get("after", [])),
        )
    elif vt == "scope_matrix":
        layout_engine.add_scope_matrix(
            slide,
            list(content.get("included", [])),
            list(content.get("excluded", [])),
        )
    elif vt == "wbs_table":
        layout_engine.add_wbs_table(slide, list(content.get("rows", [])))
    elif vt == "gantt_like_timeline":
        layout_engine.add_process_flow(slide, list(content.get("milestones", content.get("steps", []))))
    elif vt == "budget_table":
        rows = list(content.get("rows", []))
        if content.get("kpis"):
            rows = rows[:5]
        layout_engine.add_budget_table(slide, rows)
        kpis = list(content.get("kpis") or [])
        if kpis:
            layout_engine.add_compact_kpis_below(slide, kpis)
    elif vt == "kpi_cards":
        layout_engine.add_kpi_cards(slide, list(content.get("kpis", [])))
    elif vt == "risk_matrix":
        layout_engine.add_risk_matrix(slide, list(content.get("risks", [])))
    elif vt == "conclusion_box":
        txt = str(content.get("text") or spec.key_message or "")
        layout_engine.add_conclusion_box(slide, txt)
    elif vt == "org_role_map":
        layout_engine.add_org_role_map(slide, list(content.get("roles", [])))
    elif vt == "architecture_block_diagram":
        layers = [str(x) for x in content.get("layers", content.get("blocks", []))]
        layout_engine.add_architecture_blocks(slide, layers)
    elif vt == "swimlane_process":
        layout_engine.add_swimlane_simple(slide, list(content.get("lanes", [])))
    elif vt == "comparison_table":
        headers = list(content.get("headers", ["항목", "AS-IS", "TO-BE"]))
        rows_raw = content.get("rows", [])
        rows: list[list[str]] = []
        for r in rows_raw:
            if isinstance(r, dict):
                rows.append([str(r.get("a", "")), str(r.get("b", "")), str(r.get("c", ""))])
            elif isinstance(r, list):
                rows.append([str(x) for x in r])
        layout_engine.add_comparison_table(slide, headers, rows or [["", "", ""]])
    elif vt == "priority_matrix":
        items = [str(x.get("name", x)) for x in content.get("items", []) if isinstance(x, dict)]
        if not items:
            items = [str(x) for x in content.get("items", [])] if isinstance(content.get("items"), list) else []
        layout_engine.add_priority_quadrant(slide, items)
    elif vt == "funnel_diagram":
        layout_engine.add_funnel_stages(slide, list(content.get("stages", [])))
    elif vt == "roadmap_timeline":
        phases = content.get("phases", [])
        if isinstance(phases, list) and phases and isinstance(phases[0], dict):
            labs = [f"{p.get('name', '')} ({p.get('period', '')})" for p in phases]
        else:
            labs = list(content.get("milestones", content.get("steps", [])))
        layout_engine.add_process_flow(slide, [str(x) for x in labs] if labs else ["Q1", "Q2", "Q3"])
    else:
        # 알 수 없는 타입도 빈 슬라이드만 두지 않도록 요약 카드로 채운다.
        layout_engine.add_summary_cards(
            slide,
            [{"title": "시각 유형", "body": vt}],
        )
