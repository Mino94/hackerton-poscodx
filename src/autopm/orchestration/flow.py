"""AutoPMFlow — Deep Agents 순차 파이프라인 + Agent 대화 + Critic Self-Correction + 문서화."""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from autopm.agents.agent_factory import build_all_agent_defs
from autopm.orchestration.deep_pipeline import (
    run_deep_critic,
    run_deep_documentation,
    run_deep_improvement,
    run_deep_pipeline,
    run_deep_single_task,
)
from autopm.data.cache_store import save_autopm_checkpoint
from autopm.data.object_storage import outputs_dir
from autopm.data.relational_store import save_project_meta
from autopm.run_result import AutoPMRunResult
from autopm.orchestration.quality_gate import evaluate_gate
from autopm.orchestration.state import AutoPMState
from autopm.orchestration.supervisor_manager import (
    init_supervisor,
    run_supervisor_checkpoint,
)
from autopm.evaluation.harness import EvaluationHarness, StageHarnessSnapshot, run_harness_improvement_loop
from autopm.services.export_service import (
    append_ppt_slide_section,
    export_business_plan_json,
    export_content_coverage_json,
    export_evaluation_reports,
    export_run_artifacts,
    export_slide_plan_json,
    export_visual_assets_json,
)
from autopm.services.llm_router import (
    generate_with_best_available_model,
    get_openai_llm_or_none,
    refine_draft_for_user_choice,
)
from autopm.services.observability import log, record_phase_ms
from autopm.services.prompt_manager import load_tasks
from autopm.tools.calculation_engine import estimate_rough_cost
from autopm.tools.document_parser import sample_parse_for_demo
from autopm.tools.rag_engine import keyword_search
from autopm.tools.visualization_generator import markdown_gantt_placeholder
from autopm.ppt.asset_manifest import VisualAssetsManifest
from autopm.ppt.content_builder import build_business_plan
from autopm.ppt.deck_json import deck_from_llm_chain
from autopm.ppt.graphics_agent import enrich_graphics_pipeline
from autopm.ppt.ppt_composer import build_fallback_slide_deck, create_project_plan_ppt
from autopm.ppt.slide_builder import (
    build_slide_deck_spec,
    ensure_valid_deck,
    merge_llm_deck_graphics,
    validate_slide_deck_content,
)
from autopm.ppt.slide_plan_adjust import adjust_storyline_slide_count
from autopm.ppt.slide_schema import SlideDeckSpec
from autopm.state.decision_enrichment import apply_decisions_to_enriched
from autopm.state.ppt_generation_state import (
    PHASE_COMPOSER,
    PHASE_CORE_DOC,
    PHASE_DRAFT_ONLY,
    PHASE_FULL_AUTO,
    PHASE_GRAPHICS,
    PHASE_IMPROVE_CHAIN,
    PHASE_REFINE_DRAFT,
    PHASE_STORYLINE,
    PHASE_VISUALIZATION,
    PPTGenerationState,
)

# 파이프라인 태스크 키와 State 필드 매핑 — AGENTS.md 8단계 Core PM 흐름
_PIPELINE_KEYS: list[str] = [
    "orchestrate_task",
    "requirement_task",
    "business_analysis_task",
    "solution_design_task",
    "development_scope_task",
    "wbs_task",
    "budget_roi_task",
    "risk_critic_task",
]
_STATE_FIELDS: list[str] = [
    "orchestration_brief",
    "requirement_analysis",
    "business_analysis",
    "solution_direction",
    "development_scope",
    "wbs_plan",
    "budget_roi",
    "risk_management",
]

_PIPELINE_PHASE_LABELS: list[str] = [
    "phase_1_orchestration",
    "phase_2_requirement",
    "phase_3_business",
    "phase_4_solution",
    "phase_5_scope",
    "phase_6_wbs",
    "phase_7_budget",
    "phase_8_risk",
]

# UI 진행 메시지 — AGENTS.md Agent Progress Panel과 동일한 텍스트를 쓴다.
_PIPELINE_USER_MSG: list[str] = [
    "[1/12] PM Orchestrator: 전체 추진계획 구조 설계",
    "[2/12] Requirement Interview: 요구사항 및 누락 정보 분석",
    "[3/12] Business Analyst: AS-IS / Pain Point 분석",
    "[4/12] Solution Architect: TO-BE / 개선 방향 설계",
    "[5/12] Development Scope: 개발 범위 정의",
    "[6/12] WBS Planner: 추진 일정 생성",
    "[7/12] Budget & ROI: 예산 및 기대효과 산출",
    "[8/12] Risk & Critic: 리스크 및 품질 검토",
]

# Critic FAIL 시 재실행할 타깃 → (task_key, state_field)
_IMPROVEMENT_MAP: dict[str, tuple[str, str]] = {
    "orchestration": ("orchestrate_task", "orchestration_brief"),
    "requirement": ("requirement_task", "requirement_analysis"),
    "business": ("business_analysis_task", "business_analysis"),
    "solution": ("solution_design_task", "solution_direction"),
    "scope": ("development_scope_task", "development_scope"),
    "wbs": ("wbs_task", "wbs_plan"),
    "budget": ("budget_roi_task", "budget_roi"),
    "risk": ("risk_critic_task", "risk_management"),
}

_KNOWLEDGE = Path(__file__).resolve().parents[1] / "knowledge" / "sample_project_template.md"

# tasks.yaml format() 시 키 누락으로 Crew가 죽지 않게 기본 키를 채운다 — 구 세션·수동 입력 호환.
_CREW_INPUT_OPTIONAL_KEYS: tuple[str, ...] = (
    "proposal_title",
    "proposal_purpose",
    "background_context",
    "current_problems",
    "target_system",
    "business_scope",
    "improvement_direction",
    "target_audience",
    "key_emphasis",
    "presentation_tone",
    "proposal_meta_hints",
    "related_departments",
    "timeline",
    "budget_range",
    "expected_effects",
    "constraints",
    "reference_materials",
)


def _coerce_crew_input_dict(inputs: dict[str, str]) -> dict[str, str]:
    """proposal 중심 키와 레거시 키를 합쳐 템플릿 placeholder를 안전하게 채운다."""
    d = dict(inputs)
    for k in _CREW_INPUT_OPTIONAL_KEYS:
        d.setdefault(k, "")
    d.setdefault("idea_title", d.get("proposal_title", "") or "")
    d.setdefault("current_process", "")
    d.setdefault("pain_points", d.get("current_problems", "") or "")
    d.setdefault("departments", d.get("related_departments", "") or "")
    d.setdefault("goals", d.get("improvement_direction", "") or "")
    d.setdefault("target_timeline", d.get("timeline", "") or "")
    if d.get("proposal_title") and not d.get("idea_title"):
        d["idea_title"] = d["proposal_title"]
    return d


def _build_interview_seed(inp: dict[str, str]) -> str:
    """Rule-based 인터뷰에서 모은 Crew 입력을 Orchestrator가 한눈에 보게 압축 요약한다."""
    title = inp.get("proposal_title") or inp.get("idea_title", "")
    lines = [
        f"• 추진계획서 제목/주제: {title}",
        f"• 목적: {(inp.get('proposal_purpose') or '')[:500]}",
        f"• 배경: {(inp.get('background_context') or '')[:500]}",
        f"• 핵심 문제: {(inp.get('current_problems') or inp.get('pain_points', ''))[:500]}",
        f"• 대상 시스템: {(inp.get('target_system') or '')[:400]}",
        f"• 업무·기능 범위: {(inp.get('business_scope') or '')[:400]}",
        f"• 개선 방향: {(inp.get('improvement_direction') or '')[:400]}",
        f"• 보고 대상·의사결정자: {(inp.get('target_audience') or '')[:400]}",
        f"• 강조 포인트: {(inp.get('key_emphasis') or '')[:400]}",
        f"• PPT 톤: {(inp.get('presentation_tone') or '')[:200]}",
        f"• 메타 힌트: {inp.get('proposal_meta_hints', '')[:400]}",
        f"• 관련 부서: {inp.get('related_departments') or inp.get('departments', '')}",
        f"• 월 소요(시간) / 인원: {inp.get('monthly_hours', '')} / {inp.get('headcount', '')}",
        f"• 일정 / 예산: {inp.get('timeline') or inp.get('target_timeline', '')} / {inp.get('budget_range', '')}",
        f"• 기대 효과: {(inp.get('expected_effects') or '')[:300]}",
    ]
    return "\n".join(lines).strip()[:4000]


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _slide_target_from_ppt(ppt: PPTGenerationState) -> int:
    """Decision Point 3 — 슬라이드 장 수를 정수로 고정한다(후처리·프롬프트 공통)."""
    m = {"compact_6": 6, "default_10": 10, "detailed_12": 12, "custom_add_remove": 10, "reorder": 10}
    return m.get(ppt.selected_options.get("slide_structure", "default_10"), 10)


def _ensure_drafts_and_seed(inputs: dict[str, str]) -> None:
    """이미 초안이 채워졌으면 Guided 단계에서 OpenAI/mock 재호출을 피한다."""
    if not (inputs.get("open_source_draft") or "").strip():
        try:
            bundle = generate_with_best_available_model(inputs)
            inputs["open_source_draft"] = (bundle.get("draft_markdown") or "").strip()
            inputs["openai_refined_brief"] = (bundle.get("refined_markdown") or "").strip()
        except Exception as exc:  # noqa: BLE001
            inputs["open_source_draft"] = f"(초안 생성 실패: {exc})"
            inputs["openai_refined_brief"] = ""
    if not (inputs.get("interview_seed") or "").strip():
        inputs["interview_seed"] = _build_interview_seed(inputs)


def _merge_inputs_bundle(inputs: dict[str, str]) -> None:
    """Auto 전체 실행 시 초안·시드 한 번에 채운다 — 기존 run() 동작 유지."""
    try:
        bundle = generate_with_best_available_model(inputs)
        inputs["open_source_draft"] = (bundle.get("draft_markdown") or "").strip()
        inputs["openai_refined_brief"] = (bundle.get("refined_markdown") or "").strip()
    except Exception as exc:  # noqa: BLE001
        inputs["open_source_draft"] = f"(초안 생성 실패: {exc})"
        inputs["openai_refined_brief"] = ""
    inputs["interview_seed"] = _build_interview_seed(inputs)


def _parse_critic_output(text: str) -> tuple[int | None, str, str, str, str]:
    """Critic 출력에서 점수·상태·타깃·노트를 추출 — 형식이 깨져도 데모가 멈추지 않게."""
    score: int | None = None
    for pat in (r"CRITIC_SCORE:\s*(\d+)", r"품질\s*점수\s*[:：]?\s*(\d+)"):
        m = re.search(pat, text, re.I)
        if m:
            score = max(0, min(100, int(m.group(1))))
            break
    status = "FAIL"
    m = re.search(r"STATUS:\s*(PASS|FAIL)", text, re.I)
    if m:
        status = m.group(1).upper()
    target = "none"
    m = re.search(r"FEEDBACK_TARGET:\s*([\w_]+)", text, re.I)
    if m:
        raw_t = m.group(1).lower().strip()
        if raw_t in _IMPROVEMENT_MAP or raw_t == "none":
            target = raw_t
    notes = ""
    m = re.search(r"IMPROVEMENT_NOTES:\s*(.+?)(?=FINAL_RECOMMENDATION:|$)", text, re.I | re.S)
    if m:
        notes = m.group(1).strip()
    final_rec = ""
    m = re.search(r"FINAL_RECOMMENDATION:\s*(.+)$", text, re.I | re.S)
    if m:
        final_rec = m.group(1).strip()
    return score, status, target, notes, final_rec


class AutoPMFlow:
    """Supervisor가 호출하는 실제 실행기 — Phase/Critic Loop/문서화를 한 클래스에 둔다(MVP 단순화)."""

    def _build_enriched(self, inputs: dict[str, str], ppt_gen: PPTGenerationState | None) -> dict[str, str]:
        """사용자 결정(PPTGenerationState)을 Task placeholder 문자열로 합성한다."""
        merged_inp = _coerce_crew_input_dict(inputs)
        return apply_decisions_to_enriched(
            {
                **merged_inp,
                "rag_snippet": keyword_search(
                    inputs.get("proposal_title") or inputs.get("idea_title", ""),
                    _KNOWLEDGE,
                ),
                "calc_hints": estimate_rough_cost(
                    inputs.get("monthly_hours", "0"),
                    inputs.get("headcount", "0"),
                    inputs.get("budget_range", ""),
                ),
                "gantt_hint": markdown_gantt_placeholder(
                    inputs.get("proposal_title") or inputs.get("idea_title", "Project"),
                    weeks=4,
                ),
                "feedback_block": "",
            },
            ppt_gen,
        )

    def run(
        self,
        inputs: dict[str, str],
        *,
        on_progress: Callable[[str], None] | None = None,
        ppt_gen: PPTGenerationState | None = None,
    ) -> AutoPMRunResult:
        return self.run_phased(
            PHASE_FULL_AUTO,
            inputs,
            autopm_state_json=None,
            ppt_gen=ppt_gen,
            on_progress=on_progress,
        )

    def run_phased(
        self,
        phase: str,
        inputs: dict[str, str],
        *,
        autopm_state_json: dict[str, Any] | None = None,
        ppt_gen: PPTGenerationState | None = None,
        on_progress: Callable[[str], None] | None = None,
    ) -> AutoPMRunResult:
        """Guided Mode용 단계 실행 — Streamlit이 세션에 autopm_state·ppt_gen을 넘겨 이어 붙인다."""
        pg = ppt_gen or PPTGenerationState()
        root = _project_root()
        inputs = dict(inputs)

        def _struct(extra: dict[str, Any] | None = None) -> dict[str, Any]:
            d: dict[str, Any] = {
                "phase": phase,
                "ppt_generation_state": pg.to_dict(),
            }
            if extra:
                d.update(extra)
            return d

        if phase == PHASE_DRAFT_ONLY:
            _merge_inputs_bundle(inputs)
            state = AutoPMState(user_input=inputs)
            log(state, "phased_draft_only")
            pg.last_draft_markdown = inputs.get("open_source_draft", "")
            pg.draft_generated = True
            return AutoPMRunResult(
                markdown=inputs.get("open_source_draft", ""),
                structured={**_struct(), "autopm_state": state.model_dump()},
                state=state,
            )

        if phase == PHASE_REFINE_DRAFT:
            _ensure_drafts_and_seed(inputs)
            tone = pg.selected_options.get("draft_tone", "proceed")
            extra = (pg.user_decisions.get("draft_extra", "") + "\n".join(pg.revision_requests[-5:])).strip()
            new_d = refine_draft_for_user_choice(inputs.get("open_source_draft", ""), inputs, tone, extra)
            inputs["open_source_draft"] = new_d
            state = AutoPMState.model_validate(autopm_state_json) if autopm_state_json else AutoPMState(user_input=inputs)
            state.user_input = inputs
            log(state, "phased_refine_draft")
            pg.last_draft_markdown = new_d
            pg.draft_approved = True
            return AutoPMRunResult(
                markdown=new_d,
                structured={**_struct(), "autopm_state": state.model_dump()},
                state=state,
            )

        if phase == PHASE_CORE_DOC:
            _ensure_drafts_and_seed(inputs)
            state = AutoPMState.model_validate(autopm_state_json) if autopm_state_json else AutoPMState(user_input=inputs)
            state.user_input = inputs
            log(state, "ph_core_doc_start")
            state.parsed_input = sample_parse_for_demo(
                inputs.get("proposal_title") or inputs.get("idea_title", ""),
                inputs.get("current_process", ""),
                inputs.get("pain_points") or inputs.get("current_problems", ""),
            )
            enriched = self._build_enriched(inputs, pg)
            try:
                t0_core = time.perf_counter()
                final_md = self._run_deep_core_document(
                    state, inputs, enriched, pg, root, on_progress, demo_mode=False
                )
                record_phase_ms(state, "core_doc_phased", time.perf_counter() - t0_core)
                save_autopm_checkpoint(root, "after_doc_phased", state)
                mode = "deep_demo" if get_openai_llm_or_none() is None else "deep_llm"
                return AutoPMRunResult(
                    markdown=final_md,
                    structured={**_struct(), "mode": mode, "autopm_state": state.model_dump()},
                    state=state,
                )
            except Exception as exc:  # noqa: BLE001
                state.errors.append(str(exc))
                md = self._fallback_markdown(state, reason=f"오류: {exc}")
                state.workspace_markdown = md
                return AutoPMRunResult(
                    markdown=md,
                    structured={**_struct(), "error": str(exc), "autopm_state": state.model_dump()},
                    state=state,
                )

        if phase in (PHASE_STORYLINE, PHASE_VISUALIZATION, PHASE_GRAPHICS, PHASE_COMPOSER, PHASE_IMPROVE_CHAIN):
            if not autopm_state_json:
                st_err = AutoPMState(user_input=inputs)
                st_err.errors.append("autopm_state_json required for PPT phase")
                return AutoPMRunResult(
                    markdown="",
                    structured={**_struct(), "error": "missing autopm_state"},
                    state=st_err,
                )
            state = AutoPMState.model_validate(autopm_state_json)
            state.user_input = inputs
            enriched = self._build_enriched(inputs, pg)
            try:
                agent_defs = build_all_agent_defs()
                task_defs = load_tasks()
                final_md = (state.workspace_markdown or "").strip()
                if not final_md:
                    return AutoPMRunResult(
                        markdown="",
                        structured={**_struct(), "error": "empty workspace_markdown"},
                        state=state,
                    )

                if phase == PHASE_IMPROVE_CHAIN:
                    state.slide_storyline_raw = ""
                    state.visualization_raw = ""
                    state.presentation_graphics_raw = ""
                    state.ppt_composer_raw = ""

                title = enriched.get("proposal_title") or enriched.get("idea_title", "AutoPM")

                if phase in (PHASE_STORYLINE, PHASE_IMPROVE_CHAIN):
                    ctx1 = {**enriched, "final_markdown": final_md, "idea_title": title}
                    self._notify(on_progress, "[9/12] Storyline Agent: PPT 장표 흐름 설계")
                    out1 = run_deep_single_task(
                        state,
                        agent_defs,
                        task_defs,
                        ctx1,
                        "slide_storyline_task",
                        on_progress,
                        "[9/12] Storyline Agent: PPT 장표 흐름 설계",
                    )
                    state.slide_storyline_raw = adjust_storyline_slide_count(out1, _slide_target_from_ppt(pg))
                    pg.last_storyline_json = state.slide_storyline_raw
                    pg.slide_plan_generated = True
                    if phase == PHASE_STORYLINE:
                        return AutoPMRunResult(
                            markdown=state.slide_storyline_raw,
                            structured={**_struct(), "autopm_state": state.model_dump()},
                            state=state,
                        )

                if phase in (PHASE_VISUALIZATION, PHASE_IMPROVE_CHAIN):
                    if not state.slide_storyline_raw:
                        return AutoPMRunResult(
                            markdown="",
                            structured={**_struct(), "error": "missing slide_storyline_raw"},
                            state=state,
                        )
                    ctx2 = {**enriched, "storyline_json": state.slide_storyline_raw}
                    self._notify(on_progress, "[10/12] Visualization Agent")
                    out2 = run_deep_single_task(
                        state,
                        agent_defs,
                        task_defs,
                        ctx2,
                        "visualization_design_task",
                        on_progress,
                        "[10/12] Visualization Agent: 시각자료 타입 설계",
                    )
                    state.visualization_raw = out2
                    pg.last_visualization_json = out2
                    pg.visual_plan_generated = True
                    if phase == PHASE_VISUALIZATION:
                        return AutoPMRunResult(
                            markdown=state.visualization_raw,
                            structured={**_struct(), "autopm_state": state.model_dump()},
                            state=state,
                        )

                if phase in (PHASE_GRAPHICS, PHASE_IMPROVE_CHAIN):
                    if not state.visualization_raw:
                        return AutoPMRunResult(
                            markdown="",
                            structured={**_struct(), "error": "missing visualization_raw"},
                            state=state,
                        )
                    ctx3 = {**enriched, "visualization_json": state.visualization_raw}
                    self._notify(on_progress, "[11/12] Presentation Graphics")
                    out3 = run_deep_single_task(
                        state,
                        agent_defs,
                        task_defs,
                        ctx3,
                        "presentation_graphics_task",
                        on_progress,
                        "[11/12] Presentation Graphics: 장표·에셋 스펙 설계",
                    )
                    state.presentation_graphics_raw = out3
                    pg.last_graphics_json = out3
                    if phase == PHASE_GRAPHICS:
                        return AutoPMRunResult(
                            markdown=state.presentation_graphics_raw,
                            structured={**_struct(), "autopm_state": state.model_dump()},
                            state=state,
                        )

                if phase in (PHASE_COMPOSER, PHASE_IMPROVE_CHAIN):
                    if not state.presentation_graphics_raw:
                        return AutoPMRunResult(
                            markdown="",
                            structured={**_struct(), "error": "missing presentation_graphics_raw"},
                            state=state,
                        )
                    ctx4 = {
                        **enriched,
                        "visualization_json": state.visualization_raw,
                        "presentation_graphics_json": state.presentation_graphics_raw,
                    }
                    self._notify(on_progress, "[12/12] PPT Composer")
                    out4 = run_deep_single_task(
                        state,
                        agent_defs,
                        task_defs,
                        ctx4,
                        "ppt_composition_task",
                        on_progress,
                        "[12/12] PPT Composer: 최종 슬라이드 스펙 확정",
                    )
                    state.ppt_composer_raw = out4
                    t0_ppt = time.perf_counter()
                    self._finalize_ppt_and_exports(
                        state,
                        final_md,
                        root,
                        llm_ok=True,
                        agent_defs=agent_defs,
                        task_defs=task_defs,
                        enriched=enriched,
                        on_progress=on_progress,
                        skip_chain=True,
                        ppt_gen=pg,
                        harness_inputs=inputs,
                    )
                    record_phase_ms(state, "ppt_pipeline", time.perf_counter() - t0_ppt)
                    pg.ppt_generated = True
                    save_project_meta(
                        outputs_dir(root),
                        {
                            "title": inputs.get("proposal_title") or inputs.get("idea_title"),
                            "phase": phase,
                        },
                    )
                    save_autopm_checkpoint(root, "after_phased_ppt", state)
                    return AutoPMRunResult(
                        markdown=state.document_output,
                        structured={
                            **_struct(),
                            "loop": state.structured_loop_summary(),
                            "artifacts": dict(state.artifacts),
                            "harness": state.artifacts.get("evaluation_report", {}),
                            "autopm_state": state.model_dump(),
                            "ppt_generation_state": pg.to_dict(),
                        },
                        state=state,
                    )

            except Exception as exc:  # noqa: BLE001
                state.errors.append(str(exc))
                md = self._fallback_markdown(state, reason=f"PPT phase 오류: {exc}")
                self._finalize_ppt_and_exports(
                    state,
                    md,
                    root,
                    llm_ok=False,
                    agent_defs=None,
                    task_defs=None,
                    enriched=enriched,
                    on_progress=on_progress,
                    ppt_gen=pg,
                    harness_inputs=inputs,
                )
                return AutoPMRunResult(
                    markdown=state.document_output,
                    structured={**_struct(), "error": str(exc), "autopm_state": state.model_dump()},
                    state=state,
                )

        # PHASE_FULL_AUTO — 기존 end-to-end (Auto Mode)
        if phase != PHASE_FULL_AUTO:
            stx = AutoPMState(user_input=inputs)
            stx.errors.append(f"unknown phase: {phase}")
            return AutoPMRunResult(markdown="", structured=_struct({"error": "unknown_phase"}), state=stx)

        """전체 오케스트레이션 — 파이프라인/Critic/문서화를 Crew 단위로 나누어 재시도·데모 안정성을 확보한다."""
        # Crew Task placeholder에 넣기 위해 입력 dict를 복사·보강한다 — 원본 호출부를 오염시키지 않는다.
        _merge_inputs_bundle(inputs)

        state = AutoPMState(user_input=inputs)
        log(state, "run_start")

        state.parsed_input = sample_parse_for_demo(
            inputs.get("proposal_title") or inputs.get("idea_title", ""),
            inputs.get("current_process", ""),
            inputs.get("pain_points") or inputs.get("current_problems", ""),
        )
        enriched: dict[str, str] = self._build_enriched(inputs, pg)

        llm = get_openai_llm_or_none()
        demo_mode = llm is None

        try:
            agent_defs = build_all_agent_defs()
            task_defs = load_tasks()
            init_supervisor(state, enriched)

            t0_pipe = time.perf_counter()
            final_md = self._run_deep_core_document(
                state,
                inputs,
                enriched,
                pg,
                root,
                on_progress,
                demo_mode=demo_mode,
            )
            record_phase_ms(state, "pipeline_total", time.perf_counter() - t0_pipe)

            t0_ppt = time.perf_counter()
            self._finalize_ppt_and_exports(
                state,
                final_md,
                root,
                llm_ok=True,
                agent_defs=agent_defs,
                task_defs=task_defs,
                enriched=enriched,
                on_progress=on_progress,
                ppt_gen=pg,
                harness_inputs=inputs,
            )
            record_phase_ms(state, "ppt_pipeline", time.perf_counter() - t0_ppt)
            save_project_meta(
                outputs_dir(root),
                {
                    "title": inputs.get("proposal_title") or inputs.get("idea_title"),
                    "loop_count": state.loop_count,
                    "critic_score": state.critic_score,
                    "pass_quality_gate": state.pass_quality_gate,
                    "mode": "deep_demo" if demo_mode else "deep_llm",
                },
            )
            save_autopm_checkpoint(root, "after_run", state)
            structured = {
                "mode": "deep_demo" if demo_mode else "deep_llm",
                "loop": state.structured_loop_summary(),
                "artifacts": dict(state.artifacts),
                "harness": state.artifacts.get("evaluation_report", {}),
                "ppt_generation_state": pg.to_dict(),
            }
            return AutoPMRunResult(markdown=state.document_output, structured=structured, state=state)
        except Exception as exc:  # noqa: BLE001 — 데모 연속성이 우선
            state.errors.append(str(exc))
            log(state, f"error {exc!r}")
            md = self._fallback_markdown(state, reason=f"오류: {exc}")
            self._finalize_ppt_and_exports(
                state,
                md,
                root,
                llm_ok=False,
                agent_defs=None,
                task_defs=None,
                enriched=enriched,
                on_progress=on_progress,
                ppt_gen=pg,
                harness_inputs=inputs,
            )
            return AutoPMRunResult(
                markdown=state.document_output,
                structured={
                    "error": str(exc),
                    "loop": state.structured_loop_summary(),
                    "artifacts": dict(state.artifacts),
                    "harness": state.artifacts.get("evaluation_report", {}),
                    "ppt_generation_state": pg.to_dict(),
                },
                state=state,
            )

    def rate_limit_result(self, inputs: dict[str, str]) -> AutoPMRunResult:
        """Gateway RateLimiter가 걸렸을 때 사용자에게 돌려줄 안전한 결과 — Crew 호출 없음."""
        state = AutoPMState(user_input=inputs)
        state.errors.append("gateway_rate_limited")
        md = self._fallback_markdown(state, reason="Gateway RateLimiter (AUTOPM_RATE_LIMIT_PER_MIN)")
        root = _project_root()
        enriched_rl = self._build_enriched(inputs, None)
        self._finalize_ppt_and_exports(
            state,
            md,
            root,
            llm_ok=False,
            agent_defs=None,
            task_defs=None,
            enriched=enriched_rl,
            harness_inputs=inputs,
        )
        return AutoPMRunResult(
            markdown=state.document_output,
            structured={
                "rate_limited": True,
                "loop": state.structured_loop_summary(),
                "artifacts": dict(state.artifacts),
                "harness": state.artifacts.get("evaluation_report", {}),
            },
            state=state,
        )

    def _harness_after_pipeline(
        self,
        state: AutoPMState,
        inputs: dict[str, str],
        pg: PPTGenerationState | None,
        agent_defs: dict[str, Any],
        task_defs: dict[str, Any],
        enriched: dict[str, str],
        on_progress: Callable[[str], None] | None,
    ) -> None:
        """
        코어 8단계 Deep Agent 직후 루브릭 점검 + 미달 시 최대 3회 부분 재실행 —
        Critic 루프와 별도로 '형식·완성도'를 먼저 끌어올린다.
        """

        def _improve(
            st: AutoPMState,
            _agents_unused: dict[str, Any],
            tdefs: dict[str, Any],
            enr: dict[str, str],
            target: str,
            feedback: str,
            prog: Callable[[str], None] | None,
        ) -> None:
            run_deep_improvement(st, agent_defs, tdefs, enr, target, feedback, _IMPROVEMENT_MAP, prog)

        harness = EvaluationHarness()
        pre = [
            harness.evaluate_interview(inputs),
            harness.evaluate_draft(inputs.get("open_source_draft", "")),
        ]
        _core_results, attempts, _fb = run_harness_improvement_loop(
            state, agent_defs, task_defs, enriched, _improve, on_progress, max_attempts=3
        )
        if pg is not None:
            pg.improvement_attempts = int(attempts)
            pg.max_improvement_attempts = 3
        state.evaluation_harness_snapshot = {
            "pre_stages": [{"stage": s.stage, "passed": s.passed, "score": s.score, "details": dict(s.details)} for s in pre],
            "core_improvement_attempts": int(attempts),
        }

    def _notify(self, cb: Callable[[str], None] | None, msg: str) -> None:
        if cb:
            cb(msg)

    def _run_deep_core_document(
        self,
        state: AutoPMState,
        inputs: dict[str, str],
        enriched: dict[str, str],
        pg: PPTGenerationState | None,
        root: Path,
        on_progress: Callable[[str], None] | None,
        *,
        demo_mode: bool = False,
    ) -> str:
        """
        Core 8 Agent + Critic + 문서화 — OpenAI Key 없어도 deep_runner fallback으로 동작한다.
        demo_mode=True이면 Critic 루프는 1회만 돌리고 PPT 체인까지 이어 붙인다(FULL_AUTO용).
        """
        agent_defs = build_all_agent_defs()
        task_defs = load_tasks()
        state.current_phase = "phase_pipeline"
        run_deep_pipeline(state, agent_defs, task_defs, enriched, on_progress)
        save_autopm_checkpoint(root, "after_pipeline", state)
        run_supervisor_checkpoint(
            state, label="after_core", enriched=enriched, agent_defs=agent_defs
        )
        self._harness_after_pipeline(state, inputs, pg, agent_defs, task_defs, enriched, on_progress)

        state.current_phase = "critic_loop"
        max_loops = 1 if demo_mode else state.max_loops
        while True:
            if on_progress:
                on_progress(f"[Critic] 평가 중 (loop_count={state.loop_count})")
            critic_text = run_deep_critic(state, agent_defs, task_defs, enriched, on_progress)
            state.critic_review = critic_text
            score, _status, target, notes, final_rec = _parse_critic_output(critic_text)
            state.critic_score = score
            state.critic_status = _status
            state.feedback_target = target
            state.feedback_text = notes
            if final_rec:
                state.final_recommendation = final_rec
            if evaluate_gate(score):
                state.pass_quality_gate = True
                break
            if score is None and target == "none":
                break
            if state.loop_count >= max_loops:
                break
            if target not in _IMPROVEMENT_MAP:
                break
            run_deep_improvement(
                state, agent_defs, task_defs, enriched, target, notes, _IMPROVEMENT_MAP, on_progress
            )
            state.loop_count += 1
            state.improvement_applied.append(f"{target}: {notes[:200]}")

        state.current_phase = "documentation"
        loop_meta = (
            f"loop_count={state.loop_count}, max_loops={state.max_loops}, "
            f"pass_quality_gate={state.pass_quality_gate}, critic_score={state.critic_score}"
        )
        try:
            final_md = run_deep_documentation(
                state, agent_defs, task_defs, enriched, loop_meta, on_progress
            )
        except Exception:
            final_md = self._fallback_markdown(
                state, reason="문서화 Deep Agent 실패 — rule-based 조립"
            )
        state.workspace_markdown = final_md
        return final_md

    def _run_ppt_deep_chain(
        self,
        state: AutoPMState,
        agent_defs: dict[str, Any],
        task_defs: dict[str, Any],
        enriched: dict[str, str],
        final_markdown: str,
        on_progress: Callable[[str], None] | None,
    ) -> None:
        """Storyline → Visualization → Graphics → Composer — Deep Agent 순차 실행."""
        title = enriched.get("proposal_title") or enriched.get("idea_title", "AutoPM")
        ctx1 = {**enriched, "final_markdown": final_markdown, "idea_title": title}
        out1 = run_deep_single_task(
            state,
            agent_defs,
            task_defs,
            ctx1,
            "slide_storyline_task",
            on_progress,
            "[9/12] Storyline Agent: PPT 장표 흐름 설계",
        )
        state.slide_storyline_raw = out1
        ctx2 = {**enriched, "storyline_json": out1}
        out2 = run_deep_single_task(
            state,
            agent_defs,
            task_defs,
            ctx2,
            "visualization_design_task",
            on_progress,
            "[10/12] Visualization Agent: 시각자료 타입 설계",
        )
        state.visualization_raw = out2
        ctx3 = {**enriched, "visualization_json": out2}
        out3 = run_deep_single_task(
            state,
            agent_defs,
            task_defs,
            ctx3,
            "presentation_graphics_task",
            on_progress,
            "[11/12] Presentation Graphics: 장표·에셋 스펙 설계",
        )
        state.presentation_graphics_raw = out3
        ctx4 = {**enriched, "visualization_json": out2, "presentation_graphics_json": out3}
        out4 = run_deep_single_task(
            state,
            agent_defs,
            task_defs,
            ctx4,
            "ppt_composition_task",
            on_progress,
            "[12/12] PPT Composer: 최종 슬라이드 스펙 확정",
        )
        state.ppt_composer_raw = out4

    def _finalize_ppt_and_exports(
        self,
        state: AutoPMState,
        markdown_before_slides: str,
        root: Path,
        *,
        llm_ok: bool,
        agent_defs: dict[str, Any] | None,
        task_defs: dict[str, Any] | None,
        enriched: dict[str, str] | None,
        on_progress: Callable[[str], None] | None = None,
        skip_chain: bool = False,
        ppt_gen: PPTGenerationState | None = None,
        harness_inputs: dict[str, str] | None = None,
    ) -> None:
        """slide_plan.json·project_plan.pptx·Markdown §12를 맞추고 export_run_artifacts를 한 번만 호출한다."""
        title = (
            (state.user_input.get("proposal_title") or state.user_input.get("idea_title") or "").strip() or "AutoPM"
        )
        if enriched:
            title = (enriched.get("proposal_title") or enriched.get("idea_title") or title).strip() or "AutoPM"

        inp_combined: dict[str, str] = {k: str(v) for k, v in dict(state.user_input).items() if v is not None}
        if enriched:
            for k, v in enriched.items():
                if v is not None:
                    inp_combined[k] = str(v)

        # 1) 인터뷰·Markdown → business_plan 통합 (slide·PPT의 단일 소스)
        business_plan = build_business_plan(inp_combined, {"markdown": markdown_before_slides})
        outp = root / "outputs"
        try:
            outp.mkdir(parents=True, exist_ok=True)
            state.artifacts["business_plan.json"] = export_business_plan_json(outp, business_plan)
        except OSError as exc:
            state.errors.append(f"business_plan.json: {exc}")

        deck_dict = build_slide_deck_spec(business_plan, {"subtitle": "AutoPM — 추진계획서"})
        llm_deck: SlideDeckSpec | None = None
        if llm_ok and agent_defs and task_defs and enriched:
            try:
                if not skip_chain:
                    self._run_ppt_deep_chain(
                        state, agent_defs, task_defs, enriched, markdown_before_slides, on_progress
                    )
                llm_deck = deck_from_llm_chain(
                    state.slide_storyline_raw,
                    state.visualization_raw,
                    state.ppt_composer_raw,
                    project_title=title,
                    presentation_graphics_text=state.presentation_graphics_raw,
                )
                deck_dict = merge_llm_deck_graphics(deck_dict, llm_deck)
            except Exception as exc:  # noqa: BLE001
                state.errors.append(f"ppt_crew: {exc}")

        deck_dict = ensure_valid_deck(deck_dict, business_plan)
        ok_cov, _cov_errs, cov_report = validate_slide_deck_content(deck_dict)
        cov_report["validation_passed"] = ok_cov
        try:
            state.artifacts["content_coverage_report.json"] = export_content_coverage_json(outp, cov_report)
        except OSError as exc:
            state.errors.append(f"content_coverage_report.json: {exc}")

        deck = SlideDeckSpec.model_validate(deck_dict)
        manifest: VisualAssetsManifest | None = None
        try:
            deck, manifest = enrich_graphics_pipeline(deck, root)
        except Exception as exc:  # noqa: BLE001
            state.errors.append(f"graphics_pipeline: {exc}")
            manifest = VisualAssetsManifest(project_title=getattr(deck, "project_title", None) or title)

        try:
            export_slide_plan_json(outp, deck)
            state.artifacts["slide_plan.json"] = str((outp / "slide_plan.json").resolve())
        except OSError as exc:
            state.errors.append(f"slide_plan.json: {exc}")
        try:
            if manifest:
                export_visual_assets_json(outp, manifest)
                state.artifacts["visual_assets.json"] = str((outp / "visual_assets.json").resolve())
        except Exception as exc:  # noqa: BLE001
            state.errors.append(f"visual_assets.json: {exc}")
        try:
            pptx_path = create_project_plan_ppt(deck.model_dump(), str(outp / "project_plan.pptx"))
            state.artifacts["project_plan.pptx"] = pptx_path
        except Exception as exc:  # noqa: BLE001
            state.errors.append(f"pptx: {exc}")
        full_md = append_ppt_slide_section(markdown_before_slides, deck)
        state.document_output = full_md
        export_run_artifacts(state, full_md)

        if agent_defs and enriched:
            pptx_p = state.artifacts.get("project_plan.pptx", "")
            if pptx_p:
                from autopm.orchestration.supervisor_manager import supervisor_agent_complete

                supervisor_agent_complete(
                    state,
                    agent_id="ppt_composer",
                    output=state.ppt_composer_raw or "",
                    artifact_path=pptx_p,
                )
            run_supervisor_checkpoint(
                state, label="after_ppt", enriched=enriched, agent_defs=agent_defs
            )
            run_supervisor_checkpoint(state, label="final", enriched=enriched, agent_defs=agent_defs)

        self._notify(on_progress, "[Harness] 최종 산출·PPT 품질 평가")
        try:
            h = EvaluationHarness()
            snap = state.evaluation_harness_snapshot or {}
            pre_raw = snap.get("pre_stages") or []
            stages: list[StageHarnessSnapshot] = []
            for s in pre_raw:
                if isinstance(s, dict):
                    stages.append(
                        StageHarnessSnapshot(
                            str(s.get("stage", "")),
                            bool(s.get("passed")),
                            s.get("score"),
                            dict(s.get("details") or {}),
                        )
                    )
            hinp = harness_inputs or dict(state.user_input)
            if not stages and hinp:
                stages = [
                    h.evaluate_interview(hinp),
                    h.evaluate_draft(hinp.get("open_source_draft", "")),
                ]
            imp_att = int(snap.get("core_improvement_attempts", 0))
            core_results = h.evaluate_all_core(state)
            chain: list[Any] = []
            def _hs(v: object) -> str:
                return v if isinstance(v, str) else str(v or "")

            if _hs(state.slide_storyline_raw).strip():
                chain.append(h.evaluate_storyline(_hs(state.slide_storyline_raw)))
            if _hs(state.visualization_raw).strip() and _hs(state.slide_storyline_raw).strip():
                chain.append(h.evaluate_visualization(_hs(state.visualization_raw), _hs(state.slide_storyline_raw)))
            if _hs(state.presentation_graphics_raw).strip():
                chain.append(h.evaluate_graphics(state.presentation_graphics_raw))
            pptx_p = Path(state.artifacts["project_plan.pptx"]) if state.artifacts.get("project_plan.pptx") else None
            chain.append(h.evaluate_composer_raw(state.ppt_composer_raw or "", pptx_p))
            final_ppt = h.evaluate_final_ppt(deck, pptx_p, full_md)
            combined = h.build_combined_report(
                deck=deck,
                core_results=core_results,
                chain_results=chain,
                final_ppt=final_ppt,
                stages=stages,
                improvement_attempts=imp_att,
                max_improvement_attempts=3,
            )
            rep = combined.to_serializable()
            state.artifacts["evaluation_report"] = rep
            ev_paths = export_evaluation_reports(outp, rep)
            state.artifacts.update(ev_paths)
            if ppt_gen is not None:
                ppt_gen.evaluation_score = combined.overall_score
                ppt_gen.pass_threshold = combined.pass_threshold
                ppt_gen.failed_criteria = list(combined.failed_criteria)
                ppt_gen.feedback_target = combined.feedback_target
                ppt_gen.improvement_attempts = combined.improvement_attempts
                ppt_gen.max_improvement_attempts = combined.max_improvement_attempts
                ppt_gen.final_passed = combined.final_passed
        except Exception as exc:  # noqa: BLE001 — 평가 실패해도 산출물 다운로드는 유지
            state.errors.append(f"evaluation_harness: {exc}")
            imp = int((state.evaluation_harness_snapshot or {}).get("core_improvement_attempts", 0))
            rep = {
                "overall_score": 0.0,
                "pass_threshold": 85.0,
                "final_passed": False,
                "agent_scores": {},
                "failed_criteria": [f"harness_error:{exc}"],
                "feedback_target": "",
                "improvement_attempts": imp,
                "max_improvement_attempts": 3,
                "stages": [],
                "warnings": [f"평가 예외: {exc}"],
                "recommendations": ["리포트를 수동 검토하세요."],
            }
            state.artifacts["evaluation_report"] = rep
            try:
                state.artifacts.update(export_evaluation_reports(outp, rep))
            except OSError:
                pass

    def _fallback_markdown(self, state: AutoPMState, reason: str = "") -> str:
        """API 불능/예외 시 AGENTS.md Markdown 목차(§12 제외) + 루프 메타."""
        inp = state.user_input
        title = inp.get("proposal_title") or inp.get("idea_title", "")
        loop_json = json.dumps(state.structured_loop_summary(), ensure_ascii=False, indent=2)
        cp = (inp.get("current_process") or "").strip()
        bg = (inp.get("background_context") or "").strip()
        as_is_cell = cp[:900] if cp else (bg[:900] if bg else "제목·인터뷰 기반 현황 요약(가정)")
        purpose_line = (inp.get("proposal_purpose") or "").strip()
        draft = (inp.get("open_source_draft") or "").strip()
        refined = (inp.get("openai_refined_brief") or "").strip()
        draft_append = ""
        if draft:
            draft_append += f"\n\n## 오픈소스/mock 1차 초안(참고)\n{draft[:8000]}\n"
        if refined:
            draft_append += f"\n\n## OpenAI 고도화 초안(참고)\n{refined[:8000]}\n"
        prob = inp.get("current_problems") or inp.get("pain_points", "검증 지연·기준 편차·누락 위험")
        goals_fb = inp.get("goals") or inp.get("improvement_direction") or "업무 개선 파일럿을 4주 내 검증"
        dept_line = inp.get("related_departments") or inp.get("departments", "")
        return f"""# AutoPM 추진계획서

> Fallback 모드: {reason}

## 1. Executive Summary
- 과제: **{title}**
- 목적: {purpose_line or "(인터뷰에서 보완)"}
- 한 줄 결론: {goals_fb}

## 2. 추진 배경
- 배경: {bg or "(미입력)"}
- 보고 대상: {inp.get("target_audience", "")}
- PPT 톤: {inp.get("presentation_tone", "")}
- 관련 부서: {dept_line}
- 월 소요: {inp.get("monthly_hours", "")}h / 인원: {inp.get("headcount", "")}명(가정)

## 3. 현재 문제점
{prob}

## 4. AS-IS
| 단계 | 설명 |
| --- | --- |
| 현황 요약 | {as_is_cell} |
| 검증 방식 | 수작업·엑셀 기반(가정) |
| 조치 | 재작업·재확인 |

## 5. TO-BE
| 단계 | 설명 |
| --- | --- |
| 표준화 | 룰/스냅샷 |
| 자동화 | 스크립트·RPA 수준(MVP) |
| 예외 | 승인·로그 |

## 6. 개발 범위
- 포함: 규칙 정의, 자동 검증 MVP, 리포트
- 제외: ERP 커스터, 대규모 인프라, 실운영 연동

## 7. WBS
| 단계 | 작업 | 기간 | 담당 | 산출물 |
| --- | --- | --- | --- | --- |
| 1 | 킥오프 | 3일 | PM | 메모 |
| 2 | 규칙 정리 | 1주 | 현업 | 명세 |
| 3 | 구현 | 2주 | IT | 스크립트 |
| 4 | 파일럿 | 1주 | 전체 | 리포트 |

## 8. 예산 및 ROI
| 항목 | 예상 비용 | 설명 |
| --- | --- | --- |
| 인력 | {inp.get("budget_range", "")} 내(가정) | 분석·구현 |
| 절감 | 월 {inp.get("monthly_hours", "")}h의 30~40%(가정) | 자동 검증 |

## 9. KPI
| 지표 | 현재 | 목표 |
| --- | --- | --- |
| 검증 리드타임 | 기준선 | -30%(가정) |
| 누락 | 미측정 | 0건 지향 |

## 10. 리스크 매트릭스
| 리스크 | 발생 가능성 | 영향도 | 대응 방안 |
| --- | --- | --- | --- |
| 규칙 불완전 | 중 | 고 | 파일럿 2회 |
| 데이터 품질 | 중 | 중 | 샘플 검증 |

## 11. Critic Review
- 품질 점수: **72/100 (fallback)**
- 누락 항목: API 미연결/오류로 자동 Critic 생략
- 보완 제안: 키 설정 후 전체 루프 재실행
- 최종 의견: 샘플 데이터·RACI·보안 합의 후 승인 요청

## Self-Correction Loop (메타)
```json
{loop_json}
```

## 추가 확인 질문
- ERP 오류 심각도 분류 합의 여부
- 엑셀 반출·DLP 정책
{draft_append}"""

