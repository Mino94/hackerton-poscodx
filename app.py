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
from autopm.ui.agent_dialogue_chat import render_agent_dialogue_tab  # noqa: E402
from autopm.ui.guided_panel import (  # noqa: E402
    GUIDED_UI_TITLE,
    render_guided_banner_in_interview,
    render_input_confirm_table,
)
from autopm.ui.direction_recommender import resolve_preset_for_run  # noqa: E402
from autopm.ui.guided_bulk import render_guided_bulk_bar  # noqa: E402
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
    if "selected_direction_id" not in st.session_state:
        st.session_state.selected_direction_id = None
    if "user_topic" not in st.session_state:
        st.session_state.user_topic = ""
    if "directions_ready" not in st.session_state:
        st.session_state.directions_ready = False
    if "direction_recommendations" not in st.session_state:
        st.session_state.direction_recommendations = []


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
        "1. **주제 한 줄** 입력 → **추천 방향 보기**\n"
        "2. 추천 **방향 카드** 1개 선택 → 자동 생성\n"
        "3. (선택) 직접 주제·질문 인터뷰\n"
        "3. **수집·진행** · **Agent 대화** · **산출물** PPT"
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
        try:
            from autopm.services.llm_router import get_mcp_routing_status

            _mcp = get_mcp_routing_status()
            _pm = _mcp.get("presenton_mcp") or {}
            _rag = _mcp.get("proposal_rag") or {}
            st.caption(
                f"MCP: {'ON' if _mcp.get('mcp_enabled') else 'OFF'} · "
                f"prefetch {len(_mcp.get('inprocess_tools') or [])} tools · "
                f"ReAct: {'ON' if _mcp.get('mcp_react') else 'OFF'} · "
                f"RAG: {_rag.get('mode', '?')} · "
                f"Presenton MCP: {'OK' if _pm.get('healthy') else ('OFF' if not _pm.get('enabled') else 'ERR')}"
            )
        except Exception:
            pass
        try:
            from autopm.services.ppt_quality_router import get_ppt_quality_config

            _pq = get_ppt_quality_config()
            st.caption(
                f"PPT API: `{_pq.get('ppt_api_mode')}` · "
                f"Presenton: {'ON' if _pq.get('presenton_enabled') else 'OFF'} · "
                f"OpenAI 슬라이드 고도화: {'ON' if _pq.get('openai_enhance_ppt') else 'OFF'} · "
                f"Gamma: {'ON' if _pq.get('gamma_configured') else 'OFF'}"
            )
        except Exception:
            pass
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
        st.session_state.selected_direction_id = None
        st.session_state.pop("_direction_auto_run", None)
        st.session_state.user_topic = ""
        st.session_state.directions_ready = False
        st.session_state.direction_recommendations = []
        st.session_state.pop("topic_one_liner", None)
        st.session_state.last_result = None
        st.session_state.agent_steps = None
        st.session_state.ppt_gen = PPTGenerationState().to_dict()
        st.session_state.autopm_state_json = None
        st.session_state.crew_inputs = {}
        st.session_state.guided_ui_step = "input_confirm"
        for _wk in ("interview_chat_input", "seed_idea"):
            st.session_state.pop(_wk, None)
        st.rerun()

# 탭·Guided 콜백에서 공유
overall_progress = None
dash_placeholder = None
start_clicked = False
gen_clicked = False
seed = ""


def _dash_render(steps_list: list) -> None:
    """Agent 대시보드 갱신 — PPT 실행 중 콜백."""
    if dash_placeholder is not None and overall_progress is not None:
        with dash_placeholder.container():
            render_agent_progress(steps_list, progress_callback=overall_progress.progress)


def _run_autopm_auto_full() -> None:
    """Auto 모드 — 인터뷰 입력으로 전체 파이프라인 실행."""
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
            "추진계획 방향 선택 → Deep Agents(대화·고도화) → PPT → python-pptx"
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
        if overall_progress is not None:
            overall_progress.progress(1.0)
        st.session_state.last_result = result
        if result.structured.get("ppt_generation_state"):
            st.session_state.ppt_gen = result.structured["ppt_generation_state"]
        st.session_state.agent_steps = agent_steps
    st.session_state.autopm_state_json = result.state.model_dump()
    st.session_state.crew_inputs.update(result.state.user_input)


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


def _sync_after_guided_run(res: Any, agent_steps: list | None = None) -> None:
    st.session_state.autopm_state_json = res.state.model_dump()
    st.session_state.crew_inputs.update(res.state.user_input)
    if agent_steps is not None:
        st.session_state.agent_steps = agent_steps
    if res.structured.get("ppt_generation_state"):
        st.session_state.ppt_gen = res.structured["ppt_generation_state"]
    st.session_state.last_result = res


def _execute_guided_bulk(preset_id: str, rev: str) -> None:
    """프리셋 기본값으로 연속 실행."""
    pg = _get_pg()
    _apply_revision_to_pg(pg, rev)
    inputs = _base_inputs_from_interview()

    if preset_id == "demo_to_ppt":
        bot = InterviewBot(_get_iv())
        n = bot.fill_all_remaining_demo_samples()
        _save_iv(bot.state)
        st.session_state.interview_started = True
        inputs = _base_inputs_from_interview()
        st.toast(f"데모 샘플 {n}개 반영 후 PPT 생성 시작", icon="⚡")
        preset_id = "to_ppt"

    agent_steps = st.session_state.agent_steps or get_agent_steps()
    for step in agent_steps:
        step.status = "pending"
        step.artifact = ""
        step.completion_message = ""

    def _mark(pg2: PPTGenerationState, *ids: str, status: str = "complete") -> None:
        for i in ids:
            if i in pg2.step_statuses:
                pg2.step_statuses[i] = status
        _save_pg(pg2)

    final_ui = st.session_state.guided_ui_step
    res: Any = None

    with st.status("Guided 한번에 진행…", expanded=True) as status:

        def _write(msg: str) -> None:
            status.write(msg)
            apply_progress_message(agent_steps, msg)
            _dash_render(agent_steps)

        if preset_id in ("to_draft", "to_core", "to_ppt"):
            pg.selected_options["input_confirm"] = "proceed"
            _mark(pg, "idea_input", "interview", "confirm_input")
            _write("초안 생성")
            simulate_agent_progress(agent_steps, render_fn=_dash_render)
            res = _run_guided_phase(PHASE_DRAFT_ONLY, inputs, pg, agent_steps, status)
            _sync_after_guided_run(res, agent_steps)
            pg = _get_pg()
            pg.draft_generated = True
            _mark(pg, "draft_generate")
            final_ui = "draft_decide"

        if preset_id in ("to_core", "to_ppt") and res is not None:
            pg.selected_options["draft_tone"] = "proceed"
            _mark(pg, "draft_approve")
            _write("Core + 문서")
            res = _run_guided_phase(PHASE_CORE_DOC, inputs, pg, agent_steps, status)
            _sync_after_guided_run(res, agent_steps)
            pg = _get_pg()
            _mark(pg, "slide_plan_generate", "slide_plan_approve", status="pending")
            pg.step_statuses["slide_plan_generate"] = "active"
            final_ui = "slide_pick"

        if preset_id == "to_ppt" and res is not None:
            pg.selected_options["slide_structure"] = "default_10"
            pg.selected_options["visual_style"] = "execution_plan"
            pg.selected_options["visual_asset_plan"] = "proceed"
            _mark(pg, "slide_plan_generate", "slide_plan_approve", "visual_style_pick")
            for label, phase in (
                ("Storyline", PHASE_STORYLINE),
                ("Visualization", PHASE_VISUALIZATION),
                ("Graphics", PHASE_GRAPHICS),
                ("PPT", PHASE_COMPOSER),
            ):
                _write(label)
                res = _run_guided_phase(phase, inputs, pg, agent_steps, status)
                _sync_after_guided_run(res, agent_steps)
                pg = _get_pg()
            pg.slide_plan_generated = True
            pg.visual_plan_generated = True
            if res:
                pg.last_storyline_json = res.state.slide_storyline_raw or ""
                pg.last_visualization_json = res.state.visualization_raw or ""
                pg.last_graphics_json = res.state.presentation_graphics_raw or ""
            _mark(pg, "visual_asset_generate", "visual_plan_approve", "ppt_generate", "post_ppt_review")
            final_ui = "post_ppt"

        if preset_id == "ppt_from_core":
            pg.selected_options["slide_structure"] = "default_10"
            pg.selected_options["visual_style"] = "execution_plan"
            pg.selected_options["visual_asset_plan"] = "proceed"
            _mark(pg, "slide_plan_generate", "slide_plan_approve", "visual_style_pick")
            for label, phase in (
                ("Storyline", PHASE_STORYLINE),
                ("Visualization", PHASE_VISUALIZATION),
                ("Graphics", PHASE_GRAPHICS),
                ("PPT", PHASE_COMPOSER),
            ):
                _write(label)
                res = _run_guided_phase(phase, inputs, pg, agent_steps, status)
                _sync_after_guided_run(res, agent_steps)
                pg = _get_pg()
            _mark(pg, "visual_asset_generate", "visual_plan_approve", "ppt_generate", "post_ppt_review")
            final_ui = "post_ppt"

        status.write("완료")

    if res is not None:
        finalize_agent_dashboard(agent_steps, res)
        _dash_render(agent_steps)
        if overall_progress is not None:
            overall_progress.progress(1.0)

    st.session_state.guided_ui_step = final_ui
    _save_pg(pg)
    st.success("한번에 진행 완료 — **산출물** 탭에서 PPT를 확인하세요.")
    st.rerun()


def _render_guided_panel() -> None:
    """Guided — 한번에 진행 프리셋 + (선택) 단계별 세부."""
    gu = st.session_state.guided_ui_step
    pg = _get_pg()

    with st.expander("수정 요청 (선택)", expanded=False):
        st.text_area(
            "수정 요청",
            height=48,
            key="guided_revision_box",
            placeholder="프리셋·단계 실행 시 반영할 지시",
            label_visibility="collapsed",
        )
    rev = st.session_state.get("guided_revision_box", "") or ""

    bulk_preset = render_guided_bulk_bar(
        gu,
        interview_started=st.session_state.interview_started,
    )
    if bulk_preset:
        _execute_guided_bulk(bulk_preset, rev)
        return

    with st.expander(f"단계별 세부 — {GUIDED_UI_TITLE.get(gu, gu)}", expanded=False):
        st.caption("프리셋 대신 한 단계씩 진행할 때만 펼치세요.")

        def _mark_steps(pg2: PPTGenerationState, *ids: str, status: str = "complete") -> None:
            for i in ids:
                if i in pg2.step_statuses:
                    pg2.step_statuses[i] = status
            _save_pg(pg2)

        if gu == "input_confirm":
            st.markdown("##### 3) 입력 정보 확인")
            render_input_confirm_table(_get_iv)
            st.markdown("**세부 승인**")
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
                if overall_progress is not None:
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
                if overall_progress is not None:
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
                if overall_progress is not None:
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
            st.info("Guided 완료 — **산출물** 탭에서 PPT 다운로드.")



tab_interview, tab_progress, tab_dialogue, tab_results = st.tabs(
    ["💬 인터뷰·프로세스", "📊 수집·진행", "🤝 Agent 대화", "📁 산출물"],
)

with tab_interview:
    start_clicked, gen_clicked, seed = render_interview_tab(
        st.session_state.run_mode,
        _get_iv,
        _save_iv,
        st.session_state.interview_started,
    )
    if st.session_state.run_mode == "Guided":
        render_guided_banner_in_interview()

with tab_progress:
    overall_progress, dash_placeholder = render_progress_tab(
        _get_iv,
        _save_iv,
        st.session_state.agent_steps,
        st.session_state.last_result,
        st.session_state.ppt_gen,
        run_mode=st.session_state.run_mode,
        guided_panel_fn=_render_guided_panel if st.session_state.run_mode == "Guided" else None,
    )

with tab_dialogue:
    render_agent_dialogue_tab(
        st.session_state.last_result,
        st.session_state.agent_steps,
        st.session_state.autopm_state_json,
    )

with tab_results:
    render_results_tab(st.session_state.last_result, st.session_state.agent_steps)


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
    _run_autopm_auto_full()
    st.rerun()

# PPT 톤(인터뷰) → Guided 장표 스타일 매핑
_TONE_TO_VISUAL_STYLE: dict[str, str] = {
    "경영진 보고형": "executive",
    "컨설팅 제안서형": "consulting",
    "실무 추진계획형": "execution_plan",
    "기술 아키텍처형": "architecture",
    "투자/예산 승인형": "minimal",
}

# 추천 방향 카드 클릭 → 자동 생성
_direction_run = st.session_state.pop("_direction_auto_run", None)
if _direction_run:
    preset = resolve_preset_for_run(
        _direction_run,
        st.session_state.get("direction_recommendations"),
    )
    preset_label = preset.label if preset else _direction_run
    st.toast(f"「{preset_label}」방향으로 생성을 시작합니다.", icon="🚀")
    if st.session_state.run_mode == "Guided":
        pg = _get_pg()
        iv = _get_iv()
        tone = (iv.presentation_tone or "").strip()
        if tone in _TONE_TO_VISUAL_STYLE:
            pg.selected_options["visual_style"] = _TONE_TO_VISUAL_STYLE[tone]
            _save_pg(pg)
        bulk_id = preset.bulk_preset if preset else "to_ppt"
        _execute_guided_bulk(bulk_id, "")
    else:
        _run_autopm_auto_full()
    st.rerun()


