"""
LangChain Deep Agents SDK(`create_deep_agent`) 통합 — AutoPM Parent/Sub-Agent 실행.

- Parent: `create_deep_agent` + `tasks.yaml` user 프롬프트
- Sub-Agent: `subagents.yaml` → `SubAgent` 스펙 → `task` 도구 위임
- MCP: `mcp_agent_tools.yaml` 도구를 LangChain Tool로 노출
- LLM 없음·호출 실패 시 `invoke_for_agent` 레거시 폴백
"""

from __future__ import annotations

import contextvars
import json
import os
from collections.abc import Callable
from functools import lru_cache
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

from autopm.agents.subagent_runner import SubAgentRunRecord
from autopm.mcp.integration import invoke_for_agent
from autopm.mcp.policy import resolve_tool_names
from autopm.mcp.registry import call_tool_inprocess
from autopm.services.llm_router import _coerce_llm_text, resolve_model_for_tier
from autopm.services.prompt_manager import (
    build_agent_system_prompt,
    build_subagent_system_prompt,
    build_task_user_prompt,
    load_subagents,
    proposal_context_block,
)

# invoke 중 MCP 도구가 읽는 컨텍스트 — 스레드·async 안전
_invoke_context: contextvars.ContextVar[dict[str, str]] = contextvars.ContextVar(
    "autopm_deep_agent_ctx",
    default={},
)

_AUTOPM_DELEGATION_SUFFIX = """
## AutoPM 실행 규칙 (Deep Agent)
- 최종 응답에 **기대 산출 형식**의 완성본(Markdown 또는 JSON)을 반드시 포함하라.
- Sub-Agent가 정의되어 있으면 **`task` 도구**로 각 Sub-Agent(`subagent_type`)를 **순서대로** 호출한 뒤 통합 결과를 작성하라.
- `structure_planner` → `deliverable_mapper` → `*_synthesizer` 등 YAML 순서를 따른다.
- 내장 파일시스템·셸 도구는 사용하지 말고, 제공된 AutoPM MCP 도구만 필요 시 호출하라.
- 수치·일정·비용은 **(가정)** 또는 **(예상)**을 명시하라.
"""


def is_deep_agents_sdk_enabled() -> bool:
    """Deep Agents SDK 경로 사용 — AUTOPM_USE_DEEP_AGENTS=false 로 레거시만."""
    return os.getenv("AUTOPM_USE_DEEP_AGENTS", "true").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _recursion_limit() -> int:
    try:
        return max(8, min(80, int(os.getenv("AUTOPM_DEEP_AGENT_RECURSION_LIMIT", "28"))))
    except ValueError:
        return 28


@lru_cache(maxsize=1)
def _ensure_autopm_harness_profiles() -> None:
    """AutoPM 전용 Harness — 파일·셸 내장 도구 제외, GP subagent 비활성(명시 subagents 사용 시)."""
    try:
        from deepagents import GeneralPurposeSubagentProfile, HarnessProfileConfig, register_harness_profile
    except ImportError:
        return

    cfg = HarnessProfileConfig(
        system_prompt_suffix=(
            "You are an AutoPM 추진계획서 agent. Produce structured Korean business deliverables. "
            "Do not use shell or workspace file tools."
        ),
        excluded_tools=frozenset(
            {
                "execute",
                "write_file",
                "edit_file",
                "write_todos",
                "ls",
                "read_file",
                "glob",
                "grep",
            }
        ),
        general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False),
    )
    for key in ("autopm", "openai:gpt-4o-mini", "openai:gpt-4o", "ollama"):
        try:
            register_harness_profile(key, cfg)
        except Exception:
            pass


def _tier_to_model(tier: str) -> tuple[Any | None, str]:
    return resolve_model_for_tier(tier)


def _build_subagents_from_yaml(
    parent_agent_key: str,
    agent_defs: dict[str, Any],
    context: dict[str, str],
) -> list[Any]:
    """subagents.yaml → deepagents SubAgent TypedDict 목록."""
    from deepagents.middleware.subagents import SubAgent

    chain = list(load_subagents().get(parent_agent_key) or [])
    if not chain:
        return []

    ctx_block = proposal_context_block(context)
    built: list[SubAgent] = []
    for spec in chain:
        sid = str(spec.get("id", "sub"))
        role = str(spec.get("role", sid))
        goal = str(spec.get("goal", "")).strip()
        tier = str(spec.get("llm_tier", "local")).strip().lower()
        sub_model, _ = _tier_to_model(tier)
        system = build_subagent_system_prompt(parent_agent_key, sid, role, goal)
        if ctx_block:
            system = f"{system}\n\n## 입력 맥락\n{ctx_block[:6000]}"

        entry: SubAgent = {
            "name": sid,
            "description": f"{role}: {goal[:200]}",
            "system_prompt": system,
        }
        if sub_model is not None:
            entry["model"] = sub_model
        built.append(entry)
    return built


def _make_langchain_tool(name: str, description: str):
    """MCP in-process 핸들러를 LangChain StructuredTool로 감싼다."""
    from langchain_core.tools import StructuredTool

    def _run(**kwargs: Any) -> str:
        ctx = _invoke_context.get()
        args = {k: v for k, v in kwargs.items() if v is not None}
        if "context" not in args:
            args["context"] = ctx
        return call_tool_inprocess(name, args)

    return StructuredTool.from_function(
        func=_run,
        name=name,
        description=description,
    )


_TOOL_DESCRIPTIONS: dict[str, str] = {
    "rag_search": "사내 추진계획서 표준·가이드 RAG(Chroma) 검색",
    "retrieve_reference_context": "사내 표준 양식·AS-IS/TO-BE/WBS/ROI/리스크 가이드 RAG",
    "extract_proposal_info": "제목에서 회사·전략·시스템·범위 JSON 추출(S01)",
    "generate_interview_questions": "추진계획서 보완 인터뷰 질문 5개 JSON(S02)",
    "estimate_cost": "월 소요·인원·예산으로 비용·절감 힌트(가정) 산출",
    "fp_estimate": "기능점수(FP) 자리표시자",
    "mermaid_process": "AS-IS/TO-BE 프로세스 Mermaid 다이어그램",
    "gantt_outline": "WBS·일정 Gantt Mermaid 템플릿",
    "normalize_input": "붙여넣기 텍스트 정규화",
    "read_slide_plan": "outputs/slide_plan.json 요약 조회",
}


def build_mcp_langchain_tools(agent_key: str, task_key: str = "") -> list[Any]:
    """Agent/Task 정책에 맞는 MCP LangChain 도구."""
    names = resolve_tool_names(agent_key, task_key)
    tools = []
    for n in names:
        desc = _TOOL_DESCRIPTIONS.get(n, f"AutoPM MCP tool: {n}")
        tools.append(_make_langchain_tool(n, desc))
    return tools


def _extract_final_text(messages: list[BaseMessage]) -> str:
    """그래프 종료 메시지에서 최종 Parent 산출 텍스트 추출."""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            text = msg.text if hasattr(msg, "text") else ""
            if not text and isinstance(msg.content, str):
                text = msg.content
            elif not text and isinstance(msg.content, list):
                parts = []
                for block in msg.content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        parts.append(str(block.get("text", "")))
                    elif isinstance(block, str):
                        parts.append(block)
                text = "\n".join(parts)
            if str(text).strip():
                return str(text).strip()
    return ""


def _parse_subagent_records(messages: list[BaseMessage], chain_specs: list[dict[str, Any]]) -> list[SubAgentRunRecord]:
    """task 도구 호출·응답에서 Sub-Agent 실행 기록 복원."""
    spec_by_name = {str(s.get("id")): s for s in chain_specs}
    pending: dict[str, str] = {}
    records: list[SubAgentRunRecord] = []

    for msg in messages:
        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            for tc in msg.tool_calls:
                if not isinstance(tc, dict):
                    continue
                if tc.get("name") != "task":
                    continue
                args = tc.get("args") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                sid = str(args.get("subagent_type", ""))
                tc_id = str(tc.get("id", ""))
                if tc_id and sid:
                    pending[tc_id] = sid
        if isinstance(msg, ToolMessage) and getattr(msg, "name", None) == "task":
            tc_id = str(getattr(msg, "tool_call_id", "") or "")
            sid = pending.get(tc_id, "subagent")
            spec = spec_by_name.get(sid, {})
            content = _coerce_llm_text(getattr(msg, "content", ""))
            records.append(
                SubAgentRunRecord(
                    subagent_id=sid,
                    role=str(spec.get("role", sid)),
                    llm_tier=str(spec.get("llm_tier", "local")),
                    provider="deep_agent_sdk",
                    output=content,
                )
            )
    return records


def invoke_deep_agent(
    *,
    agent_key: str,
    agent_defs: dict[str, Any],
    task_key: str,
    task_description: str,
    expected_output: str,
    context: dict[str, str],
    subagent_specs: list[dict[str, Any]] | None = None,
    prior_dialogue: str = "",
    extra_sections: str = "",
    tier: str = "cloud",
    on_progress: Callable[[str], None] | None = None,
) -> tuple[str, str, list[SubAgentRunRecord]]:
    """
    create_deep_agent 그래프 1회 invoke.

    Returns: (final_text, provider_label, subagent_records)
    """
    from deepagents import create_deep_agent

    _ensure_autopm_harness_profiles()

    model, provider = _tier_to_model(tier)
    if model is None:
        raise RuntimeError("no_llm_for_deep_agent")

    system = build_agent_system_prompt(agent_key, agent_defs)
    system = f"{system}\n\n{_AUTOPM_DELEGATION_SUFFIX.strip()}"

    user = build_task_user_prompt(
        task_key,
        task_description,
        expected_output,
        context,
        prior_dialogue=prior_dialogue,
        extra_sections=extra_sections,
    )

    subagents = []
    if subagent_specs:
        subagents = _build_subagents_from_yaml(agent_key, agent_defs, context)

    tools = build_mcp_langchain_tools(agent_key, task_key)

    if on_progress:
        on_progress(f"  ▸ Deep Agent SDK (`create_deep_agent`) — {agent_key}")

    token = _invoke_context.set(dict(context))
    try:
        graph = create_deep_agent(
            model=model,
            tools=tools or None,
            system_prompt=system,
            subagents=subagents or None,
            name=f"autopm_{agent_key}",
        )
        result = graph.invoke(
            {"messages": [HumanMessage(content=user)]},
            config={"recursion_limit": _recursion_limit()},
        )
    finally:
        _invoke_context.reset(token)

    messages = list(result.get("messages") or [])
    text = _extract_final_text(messages)
    if not text.strip():
        raise RuntimeError("empty_deep_agent_output")

    records = _parse_subagent_records(messages, subagent_specs or [])
    return text, f"deep_agent_sdk/{provider}", records


def run_task_via_deep_agent_or_fallback(
    agent_key: str,
    agent_defs: dict[str, Any],
    task_defs: dict[str, Any],
    task_key: str,
    context: dict[str, str],
    *,
    prior_dialogue: str = "",
    extra_sections: str = "",
    on_progress: Callable[[str], None] | None = None,
    use_subagents: bool = True,
) -> tuple[str, str, list[SubAgentRunRecord]]:
    """
    SDK 우선 실행 — 실패·LLM 없음 시 `invoke_for_agent` 폴백.
    """
    spec = task_defs[task_key]
    ag_key = spec["agent"]
    chain = list(load_subagents().get(ag_key) or []) if use_subagents else []

    if is_deep_agents_sdk_enabled():
        try:
            return invoke_deep_agent(
                agent_key=ag_key,
                agent_defs=agent_defs,
                task_key=task_key,
                task_description=spec["description"],
                expected_output=spec["expected_output"],
                context=context,
                subagent_specs=chain if chain else None,
                prior_dialogue=prior_dialogue,
                extra_sections=extra_sections,
                tier="cloud",
                on_progress=on_progress,
            )
        except Exception as exc:
            if on_progress:
                on_progress(f"  ↳ Deep Agent SDK 폴백 ({type(exc).__name__}): 레거시 LLM")

    # 레거시: Sub-Agent 수동 체인 + Parent 통합 (invoke_for_agent)
    if chain:
        from autopm.agents.subagent_runner import _legacy_run_subagents_then_task

        text, records = _legacy_run_subagents_then_task(
            ag_key,
            agent_defs,
            task_defs,
            task_key,
            context,
            prior_dialogue=prior_dialogue,
            on_progress=on_progress,
        )
        return text, "legacy_subagent_chain", records

    system = build_agent_system_prompt(ag_key, agent_defs)
    user = build_task_user_prompt(
        task_key,
        spec["description"],
        spec["expected_output"],
        context,
        prior_dialogue=prior_dialogue,
        extra_sections=extra_sections,
    )
    text, prov = invoke_for_agent(
        system,
        user,
        agent_key=ag_key,
        task_key=task_key,
        tier="cloud",
        fallback_key=task_key,
        context=context,
    )
    return _coerce_llm_text(text), prov, []


__all__ = [
    "build_mcp_langchain_tools",
    "invoke_deep_agent",
    "is_deep_agents_sdk_enabled",
    "run_task_via_deep_agent_or_fallback",
]
