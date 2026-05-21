"""인터뷰 탭 — 단계 안내·현재 질문·Enter 답변·빠른 선택."""

from __future__ import annotations

from typing import Callable

import streamlit as st

from autopm.chat import InterviewBot, InterviewState
from autopm.chat.question_rules import DEMO_SCENARIO_SEED, FIELD_QUICK_CHOICES, demo_sample_for_field

# 레거시 import 호환
_DEMO_SEED = DEMO_SCENARIO_SEED


def _apply_answer(get_iv: Callable[[], InterviewState], save_iv: Callable[[InterviewState], None], text: str) -> None:
    bot = InterviewBot(get_iv())
    bot.apply_chat_answer(text)
    save_iv(bot.state)


def _apply_quick(get_iv: Callable[[], InterviewState], save_iv: Callable[[InterviewState], None], choice: str) -> None:
    if not st.session_state.interview_started:
        st.session_state._interview_ui_warn = "먼저 **① 인터뷰 시작**을 눌러 주세요."
        return
    _apply_answer(get_iv, save_iv, choice)


def _apply_current_sample(get_iv: Callable[[], InterviewState], save_iv: Callable[[InterviewState], None]) -> None:
    if not st.session_state.interview_started:
        st.session_state._interview_ui_warn = "먼저 **① 인터뷰 시작**을 눌러 주세요."
        return
    bot = InterviewBot(get_iv())
    bot.apply_demo_sample_for_current()
    save_iv(bot.state)


def _fill_all_samples(get_iv: Callable[[], InterviewState], save_iv: Callable[[InterviewState], None]) -> None:
    if not st.session_state.interview_started:
        st.session_state._interview_ui_warn = "먼저 **① 인터뷰 시작**을 눌러 주세요."
        return
    bot = InterviewBot(get_iv())
    n = bot.fill_all_remaining_demo_samples()
    save_iv(bot.state)
    st.session_state._interview_ui_info = f"데모 샘플로 **{n}개** 항목을 채웠습니다. 바로 **PPT 생성** 가능합니다."


def _skip_field(get_iv: Callable[[], InterviewState], save_iv: Callable[[InterviewState], None]) -> None:
    if not st.session_state.interview_started:
        st.session_state._interview_ui_warn = "먼저 **① 인터뷰 시작**을 눌러 주세요."
        return
    iv = get_iv()
    if not iv.skip_current_field():
        st.session_state._interview_ui_warn = "이 질문은 건너뛸 수 없습니다. 짧게라도 입력해 주세요."
        return
    save_iv(iv)


def render_interview_tab(
    run_mode: str,
    get_iv: Callable[[], InterviewState],
    save_iv: Callable[[InterviewState], None],
    interview_started: bool,
) -> tuple[bool, bool, str]:
    """
    인터뷰 UI.
    Returns: (start_clicked, gen_clicked, seed_for_legacy_start_handler)
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

    # ── 진행 단계 안내 ──
    if not interview_started:
        step_hint = "**① 주제 입력** → **② 인터뷰 시작** → 질문에 **Enter로 답변**"
        step_no = 1
    elif iv.current_field():
        step_hint = f"**② 답변 입력** ({filled}/{total}) — 아래 입력창에 쓰고 **Enter**"
        step_no = 2
    else:
        step_hint = "**③ PPT 생성** — 인터뷰가 끝났습니다"
        step_no = 3

    st.progress(pct / 100.0, text=f"단계 {step_no}/3 · 수집 {filled}/{total} ({pct}%)")
    st.info(step_hint)

    start_clicked = False
    gen_clicked = False
    seed = ""

    # ── ① 시작 전: 주제만 ──
    if not interview_started:
        st.markdown("#### ① 추진계획서 주제를 입력하세요")
        st.caption("한 줄 제목만 적어도 됩니다. 시작 후 AutoPM이 목적·배경·문제 등을 **순서대로** 물어봅니다.")

        if st.button("📋 샘플 예시 넣기", help="ERP 월마감 검증 자동화 데모"):
            st.session_state.seed_idea = _DEMO_SEED
            st.rerun()

        with st.form("interview_start_form", clear_on_submit=False):
            seed = st.text_area(
                "주제 / 제목",
                height=88,
                placeholder="예: ERP 월마감 데이터 검증 자동화 추진계획서",
                key="seed_idea",
                label_visibility="collapsed",
            )
            start_clicked = st.form_submit_button(
                "② 인터뷰 시작 → 질문 받기",
                type="primary",
                use_container_width=True,
            )

        st.markdown(
            """
            | 순서 | 할 일 |
            | --- | --- |
            | 1 | 위 칸에 **주제** 입력 (또는 샘플 예시) |
            | 2 | **인터뷰 시작** 클릭 |
            | 3 | 나타나는 질문에 **입력창에서 Enter** 로 답변 |
            """
        )
        return start_clicked, gen_clicked, (seed or "").strip()

    # ── ② 인터뷰 진행 중 ──
    field = iv.current_field()
    missing_n = len(iv.get_missing_fields())

    with st.container(border=True):
        st.markdown(f"#### 지금 답할 항목: **{iv.current_question_label()}** (`{filled + 1}`/{total})")
        st.markdown(iv.current_question_body())

        sample_text = demo_sample_for_field(field)
        if sample_text:
            st.markdown(
                f'<p style="color:#555;font-size:0.9rem;margin:0.25rem 0;">'
                f'<b>샘플 답변 예시:</b> {sample_text[:200]}'
                f'{"…" if len(sample_text) > 200 else ""}</p>',
                unsafe_allow_html=True,
            )

        btn_a, btn_b = st.columns(2)
        with btn_a:
            st.button(
                "📋 이 질문 — 샘플 답변 넣기",
                use_container_width=True,
                help="ERP 월마감 데모 시나리오 값을 현재 질문에 바로 적용합니다.",
                on_click=_apply_current_sample,
                args=(get_iv, save_iv),
            )
        with btn_b:
            st.button(
                f"⚡ 남은 {missing_n}개 질문 — 샘플로 한번에 채우기",
                use_container_width=True,
                type="secondary",
                help="아직 안 채운 항목을 데모 샘플로 모두 입력하고 인터뷰를 끝냅니다.",
                on_click=_fill_all_samples,
                args=(get_iv, save_iv),
            )

        choices = FIELD_QUICK_CHOICES.get(field or "", [])
        if choices:
            st.caption("▼ 아래 버튼 중 하나를 눌러도 되고, 입력창에 직접 써도 됩니다.")
            cols = st.columns(min(len(choices), 3))
            for i, label in enumerate(choices):
                with cols[i % len(cols)]:
                    st.button(
                        label,
                        key=f"quick_{field}_{i}",
                        use_container_width=True,
                        on_click=_apply_quick,
                        args=(get_iv, save_iv, label),
                    )

    skippable = field in {
        "timeline",
        "budget_range",
        "related_departments",
        "monthly_hours",
        "people_count",
    }
    if skippable:
        st.button(
            "⏭ 이 질문 건너뛰기 (기본값)",
            on_click=_skip_field,
            args=(get_iv, save_iv),
            use_container_width=False,
        )

    with st.expander("지금까지 대화 보기", expanded=False):
        for msg in iv.chat_history[-12:]:
            role = msg.get("role", "user")
            icon = "🧑" if role == "user" else "🤖"
            st.markdown(f"{icon} {msg.get('content', '')}")

    # Enter 한 번으로 답변 전송 — 별도 '다음 질문' 버튼 불필요
    user_msg = st.chat_input(
        "여기에 답변을 입력하고 Enter ⏎",
        key="interview_chat_input",
    )
    if user_msg and user_msg.strip():
        _apply_answer(get_iv, save_iv, user_msg.strip())
        st.rerun()

    st.caption("💡 **Enter** 로 다음 질문으로 넘어갑니다. 번호(1~5)만 입력해도 선택지로 인식됩니다.")

    # ── ③ 생성 ──
    st.divider()
    if run_mode == "Auto":
        gen_clicked = st.button(
            "🚀 ③ PPT 자동 생성",
            type="primary",
            use_container_width=True,
            disabled=not interview_started,
        )
    else:
        st.caption("**Guided** 모드: 인터뷰 후 같은 탭 하단 **Guided 패널**에서 단계별로 PPT를 만듭니다.")

    return False, gen_clicked, ""
