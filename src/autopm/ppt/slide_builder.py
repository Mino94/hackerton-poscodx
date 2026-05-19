"""business_plan → SlideDeckSpec JSON — 슬라이드별 content·bullet을 강제로 채운다."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from autopm.ppt.content_builder import build_business_plan, ensure_nonempty
from autopm.ppt.slide_schema import SlideDeckSpec, SlideSpec


def _bullets_from_key_points(bp_es: dict, summary: str, n: int = 5) -> list[str]:
    pts = list(bp_es.get("key_points") or [])
    out = [str(p).strip() for p in pts if str(p).strip()][:n]
    if summary and len(out) < 3:
        out.insert(0, summary[:300])
    while len(out) < 3:
        out.append(f"추진 포인트 {len(out)+1}: 범위·일정·효과를 단계적으로 확정한다.")
    return out[:n]


def build_slide_deck_spec(business_plan: dict[str, Any], options: dict[str, Any] | None = None) -> dict[str, Any]:
    options = options or {}
    subtitle = str(options.get("subtitle") or "AutoPM — 추진계획서")
    title = str(business_plan.get("project_title") or "AutoPM")

    es = business_plan.get("executive_summary") or {}
    bg = business_plan.get("background") or {}
    problems = business_plan.get("current_problems") or []
    as_is = business_plan.get("as_is") or {}
    to_be = business_plan.get("to_be") or {}
    scope = business_plan.get("development_scope") or {}
    wbs = business_plan.get("wbs") or []
    budget = business_plan.get("budget") or []
    kpis = business_plan.get("kpis") or []
    risks = business_plan.get("risks") or []
    critic = business_plan.get("critic_review") or {}
    recs = business_plan.get("recommendations") or []

    cards = []
    for i, kp in enumerate((es.get("key_points") or [])[:4]):
        cards.append({"title": f"요점 {i+1}", "body": str(kp)[:400]})
    if len(cards) < 3:
        cards = [
            {"title": "요약", "body": es.get("summary") or title},
            {"title": "배경", "body": bg.get("context", "")[:350] or "전략·운영 요구 반영"},
            {"title": "기대", "body": "데이터 신뢰성·업무 효율 개선"},
        ]

    prob_cards = []
    for p in problems[:6]:
        if isinstance(p, dict):
            prob_cards.append(
                {
                    "title": str(p.get("title", "문제"))[:80],
                    "body": f"{p.get('description', '')}\n영향: {p.get('impact', '')}"[:500],
                }
            )
        else:
            prob_cards.append({"title": f"이슈", "body": str(p)[:400]})

    prob_simple: list[str] = (
        [f"{p.get('title', '')}: {p.get('description', '')}"[:120] for p in problems if isinstance(p, dict)][:6]
        if problems and isinstance(problems[0], dict)
        else [str(x)[:120] for x in problems][:6]
        if problems
        else ["문제 정의 필요"]
    )
    prob_bullets: list[str] = (
        [str(p.get("title", f"Issue {i+1}")) for i, p in enumerate(problems[:5]) if isinstance(p, dict)]
        if problems and isinstance(problems[0], dict)
        else [str(x)[:120] for x in problems][:5]
        if problems
        else ["데이터·프로세스 상 문제를 구체화하세요."]
    )

    slides_spec: list[dict[str, Any]] = [
        {
            "slide_no": 1,
            "title": "Executive Summary",
            "objective": "경영진에게 과제·방향·기대효과를 한 장에 전달한다.",
            "key_message": es.get("summary") or title,
            "visual_type": "summary_cards",
            "content": {
                "cards": cards[:4],
                "bullets": _bullets_from_key_points(es, str(es.get("summary") or "")),
            },
        },
        {
            "slide_no": 2,
            "title": "추진 배경",
            "objective": "과제의 맥락·시점·전략 연계를 설명한다.",
            "key_message": bg.get("why_now") or bg.get("context") or "데이터·프로세스 기반 경쟁력 강화",
            "visual_type": "problem_cards",
            "content": {
                "problem_items": [
                    {"title": "맥락", "description": bg.get("context", ""), "impact": ""},
                    {"title": "시점", "description": bg.get("why_now", ""), "impact": ""},
                    {"title": "전략 정합", "description": bg.get("strategic_alignment", ""), "impact": ""},
                ],
                "bullets": [
                    bg.get("context", "")[:200],
                    bg.get("why_now", "")[:200],
                    bg.get("strategic_alignment", "")[:200] or "경영·운영 목표와 연계",
                ],
            },
        },
        {
            "slide_no": 3,
            "title": "현재 문제점",
            "objective": "핵심 pain을 구조화해 공감대를 만든다.",
            "key_message": "정합성·수작업·실시간성·표준화 이슈를 관리해야 한다.",
            "visual_type": "problem_cards",
            "content": {
                "problem_items": prob_cards,
                "problems": prob_simple,
                "bullets": prob_bullets,
            },
        },
        {
            "slide_no": 4,
            "title": "AS-IS 프로세스",
            "objective": "현재 업무 흐름과 병목을 시각화한다.",
            "key_message": as_is.get("summary") or "현행 흐름을 단계별로 정리한다.",
            "visual_type": "process_flow",
            "content": {
                "steps": list(as_is.get("steps") or [])[:8] or ["입력", "처리", "검증", "보고"],
                "pain_points": list(as_is.get("pain_points") or [])[:5],
                "bullets": list((as_is.get("steps") or [])[:4])
                + [f"Pain: {p}" for p in (as_is.get("pain_points") or [])[:2]],
            },
        },
        {
            "slide_no": 5,
            "title": "TO-BE 프로세스",
            "objective": "개선 후 이상적 흐름·자동화 포인트를 보여 준다.",
            "key_message": to_be.get("summary") or "자동화·표준화된 목표 운영 모델",
            "visual_type": "process_flow",
            "content": {
                "steps": list(to_be.get("steps") or [])[:8] or ["수집", "검증", "알림", "리포트"],
                "improvements": list(to_be.get("improvements") or [])[:5],
                "bullets": list((to_be.get("steps") or [])[:3])
                + [str(x) for x in (to_be.get("improvements") or [])[:3]],
            },
        },
        {
            "slide_no": 6,
            "title": "개발 범위",
            "objective": "포함·제외 범위를 명확히 하여 승인 리스크를 줄인다.",
            "key_message": "MVP·모듈 단위로 범위를 고정한다.",
            "visual_type": "scope_matrix",
            "content": {
                "included": list(scope.get("included") or [])[:12] or ["핵심 기능"],
                "excluded": list(scope.get("excluded") or [])[:12] or ["범위 외"],
                "modules": list(scope.get("modules") or [])[:6],
                "bullets": (scope.get("included") or [])[:4] + (scope.get("excluded") or [])[:2],
            },
        },
        {
            "slide_no": 7,
            "title": "WBS / 추진 일정",
            "objective": "단계·기간·산출물을 표로 제시한다.",
            "key_message": "마일스톤·RACI를 문서화한다.",
            "visual_type": "wbs_table",
            "content": {
                "rows": wbs[:10]
                if wbs
                else [
                    {
                        "phase": "1",
                        "task": "착수",
                        "duration": "1주",
                        "owner": "PM",
                        "deliverable": "계획",
                    }
                ],
                "bullets": [f"{r.get('phase', '')} {r.get('task', '')}" for r in wbs[:5]],
            },
        },
        {
            "slide_no": 8,
            "title": "예산 및 ROI",
            "objective": "비용 항목과 KPI로 투자 납득을 돕는다.",
            "key_message": "비용·효과는 가정 기반으로 명시한다.",
            "visual_type": "budget_table",
            "content": {
                "rows": budget[:8]
                if budget
                else [{"item": "구현", "cost": "협의", "description": "MVP"}],
                "kpis": kpis[:6],
                "bullets": [f"{b.get('item', '')}: {b.get('cost', '')}" for b in budget[:4]],
            },
        },
        {
            "slide_no": 9,
            "title": "리스크 및 대응",
            "objective": "상위 리스크와 완화 전략을 한눈에 보여 준다.",
            "key_message": "품질·일정·조직 리스크를 관리한다.",
            "visual_type": "risk_matrix",
            "content": {
                "risks": risks[:8]
                if risks
                else [{"risk": "범위 증가", "probability": "중", "impact": "중", "response": "MVP 고정"}],
                "bullets": [str(r.get("risk", ""))[:100] for r in risks[:5]],
            },
        },
        {
            "slide_no": 10,
            "title": "기대효과 및 결론",
            "objective": "KPI·요청사항·Critic 요약으로 마무리한다.",
            "key_message": critic.get("final_opinion") or "다음 액션·승인 요청",
            "visual_type": "before_after",
            "content": {
                "before": [f"{k.get('name', '')}: 현재 {k.get('current', '')}" for k in kpis[:4]],
                "after": [f"{k.get('name', '')}: 목표 {k.get('target', '')} — {k.get('effect', '')}" for k in kpis[:4]],
                "bullets": list(recs)[:5] + [critic.get("final_opinion", "")[:200]],
            },
        },
        {
            "slide_no": 11,
            "title": "Critic Review",
            "objective": "품질 검토·보완 포인트를 투명히 공유한다.",
            "key_message": f"품질 점수 {critic.get('score', 0)} — 보완 후 승인 가능성 향상",
            "visual_type": "conclusion_box",
            "content": {
                "text": "\n".join(
                    [
                        critic.get("final_opinion", ""),
                        "",
                        "누락: " + "; ".join(critic.get("missing_items") or [])[:500],
                        "제안: " + "; ".join(critic.get("suggestions") or [])[:500],
                    ]
                )[:3500],
                "bullets": list(critic.get("suggestions") or [])[:5] or list(critic.get("missing_items") or [])[:5],
            },
        },
    ]

    return {"project_title": title, "subtitle": subtitle, "slides": slides_spec}


def _slide_content_nonempty(slide: SlideSpec) -> bool:
    c = slide.content or {}
    if c.get("bullets"):
        return len([b for b in c["bullets"] if str(b).strip()]) > 0
    for k in ("cards", "rows", "steps", "risks", "kpis", "included", "problems", "problem_items"):
        v = c.get(k)
        if isinstance(v, list) and len(v) > 0:
            return True
    if c.get("text"):
        return bool(str(c["text"]).strip())
    if c.get("before") or c.get("after"):
        return True
    return False


def validate_slide_deck_content(deck_dict: dict[str, Any]) -> tuple[bool, list[str], dict[str, Any]]:
    """덱 검증 + coverage 메타."""
    errs: list[str] = []
    slides_raw = deck_dict.get("slides") or []
    n = len(slides_raw)
    if n < 10:
        errs.append(f"슬라이드 수 부족: {n} (<10)")

    filled = 0
    empty_c = 0
    tables = 0
    cards_viz = 0
    has_wbs = False
    has_budget = False
    has_risk = False
    # AS-IS / TO-BE 프로세스 슬라이드는 각각 steps ≥3 이어야 한다.
    as_is_steps_ok = False
    to_be_steps_ok = False

    def _txt(val: object) -> str:
        return val if isinstance(val, str) else str(val or "")

    for s in slides_raw:
        if not isinstance(s, dict):
            continue
        title = _txt(s.get("title")).strip()
        if not title:
            errs.append("제목 누락 슬라이드 존재")
        if not (_txt(s.get("key_message")) or _txt(s.get("objective"))).strip():
            errs.append(f"key_message 부족: {title or s.get('slide_no')}")
        try:
            sp = SlideSpec.model_validate(s)
        except Exception:
            errs.append(f"SlideSpec 파싱 실패: {title}")
            continue
        if _slide_content_nonempty(sp):
            filled += 1
        else:
            empty_c += 1
            errs.append(f"content 비어 있음: {title}")
        vt = (sp.visual_type or "").lower()
        if vt == "wbs_table":
            has_wbs = bool((sp.content or {}).get("rows"))
            if len((sp.content or {}).get("rows") or []) < 3:
                errs.append("WBS rows 3개 미만")
        if vt == "budget_table":
            has_budget = bool((sp.content or {}).get("rows"))
            if len((sp.content or {}).get("rows") or []) < 3:
                errs.append("예산 rows 3개 미만")
        if vt == "risk_matrix":
            has_risk = bool((sp.content or {}).get("risks"))
            if len((sp.content or {}).get("risks") or []) < 3:
                errs.append("리스크 3개 미만")
        if vt == "process_flow":
            st = sp.title or ""
            steps_list = (sp.content or {}).get("steps") or []
            if len(steps_list) < 3:
                errs.append(f"프로세스 steps 3개 미만: {sp.title}")
            if "AS-IS" in st and len(steps_list) >= 3:
                as_is_steps_ok = True
            if "TO-BE" in st and len(steps_list) >= 3:
                to_be_steps_ok = True
        if vt in ("summary_cards", "problem_cards", "kpi_cards"):
            cards_viz += 1
        if vt in ("wbs_table", "risk_matrix", "budget_table"):
            tables += 1

    report = {
        "total_slides": n,
        "slides_with_body": filled,
        "empty_content_slides": empty_c,
        "table_like_slides": tables,
        "card_like_slides": cards_viz,
        "has_wbs_data": has_wbs,
        "has_budget_data": has_budget,
        "has_risk_data": has_risk,
        "has_process_steps": as_is_steps_ok and to_be_steps_ok,
        "errors": errs,
        "passed": len(errs) == 0,
    }
    return len(errs) == 0, errs, report


def repair_slide_deck_from_business_plan(deck_dict: dict[str, Any], business_plan: dict[str, Any]) -> dict[str, Any]:
    """검증 실패 시 business_plan에서 덱을 재생성."""
    fresh = build_slide_deck_spec(business_plan, {"subtitle": deck_dict.get("subtitle")})
    return fresh


def ensure_valid_deck(deck_dict: dict[str, Any], business_plan: dict[str, Any]) -> dict[str, Any]:
    ok, errs, _ = validate_slide_deck_content(deck_dict)
    if ok:
        return deck_dict
    merged_bp = deepcopy(business_plan)
    ensure_nonempty(merged_bp, {})
    fixed = repair_slide_deck_from_business_plan(deck_dict, merged_bp)
    ok2, errs2, _ = validate_slide_deck_content(fixed)
    if not ok2:
        hard = build_slide_deck_spec(build_business_plan({"proposal_title": deck_dict.get("project_title", "AutoPM")}, None), {})
        return hard
    return fixed


def merge_llm_deck_graphics(base_dict: dict[str, Any], llm_deck: SlideDeckSpec | None) -> dict[str, Any]:
    """LLM 덱의 graphics_spec·키메시지만 얹는다 — 본문은 base 우선."""
    if llm_deck is None or not llm_deck.slides:
        return base_dict
    by_no = {s.slide_no: s for s in llm_deck.slides}
    slides_out = []
    for sdict in base_dict.get("slides") or []:
        sn = int(sdict.get("slide_no") or 0)
        extra = by_no.get(sn)
        if extra:
            if extra.graphics_spec:
                sdict = dict(sdict)
                sdict["graphics_spec"] = extra.graphics_spec
            km_extra = extra.key_message if isinstance(extra.key_message, str) else str(extra.key_message or "")
            km_base = sdict.get("key_message")
            km_base_s = km_base if isinstance(km_base, str) else str(km_base or "")
            if km_extra.strip() and len(km_extra) > len(km_base_s):
                sdict = dict(sdict)
                sdict["key_message"] = km_extra
        slides_out.append(sdict)
    out = dict(base_dict)
    out["slides"] = slides_out
    return out
