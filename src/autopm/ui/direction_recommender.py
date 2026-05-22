"""주제 1줄 입력 → 키워드·메타 분석으로 추천 추진계획 방향 후보 생성."""

from __future__ import annotations

import re
from typing import Any

from autopm.chat.interview_bot import extract_from_initial_text
from autopm.chat.proposal_extract import extract_title_metadata
from autopm.ui.direction_presets import DirectionPreset, get_direction_preset

# 아키타입별 가중 키워드 — 주제와 매칭 점수
_ARCHETYPE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "erp_validation": (
        "erp",
        "월마감",
        "마감",
        "검증",
        "데이터",
        "bom",
        "재고",
        "엑셀",
        "정합",
    ),
    "cost_system": (
        "원가",
        "결산",
        "단가",
        "수불",
        "mini erp",
        "minierp",
        "경영",
        "보고",
    ),
    "ai_quality": (
        "ai",
        "인공지능",
        "머신",
        "이상",
        "탐지",
        "품질",
        "룰",
        "규칙",
        "오류",
    ),
    "process_rpa": (
        "rpa",
        "자동화",
        "프로세스",
        "워크플로",
        "반복",
        "sop",
        "배치",
    ),
    "budget_approval": (
        "예산",
        "투자",
        "roi",
        "승인",
        "비용",
        "절감",
        "가성비",
    ),
    "exec_strategy": (
        "전략",
        "경영",
        "미래",
        "거버넌스",
        "kpi",
        "의사결정",
        "디지털",
        "변혁",
    ),
}

# 표시 순서 (점수 동점 시)
_ARCHETYPE_ORDER: tuple[str, ...] = (
    "erp_validation",
    "process_rpa",
    "ai_quality",
    "cost_system",
    "budget_approval",
    "exec_strategy",
)


def _topic_title_line(topic: str) -> str:
    """첫 줄을 추진계획서 제목으로 쓴다."""
    line = (topic or "").strip().split("\n")[0].strip()
    if len(line) > 120:
        line = line[:117] + "…"
    return line or "업무 개선 추진계획"


def _topic_snippet(topic: str, max_len: int = 200) -> str:
    t = re.sub(r"\s+", " ", (topic or "").strip())
    return t[:max_len] if len(t) > max_len else t


def _score_archetypes(topic: str) -> list[tuple[str, int]]:
    t = (topic or "").lower()
    scores: list[tuple[str, int]] = []
    for aid, keys in _ARCHETYPE_KEYWORDS.items():
        s = sum(1 for k in keys if k.lower() in t)
        scores.append((aid, s))
    scores.sort(key=lambda x: (-x[1], _ARCHETYPE_ORDER.index(x[0])))
    return scores


def _build_fields_for_archetype(topic: str, archetype_id: str) -> dict[str, Any]:
    """주제 + 아키타입 템플릿으로 인터뷰 필드 dict 생성."""
    base_preset = get_direction_preset(archetype_id)
    if base_preset is None:
        return {"proposal_title": _topic_title_line(topic)}

    fields = dict(base_preset.fields)
    title = _topic_title_line(topic)
    snippet = _topic_snippet(topic)
    hints = extract_from_initial_text(topic)
    meta = extract_title_metadata(topic)

    fields["proposal_title"] = title
    fields["idea_title"] = title

    # 주제 본문을 배경에 반영
    if snippet:
        fields["background_context"] = (
            f"{snippet}\n\n"
            f"(추천 방향: {base_preset.label} — {base_preset.tagline})"
        )

    if meta.get("target_system"):
        fields["target_system"] = str(meta["target_system"])
    elif hints.get("target_system"):
        fields["target_system"] = str(hints["target_system"])

    if "자동화" in topic and archetype_id == "process_rpa":
        fields.setdefault("improvement_direction", "프로세스·반복 업무 자동화 및 표준화")
    if "검증" in topic or "월마감" in topic:
        if not fields.get("current_problems"):
            fields["current_problems"] = (
                "수작업·담당자별 기준 차이로 검증 시간이 길고 오류가 누락될 수 있음"
            )

    if meta.get("likely_tone") and archetype_id == "exec_strategy":
        fields["presentation_tone"] = "경영진 보고형"
    if hints.get("timeline"):
        fields["timeline"] = str(hints["timeline"])
    if hints.get("budget_range"):
        fields["budget_range"] = str(hints["budget_range"])

    if meta.get("target_company"):
        fields.setdefault(
            "target_audience",
            f"{meta['target_company']} 관련 부서·의사결정자",
        )

    return fields


def _label_for_topic(topic: str, archetype_id: str, base: DirectionPreset) -> str:
    """주제에 맞게 카드 제목을 살짝 다듬는다."""
    title = _topic_title_line(topic)
    short = title if len(title) <= 36 else title[:33] + "…"
    suffix = {
        "erp_validation": "검증·월마감 자동화",
        "cost_system": "원가·시스템 개선",
        "ai_quality": "AI·품질 검증",
        "process_rpa": "프로세스·RPA",
        "budget_approval": "예산·ROI 승인",
        "exec_strategy": "전략·경영 보고",
    }.get(archetype_id, base.label)
    return f"{short} — {suffix}"


def recommend_directions_for_topic(topic: str, *, max_count: int = 6) -> list[DirectionPreset]:
    """
    주제 문자열을 분석해 추천 방향 프리셋 목록을 반환한다.
    점수 상위 아키타입을 주제에 맞게 필드 커스터마이즈한다.
    """
    topic = (topic or "").strip()
    if not topic:
        topic = "업무 프로세스 개선"

    scored = _score_archetypes(topic)
    # 점수 0인 것도 최소 4개는 보여 주기 위해 상위 + 기본 순서 병합
    seen: set[str] = set()
    ordered_ids: list[str] = []
    for aid, sc in scored:
        if sc > 0 and aid not in seen:
            ordered_ids.append(aid)
            seen.add(aid)
    for aid in _ARCHETYPE_ORDER:
        if aid not in seen:
            ordered_ids.append(aid)
            seen.add(aid)
    ordered_ids = ordered_ids[:max_count]

    out: list[DirectionPreset] = []
    for aid in ordered_ids:
        base = get_direction_preset(aid)
        if base is None:
            continue
        fields = _build_fields_for_archetype(topic, aid)
        label = _label_for_topic(topic, aid, base)
        tagline = f"{base.tagline} · 주제 맞춤"
        out.append(
            DirectionPreset(
                id=f"rec_{aid}",
                label=label,
                icon=base.icon,
                tagline=tagline,
                highlights=base.highlights,
                fields=fields,
                bulk_preset=base.bulk_preset,
            )
        )
    return out


def preset_to_session_dict(p: DirectionPreset) -> dict[str, Any]:
    """Streamlit session_state 저장용."""
    return {
        "id": p.id,
        "label": p.label,
        "icon": p.icon,
        "tagline": p.tagline,
        "highlights": list(p.highlights),
        "fields": dict(p.fields),
        "bulk_preset": p.bulk_preset,
    }


def preset_from_session_dict(d: dict[str, Any]) -> DirectionPreset:
    return DirectionPreset(
        id=str(d["id"]),
        label=str(d["label"]),
        icon=str(d["icon"]),
        tagline=str(d["tagline"]),
        highlights=tuple(d.get("highlights") or ()),
        fields=dict(d.get("fields") or {}),
        bulk_preset=str(d.get("bulk_preset") or "to_ppt"),
    )


def resolve_preset_for_run(
    preset_id: str,
    session_recommendations: list[dict[str, Any]] | None = None,
) -> DirectionPreset | None:
    """자동 생성 시 세션 추천 목록 또는 정적 프리셋에서 DirectionPreset을 찾는다."""
    for raw in session_recommendations or []:
        if raw.get("id") == preset_id:
            return preset_from_session_dict(raw)
    if preset_id.startswith("rec_"):
        return get_direction_preset(preset_id[4:])
    return get_direction_preset(preset_id)


__all__ = [
    "recommend_directions_for_topic",
    "preset_to_session_dict",
    "preset_from_session_dict",
    "resolve_preset_for_run",
]
