"""
visual_type → 렌더 전략 매핑 — 18종 유형 정의와 기본 graphics_spec 생성.

각 타입별로:
- 필요한 content 키(개념적)
- 기본 render_mode: ppt_shapes 우선, 일부는 matplotlib_png 시도
- python-pptx 직접 도형 vs PNG는 visual_registry + graphics_agent에서 일관되게 결정한다.
"""

from __future__ import annotations

from typing import Any

from autopm.ppt.chart_renderer import render_budget_bar_png, render_kpi_bullet_png, render_placeholder_png
from autopm.ppt.diagram_renderer import render_architecture_blocks_png, render_process_flow_png
from autopm.ppt.slide_schema import SlideSpec

# 지원 visual_type (Visualization Agent가 다른 키를 주면 normalize에서 매핑)
VISUAL_TYPES: dict[str, str] = {
    "summary_cards": "요약 카드 — content.cards[{title,body}]",
    "problem_cards": "문제 카드 — content.problems[]",
    "process_flow": "프로세스 — content.steps[]",
    "before_after": "비교 — content.before[], after[]",
    "scope_matrix": "범위 — content.included[], excluded[]",
    "wbs_table": "WBS 표 — content.rows[]",
    "gantt_like_timeline": "일정 바 — content.milestones[] 또는 steps",
    "budget_table": "예산 표 — content.rows[] ; 선택적 matplotlib 막대",
    "kpi_cards": "KPI — content.kpis[] ; 선택적 matplotlib 요약 PNG",
    "risk_matrix": "리스크 표 — content.risks[]",
    "org_role_map": "조직/역할 — content.roles[{name, responsibility}]",
    "architecture_block_diagram": "아키텍처 블록 — content.layers[]",
    "swimlane_process": "swimlane — content.lanes[{name, steps:[]}]",
    "comparison_table": "비교 표 — content.headers[], rows[]",
    "priority_matrix": "우선순위 2x2 — content.items[{name,x,y}] 간소화 시 카드",
    "funnel_diagram": "퍼널 — content.stages[]",
    "roadmap_timeline": "로드맵 — content.phases[{name,period}]",
    "conclusion_box": "결론 텍스트 — content.text",
}

# 레거시 timeline → gantt_like_timeline
_ALIASES: dict[str, str] = {
    "timeline": "gantt_like_timeline",
}


def normalize_visual_type(raw: str) -> str:
    """LLM이 예전 키를 쓰면 신규 레지스트리 키로 정규화한다."""
    v = (raw or "summary_cards").strip()
    v = _ALIASES.get(v, v)
    if v in VISUAL_TYPES:
        return v
    return "summary_cards"


def build_elements_for_process(steps: list[str]) -> list[dict[str, Any]]:
    """graphics_spec.elements — ppt_shapes 파이프라인용."""
    els: list[dict[str, Any]] = []
    for i, s in enumerate(steps):
        els.append({"type": "rounded_box", "label": s[:120]})
        if i < len(steps) - 1:
            els.append({"type": "arrow"})
    return els


def default_graphics_spec_for_slide(slide: SlideSpec) -> dict[str, Any]:
    """LLM이 graphics_spec을 비웠을 때 결정론적으로 채운다 — 데모·API 실패 시에도 동일 품질."""
    vt = normalize_visual_type(slide.visual_type)
    content = slide.content or {}
    style = "clean_b2b"

    if vt == "process_flow":
        steps = list(content.get("steps", []))
        return {
            "render_mode": "ppt_shapes",
            "asset_type": "diagram",
            "style": style,
            "elements": build_elements_for_process([str(s) for s in steps] if steps else ["단계1", "단계2"]),
        }
    if vt == "before_after":
        return {
            "render_mode": "ppt_shapes",
            "asset_type": "comparison",
            "style": style,
            "notes": "layout_engine.add_before_after",
        }
    if vt == "risk_matrix":
        return {
            "render_mode": "ppt_shapes",
            "asset_type": "matrix",
            "style": style,
            "notes": "layout_engine.add_risk_matrix",
        }
    if vt == "budget_table":
        return {
            "render_mode": "hybrid",
            "asset_type": "chart",
            "style": style,
            "notes": "표는 ppt_shapes, 선택적 matplotlib PNG",
        }
    if vt == "kpi_cards":
        return {
            "render_mode": "hybrid",
            "asset_type": "kpi_cards",
            "style": style,
        }
    if vt == "architecture_block_diagram":
        layers = list(content.get("layers", content.get("blocks", [])))
        if not layers:
            layers = ["채널/UI", "검증 서비스", "ERP/마스터 데이터"]
        els = []
        for lay in layers:
            els.append({"type": "rounded_box", "label": str(lay)[:80]})
            els.append({"type": "arrow_down"})
        if els and els[-1]["type"] == "arrow_down":
            els.pop()
        return {
            "render_mode": "ppt_shapes",
            "asset_type": "diagram",
            "style": style,
            "elements": els,
        }
    if vt in ("gantt_like_timeline", "roadmap_timeline"):
        milestones = content.get("milestones") or content.get("phases") or content.get("steps") or []
        labs = [str(m.get("name", m) if isinstance(m, dict) else m) for m in milestones][:8]
        if not labs:
            labs = ["주1", "주2", "주3", "주4"]
        return {
            "render_mode": "ppt_shapes",
            "asset_type": "timeline",
            "style": style,
            "elements": build_elements_for_process(labs),
        }
    if vt == "swimlane_process":
        lanes = content.get("lanes") or []
        steps_flat: list[str] = []
        if isinstance(lanes, list):
            for ln in lanes[:4]:
                if isinstance(ln, dict):
                    steps_flat.append(f"{ln.get('name', '')}: " + ", ".join(map(str, ln.get("steps", [])[:3])))
        if not steps_flat:
            steps_flat = ["현업: 입력", "IT: 검증", "운영: 승인"]
        return {
            "render_mode": "matplotlib_png",
            "asset_type": "diagram",
            "style": style,
            "fallback_elements": build_elements_for_process(steps_flat),
        }
    if vt == "comparison_table":
        return {
            "render_mode": "ppt_shapes",
            "asset_type": "table",
            "style": style,
        }
    if vt == "org_role_map":
        roles = content.get("roles") or content.get("org", [])
        labels = []
        if isinstance(roles, list):
            for r in roles[:6]:
                if isinstance(r, dict):
                    labels.append(str(r.get("name", r.get("role", "")))[:40])
                else:
                    labels.append(str(r)[:40])
        if not labels:
            labels = ["스폰서", "PM", "현업", "IT"]
        return {
            "render_mode": "ppt_shapes",
            "asset_type": "diagram",
            "style": style,
            "elements": build_elements_for_process(labels),
        }
    if vt == "funnel_diagram":
        stages = [str(s) for s in content.get("stages", [])][:5]
        if not stages:
            stages = ["후보", "검증", "배포", "안정화"]
        return {
            "render_mode": "ppt_shapes",
            "asset_type": "funnel",
            "style": style,
            "elements": [{"type": "trapezoid", "label": x} for x in stages],
        }
    if vt == "priority_matrix":
        return {
            "render_mode": "ppt_shapes",
            "asset_type": "matrix",
            "style": style,
            "notes": "2x2 축은 ppt 도형; 항목은 카드 요약",
        }
    return {
        "render_mode": "ppt_shapes",
        "asset_type": "cards",
        "style": style,
        "notes": f"default for {vt}",
    }


def try_render_asset_png(
    slide_no: int,
    slide: SlideSpec,
    abs_out: Any,
) -> tuple[str | None, str]:
    """
    선택적 PNG 생성 — (상대 경로 문자열 또는 None, render_mode 힌트).
    abs_out: Path (절대 경로 PNG).
    """
    _ = slide_no  # 파일명은 호출자에서 결정 — 시그니처만 슬라이드 번호 노출
    vt = normalize_visual_type(slide.visual_type)
    content = slide.content or {}
    gs = slide.graphics_spec or {}
    try:
        if vt == "process_flow" and gs.get("render_mode") == "matplotlib_png":
            steps = list(content.get("steps", []))
            ok = render_process_flow_png(abs_out, [str(s) for s in steps], title=slide.title)
            return ("outputs/assets/" + abs_out.name, "matplotlib_png") if ok else (None, "ppt_shapes")
        if vt == "budget_table":
            rows = list(content.get("rows", []))
            rel = "outputs/assets/" + abs_out.name
            if render_budget_bar_png(abs_out, rows, title=slide.title):
                return (rel, "matplotlib_png")
            lines = [
                f"{str(r.get('item', r.get('항목', '')))}: {str(r.get('cost', r.get('예상 비용', '')))}"
                for r in rows[:10]
            ]
            if render_placeholder_png(abs_out, lines or ["(예산 행 없음 — 텍스트 폴백)"], title=slide.title):
                return (rel, "pillow_png")
            return (None, "ppt_shapes")
        if vt == "kpi_cards":
            kpis = list(content.get("kpis", []))
            rel = "outputs/assets/" + abs_out.name
            if render_kpi_bullet_png(abs_out, kpis, title=slide.title):
                return (rel, "matplotlib_png")
            lines = [
                f"{k.get('name','KPI')}: {k.get('current','')} → {k.get('target','')}"
                for k in kpis
                if isinstance(k, dict)
            ]
            if render_placeholder_png(abs_out, lines or ["(KPI 없음)"], title=slide.title):
                return (rel, "pillow_png")
            return (None, "ppt_shapes")
        if vt == "architecture_block_diagram":
            layers = list(content.get("layers", content.get("blocks", [])))
            rel = "outputs/assets/" + abs_out.name
            if render_architecture_blocks_png(abs_out, [str(x) for x in layers], title=slide.title):
                return (rel, "matplotlib_png")
            if render_placeholder_png(abs_out, [str(x) for x in layers] or ["Layer A", "Layer B"], title=slide.title):
                return (rel, "pillow_png")
            return (None, "ppt_shapes")
        if vt == "swimlane_process":
            ok = render_process_flow_png(
                abs_out,
                [str(x) for x in (content.get("lanes") or ["Lane A", "Lane B"])],
                title=slide.title,
            )
            return ("outputs/assets/" + abs_out.name, "matplotlib_png") if ok else (None, "ppt_shapes")
    except Exception:
        return None, "ppt_shapes"
    return None, "ppt_shapes"
