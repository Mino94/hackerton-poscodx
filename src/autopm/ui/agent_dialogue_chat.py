"""Agent 간 피어 대화 — 채팅 UI로 문서 고도화 과정을 표시."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

from autopm.orchestration.state import agent_dialogue_entries_as_dicts

# speaker → 채팅 말풍선 방향 (검토=assistant, 작성자=user)
_REVIEWER_AVATAR = "🔍"
_PRODUCER_AVATAR = "✏️"
_SYSTEM_AVATAR = "📋"


def _collect_dialogue_entries(
    last_result: Any | None,
    autopm_state_json: dict | None,
) -> list[dict[str, Any]]:
    """실행 결과·세션·산출물 파일에서 대화 스레드를 모은다."""
    if last_result and getattr(last_result, "state", None):
        entries = agent_dialogue_entries_as_dicts(last_result.state)
        if entries:
            return entries
        arts = getattr(last_result.state, "artifacts", None) or {}
        path = arts.get("agent_dialogue.json")
        if path and Path(path).is_file():
            try:
                data = json.loads(Path(path).read_text(encoding="utf-8"))
                dlg = data.get("dialogue") if isinstance(data, dict) else data
                if isinstance(dlg, list):
                    return dlg
            except (OSError, json.JSONDecodeError):
                pass

    if autopm_state_json:
        raw = autopm_state_json.get("agent_dialogue") or []
        out: list[dict[str, Any]] = []
        for item in raw:
            if hasattr(item, "model_dump"):
                out.append(item.model_dump())
            elif isinstance(item, dict):
                out.append(item)
        if out:
            return out
    return []


def _thread_title(thread: dict[str, Any], index: int) -> str:
    fr = thread.get("from_role") or thread.get("from_agent") or "Producer"
    to = thread.get("to_role") or thread.get("to_agent") or "Reviewer"
    tk = thread.get("task_key") or ""
    n = len(thread.get("rounds") or [])
    return f"{index}. {fr} ↔ {to}" + (f" · {n}턴" if n else "") + (f" · `{tk}`" if tk else "")


def _render_turn_bubble(turn: dict[str, Any], thread: dict[str, Any]) -> None:
    """한 턴을 st.chat_message 스타일로 렌더."""
    speaker = str(turn.get("speaker") or "")
    is_reviewer = speaker == "reviewer"
    role = turn.get("role") or (thread.get("to_role") if is_reviewer else thread.get("from_role")) or "Agent"
    rnd = turn.get("round", "?")
    prov = turn.get("provider") or ""
    msg = (turn.get("message") or "").strip()
    if not msg:
        return

    avatar = _REVIEWER_AVATAR if is_reviewer else _PRODUCER_AVATAR
    label = "검토" if is_reviewer else "작성·수정"
    with st.chat_message("assistant" if is_reviewer else "user", avatar=avatar):
        meta = f"**{role}** · R{rnd} · {label}"
        if prov and prov not in ("fallback", "fallback_dialogue"):
            meta += f" · `{prov}`"
        st.caption(meta)
        st.markdown(msg)


def _render_thread_footer(thread: dict[str, Any]) -> None:
    """대화 후 문서 고도화 힌트·반영 여부."""
    hint = (thread.get("revision_hint") or "").strip()
    if hint:
        with st.chat_message("assistant", avatar=_SYSTEM_AVATAR):
            st.caption("**문서 고도화 힌트** (다음 Agent 프롬프트에 반영)")
            st.markdown(hint[:2500])
    if thread.get("revised_after_dialogue"):
        st.success("✓ 대화 내용을 반영해 산출물을 한 번 더 개선했습니다.", icon="✅")


def _render_timeline(entries: list[dict[str, Any]]) -> None:
    """모든 스레드를 순서대로 채팅 타임라인으로 표시."""
    for i, thread in enumerate(entries, 1):
        st.markdown(
            f'<div style="margin:0.6rem 0 0.35rem;padding:0.35rem 0.5rem;'
            f'background:#eef2f7;border-radius:8px;font-size:0.85rem;">'
            f"<b>{_thread_title(thread, i)}</b></div>",
            unsafe_allow_html=True,
        )
        rounds = thread.get("rounds") or []
        if rounds:
            for turn in rounds:
                _render_turn_bubble(turn, thread)
        elif thread.get("message"):
            with st.chat_message("assistant", avatar=_REVIEWER_AVATAR):
                st.markdown(thread.get("message", ""))
        _render_thread_footer(thread)


def _render_single_thread(thread: dict[str, Any]) -> None:
    """선택한 스레드만 채팅으로 표시."""
    rounds = thread.get("rounds") or []
    if rounds:
        for turn in rounds:
            _render_turn_bubble(turn, thread)
    elif thread.get("message"):
        with st.chat_message("assistant"):
            st.markdown(thread.get("message", ""))
    _render_thread_footer(thread)


def render_agent_dialogue_tab(
    last_result: Any | None,
    agent_steps: list[Any] | None,
    autopm_state_json: dict | None = None,
) -> None:
    """
    Agent 대화 탭 — Core Agent 피어 리뷰를 채팅처럼 표시.
    workflow 탭 대체.
    """
    st.markdown("#### Agent 협업 대화")
    st.caption(
        "각 단계 산출 후 **다음 Agent**가 검토·질의하고, 작성 Agent가 수정 방향에 응답합니다. "
        "합의 내용은 이후 프롬프트에 반영되어 **문서·PPT가 고도화**됩니다."
    )

    entries = _collect_dialogue_entries(last_result, autopm_state_json)
    total_turns = sum(len(t.get("rounds") or []) for t in entries)

    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("대화 스레드", len(entries))
    with m2:
        st.metric("총 턴", total_turns)
    with m3:
        revised = sum(1 for t in entries if t.get("revised_after_dialogue"))
        st.metric("산출 개선", revised)

    if not entries:
        st.info(
            "**Auto** 또는 **Guided**로 Core 단계를 실행하면 Agent 간 대화가 여기에 표시됩니다.\n\n"
            "인터뷰 완료 → **수집·진행** 탭에서 승인·생성을 진행하세요."
        )
        with st.expander("대화가 어떻게 이루어지나요?", expanded=False):
            st.markdown(
                "1. **Requirement** 산출 → **Business Analyst**가 검토 (R1)\n"
                "2. **BA**가 수정 방향 응답 (R2)\n"
                "3. 합의·다음 단계 지시 (R3)\n"
                "4. 이 패턴이 Solution → Scope → WBS → … 단계마다 반복됩니다."
            )
        return

    view = st.radio(
        "보기",
        ["전체 타임라인", "스레드 선택"],
        horizontal=True,
        label_visibility="collapsed",
    )

    if view == "스레드 선택":
        labels = [_thread_title(t, i) for i, t in enumerate(entries, 1)]
        pick = st.selectbox("스레드", labels, label_visibility="collapsed")
        idx = labels.index(pick) if pick in labels else 0
        _render_single_thread(entries[idx])
    else:
        _render_timeline(entries)

    with st.expander("원본 JSON", expanded=False):
        st.json(entries)
