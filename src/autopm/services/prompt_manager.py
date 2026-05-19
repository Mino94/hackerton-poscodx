"""prompt_manager — System Prompt·Few-shot(경계 케이스) 조립의 단일 진입점."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_CONFIG = Path(__file__).resolve().parents[1] / "config"


def load_tasks() -> dict[str, Any]:
    with (_CONFIG / "tasks.yaml").open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_agents() -> dict[str, Any]:
    with (_CONFIG / "agents.yaml").open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_subagents() -> dict[str, Any]:
    """Parent Agent 키 → Sub-Agent 체인 목록."""
    path = _CONFIG / "subagents.yaml"
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


@lru_cache(maxsize=1)
def load_system_prompts() -> dict[str, Any]:
    """System Prompt + Few-shot 정의 — 파일 없으면 최소 기본값."""
    path = _CONFIG / "system_prompts.yaml"
    if not path.is_file():
        return {"global": {"system": "", "rules": []}, "few_shots": {}}
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


def safe_format_prompt(template: str, context: dict[str, str]) -> str:
    """tasks.yaml placeholder 누락 시 KeyError 없이 빈 문자열로 채운다."""
    out = template
    for key in set(re.findall(r"\{(\w+)\}", template)):
        out = out.replace("{" + key + "}", str(context.get(key) or ""))
    return out


def _lines(items: list[str] | None, prefix: str = "- ") -> str:
    if not items:
        return ""
    return "\n".join(f"{prefix}{x}" for x in items if str(x).strip())


def build_global_system_block() -> str:
    """모든 Agent에 공통 적용되는 System Prompt 본문."""
    g = load_system_prompts().get("global") or {}
    parts: list[str] = []
    core = str(g.get("system") or "").strip()
    if core:
        parts.append(core)
    rules = _lines(g.get("rules"))
    if rules:
        parts.append("## 필수 규칙\n" + rules)
    anti = _lines(g.get("anti_patterns"))
    if anti:
        parts.append("## 하지 말 것\n" + anti)
    boundary = _lines(g.get("boundary_policy"))
    if boundary:
        parts.append("## 경계 입력 처리 원칙\n" + boundary)
    return "\n\n".join(parts).strip()


def format_few_shot_block(
    examples: list[dict[str, Any]] | None,
    *,
    section_title: str = "Few-shot 참고",
) -> str:
    """
    Few-shot 블록 — 경계 케이스 예시를 user 메시지 상단에 붙인다.
    LLM이 예시 수치를 복사하지 않도록 경고 문구를 포함한다.
    """
    if not examples:
        return ""
    lines = [
        f"## {section_title}",
        "*(아래 예시는 **형식·구조·경계 처리 방법**만 참고하라. 수치·고유명사·프로젝트명은 "
        "**현재 사용자 입력**을 우선하고 예시 값을 복사하지 마라.)*",
        "",
    ]
    for i, ex in enumerate(examples, 1):
        label = ex.get("case_label") or ex.get("title") or f"예시 {i}"
        lines.append(f"### {label}")
        if ex.get("boundary_note"):
            lines.append(f"- **경계 포인트:** {ex['boundary_note']}")
        if ex.get("input_summary"):
            lines.append(f"- **입력 요약:** {ex['input_summary']}")
        out = str(ex.get("output") or "").strip()
        if out:
            lines.append(f"- **기대 출력 샘플:**\n{out}")
        lines.append("")
    return "\n".join(lines).strip()


def get_few_shots_for_task(task_key: str) -> list[dict[str, Any]]:
    fs = (load_system_prompts().get("few_shots") or {}).get("by_task") or {}
    return list(fs.get(task_key) or [])


def get_few_shots_for_subagent(subagent_id: str) -> list[dict[str, Any]]:
    fs = (load_system_prompts().get("few_shots") or {}).get("by_subagent") or {}
    return list(fs.get(subagent_id) or [])


def get_peer_dialogue_few_shots() -> list[dict[str, Any]]:
    fs = load_system_prompts().get("few_shots") or {}
    return list(fs.get("peer_dialogue") or [])


def build_agent_system_prompt(agent_key: str, agent_defs: dict[str, Any]) -> str:
    """Parent Agent용 System Prompt — global 규칙 + role/goal/backstory."""
    spec = agent_defs[agent_key]
    role = str(spec.get("role", agent_key))
    goal = str(spec.get("goal", "")).strip()
    backstory = str(spec.get("backstory", "")).strip()

    global_block = build_global_system_block()
    agent_block = (
        f"## 당신의 역할\n"
        f"- **역할:** {role}\n"
        f"- **목표:** {goal}\n"
        f"- **배경:** {backstory}\n"
        f"- **Agent ID:** `{agent_key}`"
    )
    parts = [p for p in (global_block, agent_block) if p.strip()]
    return "\n\n".join(parts)


def build_subagent_system_prompt(
    parent_agent_key: str,
    subagent_id: str,
    role: str,
    goal: str,
) -> str:
    """Sub-Agent용 System Prompt — global + Sub-Agent 역할 + 해당 Sub-Agent Few-shot."""
    global_block = build_global_system_block()
    sub_block = (
        f"## Sub-Agent\n"
        f"- **역할:** {role}\n"
        f"- **Parent Agent:** `{parent_agent_key}`\n"
        f"- **Sub-Agent ID:** `{subagent_id}`\n"
        f"- **목표:** {goal}\n"
        "- 다른 Sub-Agent와 **중복 최소화**. Parent synthesizer가 통합하므로 **세부 분석에만 집중**."
    )
    few = format_few_shot_block(
        get_few_shots_for_subagent(subagent_id),
        section_title="Sub-Agent Few-shot (경계 케이스)",
    )
    parts = [global_block, sub_block]
    if few:
        parts.append(few)
    return "\n\n".join(p for p in parts if p.strip())


def build_task_user_prompt(
    task_key: str,
    description: str,
    expected_output: str,
    context: dict[str, str],
    *,
    prior_dialogue: str = "",
    extra_sections: str = "",
) -> str:
    """
    Task user 메시지 — Few-shot(경계) → 실제 과제 → 기대 형식.
    prior_dialogue는 실제 과제 블록 안에 포함한다.
    """
    few_block = format_few_shot_block(
        get_few_shots_for_task(task_key),
        section_title="Few-shot 참고 (경계 케이스 포함)",
    )
    desc = safe_format_prompt(description.strip(), context)
    if prior_dialogue.strip():
        desc += f"\n\n### 이전 Agent 간 대화·검토\n{prior_dialogue.strip()[:6000]}"

    parts: list[str] = []
    if few_block:
        parts.append(few_block)
    parts.append("---")
    parts.append("## 실제 과제 (현재 사용자 입력 기준)")
    parts.append(desc)
    parts.append(f"\n**기대 산출 형식 (반드시 준수):**\n{expected_output.strip()}")
    if extra_sections.strip():
        parts.append(extra_sections.strip())
    return "\n\n".join(parts)


def proposal_context_block(context: dict[str, str]) -> str:
    """Sub-Agent·피어 리뷰 공통 — proposal 중심 필드를 압축한다."""
    keys = (
        "proposal_title",
        "proposal_purpose",
        "background_context",
        "current_problems",
        "target_system",
        "business_scope",
        "improvement_direction",
        "target_audience",
        "key_emphasis",
        "presentation_tone",
        "proposal_meta_hints",
        "interview_seed",
        "feedback_block",
        "agent_dialogue_summary",
    )
    lines = []
    for k in keys:
        v = (context.get(k) or "").strip()
        if v:
            lines.append(f"- **{k}**: {v[:600]}")
    return "\n".join(lines) if lines else "(컨텍스트 없음)"


def build_subagent_user_prompt(
    goal: str,
    context: dict[str, str],
    prior_subagent_block: str,
) -> str:
    """Sub-Agent user 메시지 — 맥락 + 이전 Sub-Agent + 과제."""
    return (
        f"## 추진계획서 맥락\n{proposal_context_block(context)}\n\n"
        f"## 이전 Sub-Agent 산출\n{prior_subagent_block or '(첫 Sub-Agent)'}\n\n"
        f"## 이번 Sub-Agent 과제\n{goal}"
    )


def build_peer_dialogue_user_prompt(
    *,
    title: str,
    from_role: str,
    to_role: str,
    producer_clip: str,
) -> str:
    """피어 리뷰 user 메시지 — Few-shot + 검토 대상."""
    few = format_few_shot_block(
        get_peer_dialogue_few_shots(),
        section_title="피어 리뷰 Few-shot",
    )
    body = (
        f"추진계획서 제목: {title}\n"
        f"검토 대상 Agent: {from_role}\n"
        f"다음 단계 Agent(당신): {to_role}\n\n"
        f"### 검토할 산출물\n{producer_clip}\n\n"
        "위 내용을 3~5문장으로 검토하라. "
        "1) 잘된 점 2) 보완할 점 3) 다음 Agent가 반영할 **구체 힌트 1~2개**(표/필드명 포함). "
        '"검토 완료"만 쓰지 마라.'
    )
    if few:
        return f"{few}\n\n---\n\n{body}"
    return body


__all__ = [
    "load_tasks",
    "load_agents",
    "load_subagents",
    "load_system_prompts",
    "safe_format_prompt",
    "build_global_system_block",
    "build_agent_system_prompt",
    "build_subagent_system_prompt",
    "build_task_user_prompt",
    "build_subagent_user_prompt",
    "build_peer_dialogue_user_prompt",
    "format_few_shot_block",
    "get_few_shots_for_task",
    "get_few_shots_for_subagent",
    "get_peer_dialogue_few_shots",
    "proposal_context_block",
]
