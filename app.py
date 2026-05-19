"""AutoPM Streamlit — 3탭: 인터뷰 / 수집·진행 / 산출물."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import streamlit as st
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from autopm.chat import InterviewBot, InterviewState  # noqa: E402
from autopm.crew import run_autopm, run_autopm_phased  # noqa: E402
from autopm.state.ppt_generation_state import (  # noqa: E402
    PHASE_COMPOSER,
    PHASE_CORE_DOC,
    PHASE_DRAFT_ONLY,
    PHASE_GRAPHICS,
    PHASE_IMPROVE_CHAIN,
    PHASE_REFINE_DRAFT,
    PHASE_STORYLINE,
    PHASE_VISUALIZATION,
    PPTGenerationState,
)
from autopm.ui.agent_progress import (  # noqa: E402
    apply_progress_message,
    finalize_agent_dashboard,
    get_agent_steps,
    render_agent_progress,
    simulate_agent_progress,
)
from autopm.ui.compact_tabs import inject_compact_css, render_progress_tab  # noqa: E402
from autopm.ui.interview_panel import render_interview_tab  # noqa: E402
from autopm.ui.results_panel import render_results_tab  # noqa: E402

load_dotenv()

# 데모·발표 시 레이어 설명을 빠르게 보여주기 위한 정적 카드 — 코드 동작과 무관하다.
_LAYERS_KR = """
| Layer | MVP 구현 |
| --- | --- |
| **L1 Presentation** | Streamlit (본 화면) |
| **L2 API/Auth** | `api/gateway.py` 어댑터 + auth/rate_limit 스텁 |
| **L3 Orchestration** | Deep Agents + Supervisor + `AutoPMFlow` + Agent 대화 + PPT 파이프라인 |
| **L4 Tools/Services** | `tools/`, `services/`, `ppt/` (python-pptx Composer) |
| **L5 Data** | `data/` + `outputs/` (md/pptx/json/csv) |
"""

_SIDEBAR = """
**Supervisor** — 추진계획서 주제 입력 → 인터뷰(목적·배경·문제·톤) → 8 Core 태스크 → Critic → 문서화 →
**Storyline / Visualization / Presentation Graphics / Composer** → `project_plan.pptx`
"""


def _ensure_session_defaults() -> None:
    """Streamlit rerun 사이에 인터뷰·대시보드 상태가 사라지지 않게 시드한다."""
    if "interview_state" not in st.session_state:
        st.session_state.interview_state = InterviewState().to_dict()
    if "interview_started" not in st.session_state:
        st.session_state.interview_started = False
    if "last_result" not in st.session_state:
        st.session_state.last_result = None
    if "agent_steps" not in st.session_state:
        st.session_state.agent_steps = None
    if "ppt_gen" not in st.session_state:
        st.session_state.ppt_gen = PPTGenerationState().to_dict()
    if "autopm_state_json" not in st.session_state:
        st.session_state.autopm_state_json = None
    if "crew_inputs" not in st.session_state:
        st.session_state.crew_inputs = {}
    if "guided_ui_step" not in st.session_state:
        st.session_state.guided_ui_step = "input_confirm"
    if "run_mode" not in st.session_state:
        st.session_state.run_mode = "Guided"


def _get_pg() -> PPTGenerationState:
    return PPTGenerationState.from_dict(st.session_state.ppt_gen)


def _save_pg(pg: PPTGenerationState) -> None:
    st.session_state.ppt_gen = pg.to_dict()


def _base_inputs_from_interview() -> dict:
    """인터뷰 상태 + 세션에 누적된 초안 필드를 Crew 입력으로 합친다."""
    d = _get_iv().to_autopm_inputs()
    d.update({k: str(v) for k, v in st.session_state.crew_inputs.items() if v is not None})
    return d


def _get_iv() -> InterviewState:
    return InterviewState.from_dict(st.session_state.interview_state)


def _save_iv(s: InterviewState) -> None:
    st.session_state.interview_state = s.to_dict()


st.set_page_config(page_title="AutoPM", layout="wide", initial_sidebar_state="expanded")


def _secrets_into_os_environ() -> None:
    """
    Streamlit Cloud secrets.toml → os.environ.
    로컬에 secrets.toml이 없으면 .env(load_dotenv)만 쓰고 조용히 넘어간다.
    (`key in st.secrets`는 파일 없을 때 StreamlitSecretNotFoundError를 낸다.)
    """
    try:
        from streamlit.errors import StreamlitSecretNotFoundError
    except ImportError:
        StreamlitSecretNotFoundError = type("_SecretNotFound", (Exception,), {})  # type: ignore[misc, assignment]

    keys = (
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
        "OPEN_SOURCE_LLM_PROVIDER",
        "OLLAMA_HOST",
        "OLLAMA_MODEL",
        "AUTOPM_RATE_LIMIT_PER_MIN",
        "AUTOPM_USE_LOCAL_LLM",
        "AUTOPM_ENABLE_SUBAGENTS",
    )
    try:
        sec = st.secrets
    except StreamlitSecretNotFoundError:
        return
    except Exception:
        return

    for key in keys:
        try:
            val = sec[key]
        except StreamlitSecretNotFoundError:
            return
        except (KeyError, TypeError):
            continue
        if val is not None and str(val).strip():
            os.environ.setdefault(key, str(val))


_secrets_into_os_environ()
_ensure_session_defaults()
inject_compact_css()

h1, h2 = st.columns([3, 1])
with h1:
    st.title("AutoPM")
    st.caption("인터뷰 → Agent 분석 → 발표용 추진계획서 PPT")
with h2:
    run_mode = st.radio(
        "모드",
        ["Guided", "Auto"],
        index=0 if st.session_state.run_mode == "Guided" else 1,
        horizontal=True,
        label_visibility="collapsed",
    )
st.session_state.run_mode = run_mode

with st.sidebar:
    st.subheader("워크플로")
    st.markdown(_SIDEBAR)
    st.markdown(
        "**인터뷰 사용법**\n"
        "1. 주제 입력 → **인터뷰 시작**\n"
        "2. 파란 질문 박스 확인\n"
        "3. 하단 입력창에 답하고 **Enter**"
    )
    with st.expander("5-Layer Architecture", expanded=False):
        st.markdown(_LAYERS_KR)
    st.divider()
    try:
        from autopm.services.llm_router import get_llm_routing_status

        _llm = get_llm_routing_status()
        st.caption("**LLM 라우팅**")
        st.caption(
            f"OpenAI: {'ON' if _llm.get('openai_configured') else 'OFF'} · "
            f"로컬(Ollama): {'ON' if _llm.get('local_llm_enabled') else 'OFF'} · "
            f"Sub-Agent: {'ON' if _llm.get('subagents_enabled') else 'OFF'}"
        )
        if _llm.get("local_llm_enabled"):
            st.caption(f"Ollama: `{_llm.get('ollama_model')}` @ `{_llm.get('ollama_host')}`")
    except Exception:
        pass
    st.caption(
        "`OPEN_SOURCE_LLM_PROVIDER=ollama` 또는 `AUTOPM_USE_LOCAL_LLM=true` 이면 Sub-Agent·피어 리뷰에 로컬 LLM을 씁니다. "
        "mock이면 rule-based fallback으로도 PPT가 생성됩니다."
    )
    if st.button("새 인터뷰 초기화", help="대화·수집 상태를 비웁니다."):
        st.session_state.interview_state = InterviewState().to_dict()
        st.session_state.interview_started = False
        st.session_state.last_result = None
        st.session_state.agent_steps = None
        st.session_state.ppt_gen = PPTGenerationState().to_dict()
        st.session_state.autopm_state_json = None
        st.session_state.crew_inputs = {}
        st.session_state.guided_ui_step = "input_confirm"
        for _wk in ("interview_chat_input", "seed_idea"):
            st.session_state.pop(_wk, None)
        st.rerun()

tab_interview, tab_progress, tab_results = st.tabs(
    ["💬 인터뷰·프로세스", "📊 수집·진행", "📁 산출물"],
)

with tab_interview:
    start_clicked, gen_clicked, seed = render_interview_tab(
        st.session_state.run_mode,
        _get_iv,
        _save_iv,
        st.session_state.interview_started,
    )
with tab_progress:
    overall_progress, dash_placeholder = render_progress_tab(
        _get_iv,
        _save_iv,
        st.session_state.agent_steps,
        st.session_state.last_result,
        st.session_state.ppt_gen,
    )

with tab_results:
    render_results_tab(st.session_state.last_result, st.session_state.agent_steps)


def _dash_render(steps_list: list) -> None:
    """우측 Agent 대시보드를 갱신한다 — PPT 실행 중 콜백에서 호출된다."""
    with dash_placeholder.container():
        render_agent_progress(steps_list, progress_callback=overall_progress.progress)


if start_clicked:
    if not (seed or "").strip():
        st.warning("한 문장 이상 입력한 뒤 **인터뷰 시작**을 눌러 주세요.")
    else:
        s0 = InterviewState()
        bot0 = InterviewBot(s0)
        bot0.start_with_initial_message(seed)
        _save_iv(bot0.state)
        st.session_state.interview_started = True
        st.rerun()

if gen_clicked:
    st.toast("생성 중 — **수집·진행** 탭에서 Agent 상태를 확인하세요.", icon="⏳")
    s_run = _get_iv()
    inputs = s_run.to_autopm_inputs()
    agent_steps = get_agent_steps()
    simulate_agent_progress(agent_steps, render_fn=_dash_render)

    for step in agent_steps:
        step.status = "pending"
        step.artifact = ""
        step.completion_message = ""

    with st.status("Supervisor / AutoPMFlow 실행 중…", expanded=True) as status:

        def _prog(msg: str) -> None:
            status.write(msg)
            apply_progress_message(agent_steps, msg)
            _dash_render(agent_steps)

        status.write(
            "추진계획서 주제·인터뷰 → mock/ollama 초안 → (선택) OpenAI refine → Deep Agents(대화·고도화) → PPT → python-pptx"
        )
        inputs.update({k: str(v) for k, v in st.session_state.crew_inputs.items() if v})
        status.write(f"실행 입력 키: `{', '.join(sorted(inputs.keys()))}`")
        result = run_autopm(
            inputs,
            on_progress=_prog,
            ppt_gen_json=PPTGenerationState.for_auto_mode().to_dict(),
        )
        status.write("완료")

        finalize_agent_dashboard(agent_steps, result)
        _dash_render(agent_steps)
        overall_progress.progress(1.0)
        st.session_state.last_result = result
        if result.structured.get("ppt_generation_state"):
            st.session_state.ppt_gen = result.structured["ppt_generation_state"]
        st.session_state.agent_steps = agent_steps
    st.session_state.autopm_state_json = result.state.model_dump()
    st.session_state.crew_inputs.update(result.state.user_input)
    st.rerun()


def _apply_revision_to_pg(pg: PPTGenerationState, text: str) -> None:
    t = (text or "").strip()
    if t:
        pg.add_revision(t)


def _run_guided_phase(
    phase: str,
    inputs: dict,
    pg: PPTGenerationState,
    agent_steps: list,
    status_box,
) -> Any:
    """Guided 모드에서 run_autopm_phased를 호출하고 세션 스냅샷을 갱신한다."""

    def _prog(msg: str) -> None:
        status_box.write(msg)
        apply_progress_message(agent_steps, msg)
        _dash_render(agent_steps)

    return run_autopm_phased(
        phase,
        inputs,
        st.session_state.autopm_state_json,
        pg.to_dict(),
        on_progress=_prog,
    )


def _render_guided_panel() -> None:
    """Guided 모드 — 인터뷰 탭 하단에서 단계별 승인 UI."""
    st.divider()
    st.markdown("##### Guided — 단계별 승인")
    rev = st.text_area("Revision / 수정 요청", height=60, key="guided_revision_box")
    pg = _get_pg()
    gu = st.session_state.guided_ui_step
    st.caption(f"현재 단계: **{gu}**")

    def _mark_steps(pg2: PPTGenerationState, *ids: str, status: str = "complete") -> None:
        for i in ids:
            if i in pg2.step_statuses:
                pg2.step_statuses[i] = status
        _save_pg(pg2)

    if gu == "input_confirm":
        st.markdown("##### 3) 입력 정보 확인")
        iv = _get_iv()
        for lb, dp, ok in iv.summary_rows():
            st.write(f"{'✅' if ok else '⏳'} **{lb}** — {dp}")
        a, b, c = st.columns(3)
        if a.button("① 이 정보로 계속 진행", key="in_ok"):
            pg.selected_options["input_confirm"] = "proceed"
            _apply_revision_to_pg(pg, rev)
            _mark_steps(pg, "idea_input", "interview", "confirm_input")
            st.session_state.guided_ui_step = "draft_generate"
            _save_pg(pg)
            st.rerun()
        if b.button("② 부족한 정보 추가 입력", key="in_add"):
            pg.selected_options["input_confirm"] = "add_info"
            st.info("왼쪽 인터뷰를 계속한 뒤 다시 ①을 눌러 주세요.")
        if c.button("③ 일부 항목 수정", key="in_edit"):
            pg.selected_options["input_confirm"] = "edit_fields"
            st.info("오른쪽 **상세 필드 직접 수정** 폼을 사용하세요.")

    elif gu == "draft_generate":
        st.markdown("##### 4) 1차 초안 생성")
        if st.button("다음 단계: 1차 초안 생성", type="primary"):
            inputs = _base_inputs_from_interview()
            agent_steps = get_agent_steps()
            for step in agent_steps:
                step.status = "pending"
                step.artifact = ""
                step.completion_message = ""
            simulate_agent_progress(agent_steps, render_fn=_dash_render)
            with st.status("draft_only", expanded=True) as status:
                res = _run_guided_phase(PHASE_DRAFT_ONLY, inputs, pg, agent_steps, status)
                status.write("초안 완료")
            st.session_state.autopm_state_json = res.state.model_dump()
            st.session_state.crew_inputs.update(res.state.user_input)
            pg = _get_pg()
            pg.draft_generated = True
            _mark_steps(pg, "draft_generate")
            st.session_state.guided_ui_step = "draft_decide"
            _save_pg(pg)
            finalize_agent_dashboard(agent_steps, res)
            _dash_render(agent_steps)
            overall_progress.progress(1.0)
            st.rerun()

    elif gu == "draft_decide":
        st.markdown("##### 5) 초안 승인 / 톤 선택")
        st.code(st.session_state.crew_inputs.get("open_source_draft", "")[:6000], language="markdown")
        r1, r2, r3, r4, r5 = st.columns(5)
        if r1.button("① 그대로 진행"):
            pg.selected_options["draft_tone"] = "proceed"
            _apply_revision_to_pg(pg, rev)
            _mark_steps(pg, "draft_approve")
            st.session_state.guided_ui_step = "core_run"
            _save_pg(pg)
            st.rerun()
        if r2.button("② 더 전문적"):
            pg.selected_options["draft_tone"] = "tone_pro"
            _apply_revision_to_pg(pg, rev)
            inputs = _base_inputs_from_interview()
            agent_steps = get_agent_steps()
            with st.status("refine_draft", expanded=True) as status:
                res = _run_guided_phase(PHASE_REFINE_DRAFT, inputs, pg, agent_steps, status)
            st.session_state.autopm_state_json = res.state.model_dump()
            st.session_state.crew_inputs.update(res.state.user_input)
            st.session_state.guided_ui_step = "core_run"
            _mark_steps(pg, "draft_approve")
            _save_pg(pg)
            st.rerun()
        if r3.button("③ 더 간결"):
            pg.selected_options["draft_tone"] = "tone_concise"
            _apply_revision_to_pg(pg, rev)
            inputs = _base_inputs_from_interview()
            agent_steps = get_agent_steps()
            with st.status("refine_draft", expanded=True) as status:
                res = _run_guided_phase(PHASE_REFINE_DRAFT, inputs, pg, agent_steps, status)
            st.session_state.autopm_state_json = res.state.model_dump()
            st.session_state.crew_inputs.update(res.state.user_input)
            st.session_state.guided_ui_step = "core_run"
            _mark_steps(pg, "draft_approve")
            _save_pg(pg)
            st.rerun()
        if r4.button("④ 경영진 톤"):
            pg.selected_options["draft_tone"] = "tone_exec"
            _apply_revision_to_pg(pg, rev)
            inputs = _base_inputs_from_interview()
            agent_steps = get_agent_steps()
            with st.status("refine_draft", expanded=True) as status:
                res = _run_guided_phase(PHASE_REFINE_DRAFT, inputs, pg, agent_steps, status)
            st.session_state.autopm_state_json = res.state.model_dump()
            st.session_state.crew_inputs.update(res.state.user_input)
            st.session_state.guided_ui_step = "core_run"
            _mark_steps(pg, "draft_approve")
            _save_pg(pg)
            st.rerun()
        if r5.button("⑤ 특정 추가"):
            pg.selected_options["draft_tone"] = "tone_custom"
            pg.user_decisions["draft_extra"] = rev
            inputs = _base_inputs_from_interview()
            agent_steps = get_agent_steps()
            with st.status("refine_draft", expanded=True) as status:
                res = _run_guided_phase(PHASE_REFINE_DRAFT, inputs, pg, agent_steps, status)
            st.session_state.autopm_state_json = res.state.model_dump()
            st.session_state.crew_inputs.update(res.state.user_input)
            st.session_state.guided_ui_step = "core_run"
            _mark_steps(pg, "draft_approve")
            _save_pg(pg)
            st.rerun()

    elif gu == "core_run":
        st.markdown("##### 6–7) Core Deep Agents + 문서 (승인 후 실행)")
        if st.button("현재 단계 승인 → Core+문서 생성", type="primary"):
            inputs = _base_inputs_from_interview()
            agent_steps = get_agent_steps()
            simulate_agent_progress(agent_steps, render_fn=_dash_render)
            with st.status("core_doc", expanded=True) as status:
                res = _run_guided_phase(PHASE_CORE_DOC, inputs, pg, agent_steps, status)
            st.session_state.autopm_state_json = res.state.model_dump()
            st.session_state.crew_inputs.update(res.state.user_input)
            st.session_state.last_result = res
            st.session_state.agent_steps = agent_steps
            _mark_steps(pg, "slide_plan_generate", "slide_plan_approve", status="pending")
            pg.step_statuses["slide_plan_generate"] = "active"
            st.session_state.guided_ui_step = "slide_pick"
            _save_pg(pg)
            finalize_agent_dashboard(agent_steps, res)
            _dash_render(agent_steps)
            overall_progress.progress(1.0)
            st.rerun()

    elif gu == "slide_pick":
        st.markdown("##### 8) 슬라이드 구성 선택")
        s1, s2, s3, s4, s5 = st.columns(5)
        if s1.button("① 기본 10장"):
            pg.selected_options["slide_structure"] = "default_10"
            _save_pg(pg)
            st.session_state.guided_ui_step = "slide_exec"
            st.rerun()
        if s2.button("② 간략 6장"):
            pg.selected_options["slide_structure"] = "compact_6"
            _save_pg(pg)
            st.session_state.guided_ui_step = "slide_exec"
            st.rerun()
        if s3.button("③ 상세 12장"):
            pg.selected_options["slide_structure"] = "detailed_12"
            _save_pg(pg)
            st.session_state.guided_ui_step = "slide_exec"
            st.rerun()
        if s4.button("④ 추가/삭제"):
            pg.selected_options["slide_structure"] = "custom_add_remove"
            pg.user_decisions["slide_custom_notes"] = rev
            _save_pg(pg)
            st.session_state.guided_ui_step = "slide_exec"
            st.rerun()
        if s5.button("⑤ 순서 변경"):
            pg.selected_options["slide_structure"] = "reorder"
            pg.user_decisions["slide_custom_notes"] = rev
            _save_pg(pg)
            st.session_state.guided_ui_step = "slide_exec"
            st.rerun()

    elif gu == "slide_exec":
        st.markdown("##### 슬라이드 스토리라인 생성")
        if st.button("Storyline Agent 실행"):
            inputs = _base_inputs_from_interview()
            agent_steps = st.session_state.agent_steps or get_agent_steps()
            _apply_revision_to_pg(pg, rev)
            with st.status("storyline", expanded=True) as status:
                res = _run_guided_phase(PHASE_STORYLINE, inputs, pg, agent_steps, status)
            st.session_state.autopm_state_json = res.state.model_dump()
            pg = _get_pg()
            pg.slide_plan_generated = True
            pg.last_storyline_json = res.state.slide_storyline_raw or ""
            _mark_steps(pg, "slide_plan_generate")
            st.session_state.guided_ui_step = "style_pick"
            _save_pg(pg)
            st.rerun()

    elif gu == "style_pick":
        st.markdown("##### 9) 장표 스타일")
        _pgv = _get_pg()
        _snip = (
            (_pgv.last_storyline_json or "")[:4000]
            if _pgv.last_storyline_json
            else (
                (st.session_state.autopm_state_json or {}).get("slide_storyline_raw", "")[:4000]
                if st.session_state.autopm_state_json
                else ""
            )
        )
        st.code(_snip or "(스토리라인 없음)", language="json")
        v1, v2, v3, v4, v5 = st.columns(5)
        if v1.button("① 경영진 보고형"):
            pg.selected_options["visual_style"] = "executive"
            _save_pg(pg)
            st.session_state.guided_ui_step = "vap_options"
            st.rerun()
        if v2.button("② 컨설팅 제안서형"):
            pg.selected_options["visual_style"] = "consulting"
            _save_pg(pg)
            st.session_state.guided_ui_step = "vap_options"
            st.rerun()
        if v3.button("③ 실무 추진계획형"):
            pg.selected_options["visual_style"] = "execution_plan"
            _save_pg(pg)
            st.session_state.guided_ui_step = "vap_options"
            st.rerun()
        if v4.button("④ 기술 아키텍처형"):
            pg.selected_options["visual_style"] = "architecture"
            _save_pg(pg)
            st.session_state.guided_ui_step = "vap_options"
            st.rerun()
        if v5.button("⑤ 미니멀 요약형"):
            pg.selected_options["visual_style"] = "minimal"
            _save_pg(pg)
            st.session_state.guided_ui_step = "vap_options"
            st.rerun()

    elif gu == "vap_options":
        st.markdown("##### 10) Visual Asset Plan 방향")
        q1, q2, q3, q4, q5 = st.columns(5)
        if q1.button("① 그대로"):
            pg.selected_options["visual_asset_plan"] = "proceed"
            _save_pg(pg)
            st.session_state.guided_ui_step = "vis_run"
            st.rerun()
        if q2.button("② 그림 더 많이"):
            pg.selected_options["visual_asset_plan"] = "more_graphics"
            _save_pg(pg)
            st.session_state.guided_ui_step = "vis_run"
            st.rerun()
        if q3.button("③ 표 중심"):
            pg.selected_options["visual_asset_plan"] = "table_focus"
            _save_pg(pg)
            st.session_state.guided_ui_step = "vis_run"
            st.rerun()
        if q4.button("④ 프로세스 강화"):
            pg.selected_options["visual_asset_plan"] = "process_focus"
            _save_pg(pg)
            st.session_state.guided_ui_step = "vis_run"
            st.rerun()
        if q5.button("⑤ 슬라이드별 수정"):
            pg.selected_options["visual_asset_plan"] = "per_slide_edit"
            pg.user_decisions["visual_slide_edit"] = rev
            _save_pg(pg)
            st.session_state.guided_ui_step = "vis_run"
            st.rerun()

    elif gu == "vis_run":
        st.markdown("##### Visualization Agent")
        if st.button("Visualization 실행"):
            inputs = _base_inputs_from_interview()
            agent_steps = st.session_state.agent_steps or get_agent_steps()
            _apply_revision_to_pg(pg, rev)
            with st.status("visualization", expanded=True) as status:
                res = _run_guided_phase(PHASE_VISUALIZATION, inputs, pg, agent_steps, status)
            st.session_state.autopm_state_json = res.state.model_dump()
            pg = _get_pg()
            pg.last_visualization_json = res.state.visualization_raw or ""
            pg.visual_plan_generated = True
            _mark_steps(pg, "visual_asset_generate")
            st.session_state.guided_ui_step = "visual_ok"
            _save_pg(pg)
            st.rerun()

    elif gu == "visual_ok":
        st.markdown("##### Visual 계획 확인")
        st.code(_get_pg().last_visualization_json[:5000] if _get_pg().last_visualization_json else "", language="json")
        if st.button("승인 → Presentation Graphics"):
            _mark_steps(pg, "visual_plan_approve")
            st.session_state.guided_ui_step = "gfx_run"
            _save_pg(pg)
            st.rerun()

    elif gu == "gfx_run":
        st.markdown("##### Presentation Graphics Agent")
        if st.button("Graphics 실행"):
            inputs = _base_inputs_from_interview()
            agent_steps = st.session_state.agent_steps or get_agent_steps()
            _apply_revision_to_pg(pg, rev)
            with st.status("graphics", expanded=True) as status:
                res = _run_guided_phase(PHASE_GRAPHICS, inputs, pg, agent_steps, status)
            st.session_state.autopm_state_json = res.state.model_dump()
            pg = _get_pg()
            pg.last_graphics_json = res.state.presentation_graphics_raw or ""
            _save_pg(pg)
            st.session_state.guided_ui_step = "compose_run"
            st.rerun()

    elif gu == "compose_run":
        st.markdown("##### 11) PPT Composer + 파일 생성")
        if st.button("PPT 생성 (Composer)", type="primary"):
            inputs = _base_inputs_from_interview()
            agent_steps = st.session_state.agent_steps or get_agent_steps()
            _apply_revision_to_pg(pg, rev)
            with st.status("composer", expanded=True) as status:
                res = _run_guided_phase(PHASE_COMPOSER, inputs, pg, agent_steps, status)
            st.session_state.autopm_state_json = res.state.model_dump()
            st.session_state.crew_inputs.update(res.state.user_input)
            st.session_state.last_result = res
            if res.structured.get("ppt_generation_state"):
                st.session_state.ppt_gen = res.structured["ppt_generation_state"]
            st.session_state.agent_steps = agent_steps
            _mark_steps(pg, "ppt_generate", "post_ppt_review")
            st.session_state.guided_ui_step = "post_ppt"
            _save_pg(pg)
            finalize_agent_dashboard(agent_steps, res)
            _dash_render(agent_steps)
            overall_progress.progress(1.0)
            st.rerun()

    elif gu == "post_ppt":
        st.markdown("##### 12) 최종 개선 / 다운로드")
        st.caption("아래 선택 시 `improve_chain`으로 스토리라인 이후 단계가 재실행됩니다.")
        p1, p2, p3, p4, p5, p6 = st.columns(6)
        if p1.button("① PPT 다시 생성"):
            pg.selected_options["post_ppt"] = "regenerate"
            _apply_revision_to_pg(pg, rev)
            inputs = _base_inputs_from_interview()
            agent_steps = st.session_state.agent_steps or get_agent_steps()
            with st.status("improve", expanded=True) as status:
                res = _run_guided_phase(PHASE_IMPROVE_CHAIN, inputs, pg, agent_steps, status)
            st.session_state.autopm_state_json = res.state.model_dump()
            st.session_state.last_result = res
            st.session_state.agent_steps = agent_steps
            _save_pg(pg)
            st.rerun()
        if p2.button("② 문구 간결"):
            pg.selected_options["post_ppt"] = "concise_copy"
            _apply_revision_to_pg(pg, rev)
            inputs = _base_inputs_from_interview()
            agent_steps = st.session_state.agent_steps or get_agent_steps()
            with st.status("improve", expanded=True) as status:
                res = _run_guided_phase(PHASE_IMPROVE_CHAIN, inputs, pg, agent_steps, status)
            st.session_state.autopm_state_json = res.state.model_dump()
            st.session_state.last_result = res
            _save_pg(pg)
            st.rerun()
        if p3.button("③ 디자인 전문"):
            pg.selected_options["post_ppt"] = "pro_design"
            _apply_revision_to_pg(pg, rev)
            inputs = _base_inputs_from_interview()
            agent_steps = st.session_state.agent_steps or get_agent_steps()
            with st.status("improve", expanded=True) as status:
                res = _run_guided_phase(PHASE_IMPROVE_CHAIN, inputs, pg, agent_steps, status)
            st.session_state.autopm_state_json = res.state.model_dump()
            st.session_state.last_result = res
            _save_pg(pg)
            st.rerun()
        if p4.button("④ 리스크/ROI"):
            pg.selected_options["post_ppt"] = "risk_roi_slides"
            _apply_revision_to_pg(pg, rev)
            inputs = _base_inputs_from_interview()
            agent_steps = st.session_state.agent_steps or get_agent_steps()
            with st.status("improve", expanded=True) as status:
                res = _run_guided_phase(PHASE_IMPROVE_CHAIN, inputs, pg, agent_steps, status)
            st.session_state.autopm_state_json = res.state.model_dump()
            st.session_state.last_result = res
            _save_pg(pg)
            st.rerun()
        if p5.button("⑤ Exec Summary"):
            pg.selected_options["post_ppt"] = "exec_summary"
            _apply_revision_to_pg(pg, rev)
            inputs = _base_inputs_from_interview()
            agent_steps = st.session_state.agent_steps or get_agent_steps()
            with st.status("improve", expanded=True) as status:
                res = _run_guided_phase(PHASE_IMPROVE_CHAIN, inputs, pg, agent_steps, status)
            st.session_state.autopm_state_json = res.state.model_dump()
            st.session_state.last_result = res
            _save_pg(pg)
            st.rerun()
        if p6.button("⑥ 버전 확정"):
            pg.selected_options["post_ppt"] = "finalize"
            _mark_steps(pg, "post_ppt_review", status="complete")
            st.session_state.guided_ui_step = "done"
            _save_pg(pg)
            st.success("Guided 플로를 확정했습니다. **산출물** 탭에서 다운로드하세요.")
            st.rerun()

    elif gu == "done":
        st.info("Guided 세션 확정됨 — 필요 시 **새 인터뷰 초기화**로 처음부터 다시 시작하세요.")


if st.session_state.run_mode == "Guided":
    with tab_interview:
        _render_guided_panel()
