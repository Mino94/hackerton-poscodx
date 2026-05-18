"""인터뷰 대화 상태 — 추진계획서(proposal) 맥락을 우선 수집하고 Crew 입력으로 정규화한다."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from autopm.chat.question_rules import ASSUMPTION_SUFFIX, FIELD_LABELS_KR, PRIMARY_FIELD_ORDER


@dataclass
class InterviewState:
    """Proposal 중심 필드 + 레거시(idea_title 등) 호환 — 세션/체크포인트 직렬화에 쓰인다."""

    proposal_title: str | None = None
    proposal_purpose: str | None = None
    background_context: str | None = None
    current_problems: str | None = None
    target_system: str | None = None
    business_scope: str | None = None
    improvement_direction: str | None = None
    target_audience: str | None = None
    key_emphasis: str | None = None
    presentation_tone: str | None = None
    related_departments: str | None = None
    timeline: str | None = None
    budget_range: str | None = None
    expected_effects: str | None = None
    constraints: str | None = None
    reference_materials: str | None = None
    monthly_hours: int | None = None
    people_count: int | None = None

    inferred_target_company: str | None = None
    inferred_strategy_context: str | None = None
    inferred_output_type: str | None = None
    inferred_likely_purpose: str | None = None
    inferred_proposal_type: str | None = None
    inferred_likely_tone: str | None = None

    idea_title: str | None = None
    current_process: str | None = None
    pain_points: str | None = None
    goal: str | None = None

    chat_history: list[dict[str, str]] = field(default_factory=list)
    completed: bool = False

    def _sync_title_aliases(self) -> None:
        """제목은 proposal_title ↔ idea_title 동기화 — 레거시 Crew 키와 맞춘다."""
        pt = (self.proposal_title or "").strip() or None
        it = (self.idea_title or "").strip() or None
        if pt and not it:
            self.idea_title = pt
        elif it and not pt:
            self.proposal_title = it

    def to_dict(self) -> dict[str, Any]:
        self._sync_title_aliases()
        return {
            "proposal_title": self.proposal_title,
            "proposal_purpose": self.proposal_purpose,
            "background_context": self.background_context,
            "current_problems": self.current_problems,
            "target_system": self.target_system,
            "business_scope": self.business_scope,
            "improvement_direction": self.improvement_direction,
            "target_audience": self.target_audience,
            "key_emphasis": self.key_emphasis,
            "presentation_tone": self.presentation_tone,
            "related_departments": self.related_departments,
            "timeline": self.timeline,
            "budget_range": self.budget_range,
            "expected_effects": self.expected_effects,
            "constraints": self.constraints,
            "reference_materials": self.reference_materials,
            "monthly_hours": self.monthly_hours,
            "people_count": self.people_count,
            "inferred_target_company": self.inferred_target_company,
            "inferred_strategy_context": self.inferred_strategy_context,
            "inferred_output_type": self.inferred_output_type,
            "inferred_likely_purpose": self.inferred_likely_purpose,
            "inferred_proposal_type": self.inferred_proposal_type,
            "inferred_likely_tone": self.inferred_likely_tone,
            "idea_title": self.idea_title,
            "current_process": self.current_process,
            "pain_points": self.pain_points,
            "goal": self.goal,
            "chat_history": list(self.chat_history),
            "completed": self.completed,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> InterviewState:
        """이전 세션(아이디어 9필드)도 새 proposal 필드로 승격해 로드한다."""
        if not d:
            return cls()
        data = dict(d)
        if data.get("idea_title") and not data.get("proposal_title"):
            data["proposal_title"] = data["idea_title"]
        if data.get("pain_points") and not data.get("current_problems"):
            data["current_problems"] = data["pain_points"]
        if data.get("goal") and not data.get("improvement_direction"):
            data["improvement_direction"] = data["goal"]
        if data.get("current_process") and not data.get("background_context"):
            data["background_context"] = data["current_process"]
        return cls(
            proposal_title=data.get("proposal_title"),
            proposal_purpose=data.get("proposal_purpose"),
            background_context=data.get("background_context"),
            current_problems=data.get("current_problems"),
            target_system=data.get("target_system"),
            business_scope=data.get("business_scope"),
            improvement_direction=data.get("improvement_direction"),
            target_audience=data.get("target_audience"),
            key_emphasis=data.get("key_emphasis"),
            presentation_tone=data.get("presentation_tone"),
            related_departments=data.get("related_departments"),
            timeline=data.get("timeline"),
            budget_range=data.get("budget_range"),
            expected_effects=data.get("expected_effects"),
            constraints=data.get("constraints"),
            reference_materials=data.get("reference_materials"),
            monthly_hours=data.get("monthly_hours"),
            people_count=data.get("people_count"),
            inferred_target_company=data.get("inferred_target_company"),
            inferred_strategy_context=data.get("inferred_strategy_context"),
            inferred_output_type=data.get("inferred_output_type"),
            inferred_likely_purpose=data.get("inferred_likely_purpose"),
            inferred_proposal_type=data.get("inferred_proposal_type"),
            inferred_likely_tone=data.get("inferred_likely_tone"),
            idea_title=data.get("idea_title"),
            current_process=data.get("current_process"),
            pain_points=data.get("pain_points"),
            goal=data.get("goal"),
            chat_history=list(data.get("chat_history") or []),
            completed=bool(data.get("completed")),
        )

    def _is_str_filled(self, val: Any) -> bool:
        return bool((val or "").strip()) if val is not None else False

    def _needs_resource_questions(self) -> bool:
        """시간·인건비 산정이 의미 있을 때만 월시간/인원을追加 질문한다."""
        blob = f"{self.key_emphasis or ''} {self.improvement_direction or ''}".lower()
        keys = ("업무 효율", "시간 절감", "인건비", "절감", "효율화", "자동화")
        return any(k in blob for k in keys)

    def get_missing_fields(self) -> list[str]:
        """질문 순서대로 아직 비어 있는 필드 — proposal_title → PRIMARY → (조건부) 리소스."""
        self._sync_title_aliases()
        if not self._is_str_filled(self.proposal_title) and not self._is_str_filled(self.idea_title):
            return ["proposal_title"]
        missing: list[str] = []
        for key in PRIMARY_FIELD_ORDER:
            if not self._is_str_filled(getattr(self, key, None)):
                missing.append(key)
        if not missing and self._needs_resource_questions():
            if self.monthly_hours is None:
                missing.append("monthly_hours")
            if self.people_count is None:
                missing.append("people_count")
        return missing

    def update_from_answer(self, field: str, answer: str) -> None:
        """특정 필드에 답변 반영 — 숫자 필드는 정수 파싱 시도."""
        answer = (answer or "").strip()
        if field in ("monthly_hours", "people_count"):
            m = re.search(r"(\d+)", answer.replace(",", ""))
            if m:
                setattr(self, field, int(m.group(1)))
            return
        setattr(self, field, answer or None)
        if field == "proposal_title":
            self.idea_title = (answer or None) or self.idea_title

    def is_ready_for_generation(self) -> bool:
        return True

    def is_interview_filled_for_ui(self) -> bool:
        return len(self.get_missing_fields()) == 0

    def filled_count(self) -> int:
        """제목·필수 질문 필드(+조건부 월시간/인원)까지 채워진 개수 — 진행률 바에 사용한다."""
        self._sync_title_aliases()
        n = 0
        if self._is_str_filled(self.proposal_title) or self._is_str_filled(self.idea_title):
            n += 1
        for k in PRIMARY_FIELD_ORDER:
            if self._is_str_filled(getattr(self, k, None)):
                n += 1
        if self._needs_resource_questions():
            if self.monthly_hours is not None:
                n += 1
            if self.people_count is not None:
                n += 1
        return n

    def total_fields(self) -> int:
        t = 1 + len(PRIMARY_FIELD_ORDER)
        if self._needs_resource_questions():
            t += 2
        return t

    def _legacy_current_process_synthetic(self) -> str:
        """구 Crew placeholder `current_process`용 — 배경·시스템·범위를 한 덩어리로 보낸다."""
        parts = [
            self.background_context or "",
            self.target_system or "",
            self.business_scope or "",
        ]
        if self.inferred_target_company:
            parts.insert(0, f"[조직/회사] {self.inferred_target_company}")
        return " / ".join(p for p in parts if (p or "").strip()).strip()

    def _legacy_goals_synthetic(self) -> str:
        """구 `goals` 키 — 개선 방향 + 강조 포인트 + 목적."""
        chunks = [
            self.improvement_direction or "",
            self.key_emphasis or "",
            self.proposal_purpose or "",
        ]
        return " | ".join(c for c in chunks if (c or "").strip()).strip()

    def to_autopm_inputs(self) -> dict[str, str]:
        """
        CrewAI tasks.yaml·Fallback이 기대하는 키를 모두 채운다.
        proposal_*는 스펙 그대로 두고, idea_title 등 레거시 alias는 자동 합성한다.
        """
        self._sync_title_aliases()
        title = (self.proposal_title or self.idea_title or "").strip() or f"추진계획서 과제{ASSUMPTION_SUFFIX}"

        def _s(key: str, default: str) -> str:
            v = getattr(self, key, None)
            return (str(v).strip() if v is not None else "") or default

        primary: dict[str, str] = {
            "proposal_title": title[:500],
            "proposal_purpose": _s("proposal_purpose", f"(미입력) 목적은 인터뷰에서 보완{ASSUMPTION_SUFFIX}")[:4000],
            "background_context": _s("background_context", f"(미입력) 배경 미정{ASSUMPTION_SUFFIX}")[:4000],
            "current_problems": _s("current_problems", f"(미입력) 문제점 미정{ASSUMPTION_SUFFIX}")[:4000],
            "target_system": _s("target_system", f"(미입력) 대상 시스템{ASSUMPTION_SUFFIX}")[:2000],
            "business_scope": _s("business_scope", f"(미입력) 업무 범위{ASSUMPTION_SUFFIX}")[:4000],
            "improvement_direction": _s(
                "improvement_direction",
                f"(미입력) 개선 방향{ASSUMPTION_SUFFIX}",
            )[:4000],
            "target_audience": _s("target_audience", f"(미입력) 보고 대상{ASSUMPTION_SUFFIX}")[:2000],
            "key_emphasis": _s("key_emphasis", f"(미입력) 강조 포인트{ASSUMPTION_SUFFIX}")[:2000],
            "presentation_tone": _s("presentation_tone", f"실무 추진계획형{ASSUMPTION_SUFFIX}")[:500],
            "related_departments": _s("related_departments", f"(미입력) 관련 부서{ASSUMPTION_SUFFIX}")[:500],
            "timeline": _s("timeline", f"4주{ASSUMPTION_SUFFIX}")[:200],
            "budget_range": _s("budget_range", f"내부 협의 범위 내{ASSUMPTION_SUFFIX}")[:500],
            "expected_effects": _s("expected_effects", "")[:4000],
            "constraints": _s("constraints", "")[:4000],
            "reference_materials": _s("reference_materials", "")[:4000],
        }

        mh = self.monthly_hours
        pc = self.people_count
        mh_str = str(mh) if mh is not None else f"40{ASSUMPTION_SUFFIX}"
        hc_str = str(pc) if pc is not None else f"2{ASSUMPTION_SUFFIX}"

        cp_syn = self._legacy_current_process_synthetic() or f"(미입력) 현황{ASSUMPTION_SUFFIX}"
        goals_syn = self._legacy_goals_synthetic() or f"추진 목표·효과 검증{ASSUMPTION_SUFFIX}"
        pain = (self.current_problems or self.pain_points or "").strip() or primary["current_problems"]
        dept = primary["related_departments"]

        legacy: dict[str, str] = {
            "idea_title": title[:500],
            "current_process": cp_syn[:4000],
            "pain_points": pain[:4000],
            "departments": dept[:500],
            "monthly_hours": mh_str[:50],
            "headcount": hc_str[:50],
            "goals": goals_syn[:4000],
            "target_timeline": primary["timeline"][:200],
            "budget_range": primary["budget_range"][:500],
        }
        meta = []
        if self.inferred_target_company:
            meta.append(f"조직:{self.inferred_target_company}")
        if self.inferred_strategy_context:
            meta.append(f"전략맥락:{self.inferred_strategy_context}")
        if self.inferred_output_type:
            meta.append(f"산출물:{self.inferred_output_type}")
        if self.inferred_likely_purpose:
            meta.append(f"목적힌트:{self.inferred_likely_purpose}")
        if self.inferred_proposal_type:
            meta.append(f"문서유형:{self.inferred_proposal_type}")
        if self.inferred_likely_tone:
            meta.append(f"톤힌트:{self.inferred_likely_tone}")
        primary["proposal_meta_hints"] = " · ".join(meta)[:500]

        return {**primary, **legacy}

    def has_assumptions(self) -> bool:
        return len(self.get_missing_fields()) > 0

    def summary_rows(self) -> list[tuple[str, str, bool]]:
        rows: list[tuple[str, str, bool]] = []
        order: list[tuple[str, Any]] = [
            ("proposal_title", self.proposal_title),
            ("proposal_purpose", self.proposal_purpose),
            ("background_context", self.background_context),
            ("current_problems", self.current_problems),
            ("target_system", self.target_system),
            ("business_scope", self.business_scope),
            ("improvement_direction", self.improvement_direction),
            ("target_audience", self.target_audience),
            ("key_emphasis", self.key_emphasis),
            ("presentation_tone", self.presentation_tone),
            ("timeline", self.timeline),
            ("budget_range", self.budget_range),
            ("related_departments", self.related_departments),
            ("monthly_hours", self.monthly_hours),
            ("people_count", self.people_count),
            ("inferred_target_company", self.inferred_target_company),
            ("inferred_likely_purpose", self.inferred_likely_purpose),
            ("inferred_proposal_type", self.inferred_proposal_type),
            ("inferred_likely_tone", self.inferred_likely_tone),
            ("expected_effects", self.expected_effects),
        ]
        for key, val in order:
            label = FIELD_LABELS_KR.get(key, key)
            if key in ("monthly_hours", "people_count"):
                ok = val is not None
                disp = str(val) if ok else "— (효율·절감 강조 시 질문)"
            else:
                ok = bool((val or "").strip())
                disp = (val or "—") if ok else "—"
            rows.append((label, disp, ok))
        return rows
