"""AutoPM Streamlit — 좌측 Rule-based 인터뷰 / 우측 수집 요약·Agent Progress / 하단 PPT·산출물."""

from __future__ import annotations

import json
import re
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
    GUIDED_STEP_LABELS,
    PHASE_COMPOSER,
    PHASE_CORE_DOC,
    PHASE_DRAFT_ONLY,
    PHASE_GRAPHICS,
    PHASE_IMPROVE_CHAIN,
    PHASE_REFINE_DRAFT,
    PHASE_STORYLINE,
    PHASE_VISUALIZATION,
    PPTGenerationState,
    STEP_ORDER,
)
from autopm.ui.agent_progress import (  # noqa: E402
    apply_progress_message,
    finalize_agent_dashboard,
    get_agent_steps,
    render_agent_progress,
    simulate_agent_progress,
)

load_dotenv()

# 데모·발표 시 레이어 설명을 빠르게 보여주기 위한 정적 카드 — 코드 동작과 무관하다.
_LAYERS_KR = """
| Layer | MVP 구현 |
| --- | --- |
| **L1 Presentation** | Streamlit (본 화면) |
| **L2 API/Auth** | `api/gateway.py` 어댑터 + auth/rate_limit 스텁 |
| **L3 Orchestration** | CrewAI + Supervisor + `AutoPMFlow` + Critic + PPT Crew |
| **L4 Tools/Services** | `tools/`, `services/`, `ppt/` (python-pptx Composer) |
| **L5 Data** | `data/` + `outputs/` (md/pptx/json/csv) |
"""

_SIDEBAR = """
**Supervisor** — 추진계획서 주제 입력 → 인터뷰(목적·배경·문제·톤) → 8 Core 태스크 → Critic → 문서화 →
**Storyline / Visualization / Presentation Graphics / Composer** → `project_plan.pptx`
"""


def _split_numbered_sections(text: str) -> dict[int, str]:
    sections: dict[int, list[str]] = {}
    current: int | None = None
    preamble: list[str] = []

    for line in text.splitlines():
        m = re.match(r"^##\s+(\d+)\.\s+.*$", line)
        if m:
            idx = int(m.group(1))
            current = idx
            sections.setdefault(idx, []).append(line)
            continue
        if current is None:
            preamble.append(line)
        else:
            sections[current].append(line)

    out = {k: "\n".join(v).strip() for k, v in sections.items()}
    if preamble:
        pre = "\n".join(preamble).strip()
        if pre:
            out[0] = pre
    return out


def _join_sections(parts: dict[int, str], start: int, end: int) -> str:
    chunks = []
    for i in range(start, end + 1):
        if i in parts:
            chunks.append(parts[i])
    return "\n\n".join(chunks).strip()


def _outline_json(text: str) -> str:
    sections = _split_numbered_sections(text)
    outline: dict[str, str] = {}
    for num in sorted(k for k in sections if k > 0):
        first = sections[num].splitlines()[0] if sections[num] else ""
        outline[str(num)] = first
    return json.dumps(outline, ensure_ascii=False, indent=2)


def _slide_count_from_json(path_str: str | None) -> int | None:
    if not path_str:
        return None
    p = Path(path_str)
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        slides = data.get("slides")
        if isinstance(slides, list):
            return len(slides)
    except (OSError, json.JSONDecodeError):
        return None
    return None


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
_ensure_session_defaults()

st.title("AutoPM")
st.caption("추진계획서 제목만 입력하면, Agent가 필요한 내용을 질문하고 발표 가능한 PPT를 생성합니다.")
run_mode = st.radio(
    "실행 모드",
    ["Guided", "Auto"],
    index=0 if st.session_state.run_mode == "Guided" else 1,
    horizontal=True,
    help="Guided: 단계별 승인·선택. Auto: 한 번에 끝까지 생성.",
)
st.session_state.run_mode = run_mode

with st.expander("12단계 진행 상태 (User Decision State)", expanded=False):
    pg_s = _get_pg()
    cols = st.columns(4)
    for i, sid in enumerate(STEP_ORDER):
        with cols[i % 4]:
            stat = pg_s.step_statuses.get(sid, "pending")
            st.caption(f"**{GUIDED_STEP_LABELS.get(sid, sid)}**")
            st.caption(f"`{stat}`")

with st.expander("5-Layer Architecture — MVP 매핑", expanded=False):
    st.markdown(_LAYERS_KR)

with st.sidebar:
    st.subheader("워크플로")
    st.markdown(_SIDEBAR)
    st.divider()
    st.caption(
        "`OPEN_SOURCE_LLM_PROVIDER=mock` 이면 API Key 없이도 초안·Fallback PPT가 동작합니다. "
        "OpenAI Key가 있으면 Crew 단계와 refine이 추가로 실행됩니다."
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
        st.rerun()

left_col, right_col = st.columns([0.48, 0.52])

start_clicked = False
next_clicked = False
gen_clicked = False
seed = ""
ans = ""

with left_col:
    st.subheader("대화형 인터뷰")
    st.caption(
        "AutoPM이 추진 **목적**, **배경**, **문제점**, **개선 범위**, **강조 포인트**, **PPT 톤**을 질문해 **PPT 방향**을 잡습니다."
    )
    seed = st.text_area(
        "작성할 추진계획서 주제/제목을 입력하세요.",
        value="",
        height=100,
        placeholder=(
            "예: 포스코 2026년 미래전략을 위한 Mini ERP 시스템 원가시스템 개선 제안 추진계획서"
        ),
        key="seed_idea",
        help="제목·주제만 적어도 됩니다. 이후 봇이 목적·배경 등을 순서대로 묻습니다.",
    )
    b_start, _b_spacer = st.columns([1, 3])
    with b_start:
        start_clicked = st.button("인터뷰 시작", type="secondary")

    st.divider()
    st.caption("인터뷰 대화")
    iv = _get_iv()
    for msg in iv.chat_history:
        with st.chat_message(msg.get("role", "user")):
            st.markdown(msg.get("content", ""))

    ans = st.text_area(
        "답변 입력",
        value="",
        height=88,
        key="chat_answer_box",
        help="봇의 현재 질문에 답한 뒤 **다음 질문**을 누릅니다.",
    )
    c_next, c_ppt = st.columns(2)
    with c_next:
        next_clicked = st.button("다음 질문", disabled=not st.session_state.interview_started)
    with c_ppt:
        if st.session_state.run_mode == "Auto":
            gen_clicked = st.button("🚀 AutoPM PPT 자동 생성", type="primary")
        else:
            gen_clicked = False
            st.button("🚀 Guided는 하단 패널", disabled=True)

with right_col:
    st.subheader("수집 정보·진행률")
    iv2 = _get_iv()
    filled = iv2.filled_count()
    total = iv2.total_fields()
    st.metric("필수 정보 수집률", f"{filled}/{total} 완료")
    st.progress(min(1.0, filled / max(1, total)))

    if iv2.has_assumptions():
        st.warning("일부 정보가 부족하여 AutoPM이 **가정값**을 사용합니다. 인터뷰를 더 진행하거나 아래에서 상세를 수정하세요.")

    st.markdown("##### 수집 항목 요약")
    for label, disp, ok in iv2.summary_rows():
        icon = "✅" if ok else "⏳"
        st.markdown(f"{icon} **{label}** — {disp}")

    with st.expander("상세 필드 직접 수정", expanded=False):
        st.caption("Rule-based 흐름을 건너뛰고 값만 빠르게 고칠 때 사용합니다.")
        m = _get_iv()
        with st.form("manual_interview_form"):
            st.markdown("**핵심(추진계획서)**")
            pt = st.text_input(
                "추진계획서 주제/제목",
                value=m.proposal_title or m.idea_title or "",
            )
            ppur = st.text_input("목적", value=m.proposal_purpose or "")
            bg = st.text_area("배경", value=m.background_context or "", height=64)
            prob = st.text_area("핵심 문제", value=m.current_problems or m.pain_points or "", height=56)
            ts = st.text_input("대상 시스템", value=m.target_system or "")
            bs = st.text_area("업무·기능 범위", value=m.business_scope or "", height=56)
            imp = st.text_area("개선 방향", value=m.improvement_direction or m.goal or "", height=56)
            aud = st.text_input("보고 대상·의사결정자", value=m.target_audience or "")
            emph = st.text_input("강조 포인트", value=m.key_emphasis or "")
            tone = st.text_input("PPT 톤", value=m.presentation_tone or "")
            st.markdown("**실행 정보(후순위)**")
            rd = st.text_input("관련 부서", value=m.related_departments or "")
            tl = st.text_input("희망 추진 기간", value=m.timeline or "")
            br = st.text_input("예산 범위", value=m.budget_range or "")
            eff = st.text_area("기대 효과", value=m.expected_effects or "", height=48)
            cons = st.text_area("제약·전제", value=m.constraints or "", height=40)
            refm = st.text_input("참고 자료", value=m.reference_materials or "")
            st.markdown("**리소스(선택 — 효율·절감 강조 시 인터뷰에서 별도 질문)**")
            mh = st.number_input(
                "월 소요 시간(시간)",
                min_value=0,
                value=int(m.monthly_hours) if m.monthly_hours is not None else 0,
            )
            pc = st.number_input(
                "관련 인원(명)",
                min_value=0,
                value=int(m.people_count) if m.people_count is not None else 0,
            )
            st.caption("레거시 필드(AS-IS 텍스트용)")
            cp = st.text_area("현재 업무 요약(선택)", value=m.current_process or "", height=48)
            submitted = st.form_submit_button("요약 카드에 반영")
        if submitted:
            m.proposal_title = pt.strip() or None
            m.idea_title = m.proposal_title
            m.proposal_purpose = ppur.strip() or None
            m.background_context = bg.strip() or None
            m.current_problems = prob.strip() or None
            m.pain_points = m.current_problems
            m.target_system = ts.strip() or None
            m.business_scope = bs.strip() or None
            m.improvement_direction = imp.strip() or None
            m.goal = m.improvement_direction
            m.target_audience = aud.strip() or None
            m.key_emphasis = emph.strip() or None
            m.presentation_tone = tone.strip() or None
            m.related_departments = rd.strip() or None
            m.timeline = tl.strip() or None
            m.budget_range = br.strip() or None
            m.expected_effects = eff.strip() or None
            m.constraints = cons.strip() or None
            m.reference_materials = refm.strip() or None
            m.monthly_hours = int(mh) if mh > 0 else None
            m.people_count = int(pc) if pc > 0 else None
            m.current_process = cp.strip() or None
            _save_iv(m)
            st.success("반영되었습니다.")
            st.rerun()

    st.divider()
    st.subheader("Agent Progress Dashboard")
    overall_progress = st.progress(0.0)
    dash_placeholder = st.empty()

    if st.session_state.agent_steps:
        with dash_placeholder.container():
            render_agent_progress(
                st.session_state.agent_steps,
                progress_callback=overall_progress.progress,
            )
        overall_progress.progress(1.0 if st.session_state.last_result else 0.0)
    else:
        with dash_placeholder.container():
            st.info("**Auto** 실행 또는 **Guided** 패널 진행 시 12단계 Agent 진행 상황이 여기에 표시됩니다.")


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

if next_clicked:
    if not st.session_state.interview_started:
        st.warning("먼저 **인터뷰 시작**을 눌러 주세요.")
    elif not (ans or "").strip():
        st.warning("답변을 입력해 주세요.")
    else:
        b = InterviewBot(_get_iv())
        b.apply_chat_answer(ans)
        _save_iv(b.state)
        st.session_state["chat_answer_box"] = ""
        st.rerun()

if gen_clicked:
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
            "추진계획서 주제·인터뷰 → mock/ollama 초안 → (선택) OpenAI refine → CrewAI → PPT Crew → python-pptx"
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


if st.session_state.run_mode == "Guided":
    st.divider()
    st.subheader("User Decision Panel (Guided)")
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
        st.markdown("##### 6–7) Core Crew + 문서 (승인 후 실행)")
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
            st.success("Guided 플로를 확정했습니다. 하단 산출물 탭에서 다운로드하세요.")
            st.rerun()

    elif gu == "done":
        st.info("Guided 세션 확정됨 — 필요 시 **새 인터뷰 초기화**로 처음부터 다시 시작하세요.")

st.subheader("산출물 (PPT · Slide Plan · Visual Asset · 문서)")

result = st.session_state.last_result
if not result:
    st.info(
        "**Auto**: 주제 입력·인터뷰 후 **자동 생성**. **Guided**: 하단 패널에서 단계별 승인 후 산출물이 열립니다."
    )
else:
    st.subheader("Supervisor State & Critic Loop")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Critic Score", result.state.critic_score if result.state.critic_score is not None else "—")
    with c2:
        st.metric("PASS Gate (≥80)", "PASS" if result.state.pass_quality_gate else "FAIL")
    with c3:
        st.metric("Loop Count", f"{result.state.loop_count} / {result.state.max_loops}")

    st.caption(
        f"Phase: `{result.state.current_phase}` | Feedback Target: `{result.state.feedback_target or '—'}` | "
        f"Improvements: {len(result.state.improvement_applied)}"
    )

    if st.session_state.agent_steps:
        st.subheader("Agent 산출 요약")
        rows = []
        for ag in st.session_state.agent_steps:
            rows.append(
                {
                    "Agent": ag.display_name,
                    "상태": ag.status,
                    "산출물": (ag.artifact or "")[:120],
                    "완료 메시지": ag.completion_message or "",
                }
            )
        st.dataframe(rows, hide_index=True, use_container_width=True)

    with st.expander("Structured JSON / Logs", expanded=False):
        st.json(result.structured)
        if result.state.timings_ms:
            st.caption("구간 소요(ms)")
            st.json(result.state.timings_ms)
        st.text_area("실행 로그 (최근)", value="\n".join(result.state.logs[-40:]), height=180)

    result_md = result.markdown
    parts = _split_numbered_sections(result_md)

    ppt_path = result.state.artifacts.get("project_plan.pptx")
    slide_json_path = result.state.artifacts.get("slide_plan.json")
    n_slides = _slide_count_from_json(slide_json_path)
    visual_assets_path = result.state.artifacts.get("visual_assets.json")

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

    # 사용자 요청 순서: PPT → Slide Plan → Visual Asset → Evaluation → (기존 탭) → Raw
    t_ppt, t_slide, t_vap, t_eval, t_doc, t_wbs, t_budget, t_risk, t_critic, t_raw = st.tabs(
        [
            "PPT Download",
            "Slide Plan",
            "Visual Asset Plan",
            "Evaluation Report",
            "추진계획서 Markdown",
            "WBS",
            "예산/ROI",
            "리스크",
            "Critic Review",
            "Raw JSON",
        ]
    )

    with t_ppt:
        st.markdown("##### 생성된 추진계획서 PPT")
        st.caption(f"파일: **project_plan.pptx** · 슬라이드 수: **{n_slides or '—'}**")
        if ppt_path and Path(ppt_path).is_file():
            with open(ppt_path, "rb") as fp:
                st.download_button(
                    label="📥 추진계획서 PPT 다운로드",
                    data=fp,
                    file_name="project_plan.pptx",
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                )
        else:
            st.warning("PPT 경로를 찾지 못했습니다. `outputs/project_plan.pptx` 를 확인하세요.")

    with t_slide:
        if slide_json_path and Path(slide_json_path).is_file():
            st.code(Path(slide_json_path).read_text(encoding="utf-8"), language="json")
        else:
            st.info("slide_plan.json 이 없습니다.")
        if parts.get(12):
            st.markdown("---")
            st.markdown(parts[12])

    with t_vap:
        rows_v = _visual_asset_rows_from_file(visual_assets_path)
        if rows_v:
            st.dataframe(rows_v, hide_index=True, use_container_width=True)
        else:
            st.caption("visual_assets.json 이 없거나 비어 있습니다. Fallback 실행 후에도 manifest는 생성될 수 있습니다.")
        if visual_assets_path and Path(visual_assets_path).is_file():
            with st.expander("visual_assets.json 원문"):
                st.code(Path(visual_assets_path).read_text(encoding="utf-8"), language="json")

    with t_eval:
        st.markdown("##### AutoPM Quality Harness")
        harness = result.structured.get("harness") or result.state.artifacts.get("evaluation_report") or {}
        if not harness:
            st.info("아직 Harness 리포트가 없습니다. Generate 실행 후 확인하세요.")
        else:
            overall = harness.get("overall_score", "—")
            passed = harness.get("final_passed", False)
            loops = harness.get("improvement_attempts", 0)
            max_loops = harness.get("max_improvement_attempts", 3)
            failed_criteria = harness.get("failed_criteria") or []
            st.metric("Overall Score", f"{overall} / 100")
            st.caption(f"Status: **{'PASS' if passed else 'FAIL'}** · Improvement Loops: **{loops}** / {max_loops}")
            if failed_criteria:
                st.caption(f"Failed criteria (sample): **{len(failed_criteria)}**")
            st.markdown("**Agent별 점수**")
            scores = harness.get("agent_scores") or {}
            if scores:
                st.dataframe(
                    [{"Agent": k, "Score": v} for k, v in sorted(scores.items())],
                    hide_index=True,
                    use_container_width=True,
                )
            else:
                st.caption("Agent 점수 없음 (평가 스킵 또는 오류)")
            with st.expander("실패한 기준·경고·권고"):
                st.json(
                    {
                        "failed_criteria": failed_criteria,
                        "warnings": harness.get("warnings"),
                        "recommendations": harness.get("recommendations"),
                        "feedback_target": harness.get("feedback_target"),
                    }
                )
            er_json = result.state.artifacts.get("evaluation_report.json")
            er_md = result.state.artifacts.get("evaluation_report.md")
            if er_json and Path(er_json).is_file():
                st.caption(f"`evaluation_report.json` — `{er_json}`")
            if er_md and Path(er_md).is_file():
                with st.expander("evaluation_report.md"):
                    st.code(Path(er_md).read_text(encoding="utf-8"), language="markdown")

    with t_doc:
        block = _join_sections(parts, 1, 6)
        if parts.get(0):
            st.markdown(parts[0])
        st.markdown(block or "_섹션을 찾지 못했습니다._")

    with t_wbs:
        st.markdown(parts.get(7, "_§7 WBS 없음_"))

    with t_budget:
        st.markdown(_join_sections(parts, 8, 9) or "_§8~9 예산/KPI 없음_")

    with t_risk:
        st.markdown(parts.get(10, "_§10 리스크 없음_"))

    with t_critic:
        st.markdown(parts.get(11, "_§11 Critic 없음_"))

    with t_raw:
        st.code(result_md, language="markdown")
        with st.expander("섹션 헤더 목록 JSON"):
            st.code(_outline_json(result_md), language="json")
        st.json(result.structured)
        if result.state.artifacts:
            st.caption("저장된 산출물:")
            for k, v in result.state.artifacts.items():
                st.caption(f"- **{k}**: `{v}`")
