"""Rule-based 인터뷰 봇 — 추진계획서 방향 필드를 순서대로 채운다."""

from __future__ import annotations

import re

from autopm.chat.interview_state import InterviewState
from autopm.chat.proposal_extract import extract_title_metadata
from autopm.chat.question_rules import FIELD_QUESTIONS


def extract_from_initial_text(text: str) -> dict[str, object]:
    """
    첫 입력(제목/주제)에서 메타데이터·일부 필드 후보를 채운다 — 레거시 함수명 유지.
    """
    t = (text or "").strip()
    out: dict[str, object] = {}
    if not t:
        return out

    out["proposal_title"] = t[:500]
    out["idea_title"] = t[:500]

    meta = extract_title_metadata(t)
    if meta.get("target_company"):
        out["inferred_target_company"] = meta["target_company"]
    if meta.get("strategy_context"):
        out["inferred_strategy_context"] = meta["strategy_context"]
    if meta.get("output_type"):
        out["inferred_output_type"] = meta["output_type"]
    if meta.get("likely_purpose"):
        out["inferred_likely_purpose"] = meta["likely_purpose"]
    if meta.get("proposal_type"):
        out["inferred_proposal_type"] = meta["proposal_type"]
    if meta.get("likely_tone"):
        out["inferred_likely_tone"] = str(meta["likely_tone"])

    # 대상 시스템만 1차 채움 — 배경·범위·개선방향·톤은 대화 질문으로 남긴다(Crew는 proposal_meta_hints로 참고).
    for k in ("target_system",):
        if meta.get(k):
            out[k] = meta[k]

    if meta.get("proposal_type"):
        out.setdefault("proposal_type_label", meta["proposal_type"])

    if "월마감" in t or "월 마감" in t:
        out.setdefault("business_scope", (out.get("business_scope") or "") + " 월마감 검증")

    if "자동화" in t:
        out.setdefault("improvement_direction", str(out.get("improvement_direction") or "업무 자동화 및 검증 효율화"))

    m = re.search(r"(\d+)\s*주", t)
    if m:
        out.setdefault("timeline", f"{m.group(1)}주")

    m = re.search(r"(\d+)\s*개월", t)
    if m:
        out.setdefault("timeline", f"{m.group(1)}개월")

    if "500만" in t or "5백만" in t:
        out.setdefault("budget_range", "500만 원 이하(가정)")
    m = re.search(r"(\d{2,4})\s*만", t)
    if m and "budget_range" not in out:
        out["budget_range"] = f"{m.group(1)}만 원 범위(가정)"

    return out


def apply_heuristic_updates(state: InterviewState, hints: dict[str, object]) -> None:
    """기존 값이 없을 때만 힌트를 채운다 — 사용자 답변이 항상 우선."""
    skip = {"chat_history", "completed", "proposal_type_label"}
    for k, v in hints.items():
        if k in skip:
            continue
        if k not in InterviewState.__dataclass_fields__:
            continue
        cur = getattr(state, k)
        if k in ("monthly_hours", "people_count"):
            if cur is None and isinstance(v, int):
                setattr(state, k, v)
        elif cur is None or (isinstance(cur, str) and not cur.strip()):
            if v is not None:
                setattr(state, k, str(v) if not isinstance(v, str) else v)
    state._sync_title_aliases()


class InterviewBot:
    """대화 상태를 들고 다음 질문 메시지를 만든다."""

    def __init__(self, state: InterviewState | None = None) -> None:
        self.state = state or InterviewState()

    def start_with_initial_message(self, text: str) -> str:
        """첫 입력 반영 + 봇 첫 질문(또는 완료 안내) 문자열 반환."""
        text = (text or "").strip()
        self.state.chat_history.append({"role": "user", "content": text})
        if text:
            hints = extract_from_initial_text(text)
            apply_heuristic_updates(self.state, hints)
            if not (self.state.proposal_title or "").strip():
                self.state.proposal_title = text[:500]
                self.state.idea_title = text[:500]
        self.state._sync_title_aliases()
        reply = self._next_question_text()
        self.state.chat_history.append({"role": "assistant", "content": reply})
        return reply

    def _next_question_text(self) -> str:
        missing = self.state.get_missing_fields()
        if not missing:
            return (
                "필수 항목이 모두 채워졌습니다. **PPT 생성하기**를 눌러 AutoPM을 실행해 주세요. "
                "부족한 정보가 있어도 생성은 가능하며, 가정값이 들어갈 수 있습니다."
            )
        f = missing[0]
        return FIELD_QUESTIONS.get(f, f"{f}에 대해 알려 주세요.")

    def apply_chat_answer(self, answer: str) -> str:
        """사용자 자유 답변을 '첫 번째 비어 있던 필드'에 매핑하고 다음 질문을 반환."""
        answer = (answer or "").strip()
        missing_before = self.state.get_missing_fields()
        if not missing_before:
            self.state.chat_history.append({"role": "user", "content": answer})
            reply = "이미 모든 항목이 채워져 있습니다. **PPT 생성하기**를 눌러 주세요."
            self.state.chat_history.append({"role": "assistant", "content": reply})
            return reply

        field = missing_before[0]
        self.state.update_from_answer(field, answer)
        self.state.chat_history.append({"role": "user", "content": answer})
        reply = self._next_question_text()
        self.state.chat_history.append({"role": "assistant", "content": reply})
        return reply

    def mark_completed(self) -> None:
        self.state.completed = True
