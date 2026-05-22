"""Deep Agents SDK 통합 단위 테스트 — LLM 없이 매핑·폴백."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from autopm.agents.agent_factory import build_all_agent_defs
from autopm.agents.deep_agent_sdk import (
    _build_subagents_from_yaml,
    _ensure_autopm_harness_profiles,
    _parse_subagent_records,
    is_deep_agents_sdk_enabled,
    run_task_via_deep_agent_or_fallback,
)
from autopm.agents.subagent_runner import SubAgentRunRecord
from autopm.services.prompt_manager import load_tasks
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage


def test_harness_registration_no_error():
    _ensure_autopm_harness_profiles()


def test_build_subagents_from_yaml():
    agent_defs = build_all_agent_defs()
    ctx = {"proposal_title": "ERP 테스트", "idea_title": "ERP 테스트"}
    subs = _build_subagents_from_yaml("pm_orchestrator_agent", agent_defs, ctx)
    assert len(subs) >= 3
    names = {s["name"] for s in subs}
    assert "structure_planner" in names
    assert "orchestrator_synthesizer" in names


def test_parse_subagent_records_from_messages():
    chain = [
        {"id": "gap_finder", "role": "r", "llm_tier": "local"},
    ]
    msgs = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "task",
                    "args": {"subagent_type": "gap_finder", "description": "find gaps"},
                    "id": "tc1",
                }
            ],
        ),
        ToolMessage(content="누락: 예산", name="task", tool_call_id="tc1"),
        AIMessage(content="최종 요약"),
    ]
    recs = _parse_subagent_records(msgs, chain)
    assert len(recs) == 1
    assert recs[0].subagent_id == "gap_finder"


def test_run_task_fallback_without_api_key():
    """OPENAI 없을 때 레거시/fallback 경로로 문자열 반환."""
    import os

    os.environ.pop("OPENAI_API_KEY", None)
    agent_defs = build_all_agent_defs()
    task_defs = load_tasks()
    ctx = {
        "proposal_title": "ERP 월마감",
        "idea_title": "ERP 월마감",
        "current_process": "엑셀 검증",
        "pain_points": "시간 소요",
    }
    text, prov, recs = run_task_via_deep_agent_or_fallback(
        "requirement_interview_agent",
        agent_defs,
        task_defs,
        "requirement_task",
        ctx,
        use_subagents=True,
    )
    assert isinstance(text, str) and len(text) > 20
    assert prov  # fallback or legacy label
    assert is_deep_agents_sdk_enabled()
