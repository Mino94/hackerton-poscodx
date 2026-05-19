"""Supervisor가 추적하는 전체 Agent 레지스트리 — 단계·산출물·대시보드 ID 매핑."""

from __future__ import annotations

from typing import Any

# order: 실행 순서 · dashboard_id: agent_progress.py 카드와 동기화
AGENT_REGISTRY: list[dict[str, Any]] = [
    {
        "id": "pm_orchestrator",
        "order": 1,
        "dashboard_id": "pm_orchestrator",
        "agent_key": "pm_orchestrator_agent",
        "task_key": "orchestrate_task",
        "state_field": "orchestration_brief",
        "display_name": "PM Orchestrator Agent",
        "phase_group": "core",
        "deliverable_label": "추진계획 구조·목차",
    },
    {
        "id": "requirement_interview",
        "order": 2,
        "dashboard_id": "requirement_interview",
        "agent_key": "requirement_interview_agent",
        "task_key": "requirement_task",
        "state_field": "requirement_analysis",
        "display_name": "Requirement Interview Agent",
        "phase_group": "core",
        "deliverable_label": "요구사항·누락·가정",
    },
    {
        "id": "business_analyst",
        "order": 3,
        "dashboard_id": "business_analyst",
        "agent_key": "business_analyst_agent",
        "task_key": "business_analysis_task",
        "state_field": "business_analysis",
        "display_name": "Business Analyst Agent",
        "phase_group": "core",
        "deliverable_label": "AS-IS·Pain·이해관계자",
    },
    {
        "id": "solution_architect",
        "order": 4,
        "dashboard_id": "solution_architect",
        "agent_key": "solution_architect_agent",
        "task_key": "solution_design_task",
        "state_field": "solution_direction",
        "display_name": "Solution Architect Agent",
        "phase_group": "core",
        "deliverable_label": "TO-BE·시스템 방향",
    },
    {
        "id": "development_scope",
        "order": 5,
        "dashboard_id": "development_scope",
        "agent_key": "development_scope_agent",
        "task_key": "development_scope_task",
        "state_field": "development_scope",
        "display_name": "Development Scope Agent",
        "phase_group": "core",
        "deliverable_label": "개발 범위 In/Out",
    },
    {
        "id": "wbs_planner",
        "order": 6,
        "dashboard_id": "wbs_planner",
        "agent_key": "wbs_planner_agent",
        "task_key": "wbs_task",
        "state_field": "wbs_plan",
        "display_name": "WBS Planner Agent",
        "phase_group": "core",
        "deliverable_label": "WBS·일정",
    },
    {
        "id": "budget_roi",
        "order": 7,
        "dashboard_id": "budget_roi",
        "agent_key": "budget_roi_agent",
        "task_key": "budget_roi_task",
        "state_field": "budget_roi",
        "display_name": "Budget & ROI Agent",
        "phase_group": "core",
        "deliverable_label": "예산·ROI·KPI",
    },
    {
        "id": "risk_critic",
        "order": 8,
        "dashboard_id": "risk_critic_doc",
        "agent_key": "risk_critic_agent",
        "task_key": "risk_critic_task",
        "state_field": "risk_management",
        "display_name": "Risk & Critic Agent",
        "phase_group": "core",
        "deliverable_label": "리스크 매트릭스",
    },
    {
        "id": "critic_gate",
        "order": 9,
        "dashboard_id": "risk_critic_doc",
        "agent_key": "critic_agent",
        "task_key": "critic_task",
        "state_field": "critic_review",
        "display_name": "Critic Agent (품질 게이트)",
        "phase_group": "quality",
        "deliverable_label": "Critic 평가",
    },
    {
        "id": "documentation",
        "order": 10,
        "dashboard_id": "risk_critic_doc",
        "agent_key": "documentation_agent",
        "task_key": "documentation_task",
        "state_field": "document_output",
        "display_name": "Documentation Agent",
        "phase_group": "quality",
        "deliverable_label": "추진계획서 Markdown",
    },
    {
        "id": "storyline",
        "order": 11,
        "dashboard_id": "storyline",
        "agent_key": "storyline_slide_planning_agent",
        "task_key": "slide_storyline_task",
        "state_field": "slide_storyline_raw",
        "display_name": "Storyline / Slide Planning Agent",
        "phase_group": "ppt",
        "deliverable_label": "슬라이드 스토리라인 JSON",
    },
    {
        "id": "visualization",
        "order": 12,
        "dashboard_id": "visualization",
        "agent_key": "visualization_agent",
        "task_key": "visualization_design_task",
        "state_field": "visualization_raw",
        "display_name": "Visualization Agent",
        "phase_group": "ppt",
        "deliverable_label": "visual_type·content",
    },
    {
        "id": "presentation_graphics",
        "order": 13,
        "dashboard_id": "presentation_graphics",
        "agent_key": "presentation_graphics_agent",
        "task_key": "presentation_graphics_task",
        "state_field": "presentation_graphics_raw",
        "display_name": "Presentation Graphics Agent",
        "phase_group": "ppt",
        "deliverable_label": "graphics_spec",
    },
    {
        "id": "ppt_composer",
        "order": 14,
        "dashboard_id": "ppt_composer",
        "agent_key": "ppt_composer_agent",
        "task_key": "ppt_composition_task",
        "state_field": "ppt_composer_raw",
        "display_name": "PPT Composer Agent",
        "phase_group": "ppt",
        "deliverable_label": "project_plan.pptx",
    },
]

_REGISTRY_BY_TASK: dict[str, dict[str, Any]] = {r["task_key"]: r for r in AGENT_REGISTRY}
_REGISTRY_BY_ID: dict[str, dict[str, Any]] = {r["id"]: r for r in AGENT_REGISTRY}


def get_registry_entry_by_task(task_key: str) -> dict[str, Any] | None:
    return _REGISTRY_BY_TASK.get(task_key)


def get_registry_entry_by_id(agent_id: str) -> dict[str, Any] | None:
    return _REGISTRY_BY_ID.get(agent_id)


__all__ = [
    "AGENT_REGISTRY",
    "get_registry_entry_by_task",
    "get_registry_entry_by_id",
]
