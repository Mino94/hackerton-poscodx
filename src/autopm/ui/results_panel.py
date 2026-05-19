"""탭 3 — PPT·문서·Agent 산출물 뷰 (컴팩트 서브탭)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

from autopm.ui.markdown_utils import join_sections, outline_json, slide_count_from_json, split_numbered_sections
from autopm.ui.supervisor_panel import render_supervisor_panel


def _visual_asset_rows_from_file(path_str: str | None) -> list[dict]:
    if not path_str:
        return []
    p = Path(path_str)
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows_va: list[dict] = []
    for s in data.get("slides") or []:
        if not isinstance(s, dict):
            continue
        for a in s.get("assets") or []:
            if not isinstance(a, dict):
                continue
            rows_va.append(
                {
                    "slide_no": s.get("slide_no"),
                    "title": s.get("title"),
                    "visual_type": s.get("visual_type") or a.get("visual_type"),
                    "render_mode": a.get("render_mode") or s.get("render_mode"),
                    "asset_path": a.get("path") or "",
                }
            )
    return rows_va


def render_results_tab(result: Any | None, agent_steps: list[Any] | None) -> None:
    """산출물이 없으면 안내, 있으면 요약 메트릭 + 서브탭."""
    if not result:
        st.info(
            "**Auto**: 인터뷰 탭에서 주제 입력 후 **PPT 자동 생성**. "
            "**Guided**: 인터뷰 탭 하단 패널에서 단계 승인 후 여기에 표시됩니다."
        )
        return

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Critic", result.state.critic_score if result.state.critic_score is not None else "—")
    with c2:
        st.metric("품질 게이트", "PASS" if result.state.pass_quality_gate else "FAIL")
    with c3:
        st.metric("루프", f"{result.state.loop_count}/{result.state.max_loops}")
    with c4:
        ppt_path = result.state.artifacts.get("project_plan.pptx")
        n = slide_count_from_json(result.state.artifacts.get("slide_plan.json"))
        st.metric("PPT 슬라이드", n or "—")

    st.caption(
        f"Phase `{result.state.current_phase}` · "
        f"Feedback `{result.state.feedback_target or '—'}` · "
        f"개선 {len(result.state.improvement_applied)}건"
    )

    t_main, t_agents, t_files = st.tabs(["핵심 산출물", "Agent·대화", "Supervisor·로그"])

    with t_main:
        _render_file_subtabs(result)

    with t_agents:
        _render_agent_subtabs(result, agent_steps)

    with t_files:
        with st.expander("Supervisor PM", expanded=True):
            render_supervisor_panel(getattr(result.state, "supervisor", None) or {})
        with st.expander("Structured JSON / Logs", expanded=False):
            st.json(result.structured)
            if result.state.timings_ms:
                st.caption("구간 소요(ms)")
                st.json(result.state.timings_ms)
            st.text_area("실행 로그", value="\n".join(result.state.logs[-40:]), height=140)


def _render_file_subtabs(result: Any) -> None:
    result_md = result.markdown
    parts = split_numbered_sections(result_md)
    artifacts = result.state.artifacts

    ppt_path = artifacts.get("project_plan.pptx")
    slide_json_path = artifacts.get("slide_plan.json")
    business_plan_path = artifacts.get("business_plan.json")
    content_coverage_path = artifacts.get("content_coverage_report.json")
    visual_assets_path = artifacts.get("visual_assets.json")
    n_slides = slide_count_from_json(slide_json_path)

    t_ppt, t_doc, t_slide, t_data, t_eval = st.tabs(
        ["PPT", "추진계획서", "Slide Plan", "WBS·예산·리스크", "품질·Coverage"]
    )

    with t_ppt:
        st.caption(f"**project_plan.pptx** · {n_slides or '—'}장")
        if ppt_path and Path(ppt_path).is_file():
            with open(ppt_path, "rb") as fp:
                st.download_button(
                    label="📥 PPT 다운로드",
                    data=fp,
                    file_name="project_plan.pptx",
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    use_container_width=True,
                )
        else:
            st.warning("`outputs/project_plan.pptx` 없음")

    with t_doc:
        if parts.get(0):
            st.markdown(parts[0])
        st.markdown(join_sections(parts, 1, 6) or "_본문 없음_")

    with t_slide:
        if business_plan_path and Path(business_plan_path).is_file():
            with st.expander("business_plan.json", expanded=False):
                st.code(Path(business_plan_path).read_text(encoding="utf-8")[:8000], language="json")
        if slide_json_path and Path(slide_json_path).is_file():
            st.code(Path(slide_json_path).read_text(encoding="utf-8")[:12000], language="json")
        else:
            st.info("slide_plan.json 없음")
        if parts.get(12):
            st.markdown("---")
            st.markdown(parts[12])

    with t_data:
        st.markdown(parts.get(7, "_WBS 없음_"))
        st.divider()
        st.markdown(join_sections(parts, 8, 9) or "_예산/KPI 없음_")
        st.divider()
        st.markdown(parts.get(10, "_리스크 없음_"))
        st.divider()
        st.markdown(parts.get(11, "_Critic 없음_"))

    with t_eval:
        _render_coverage(content_coverage_path)
        st.divider()
        _render_harness(result)
        rows_v = _visual_asset_rows_from_file(visual_assets_path)
        if rows_v:
            st.markdown("**Visual Assets**")
            st.dataframe(rows_v, hide_index=True, use_container_width=True)


def _render_coverage(content_coverage_path: str | None) -> None:
    if not content_coverage_path or not Path(content_coverage_path).is_file():
        st.caption("content_coverage_report.json 없음")
        return
    try:
        cov = json.loads(Path(content_coverage_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        cov = {}
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("슬라이드", cov.get("total_slides", "—"))
    c2.metric("본문 채움", cov.get("slides_with_body", "—"))
    c3.metric("빈 content", cov.get("empty_content_slides", "—"))
    c4.metric("검증", "✓" if cov.get("passed") else "✗")


def _render_harness(result: Any) -> None:
    harness = result.structured.get("harness") or result.state.artifacts.get("evaluation_report") or {}
    if not harness:
        st.caption("Evaluation harness 없음")
        return
    st.metric("Overall", f"{harness.get('overall_score', '—')} / 100")
    scores = harness.get("agent_scores") or {}
    if scores:
        st.dataframe(
            [{"Agent": k, "Score": v} for k, v in sorted(scores.items())],
            hide_index=True,
            use_container_width=True,
        )


def _render_agent_subtabs(result: Any, agent_steps: list[Any] | None) -> None:
    if agent_steps:
        st.dataframe(
            [
                {
                    "Agent": ag.display_name,
                    "상태": ag.status,
                    "산출": (ag.artifact or "")[:80],
                }
                for ag in agent_steps
            ],
            hide_index=True,
            use_container_width=True,
        )

    t_out, t_sub, t_dlg, t_raw = st.tabs(["결과물", "Sub-Agent", "대화", "Raw"])
    outputs_map = result.state.agent_outputs or {}
    sub_map = getattr(result.state, "subagent_outputs", None) or {}

    with t_out:
        if not outputs_map:
            st.caption("태스크별 Markdown·JSON이 여기 표시됩니다.")
        for task_key, body in outputs_map.items():
            n_sub = len(sub_map.get(task_key) or [])
            label = f"`{task_key}`" + (f" · Sub {n_sub}" if n_sub else "")
            with st.expander(label, expanded=False):
                lang = "json" if (body or "").strip().startswith("{") else "markdown"
                st.code((body or "")[:10000], language=lang)

    with t_sub:
        for task_key, recs in sub_map.items():
            with st.expander(f"`{task_key}` ({len(recs)})", expanded=False):
                for rec in recs:
                    st.markdown(
                        f"**{rec.get('subagent_id', '?')}** · "
                        f"`{rec.get('llm_tier', '')}` · {rec.get('provider', '?')}"
                    )
                    st.code((rec.get("output") or "")[:5000], language="markdown")

    with t_dlg:
        dialogue = result.state.agent_dialogue_as_dicts()
        for i, d in enumerate(dialogue, 1):
            fr = d.get("from_role") or d.get("from_agent", "?")
            to = d.get("to_role") or d.get("to_agent", "?")
            rounds = d.get("rounds") or []
            with st.expander(f"{i}. {fr} ↔ {to}" + (f" · {len(rounds)}R" if rounds else ""), expanded=i <= 2):
                if rounds:
                    for t in rounds:
                        st.markdown(f"**R{t.get('round')} · {t.get('role', '?')}**")
                        st.markdown(t.get("message", ""))
                else:
                    st.markdown(d.get("message", ""))

    with t_raw:
        st.code(result.markdown, language="markdown")
        st.code(outline_json(result.markdown), language="json")
        if result.state.artifacts:
            for k, v in result.state.artifacts.items():
                st.caption(f"**{k}**: `{v}`")
