"""Deep Agents SDK 단위 검증 — pytest 없이 실행."""

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
    run_task_via_deep_agent_or_fallback,
)
from autopm.services.prompt_manager import load_tasks
from langchain_core.messages import AIMessage, ToolMessage


def main() -> int:
    _ensure_autopm_harness_profiles()
    agent_defs = build_all_agent_defs()
    ctx = {"proposal_title": "ERP", "idea_title": "ERP"}
    subs = _build_subagents_from_yaml("pm_orchestrator_agent", agent_defs, ctx)
    assert len(subs) >= 3, subs

    chain = [{"id": "gap_finder", "role": "r", "llm_tier": "local"}]
    msgs = [
        AIMessage(
            content="",
            tool_calls=[
                {"name": "task", "args": {"subagent_type": "gap_finder", "description": "x"}, "id": "tc1"}
            ],
        ),
        ToolMessage(content="ok", name="task", tool_call_id="tc1"),
    ]
    assert len(_parse_subagent_records(msgs, chain)) == 1

    text, prov, _ = run_task_via_deep_agent_or_fallback(
        "requirement_interview_agent",
        agent_defs,
        load_tasks(),
        "requirement_task",
        {**ctx, "current_process": "a", "pain_points": "b"},
        use_subagents=True,
    )
    assert len(text) > 10, (text, prov)
    print("deep_agent_sdk unit checks OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
