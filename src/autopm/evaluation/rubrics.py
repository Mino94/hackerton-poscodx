"""Agent·PPT 단계별 평가 루브릭 — 점수 임계값과 checklist ID를 정의한다."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rubric:
    """한 Agent(또는 단계)에 대한 최소 통과 점수와 설명 — harness가 checklist와 매칭한다."""

    agent_id: str
    display_name: str
    pass_threshold: float
    description: str
    criteria_ids: tuple[str, ...]


# 스펙의 11개 Agent + 최종 PPT — criteria_id는 scoring/validators에서 동일 키로 사용한다.
CORE_AGENT_RUBRICS: dict[str, Rubric] = {
    "requirement": Rubric(
        "requirement",
        "Requirement Interview Agent",
        80.0,
        "요약·누락·질문·맥락",
        (
            "req_has_summary",
            "req_identifies_gaps",
            "req_followup_questions",
            "req_context_sane",
        ),
    ),
    "business": Rubric(
        "business",
        "Business Analyst Agent",
        80.0,
        "AS-IS·Pain·이해관계자",
        (
            "ba_as_is_concrete",
            "ba_three_pains",
            "ba_pain_dimensions",
            "ba_stakeholders",
        ),
    ),
    "solution": Rubric(
        "solution",
        "Solution Architect Agent",
        80.0,
        "TO-BE·실행·자동화·시스템",
        (
            "sa_tobe_addresses",
            "sa_actionable",
            "sa_automation_scope",
            "sa_system_direction",
        ),
    ),
    "scope": Rubric(
        "scope",
        "Development Scope Agent",
        80.0,
        "포함·제외·MVP·기능",
        (
            "ds_in_scope_clear",
            "ds_out_scope",
            "ds_mvp_realistic",
            "ds_key_features",
        ),
    ),
    "wbs": Rubric(
        "wbs",
        "WBS Planner Agent",
        80.0,
        "일정·담당·산출물·현실성",
        (
            "wbs_phases",
            "wbs_owners",
            "wbs_deliverables",
            "wbs_time_realistic",
        ),
    ),
    "budget": Rubric(
        "budget",
        "Budget & ROI Agent",
        75.0,
        "예산·가정·ROI·KPI",
        (
            "br_items",
            "br_assumption_tag",
            "br_roi_or_saving",
            "br_three_kpis",
            "br_not_hyperbole",
        ),
    ),
    "risk": Rubric(
        "risk",
        "Risk & Critic Agent",
        80.0,
        "리스크 수·매트릭스·대응·Critic",
        (
            "rk_four_risks",
            "rk_likelihood_impact",
            "rk_mitigation",
            "rk_critic_hints",
        ),
    ),
}

PPT_CHAIN_RUBRICS: dict[str, Rubric] = {
    "storyline": Rubric(
        "storyline",
        "Storyline Agent",
        85.0,
        "10장+·필드·흐름·중복",
        (
            "st_min_slides",
            "st_slide_fields",
            "st_flow_ok",
            "st_no_dup_titles",
        ),
    ),
    "visualization": Rubric(
        "visualization",
        "Visualization Agent",
        85.0,
        "visual_type·적합성",
        (
            "viz_has_types",
            "viz_type_sane",
            "viz_layout_mix",
        ),
    ),
    "presentation_graphics": Rubric(
        "presentation_graphics",
        "Presentation Graphics Agent",
        85.0,
        "graphics_spec·삽입가능",
        (
            "pg_graphics_spec",
            "pg_shapes_or_assets",
            "pg_fallback_friendly",
        ),
    ),
    "ppt_composer": Rubric(
        "ppt_composer",
        "PPT Composer",
        85.0,
        "pptx·10장+·장표 다양성",
        (
            "pc_pptx_exists",
            "pc_min_slides",
            "pc_key_slides",
            "pc_not_text_only",
            "pc_charts_tables",
        ),
    ),
}

FINAL_PPT_PASS_SCORE = 85.0

# 최종 덱 필수 토픽(슬라이드 제목/키메시지에 키워드 존재) — 휴리스틱.
FINAL_SLIDE_TOPIC_KEYWORDS: tuple[tuple[str, ...], ...] = (
    ("executive", "요약", "summary"),
    ("문제", "pain", "현황"),
    ("as-is", "asis", "현재"),
    ("to-be", "tobe", "개선"),
    ("범위", "scope", "mvp"),
    ("wbs", "일정", "마일"),
    ("예산", "roi", "비용"),
    ("리스크", "risk"),
    ("효과", "kpi", "기대"),
    ("결론", "요청", "다음"),
)
