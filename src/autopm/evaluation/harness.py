"""Evaluation Harness 실행기 — 단계별 루브릭 점수·pass/fail·피드백 타깃을 산출한다."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from autopm.evaluation.rubrics import (
    CORE_AGENT_RUBRICS,
    FINAL_PPT_PASS_SCORE,
    FINAL_SLIDE_TOPIC_KEYWORDS,
    PPT_CHAIN_RUBRICS,
)
from autopm.evaluation.scoring import AgentScoreResult, CriterionScore, merge_agent_results, score_from_criteria
from autopm.evaluation.validators import (
    extract_json_object,
    validate_graphics_json,
    validate_interview_inputs,
    validate_pptx_file,
    validate_slide_deck_json,
    validate_visual_plan_json,
)
from autopm.orchestration.state import AutoPMState
from autopm.ppt.slide_schema import SlideDeckSpec


# Harness 실패 시 _run_improvement 타깃 키 — flow._IMPROVEMENT_MAP 과 동일 스페이스를 쓴다.
HARNESS_CORE_TO_FEEDBACK_TARGET: dict[str, str] = {
    "requirement": "requirement",
    "business": "business",
    "solution": "solution",
    "scope": "scope",
    "wbs": "wbs",
    "budget": "budget",
    "risk": "risk",
}


@dataclass
class StageHarnessSnapshot:
    """한 시점(인터뷰·초안·슬라이드 등)의 평가 스냅샷 — 리포트 JSON에 넣는다."""

    stage: str
    passed: bool
    score: float | None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class CombinedHarnessReport:
    """전체 Harness 결과 — Streamlit·파일 출력·개선 루프 제어에 쓴다."""

    overall_score: float
    pass_threshold: float
    final_passed: bool
    agent_scores: dict[str, float]
    failed_criteria: list[str]
    feedback_target: str
    improvement_attempts: int
    max_improvement_attempts: int
    stages: list[StageHarnessSnapshot] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_serializable(self) -> dict[str, Any]:
        """JSON 직렬화용 dict — pathlib 등 비직렬화 객체가 없도록 한다."""
        return {
            "overall_score": self.overall_score,
            "pass_threshold": self.pass_threshold,
            "final_passed": self.final_passed,
            "agent_scores": dict(self.agent_scores),
            "failed_criteria": list(self.failed_criteria),
            "feedback_target": self.feedback_target,
            "improvement_attempts": self.improvement_attempts,
            "max_improvement_attempts": self.max_improvement_attempts,
            "stages": [asdict(s) for s in self.stages],
            "warnings": list(self.warnings),
            "recommendations": list(self.recommendations),
        }


def _text_len_ok(t: str, n: int = 120) -> bool:
    s = t if isinstance(t, str) else str(t or "")
    return len(s.strip()) >= n


def _count_bullets(text: str) -> int:
    """Markdown/아키텍처 목록 줄을 대략 센다 — pain 개수 추정용."""
    if not text:
        return 0
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    n = 0
    for ln in lines:
        if re.match(r"^[-*•]\s+", ln) or re.match(r"^\d+\.\s+", ln):
            n += 1
    return n


def _contains_any(hay: str, needles: tuple[str, ...]) -> bool:
    """부분 문자열 매칭 — needles 중 하나라도 본문에 포함되면 True."""
    low = (hay or "").lower()
    return any(str(n).lower() in low for n in needles)


def _has_table_row(text: str) -> bool:
    return "|" in (text or "") and "---" in (text or "")


def _estimate_risk_rows(text: str) -> int:
    """리스크 표 데이터 행 수를 휴리스틱으로 센다."""
    rows = [ln for ln in (text or "").splitlines() if ln.strip().startswith("|")]
    data = [r for r in rows if not re.match(r"^\|\s*[-:]+", r)]
    return max(0, len(data) - 1)


def _kpi_mentions(text: str) -> int:
    t = text or ""
    return len(re.findall(r"\bKPI\b|지표|측정|목표값", t, re.I))


def _hyperbole_hits(text: str) -> int:
    """과장 표현 — 감점 신호(반대로 '가정'이 있으면 완화)."""
    t = text or ""
    bad = len(re.findall(r"무조건|100%|완벽|혁신적|폭발적|즉시\s*적용", t, re.I))
    good = len(re.findall(r"가정|예상|추정|범위", t, re.I))
    return max(0, bad - min(good, 3))


def _core_field_text(state: AutoPMState, agent_id: str) -> str:
    m = {
        "requirement": state.requirement_analysis,
        "business": state.business_analysis,
        "solution": state.solution_direction,
        "scope": state.development_scope,
        "wbs": state.wbs_plan,
        "budget": state.budget_roi,
        "risk": state.risk_management,
    }
    raw = m.get(agent_id, "") or ""
    return raw if isinstance(raw, str) else str(raw)


def _score_requirement(text: str) -> list[CriterionScore]:
    w = 1.0
    return [
        CriterionScore("req_has_summary", _text_len_ok(text, 150), w, "요약 길이"),
        CriterionScore(
            "req_identifies_gaps",
            _contains_any(text, ("누락", "부족", "미확인", "gap", "가정")),
            w,
            "누락/가정",
        ),
        CriterionScore("req_followup_questions", _contains_any(text, ("질문", "문의", "확인 필요")), w, "추가 질문"),
        CriterionScore("req_context_sane", _text_len_ok(text, 80) and "오류" not in text[:50], w, "맥락"),
    ]


def _score_business(text: str) -> list[CriterionScore]:
    w = 1.0
    pains = _count_bullets(text) + len(re.findall(r"문제점|pain|pain point", text, re.I))
    return [
        CriterionScore(
            "ba_as_is_concrete",
            _contains_any(text, ("as-is", "asis", "현황", "현재")),
            w,
            "AS-IS",
        ),
        CriterionScore("ba_three_pains", pains >= 3 or _count_bullets(text) >= 3, w, "Pain 수"),
        CriterionScore(
            "ba_pain_dimensions",
            _contains_any(text, ("시간", "리스크", "비용", "품질", "업무")),
            w,
            "Pain 차원",
        ),
        CriterionScore(
            "ba_stakeholders",
            _contains_any(text, ("이해관계자", "부서", "현업", "stakeholder")),
            w,
            "이해관계자",
        ),
    ]


def _score_solution(text: str, as_is_hint: str) -> list[CriterionScore]:
    w = 1.0
    return [
        CriterionScore(
            "sa_tobe_addresses",
            _contains_any(text, ("to-be", "tobe", "개선", "목표 설계"))
            and len((as_is_hint if isinstance(as_is_hint, str) else str(as_is_hint or "")).strip()) > 20,
            w,
            "TO-BE 연결",
        ),
        CriterionScore(
            "sa_actionable",
            _contains_any(text, ("단계", "절차", "주차", "일정", "실행")),
            w,
            "실행가능",
        ),
        CriterionScore("sa_automation_scope", _contains_any(text, ("자동화", "RPA", "스크립트", "검증")), w, "자동화"),
        CriterionScore(
            "sa_system_direction",
            _contains_any(text, ("시스템", "ERP", "데이터", "연동", "도구")),
            w,
            "시스템",
        ),
    ]


def _score_scope(text: str) -> list[CriterionScore]:
    w = 1.0
    return [
        CriterionScore("ds_in_scope_clear", _contains_any(text, ("포함", "in scope", "범위")), w, "포함"),
        CriterionScore("ds_out_scope", _contains_any(text, ("제외", "out of", "비포함")), w, "제외"),
        CriterionScore("ds_mvp_realistic", _contains_any(text, ("mvp", "파일럿", "4주", "8주", "단계")), w, "MVP"),
        CriterionScore("ds_key_features", _count_bullets(text) >= 2 or _text_len_ok(text, 200), w, "기능"),
    ]


def _score_wbs(text: str) -> list[CriterionScore]:
    w = 1.0
    return [
        CriterionScore("wbs_phases", _contains_any(text, ("주", "일", "단계", "milestone", "마일")), w, "일정"),
        CriterionScore("wbs_owners", _contains_any(text, ("담당", "owner", "조직", "팀")), w, "담당"),
        CriterionScore("wbs_deliverables", _contains_any(text, ("산출물", "deliverable", "결과물")), w, "산출물"),
        CriterionScore("wbs_time_realistic", _has_table_row(text) or _contains_any(text, ("4주", "8주", "2주")), w, "현실성"),
    ]


def _score_budget(text: str) -> list[CriterionScore]:
    w = 1.0
    return [
        CriterionScore("br_items", _contains_any(text, ("예산", "항목", "비용", "원")), w, "항목"),
        CriterionScore("br_assumption_tag", _contains_any(text, ("가정", "예상", "추정")), w, "가정 표기"),
        CriterionScore("br_roi_or_saving", _contains_any(text, ("roi", "절감", "효과")), w, "ROI/절감"),
        CriterionScore("br_three_kpis", _kpi_mentions(text) >= 3, w, "KPI 3+"),
        CriterionScore("br_not_hyperbole", _hyperbole_hits(text) <= 1, w, "과장 억제"),
    ]


def _score_risk(text: str) -> list[CriterionScore]:
    w = 1.0
    n = _estimate_risk_rows(text)
    return [
        CriterionScore("rk_four_risks", n >= 4 or _count_bullets(text) >= 4, w, "리스크 수"),
        CriterionScore("rk_likelihood_impact", _contains_any(text, ("가능성", "영향", "high", "중", "저")), w, "매트릭스"),
        CriterionScore("rk_mitigation", _contains_any(text, ("대응", "완화", "mitigation", "조치")), w, "대응"),
        CriterionScore(
            "rk_critic_hints",
            _contains_any(text, ("critic", "품질", "점수", "보완")),
            w,
            "Critic 힌트",
        ),
    ]


def _storyline_from_raw(raw: str) -> dict[str, Any] | None:
    return extract_json_object(raw or "")


def _score_storyline(raw: str) -> list[CriterionScore]:
    obj = _storyline_from_raw(raw)
    ok, errs = validate_slide_deck_json(obj)
    titles: list[str] = []
    if obj and isinstance(obj.get("slides"), list):
        for s in obj["slides"]:
            if isinstance(s, dict):
                titles.append(str(s.get("title", "")).strip().lower())
    dup = len(titles) != len(set(titles))
    w = 1.0
    n_slides = len(obj.get("slides", [])) if obj else 0
    return [
        CriterionScore("st_min_slides", n_slides >= 10, w, "10장+"),
        CriterionScore("st_slide_fields", ok and not errs, w, "필드"),
        CriterionScore(
            "st_flow_ok",
            n_slides >= 10 and _contains_any(str(raw), ("요약", "문제", "wbs", "리스크")),
            w,
            "흐름",
        ),
        CriterionScore("st_no_dup_titles", not dup, w, "중복 제목"),
    ]


def _score_visualization(raw_vis: str, raw_story: str) -> list[CriterionScore]:
    story = _storyline_from_raw(raw_story)
    n = len(story.get("slides", [])) if story else 0
    vobj = extract_json_object(raw_vis or "")
    ok, _ = validate_visual_plan_json(vobj, n)
    per = vobj.get("per_slide") if isinstance(vobj, dict) else None
    types: list[str] = []
    if isinstance(per, list):
        for row in per:
            if isinstance(row, dict):
                types.append(str(row.get("visual_type", "")).lower())
    sane = sum(1 for t in types if t in ("table", "chart", "process", "matrix", "diagram", "text_card", "image"))
    w = 1.0
    return [
        CriterionScore("viz_has_types", ok and len(types) >= min(n, 10), w, "visual_type"),
        CriterionScore("viz_type_sane", sane >= max(1, len(types) // 2), w, "타입 적합"),
        CriterionScore(
            "viz_layout_mix",
            len(set(types)) >= 2,
            w,
            "다양성",
        ),
    ]


def _score_graphics(raw: str) -> list[CriterionScore]:
    gob = extract_json_object(raw or "")
    ok, errs = validate_graphics_json(gob)
    spec = gob.get("graphics_spec") if isinstance(gob, dict) else None
    n = len(spec) if isinstance(spec, list) else 0
    w = 1.0
    return [
        CriterionScore("pg_graphics_spec", ok, w, "spec"),
        CriterionScore(
            "pg_shapes_or_assets",
            n > 0 and _contains_any(raw or "", ("shape", "표", "matrix", "path", "asset")),
            w,
            "도형/에셋",
        ),
        CriterionScore("pg_fallback_friendly", "fallback" in (raw or "").lower() or n > 0, w, "fallback"),
    ]


def _score_composer_raw(raw: str, ppt_path: Path | None) -> list[CriterionScore]:
    deck_obj = extract_json_object(raw or "")
    # composer 출력이 슬라이드 리스트를 포함할 수 있음
    slides = []
    if isinstance(deck_obj, dict):
        slides = deck_obj.get("slides") or deck_obj.get("slide_specs") or []
    ok_file, slide_n, errs = validate_pptx_file(ppt_path)
    w = 1.0
    text_only_ratio = 1.0
    if isinstance(slides, list) and slides:
        vt = [str((s or {}).get("visual_type", "")).lower() for s in slides if isinstance(s, dict)]
        text_only_ratio = sum(1 for x in vt if x in ("", "text", "title")) / max(len(vt), 1)
    chartish = _contains_any(str(raw), ("table", "matrix", "chart", "process", "diagram"))
    return [
        CriterionScore("pc_pptx_exists", ok_file or slide_n > 0, w, "pptx"),
        CriterionScore("pc_min_slides", slide_n >= 10 or (isinstance(slides, list) and len(slides) >= 10), w, "10장"),
        CriterionScore("pc_key_slides", chartish or slide_n >= 10, w, "키 장표"),
        CriterionScore("pc_not_text_only", text_only_ratio < 0.85, w, "텍스트 과다"),
        CriterionScore("pc_charts_tables", chartish or _has_table_row(str(raw)), w, "표/도식"),
    ]


def _final_slide_keyword_coverage(deck: SlideDeckSpec) -> tuple[int, int, list[str]]:
    """필수 토픽별 키워드 매칭 개수."""
    covered = []
    blob = " ".join(f"{s.title} {s.key_message} {(s.objective or '')}".lower() for s in deck.slides)
    missing: list[str] = []
    for keywords in FINAL_SLIDE_TOPIC_KEYWORDS:
        if any(k.lower() in blob for k in keywords):
            covered.append(keywords[0])
        else:
            missing.append(keywords[0])
    need = len(FINAL_SLIDE_TOPIC_KEYWORDS)
    return len(covered), need, missing


def _score_final_ppt(deck: SlideDeckSpec, ppt_path: Path | None, full_md: str) -> list[CriterionScore]:
    w = 1.0
    ok_file, slide_n, _ = validate_pptx_file(ppt_path)
    if slide_n < 0:
        slide_n = len(deck.slides)
    cov, need, miss = _final_slide_keyword_coverage(deck)
    vis_ok = all(
        (s.visual_type and str(s.visual_type).strip() != "") or (s.key_message and len(s.key_message) > 5)
        for s in deck.slides[: min(len(deck.slides), 20)]
    )
    msg_align = True  # 휴리스틱: 제목 비어 있지 않으면 통과
    for s in deck.slides:
        if not str(s.title or "").strip():
            msg_align = False
    assump_md = "가정" in (full_md or "") or "예상" in (full_md or "")
    flow_ok = cov >= max(6, need - 4)
    return [
        CriterionScore("fp_file", ok_file, w, "파일"),
        CriterionScore("fp_min_slides", slide_n >= 10 or len(deck.slides) >= 10, w, "10장+"),
        CriterionScore("fp_topics", cov >= 8, w, "필수 토픽"),
        CriterionScore("fp_key_message", vis_ok, w, "메시지/시각"),
        CriterionScore("fp_visual_each", len(deck.slides) > 0 and sum(1 for s in deck.slides if s.visual_type) >= min(10, len(deck.slides)) - 1, w, "시각 요소"),
        CriterionScore("fp_assumption_markers", assump_md, w, "가정 표기"),
        CriterionScore("fp_title_body", msg_align, w, "제목 정합"),
        CriterionScore("fp_flow", flow_ok, w, "흐름"),
    ]


class EvaluationHarness:
    """Flow·Streamlit이 호출하는 평가 진입점 — API 없이도 휴리스틱 점수를 낸다."""

    def evaluate_interview(self, inputs: dict[str, str]) -> StageHarnessSnapshot:
        ok, missing = validate_interview_inputs(inputs)
        score = 100.0 if ok else max(0.0, 100.0 - len(missing) * 25.0)
        return StageHarnessSnapshot(
            "after_interview",
            ok,
            score,
            {"missing_keys": missing},
        )

    def evaluate_draft(self, draft_md: str) -> StageHarnessSnapshot:
        t = draft_md or ""
        ok = _text_len_ok(t, 200) and _contains_any(t, ("#", "##", "요약", "문제"))
        score = 88.0 if ok else 55.0
        return StageHarnessSnapshot("after_draft", ok, score, {"chars": len(t)})

    def evaluate_core_agent(self, agent_id: str, text: str, *, as_is_hint: str = "") -> AgentScoreResult:
        rub = CORE_AGENT_RUBRICS[agent_id]
        if agent_id == "requirement":
            crit = _score_requirement(text)
        elif agent_id == "business":
            crit = _score_business(text)
        elif agent_id == "solution":
            crit = _score_solution(text, as_is_hint)
        elif agent_id == "scope":
            crit = _score_scope(text)
        elif agent_id == "wbs":
            crit = _score_wbs(text)
        elif agent_id == "budget":
            crit = _score_budget(text)
        elif agent_id == "risk":
            crit = _score_risk(text)
        else:
            crit = []
        base = score_from_criteria(crit, rub.pass_threshold)
        return merge_agent_results(agent_id, rub.display_name, rub.pass_threshold, base)

    def evaluate_all_core(self, state: AutoPMState) -> list[AgentScoreResult]:
        as_is = state.business_analysis or ""
        out: list[AgentScoreResult] = []
        for aid in CORE_AGENT_RUBRICS:
            txt = _core_field_text(state, aid)
            extra = as_is if aid == "solution" else ""
            out.append(self.evaluate_core_agent(aid, txt, as_is_hint=extra))
        return out

    def evaluate_storyline(self, raw: str) -> AgentScoreResult:
        rub = PPT_CHAIN_RUBRICS["storyline"]
        crit = _score_storyline(raw)
        base = score_from_criteria(crit, rub.pass_threshold)
        return merge_agent_results("storyline", rub.display_name, rub.pass_threshold, base)

    def evaluate_visualization(self, raw_vis: str, raw_story: str) -> AgentScoreResult:
        rub = PPT_CHAIN_RUBRICS["visualization"]
        crit = _score_visualization(raw_vis, raw_story)
        base = score_from_criteria(crit, rub.pass_threshold)
        return merge_agent_results("visualization", rub.display_name, rub.pass_threshold, base)

    def evaluate_graphics(self, raw: str) -> AgentScoreResult:
        rub = PPT_CHAIN_RUBRICS["presentation_graphics"]
        crit = _score_graphics(raw)
        base = score_from_criteria(crit, rub.pass_threshold)
        return merge_agent_results("presentation_graphics", rub.display_name, rub.pass_threshold, base)

    def evaluate_composer_raw(self, raw: str, ppt_path: Path | None) -> AgentScoreResult:
        rub = PPT_CHAIN_RUBRICS["ppt_composer"]
        crit = _score_composer_raw(raw, ppt_path)
        base = score_from_criteria(crit, rub.pass_threshold)
        return merge_agent_results("ppt_composer", rub.display_name, rub.pass_threshold, base)

    def evaluate_final_ppt(self, deck: SlideDeckSpec, ppt_path: Path | None, full_md: str) -> AgentScoreResult:
        crit = _score_final_ppt(deck, ppt_path, full_md)
        base = score_from_criteria(crit, FINAL_PPT_PASS_SCORE)
        return merge_agent_results("final_ppt", "Final PPT Quality", FINAL_PPT_PASS_SCORE, base)

    def first_failed_core_target(self, results: list[AgentScoreResult]) -> tuple[str, str]:
        """피드백 문자열과 함께 _IMPROVEMENT_MAP 키를 반환 — 없으면 ('', '')."""
        for r in results:
            if not r.passed and r.agent_id in HARNESS_CORE_TO_FEEDBACK_TARGET:
                fid = ", ".join(r.failed_ids[:6])
                fb = f"[Harness] {r.display_name} 미달(점수 {r.score}/{r.threshold}): {fid}"
                return HARNESS_CORE_TO_FEEDBACK_TARGET[r.agent_id], fb
        return "", ""

    def build_combined_report(
        self,
        *,
        deck: SlideDeckSpec | None,
        core_results: list[AgentScoreResult],
        chain_results: list[AgentScoreResult],
        final_ppt: AgentScoreResult | None,
        stages: list[StageHarnessSnapshot],
        improvement_attempts: int,
        max_improvement_attempts: int,
    ) -> CombinedHarnessReport:
        """deck는 필수 토픽 누락 추천에만 쓰인다 — 없으면 해당 문장을 생략한다."""
        all_r = list(core_results) + list(chain_results)
        if final_ppt:
            all_r.append(final_ppt)
        scores = {r.agent_id: r.score for r in all_r}
        avg = sum(scores.values()) / max(len(scores), 1)
        failed: list[str] = []
        for r in all_r:
            if not r.passed:
                failed.extend(f"{r.agent_id}:{fid}" for fid in r.failed_ids)
        thresh = FINAL_PPT_PASS_SCORE
        mandatory_missing = 0
        if deck and deck.slides:
            _cov, _need, miss = _final_slide_keyword_coverage(deck)
            mandatory_missing = len(miss)
        # 최종 통과: final 점수 85+ 이고 필수 토픽 누락 0, PPT 파일 criterion은 final_ppt 내부
        final_passed = bool(final_ppt and final_ppt.passed and final_ppt.score >= FINAL_PPT_PASS_SCORE)
        if mandatory_missing > 0:
            final_passed = False
        feedback_target, _ = self.first_failed_core_target(core_results)
        reco: list[str] = []
        if failed:
            reco.append("미달 기준을 feedback_block에 반영해 해당 Agent만 재실행하세요.")
        if deck and deck.slides and (not final_passed) and final_ppt:
            _cov, _need, miss = _final_slide_keyword_coverage(deck)
            if miss:
                reco.append(f"필수 슬라이드 키워드 보강: {', '.join(miss[:6])}")
        warn: list[str] = []
        if not final_passed:
            warn.append("최종 품질 기준 미달 — 다운로드는 가능하나 검토가 필요합니다.")
        overall = round((final_ppt.score * 0.55 + avg * 0.45), 2) if final_ppt else round(avg, 2)
        return CombinedHarnessReport(
            overall_score=overall,
            pass_threshold=thresh,
            final_passed=final_passed,
            agent_scores=scores,
            failed_criteria=failed,
            feedback_target=feedback_target,
            improvement_attempts=improvement_attempts,
            max_improvement_attempts=max_improvement_attempts,
            stages=list(stages),
            warnings=warn,
            recommendations=reco,
        )


def run_harness_improvement_loop(
    state: AutoPMState,
    agents: dict[str, Any],
    task_defs: dict[str, Any],
    enriched: dict[str, str],
    run_improvement: Callable[..., None],
    on_progress: Callable[[str], None] | None,
    *,
    max_attempts: int = 3,
) -> tuple[list[AgentScoreResult], int, str]:
    """
    코어 Agent 산출물이 루브릭을 통과할 때까지 `run_improvement`를 반복 호출한다.
    CrewAI 재호출 비용이 있으므로 attempts 상한을 둔다.
    """
    harness = EvaluationHarness()
    attempt = 0
    feedback = ""
    last_results = harness.evaluate_all_core(state)
    while attempt < max_attempts:
        failed = [r for r in last_results if not r.passed]
        if not failed:
            break
        target, fb = harness.first_failed_core_target(last_results)
        if not target:
            break
        feedback = fb
        if on_progress:
            on_progress(f"[Harness] 개선 루프 {attempt + 1}/{max_attempts} → target={target}")
        run_improvement(state, agents, task_defs, enriched, target, feedback, on_progress)
        attempt += 1
        last_results = harness.evaluate_all_core(state)
    return last_results, attempt, feedback

