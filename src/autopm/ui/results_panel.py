"""산출물 탭 — 다운로드 허브·문서 미리보기·데이터·품질 (사용자 친화)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from autopm.ui.markdown_utils import join_sections, slide_count_from_json, split_numbered_sections
from autopm.ui.supervisor_panel import render_supervisor_panel

# 산출물 파일 메타 — 아이콘·설명·MIME
_FILE_CATALOG: list[tuple[str, str, str, str]] = [
    ("project_plan.pptx", "📊", "추진계획서 PPT", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
    ("project_plan_gamma.pptx", "✨", "Gamma 고품질 PPT", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
    ("project_plan.md", "📄", "추진계획서 Markdown", "text/markdown"),
    ("slide_plan.json", "🗂", "슬라이드 구성 JSON", "application/json"),
    ("wbs.csv", "📅", "WBS 일정", "text/csv"),
    ("budget.csv", "💰", "예산·ROI", "text/csv"),
    ("risk_log.csv", "⚡", "리스크 로그", "text/csv"),
    ("critic_review.md", "📝", "Critic 검토", "text/markdown"),
    ("agent_dialogue.json", "💬", "Agent 대화 로그", "application/json"),
]


def _inject_results_css() -> None:
    st.markdown(
        """
        <style>
        .results-hero {
          background: linear-gradient(135deg, #f0f7ff 0%, #f8fafc 100%);
          border: 1px solid #cbd5e1; border-radius: 10px;
          padding: 1rem 1.1rem; margin-bottom: 0.75rem;
        }
        .results-hero h3 { margin: 0 0 0.35rem; color: #05509c; font-size: 1.05rem; }
        .file-card {
          border: 1px solid #e2e8f0; border-radius: 8px; padding: 0.65rem 0.75rem;
          background: #fff; min-height: 5.5rem;
        }
        .file-card .fname { font-size: 0.78rem; color: #64748b; word-break: break-all; }
        .status-pass { color: #166534; font-weight: 600; }
        .status-fail { color: #b91c1c; font-weight: 600; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _read_file_preview(path: Path, max_chars: int = 2000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:max_chars]
    except OSError:
        return ""


def _csv_to_dataframe(path: Path) -> pd.DataFrame | None:
    try:
        return pd.read_csv(path, encoding="utf-8")
    except Exception:
        return None


def _render_empty_state() -> None:
    st.markdown("### 📁 산출물")
    st.caption("생성이 완료되면 이 탭에서 **PPT 다운로드**와 문서·표를 한곳에서 확인할 수 있습니다.")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**1. 인터뷰**")
        st.caption("💬 인터뷰·프로세스 탭에서 주제·질문 답변")
    with c2:
        st.markdown("**2. 생성**")
        st.caption("Auto: PPT 자동 생성 · Guided: 📊 수집·진행에서 단계 승인")
    with c3:
        st.markdown("**3. 다운로드**")
        st.caption("여기서 PPT·CSV·Markdown 받기")
    st.info("아직 산출물이 없습니다. 위 순서대로 진행한 뒤 다시 열어 주세요.")


def _render_hero(result: Any, artifacts: dict[str, str], n_slides: int | None) -> None:
    """상단 요약 + 핵심 PPT 다운로드."""
    score = result.state.critic_score
    gate = result.state.pass_quality_gate
    gate_cls = "status-pass" if gate else "status-fail"
    gate_txt = "품질 통과" if gate else "품질 검토 필요"

    title = (result.state.user_input.get("proposal_title") or result.state.user_input.get("idea_title") or "추진계획서")[:60]
    st.markdown(
        f'<div class="results-hero">'
        f"<h3>{title}</h3>"
        f'<p style="margin:0;font-size:0.85rem;color:#475569;">'
        f"슬라이드 <b>{n_slides or '—'}</b>장 · "
        f'Critic <b>{score if score is not None else "—"}</b> · '
        f'<span class="{gate_cls}">{gate_txt}</span>'
        f"</p></div>",
        unsafe_allow_html=True,
    )

    ppt = artifacts.get("project_plan.pptx")
    gamma = artifacts.get("project_plan_gamma.pptx")
    gamma_url = artifacts.get("gamma_url", "")

    d1, d2, d3 = st.columns([1, 1, 1])
    with d1:
        if ppt and Path(ppt).is_file():
            with open(ppt, "rb") as f:
                st.download_button(
                    "📥 PPT 다운로드",
                    f,
                    "project_plan.pptx",
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    type="primary",
                    use_container_width=True,
                )
        else:
            st.button("PPT 없음", disabled=True, use_container_width=True)
    with d2:
        if gamma and Path(gamma).is_file():
            with open(gamma, "rb") as fg:
                st.download_button(
                    "✨ Gamma PPT",
                    fg,
                    "project_plan_gamma.pptx",
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    use_container_width=True,
                )
        else:
            st.caption("Gamma: API 키 설정 시 생성")
    with d3:
        md_path = artifacts.get("project_plan.md")
        if md_path and Path(md_path).is_file():
            with open(md_path, "rb") as fm:
                st.download_button("📄 Markdown", fm, "project_plan.md", use_container_width=True)
        if gamma_url:
            st.link_button("Gamma 웹에서 열기", gamma_url, use_container_width=True)


def _render_download_grid(artifacts: dict[str, str]) -> None:
    """모든 파일 — 카드 + 개별 다운로드."""
    st.markdown("##### 파일 목록")
    cols = st.columns(3)
    idx = 0
    for fname, icon, label, mime in _FILE_CATALOG:
        path_str = artifacts.get(fname)
        if not path_str or not Path(path_str).is_file():
            continue
        p = Path(path_str)
        with cols[idx % 3]:
            st.markdown(
                f'<div class="file-card">'
                f"<div style='font-size:1.4rem'>{icon}</div>"
                f"<b>{label}</b><br>"
                f"<span class='fname'>{fname}</span></div>",
                unsafe_allow_html=True,
            )
            with open(p, "rb") as f:
                st.download_button(
                    "다운로드",
                    f,
                    fname,
                    mime=mime,
                    key=f"dl_{fname}",
                    use_container_width=True,
                )
        idx += 1
    if idx == 0:
        st.caption("다운로드 가능한 파일이 아직 없습니다.")


def _render_document_view(result: Any, parts: dict[int, str]) -> None:
    """추진계획서 본문 — 섹션별 expander."""
    st.markdown("##### 문서 미리보기")

    section_labels = {
        0: "Executive Summary",
        1: "추진 배경",
        2: "현재 문제점",
        3: "AS-IS",
        4: "TO-BE",
        5: "개발 범위",
        7: "WBS",
        8: "예산 및 ROI",
        9: "KPI",
        10: "리스크 매트릭스",
        11: "Critic Review",
        12: "PPT 슬라이드 구성",
    }

    # 요약·핵심만 기본 펼침
    for num in [0, 1, 2, 3, 4, 5]:
        body = parts.get(num, "").strip()
        if not body:
            continue
        title = section_labels.get(num, f"섹션 {num}")
        first_line = body.splitlines()[0].replace("##", "").strip() if body else title
        with st.expander(first_line[:48] or title, expanded=(num <= 2)):
            st.markdown(body)

    with st.expander("WBS · 예산 · 리스크 · Critic (전체)", expanded=False):
        for num in [7, 8, 9, 10, 11]:
            body = parts.get(num, "").strip()
            if body:
                st.markdown(body)
                st.divider()

    if parts.get(12):
        with st.expander("PPT 슬라이드 구성표", expanded=False):
            st.markdown(parts[12])


def _render_data_view(artifacts: dict[str, str], parts: dict[int, str]) -> None:
    """WBS·예산·리스크 — CSV 표 우선."""
    st.markdown("##### 표·일정 데이터")

    wbs_p = artifacts.get("wbs.csv")
    if wbs_p and Path(wbs_p).is_file():
        st.markdown("**WBS / 추진 일정**")
        df = _csv_to_dataframe(Path(wbs_p))
        if df is not None and not df.empty:
            st.dataframe(df, use_container_width=True, hide_index=True)
            with open(wbs_p, "rb") as f:
                st.download_button("WBS CSV", f, "wbs.csv", key="dl_wbs_inline")
        else:
            st.markdown(parts.get(7, "_없음_"))
    elif parts.get(7):
        st.markdown(parts.get(7))

    st.divider()
    budget_p = artifacts.get("budget.csv")
    if budget_p and Path(budget_p).is_file():
        st.markdown("**예산 및 ROI**")
        df = _csv_to_dataframe(Path(budget_p))
        if df is not None and not df.empty:
            st.dataframe(df, use_container_width=True, hide_index=True)
            with open(budget_p, "rb") as f:
                st.download_button("예산 CSV", f, "budget.csv", key="dl_budget_inline")
        else:
            st.markdown(join_sections(parts, 8, 9) or "_없음_")
    elif parts.get(8) or parts.get(9):
        st.markdown(join_sections(parts, 8, 9))

    st.divider()
    risk_p = artifacts.get("risk_log.csv")
    if risk_p and Path(risk_p).is_file():
        st.markdown("**리스크**")
        df = _csv_to_dataframe(Path(risk_p))
        if df is not None and not df.empty:
            st.dataframe(df, use_container_width=True, hide_index=True)
            with open(risk_p, "rb") as f:
                st.download_button("리스크 CSV", f, "risk_log.csv", key="dl_risk_inline")
        else:
            st.markdown(parts.get(10, "_없음_"))
    elif parts.get(10):
        st.markdown(parts.get(10))


def _render_slide_outline(artifacts: dict[str, str], parts: dict[int, str]) -> None:
    """슬라이드 구성 — 표 형태로 요약."""
    slide_path = artifacts.get("slide_plan.json")
    if not slide_path or not Path(slide_path).is_file():
        if parts.get(12):
            st.markdown(parts[12])
        else:
            st.caption("slide_plan.json 없음")
        return

    try:
        data = json.loads(Path(slide_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        st.warning("슬라이드 JSON을 읽을 수 없습니다.")
        return

    slides = data.get("slides") or []
    rows = []
    for s in slides:
        if not isinstance(s, dict):
            continue
        rows.append(
            {
                "No": s.get("slide_no", ""),
                "제목": (s.get("title") or "")[:40],
                "핵심 메시지": (s.get("key_message") or "")[:50],
                "시각자료": s.get("visual_type") or "",
            }
        )
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
        with st.expander("JSON 원본", expanded=False):
            st.code(Path(slide_path).read_text(encoding="utf-8")[:8000], language="json")
    else:
        st.caption("슬라이드 항목 없음")


def _render_quality_view(result: Any, artifacts: dict[str, str]) -> None:
    """품질·Coverage·Harness."""
    st.markdown("##### 품질 점검")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Critic 점수", result.state.critic_score if result.state.critic_score is not None else "—")
    with c2:
        st.metric("품질 게이트", "PASS" if result.state.pass_quality_gate else "FAIL")
    with c3:
        st.metric("개선 루프", f"{result.state.loop_count}/{result.state.max_loops}")
    with c4:
        harness = result.structured.get("harness") or (
            result.state.harness_report() if hasattr(result.state, "harness_report") else {}
        )
        st.metric("Harness", f"{harness.get('overall_score', '—')}/100" if harness else "—")

    cov_path = artifacts.get("content_coverage_report.json")
    if cov_path and Path(cov_path).is_file():
        try:
            cov = json.loads(Path(cov_path).read_text(encoding="utf-8"))
            st.markdown("**PPT 본문 채움**")
            cc1, cc2, cc3 = st.columns(3)
            cc1.metric("슬라이드", cov.get("total_slides", "—"))
            cc2.metric("본문 있음", cov.get("slides_with_body", "—"))
            cc3.metric("검증", "통과" if cov.get("passed") else "미통과")
        except (OSError, json.JSONDecodeError):
            pass

    harness = result.structured.get("harness") or {}
    if not harness and hasattr(result.state, "harness_report"):
        harness = result.state.harness_report() or {}
    scores = harness.get("agent_scores") or {}
    if scores:
        st.markdown("**Agent별 점수**")
        st.dataframe(
            [{"Agent": k, "점수": v} for k, v in sorted(scores.items())],
            use_container_width=True,
            hide_index=True,
        )

    critic_path = artifacts.get("critic_review.md")
    if critic_path and Path(critic_path).is_file():
        with st.expander("Critic Review 전문", expanded=False):
            st.markdown(_read_file_preview(Path(critic_path), 6000))


def _render_advanced(result: Any, agent_steps: list[Any] | None) -> None:
    """기술 로그·Supervisor·태스크 원문."""
    if agent_steps:
        with st.expander("Agent 실행 요약", expanded=False):
            st.dataframe(
                [
                    {
                        "Agent": ag.display_name,
                        "상태": {"pending": "대기", "running": "실행", "complete": "완료", "error": "오류"}.get(
                            ag.status, ag.status
                        ),
                        "산출": (ag.artifact or "")[:60],
                    }
                    for ag in agent_steps
                ],
                hide_index=True,
                use_container_width=True,
            )

    outputs_map = result.state.agent_outputs or {}
    if outputs_map:
        with st.expander("태스크별 Agent 원문", expanded=False):
            for task_key, body in outputs_map.items():
                st.caption(f"`{task_key}`")
                lang = "json" if (body or "").strip().startswith("{") else "markdown"
                st.code((body or "")[:6000], language=lang)

    with st.expander("Supervisor PM", expanded=False):
        render_supervisor_panel(getattr(result.state, "supervisor", None) or {})

    with st.expander("실행 로그·JSON", expanded=False):
        if result.state.timings_ms:
            st.caption("구간 소요 (ms)")
            st.json(result.state.timings_ms)
        st.text_area("로그", value="\n".join(result.state.logs[-30:]), height=120, disabled=True)
        st.json(result.structured)


def render_results_tab(result: Any | None, agent_steps: list[Any] | None) -> None:
    """산출물 탭 — 다운로드 허브 중심."""
    _inject_results_css()

    if not result:
        _render_empty_state()
        return

    artifacts = result.state.artifacts or {}
    parts = split_numbered_sections(result.markdown or "")
    n_slides = slide_count_from_json(artifacts.get("slide_plan.json"))

    _render_hero(result, artifacts, n_slides)

    view = st.radio(
        "보기",
        ["📥 다운로드", "📄 문서", "📊 데이터·표", "🗂 슬라이드", "✓ 품질", "⚙ 고급"],
        horizontal=True,
        label_visibility="collapsed",
    )

    if view.startswith("📥"):
        _render_download_grid(artifacts)
        st.caption("Agent 협업 대화는 **🤝 Agent 대화** 탭에서 채팅 형태로 확인할 수 있습니다.")
    elif view.startswith("📄"):
        _render_document_view(result, parts)
    elif view.startswith("📊"):
        _render_data_view(artifacts, parts)
    elif view.startswith("🗂"):
        _render_slide_outline(artifacts, parts)
    elif view.startswith("✓"):
        _render_quality_view(result, artifacts)
    else:
        _render_advanced(result, agent_steps)
