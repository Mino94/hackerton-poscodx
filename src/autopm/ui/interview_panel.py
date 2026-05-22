"""인터뷰 탭 — 주제 입력 → 추천 방향 선택 → 자동 생성."""



from __future__ import annotations



from typing import Callable



import streamlit as st



from autopm.chat import InterviewBot, InterviewState

from autopm.chat.question_rules import DEMO_SCENARIO_SEED, FIELD_QUICK_CHOICES, demo_sample_for_field

from autopm.ui.direction_presets import apply_direction_preset
from autopm.ui.direction_recommender import (
    preset_to_session_dict,
    recommend_directions_for_topic,
    resolve_preset_for_run,
)



_DEMO_SEED = DEMO_SCENARIO_SEED





def _apply_answer(get_iv: Callable[[], InterviewState], save_iv: Callable[[], InterviewState], text: str) -> None:

    bot = InterviewBot(get_iv())

    bot.apply_chat_answer(text)

    save_iv(bot.state)





def _apply_quick(get_iv: Callable[[], InterviewState], save_iv: Callable[[], InterviewState], choice: str) -> None:

    if not st.session_state.interview_started:

        st.session_state._interview_ui_warn = "먼저 아래 **직접 주제 인터뷰**를 시작해 주세요."

        return

    _apply_answer(get_iv, save_iv, choice)





def _apply_current_sample(get_iv: Callable[[], InterviewState], save_iv: Callable[[], InterviewState]) -> None:

    if not st.session_state.interview_started:

        st.session_state._interview_ui_warn = "먼저 **직접 주제 인터뷰**를 시작해 주세요."

        return

    bot = InterviewBot(get_iv())

    bot.apply_demo_sample_for_current()

    save_iv(bot.state)





def _fill_all_samples(get_iv: Callable[[], InterviewState], save_iv: Callable[[], InterviewState]) -> None:

    if not st.session_state.interview_started:

        st.session_state._interview_ui_warn = "먼저 **직접 주제 인터뷰**를 시작해 주세요."

        return

    bot = InterviewBot(get_iv())

    n = bot.fill_all_remaining_demo_samples()

    save_iv(bot.state)

    st.session_state._interview_ui_info = f"데모 샘플로 **{n}개** 항목을 채웠습니다."





def _skip_field(get_iv: Callable[[], InterviewState], save_iv: Callable[[], InterviewState]) -> None:

    if not st.session_state.interview_started:

        return

    iv = get_iv()

    if not iv.skip_current_field():

        st.session_state._interview_ui_warn = "이 질문은 건너뛸 수 없습니다."

        return

    save_iv(iv)





def _trigger_direction_run(

    preset_id: str,

    get_iv: Callable[[], InterviewState],

    save_iv: Callable[[], InterviewState],

) -> None:

    """추천 방향 선택 → 인터뷰 필드 채움 + 자동 생성 플래그."""

    preset = resolve_preset_for_run(
        preset_id,
        st.session_state.get("direction_recommendations"),
    )

    if preset is None:

        st.session_state._interview_ui_warn = "선택한 방향을 찾을 수 없습니다. 주제를 다시 입력해 주세요."

        return

    state = apply_direction_preset(preset_id, preset=preset)

    save_iv(state)

    st.session_state.interview_started = True

    st.session_state.selected_direction_id = preset_id

    st.session_state._direction_auto_run = preset_id

    st.session_state.guided_ui_step = "input_confirm"





def _on_analyze_topic(get_iv: Callable[[], InterviewState], save_iv: Callable[[], InterviewState]) -> None:

    """주제 분석 → 추천 방향 목록을 세션에 저장."""

    topic = (st.session_state.get("topic_one_liner") or "").strip()

    if not topic:

        st.session_state._interview_ui_warn = "추진하고 싶은 **주제·한 줄**을 입력해 주세요."

        return



    recs = recommend_directions_for_topic(topic)

    st.session_state.user_topic = topic

    st.session_state.direction_recommendations = [preset_to_session_dict(p) for p in recs]

    st.session_state.directions_ready = True

    st.session_state.selected_direction_id = None

    st.session_state._direction_auto_run = None



    # 제목만 먼저 반영해 진행률 표시

    iv = get_iv()

    title = topic.split("\n")[0].strip()[:500]

    iv.proposal_title = title

    iv.idea_title = title

    iv.completed = False

    save_iv(iv)





def _on_reset_topic() -> None:

    """주제·추천 방향을 초기화하고 1단계로 돌아간다."""

    st.session_state.directions_ready = False

    st.session_state.direction_recommendations = []

    st.session_state.user_topic = ""

    st.session_state.selected_direction_id = None

    st.session_state._direction_auto_run = None





def _render_topic_input(

    get_iv: Callable[[], InterviewState],

    save_iv: Callable[[], InterviewState],

) -> None:

    """1단계: 주제 한 줄 입력."""

    st.markdown("#### 주제만 입력하세요")

    st.caption(

        "예: `ERP 월마감 데이터 검증 자동화`, `원가시스템 개선`, `영업 보고서 자동화` — "

        "입력 후 **추천 방향 보기**를 누르면 주제에 맞는 추진계획 방향이 나옵니다."

    )



    if st.button("📋 샘플 주제 넣기", key="topic_demo_seed"):

        st.session_state.topic_one_liner = _DEMO_SEED.split("\n")[0].strip()



    st.text_area(

        "추진 주제 (한 줄~짧은 문장)",

        height=88,

        placeholder="예: ERP 월마감 데이터 검증 자동화",

        key="topic_one_liner",

        label_visibility="collapsed",

    )

    st.button(

        "✨ 추천 방향 보기",

        type="primary",

        use_container_width=True,

        on_click=_on_analyze_topic,

        args=(get_iv, save_iv),

    )





def _render_direction_cards(

    run_mode: str,

    get_iv: Callable[[], InterviewState],

    save_iv: Callable[[], InterviewState],

) -> None:

    """2단계: 주제 기반 추천 방향 카드."""

    topic = st.session_state.get("user_topic") or ""

    st.markdown("#### 추천 추진계획 방향")

    st.caption(

        f"주제 **「{topic[:80]}{'…' if len(topic) > 80 else ''}」** 에 맞춰 정리했습니다. "

        "방향을 **한 번 선택**하면 맥락이 채워지고 "

        f"**{'PPT까지 자동 생성' if run_mode == 'Auto' else 'PPT까지 한번에 진행'}** 됩니다."

    )



    if st.button("← 주제 다시 입력", key="reset_topic_dirs"):

        _on_reset_topic()

        st.rerun()



    selected = st.session_state.get("selected_direction_id")

    recs = st.session_state.get("direction_recommendations") or []

    if not recs:

        st.info("추천 방향이 없습니다. 주제를 다시 입력해 주세요.")

        _on_reset_topic()

        return



    if selected:

        for raw in recs:

            if raw.get("id") == selected:

                st.success(f"선택됨: **{raw.get('icon', '')} {raw.get('label', '')}**")

                break



    cols = st.columns(2)

    for i, raw in enumerate(recs):

        with cols[i % 2]:

            icon = raw.get("icon", "📌")

            label = raw.get("label", "추진 방향")

            tagline = raw.get("tagline", "")

            highlights = raw.get("highlights") or []

            st.markdown(

                f"**{icon} {label}**  \n"

                f"<span style='color:#64748b;font-size:0.85rem'>{tagline}</span>",

                unsafe_allow_html=True,

            )

            if highlights:

                st.caption(" · ".join(highlights))

            pid = raw["id"]

            btn_label = (

                "🚀 이 방향으로 PPT까지 생성"

                if run_mode == "Auto"

                else "🚀 이 방향으로 시작 (PPT까지)"

            )

            st.button(

                btn_label,

                key=f"dir_run_{pid}",

                type="primary" if i == 0 else "secondary",

                use_container_width=True,

                on_click=_trigger_direction_run,

                args=(pid, get_iv, save_iv),

            )

    st.divider()





def _render_legacy_interview_flow(

    get_iv: Callable[[], InterviewState],

    save_iv: Callable[[], InterviewState],

    interview_started: bool,

) -> tuple[bool, bool, str]:

    """직접 주제 입력 → 질문 인터뷰 (기존 방식)."""

    start_clicked = False

    gen_clicked = False

    seed = ""



    if not interview_started:

        st.markdown("##### 직접 주제로 질문 인터뷰")

        if st.button("📋 샘플 예시 넣기", key="legacy_demo_seed"):

            st.session_state.seed_idea = _DEMO_SEED

            st.rerun()

        with st.form("interview_start_form", clear_on_submit=False):

            seed = st.text_area(

                "주제 / 제목",

                height=72,

                placeholder="예: ERP 월마감 데이터 검증 자동화",

                key="seed_idea",

                label_visibility="collapsed",

            )

            start_clicked = st.form_submit_button("인터뷰 시작 → 질문 받기", use_container_width=True)

        return start_clicked, gen_clicked, (seed or "").strip()



    iv = get_iv()

    field = iv.current_field()

    filled = iv.filled_count()

    total = iv.total_fields()



    if field:

        with st.container(border=True):

            st.markdown(f"**{iv.current_question_label()}** ({filled + 1}/{total})")

            st.markdown(iv.current_question_body())

            choices = FIELD_QUICK_CHOICES.get(field or "", [])

            if choices:

                qc = st.columns(min(len(choices), 3))

                for j, label in enumerate(choices):

                    with qc[j % len(qc)]:

                        st.button(

                            label,

                            key=f"quick_{field}_{j}",

                            use_container_width=True,

                            on_click=_apply_quick,

                            args=(get_iv, save_iv, label),

                        )

            st.button(

                "📋 샘플 답변",

                on_click=_apply_current_sample,

                args=(get_iv, save_iv),

            )

        user_msg = st.chat_input("답변 입력 후 Enter", key="interview_chat_input")

        if user_msg and user_msg.strip():

            _apply_answer(get_iv, save_iv, user_msg.strip())

            st.rerun()

    else:

        st.success("인터뷰 항목이 채워졌습니다. 아래에서 PPT 생성을 눌러 주세요.")

        gen_clicked = st.button("🚀 PPT 자동 생성", type="primary", use_container_width=True)



    return False, gen_clicked, ""





def render_interview_tab(

    run_mode: str,

    get_iv: Callable[[], InterviewState],

    save_iv: Callable[[], InterviewState],

    interview_started: bool,

) -> tuple[bool, bool, str]:

    """

    인터뷰 UI.

    Returns: (start_clicked, gen_clicked, seed) — 레거시 질문 인터뷰용.

    """

    warn = st.session_state.pop("_interview_ui_warn", None)

    if warn:

        st.warning(warn)

    info = st.session_state.pop("_interview_ui_info", None)

    if info:

        st.success(info)



    iv = get_iv()

    filled = iv.filled_count()

    total = iv.total_fields()

    pct = int(min(100, filled / max(1, total) * 100))



    st.progress(pct / 100.0, text=f"수집 {filled}/{total} ({pct}%)")



    # ① 주제 입력 → ② 추천 방향 선택

    if not st.session_state.get("directions_ready"):

        _render_topic_input(get_iv, save_iv)

    else:

        _render_direction_cards(run_mode, get_iv, save_iv)



    # ③ 선택: 질문 인터뷰

    with st.expander("직접 주제 입력 · 질문 인터뷰 (선택)", expanded=False):

        st.caption("방향 추천 대신 주제만 넣고 하나씩 답하고 싶을 때 사용합니다.")

        if run_mode == "Guided":

            st.caption("Guided 모드: 인터뷰 후 **수집·진행** 탭에서 단계 승인 또는 **한번에 진행**을 사용하세요.")

        start_clicked, gen_clicked, seed = _render_legacy_interview_flow(

            get_iv, save_iv, interview_started

        )

        return start_clicked, gen_clicked, seed



    return False, False, ""

