"""Agent 간 다회차 대화 — 검토·응답·합의 후 산출물 보완."""

from __future__ import annotations

import os
from typing import Any

from autopm.services.llm_router import _coerce_llm_text, invoke_with_tier
from autopm.services.prompt_manager import (
    build_agent_system_prompt,
    build_peer_dialogue_user_prompt,
    safe_format_prompt,
)


def dialogue_rounds_limit() -> int:
    """대화 라운드 수 — 홀수 권장(검토→응답→확인)."""
    raw = os.getenv("AUTOPM_DIALOGUE_ROUNDS", "3").strip()
    try:
        n = max(2, min(5, int(raw)))
    except ValueError:
        n = 3
    return n if n % 2 == 1 else n + 1  # 최소 검토·응답·마무리


def dialogue_revise_enabled() -> bool:
    """대화 후 Producer가 산출을 한 번 더 개선할지."""
    return os.getenv("AUTOPM_DIALOGUE_REVISE", "true").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


# task_key → (검토자 관점 피드백, Producer 응답, 마무리) — LLM 없을 때도 구체 대화
_DIALOGUE_SCRIPTS: dict[str, tuple[str, str, str]] = {
    "orchestrate_task": (
        "Executive 요약은 좋습니다. 다만 **WBS·예산·리스크** 섹션이 목차에 명시돼 있는지, "
        "보고 대상({target_audience})에 맞는 톤인지 확인이 필요합니다.",
        "목차에 7~10번 섹션(WBS·예산·리스크)을 반영하고, 경영 보고 톤이면 KPI·리스크를 앞쪽에 두겠습니다.",
        "합의: 다음 Requirement 단계에서 누락·가정 표를 채워 주세요.",
    ),
    "requirement_task": (
        "누락 항목에 **데이터 소스·승인 라인·파일럿 범위**가 있는지 봐 주세요. "
        "가정 표에 (가정) 표기가 빠진 행이 없는지도 확인합니다.",
        "데이터 소스(ERP/엑셀)·승인 라인·파일럿 범위를 가정 표에 추가하고, 모든 수치·범위에 (가정)을 붙이겠습니다.",
        "합의: Business Analyst는 AS-IS를 단계 3개 이상으로 쓰고 Pain은 정량(시간·건수)을 넣어 주세요.",
    ),
    "business_analysis_task": (
        "AS-IS가 bullet 1~2개면 부족합니다. **단계별 표**(단계|담당|산출물)와 "
        "Pain **3개 이상**(시간·품질·리스크)을 요청합니다.",
        "AS-IS 4단계 표와 Pain 4개(월 {monthly_hours}h 검증 부담 등)로 보강하겠습니다.",
        "합의: Solution은 TO-BE와 MVP 제외 범위를 명시해 주세요.",
    ),
    "solution_design_task": (
        "TO-BE 단계와 **MVP 포함/제외**가 분리돼 있는지 확인합니다. "
        "실 ERP 연동은 Phase 2로 미루는지 명시해 주세요.",
        "TO-BE 5단계, MVP=In(룰·배치·리포트)/Out(ERP 커스터)로 정리하겠습니다.",
        "합의: Scope Agent가 모듈 표와 우선순위를 맞춰 주세요.",
    ),
    "development_scope_task": (
        "포함·제외가 혼재되지 않았는지, **모듈 책임**이 한 줄씩 있는지 봅니다.",
        "In/Out 표 분리, 모듈 3~5개(룰 엔진·배치·UI)로 구체화하겠습니다.",
        "합의: WBS는 희망 일정({target_timeline})에 맞게 4~6행으로 압축해 주세요.",
    ),
    "wbs_task": (
        "WBS 기간 합이 **{target_timeline}**과 맞는지, 산출물 컬럼이 비어 있지 않은지 확인합니다.",
        "총 4주 내 4단계(킥오프·분석·구현·파일럿)로 재정렬하고 산출물을 채우겠습니다.",
        "합의: Budget은 모든 금액에 (가정)을 붙이고 KPI 현재/목표를 넣어 주세요.",
    ),
    "budget_roi_task": (
        "예산·KPI에 **(가정)** 표기가 있는지, ROI 논리가 2문장 이상인지 확인합니다.",
        "항목별 만 원 구간(가정)과 KPI 표(현재→목표)를 추가하겠습니다.",
        "합의: Risk는 5행 이상 매트릭스와 대응 담당을 넣어 주세요.",
    ),
    "risk_critic_task": (
        "리스크 **5개 이상**, 발생 가능성·영향도·대응이 한 행에 있는지 봅니다.",
        "데이터 품질·일정·조직 저항·범위 확대·파일럿 실패 5건으로 표를 채우겠습니다.",
        "합의: 이후 Critic·문서화 단계에서 일관성을 맞춥니다.",
    ),
}


def _format_script(template: str, enriched: dict[str, str]) -> str:
    return safe_format_prompt(template, enriched)


def _should_use_contextual_dialogue(msg: str, provider: str) -> bool:
    """LLM 미사용·generic fallback 한 줄이면 task별 스크립트로 대체한다."""
    if provider in ("fallback", "fallback_dialogue") or not msg.strip():
        return True
    low = msg.strip().lower()
    generic_markers = (
        "다음 단계에서 보완",
        "이전 단계 산출을 확인",
        "peer_dialogue",
        "(fallback)",
        "## peer_dialogue",
    )
    if any(m in low for m in generic_markers) and len(msg) < 200:
        return True
    return False


def _contextual_fallback_turn(
    *,
    round_no: int,
    speaker: str,
    task_key: str,
    from_role: str,
    to_role: str,
    enriched: dict[str, str],
    output_clip: str,
) -> str:
    """라운드·역할별 rule-based 대화 — generic 한 줄 방지."""
    scripts = _DIALOGUE_SCRIPTS.get(task_key)
    if scripts:
        critique, producer_reply, closing = scripts
        if round_no == 1 and speaker == "reviewer":
            return _format_script(critique, enriched)
        if round_no == 2 and speaker == "producer":
            return _format_script(producer_reply, enriched)
        if round_no >= 3 and speaker == "reviewer":
            return _format_script(closing, enriched)

    title = enriched.get("proposal_title") or enriched.get("idea_title", "추진계획")
    if round_no == 1 and speaker == "reviewer":
        missing = []
        if len(output_clip) < 200:
            missing.append("본문이 짧음 — 표·bullet 보강")
        if "가정" not in output_clip and "예상" not in output_clip:
            missing.append("수치·비용에 (가정) 표기")
        if "|" not in output_clip:
            missing.append("Markdown 표 1개 이상")
        hint = " / ".join(missing) if missing else "구조는 양호, 다음 단계 연계만 확인"
        return f"[{to_role}] `{title}` 기준 검토: {hint}. 구체적으로 표·단계·KPI를 보강해 주세요."

    if round_no == 2 and speaker == "producer":
        return (
            f"[{from_role}] 검토 반영하겠습니다. "
            f"{'표와 (가정) 표기를 추가' if '|' not in output_clip else '요청하신 항목을 본문에 반영'}하고 "
            f"{to_role} 단계와 톤을 맞추겠습니다."
        )

    return f"[{to_role}] 합의했습니다. 다음 단계에서 연계·중복 없이 반영해 주세요."


def _dialogue_turn_llm(
    *,
    agent_key: str,
    agent_defs: dict[str, Any],
    enriched: dict[str, str],
    round_no: int,
    speaker: str,
    from_role: str,
    to_role: str,
    task_key: str,
    output_clip: str,
    prior_turns: list[dict[str, Any]],
) -> tuple[str, str]:
    """한 라운드 LLM 호출 — (message, provider)."""
    thread = "\n".join(
        f"**R{t.get('round')} [{t.get('speaker')}]** {t.get('message', '')[:600]}"
        for t in prior_turns
    )
    system = build_agent_system_prompt(agent_key, agent_defs)
    if round_no == 1 and speaker == "reviewer":
        user = build_peer_dialogue_user_prompt(
            title=enriched.get("proposal_title") or enriched.get("idea_title", ""),
            from_role=from_role,
            to_role=to_role,
            producer_clip=output_clip,
        )
        user += (
            "\n\n이번은 **1라운드 검토**다. 잘된 점·보완점·다음 Agent가 반영할 **구체 힌트 2개**를 써라."
        )
    elif speaker == "producer":
        user = (
            f"## 검토 대상 산출 (task: {task_key})\n{output_clip[:3500]}\n\n"
            f"## 지금까지 대화\n{thread or '(첫 응답)'}\n\n"
            f"당신은 **{from_role}**이다. 검토 의견에 대해 "
            "**수용할 수정 2~3개**를 bullet로 답하고, 반대·보류가 있으면 이유 1줄."
        )
    else:
        user = (
            f"## 산출 요약\n{output_clip[:2000]}\n\n## 대화\n{thread}\n\n"
            f"**{to_role}**으로서 마지막 합의: 남은 리스크 1개 + 다음 단계({to_role})에 전달할 **한 줄 지시**."
        )

    tier = "local" if round_no < 3 else "auto"
    msg, prov = invoke_with_tier(
        system,
        user,
        tier=tier,
        fallback_key=f"peer_dialogue_r{round_no}",
        context=enriched,
    )
    if _should_use_contextual_dialogue(msg, prov):
        msg = _contextual_fallback_turn(
            round_no=round_no,
            speaker=speaker,
            task_key=task_key,
            from_role=from_role,
            to_role=to_role,
            enriched=enriched,
            output_clip=output_clip,
        )
        prov = "fallback_dialogue"
    return msg.strip(), prov


def run_multi_turn_peer_dialogue(
    *,
    from_agent_key: str,
    to_agent_key: str,
    from_role: str,
    to_role: str,
    producer_output: str,
    task_key: str,
    enriched: dict[str, str],
    agent_defs: dict[str, Any],
) -> dict[str, Any]:
    """
    Producer ↔ Reviewer 다회차 대화.
    반환: thread dict (rounds, revision_hint, …) — state.agent_dialogue에 append.
    """
    prod = producer_output if isinstance(producer_output, str) else str(producer_output or "")
    clip = prod.strip()[:4000]
    max_rounds = dialogue_rounds_limit()
    turns: list[dict[str, Any]] = []

    for r in range(1, max_rounds + 1):
        if r % 2 == 1:
            speaker = "reviewer"
            ag_key = to_agent_key
        else:
            speaker = "producer"
            ag_key = from_agent_key

        msg, provider = _dialogue_turn_llm(
            agent_key=ag_key,
            agent_defs=agent_defs,
            enriched=enriched,
            round_no=r,
            speaker=speaker,
            from_role=from_role,
            to_role=to_role,
            task_key=task_key,
            output_clip=clip,
            prior_turns=turns,
        )
        turns.append(
            {
                "round": r,
                "speaker": speaker,
                "agent_key": ag_key,
                "role": to_role if speaker == "reviewer" else from_role,
                "message": msg,
                "provider": provider,
            }
        )

    revision_hint = _consolidate_revision_hint(turns)
    return {
        "thread_id": f"{task_key}:{from_agent_key}->{to_agent_key}",
        "task_key": task_key,
        "from_agent": from_agent_key,
        "to_agent": to_agent_key,
        "from_role": from_role,
        "to_role": to_role,
        "rounds": turns,
        "round_count": len(turns),
        "message": turns[-1]["message"] if turns else "",
        "revision_hint": revision_hint,
    }


def _consolidate_revision_hint(turns: list[dict[str, Any]]) -> str:
    """대화 전체에서 feedback_block용 힌트 추출."""
    parts: list[str] = []
    for t in turns:
        msg = (t.get("message") or "").strip()
        if not msg:
            continue
        if t.get("speaker") == "reviewer" or "보완" in msg or "추가" in msg or "표" in msg:
            parts.append(f"[R{t.get('round')}] {msg[:500]}")
    return "\n".join(parts)[:2000]


def revise_output_after_dialogue(
    *,
    from_agent_key: str,
    task_key: str,
    task_defs: dict[str, Any],
    agent_defs: dict[str, Any],
    original_output: str,
    dialogue_thread: dict[str, Any],
    enriched: dict[str, str],
) -> tuple[str, str]:
    """
    대화 내용을 반영해 Producer 산출을 1회 개선.
    반환: (revised_text, provider)
    """
    if not dialogue_revise_enabled():
        return original_output, "skip_revise"

    thread_txt = format_dialogue_thread(dialogue_thread)
    spec = task_defs.get(task_key) or {}
    expected = str(spec.get("expected_output", "")).strip()

    system = build_agent_system_prompt(from_agent_key, agent_defs)
    user = (
        f"## 원본 산출 (task: {task_key})\n{original_output[:8000]}\n\n"
        f"## Agent 간 대화 (검토·합의)\n{thread_txt}\n\n"
        f"**지시:** 위 대화에서 합의한 보완을 **원본 형식을 유지**하며 반영한 개선본만 출력하라.\n"
        f"**기대 형식:**\n{expected}"
    )

    revised, provider = invoke_with_tier(
        system,
        user,
        tier="cloud",
        fallback_key=task_key,
        context=enriched,
    )
    revised = _coerce_llm_text(revised)
    if len(revised.strip()) < max(80, len(original_output.strip()) // 4):
        revised = _fallback_merge_dialogue(original_output, dialogue_thread, enriched)
        provider = "fallback_merge"
    return revised.strip(), provider


def _fallback_merge_dialogue(
    original: str,
    thread: dict[str, Any],
    enriched: dict[str, str],
) -> str:
    """LLM 없을 때 대화 합의를 본문 하단에 반영 섹션으로 붙인다."""
    hint = thread.get("revision_hint") or ""
    if not hint.strip():
        return original
    title = enriched.get("proposal_title") or "추진계획"
    block = (
        f"\n\n### Agent 간 검토 반영 (합의 · {title})\n"
        + "\n".join(f"- {line[:300]}" for line in hint.split("\n") if line.strip()[:10])
    )
    if block.strip() in original:
        return original
    return (original.rstrip() + block).strip()


def format_dialogue_thread(thread: dict[str, Any]) -> str:
    """단일 스레드 전체를 프롬프트용 문자열로."""
    lines: list[str] = []
    fr = thread.get("from_role") or thread.get("from_agent", "")
    to = thread.get("to_role") or thread.get("to_agent", "")
    lines.append(f"### {fr} ↔ {to} ({thread.get('task_key', '')})")
    for t in thread.get("rounds") or []:
        sp = t.get("speaker", "?")
        role = t.get("role", sp)
        lines.append(f"**R{t.get('round')} {role}:** {(t.get('message') or '')[:700]}")
    if thread.get("revision_hint"):
        lines.append(f"**합의 요약:** {thread['revision_hint'][:500]}")
    return "\n".join(lines)


def _dialogue_entry_as_dict(entry: Any) -> dict[str, Any]:
    """Pydantic AgentDialogueThread 또는 legacy dict → dict."""
    if hasattr(entry, "model_dump"):
        return entry.model_dump()
    return entry if isinstance(entry, dict) else {}


def format_dialogue_for_prompt(dialogue_log: list[Any], limit: int = 8) -> str:
    """최근 대화 스레드를 프롬프트에 넣는다 — 다회차 rounds 지원."""
    if not dialogue_log:
        return ""
    lines: list[str] = []
    for raw in dialogue_log[-limit:]:
        entry = _dialogue_entry_as_dict(raw)
        if entry.get("rounds"):
            lines.append(format_dialogue_thread(entry))
            continue
        fr = entry.get("from_role") or entry.get("from_agent", "")
        to = entry.get("to_role") or entry.get("to_agent", "")
        msg = (entry.get("message") or "").strip()
        if msg:
            lines.append(f"**{fr} → {to}:** {msg[:800]}")
    return "\n\n".join(lines)


# 하위 호환
def run_peer_dialogue(
    *,
    from_agent_key: str,
    to_agent_key: str,
    from_role: str,
    to_role: str,
    producer_output: str,
    enriched: dict[str, str],
    agent_defs: dict[str, Any],
    task_key: str = "",
) -> dict[str, str]:
    """단일 턴 래퍼 — 내부적으로 다회차의 마지막 메시지만 반환 형식 유지."""
    thread = run_multi_turn_peer_dialogue(
        from_agent_key=from_agent_key,
        to_agent_key=to_agent_key,
        from_role=from_role,
        to_role=to_role,
        producer_output=producer_output,
        task_key=task_key or "pipeline",
        enriched=enriched,
        agent_defs=agent_defs,
    )
    return {
        "from_agent": thread["from_agent"],
        "to_agent": thread["to_agent"],
        "from_role": thread["from_role"],
        "to_role": thread["to_role"],
        "message": thread.get("message", ""),
        "revision_hint": thread.get("revision_hint", ""),
        "rounds": thread.get("rounds", []),
    }


__all__ = [
    "dialogue_rounds_limit",
    "dialogue_revise_enabled",
    "run_multi_turn_peer_dialogue",
    "run_peer_dialogue",
    "revise_output_after_dialogue",
    "format_dialogue_for_prompt",
    "format_dialogue_thread",
]
