"""
LangGraph Orchestrator–Worker — Send()로 파이프라인 단계(Worker)를 동적 생성한다.

Orchestrator 노드가 current_idx를 보고 다음 Worker에 Send(task)를 던지고,
Worker 완료 후 다시 Orchestrator로 돌아가 8 Core 단계를 순차 진행한다.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from autopm.orchestration.deep_pipeline import (
    PIPELINE_AGENT_KEYS,
    PIPELINE_KEYS,
    PIPELINE_USER_MSG,
    STATE_FIELDS,
    execute_pipeline_step,
)
from autopm.orchestration.state import AutoPMState
from autopm.orchestration.supervisor_manager import init_supervisor, run_supervisor_checkpoint

# 그래프 실행 중 agent_defs·on_progress 등 비직렬화 컨텍스트
_PIPELINE_CTX: dict[str, Any] = {}


class PipelineGraphState(TypedDict):
    """Orchestrator가 들고 있는 상위 그래프 상태."""

    current_idx: int
    autopm_state: dict[str, Any]
    enriched: dict[str, str]
    feedback_acc: str


class WorkerTaskState(TypedDict):
    """Send(worker, …) 로 동적 생성되는 Worker 입력."""

    idx: int
    autopm_state: dict[str, Any]
    enriched: dict[str, str]
    feedback_acc: str


def _use_send_graph() -> bool:
    return os.getenv("AUTOPM_USE_SEND_GRAPH", "true").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def orchestrator_node(state: PipelineGraphState) -> dict[str, Any]:
    """Supervisor 초기화·체크포인트 — Worker 디스패치는 conditional_edges에서 Send로 처리."""
    ctx = _PIPELINE_CTX
    apm = AutoPMState.model_validate(state["autopm_state"])
    enriched = state["enriched"]
    agent_defs = ctx.get("agent_defs") or {}

    if state["current_idx"] == 0:
        init_supervisor(apm, enriched)
        run_supervisor_checkpoint(
            apm,
            label="graph_start",
            enriched=enriched,
            agent_defs=agent_defs,
        )

    if state["current_idx"] >= len(PIPELINE_KEYS):
        run_supervisor_checkpoint(
            apm,
            label="graph_core_complete",
            enriched=enriched,
            agent_defs=agent_defs,
        )

    return {"autopm_state": apm.model_dump()}


def dispatch_workers(state: PipelineGraphState) -> list[Send] | str:
    """다음 파이프라인 단계 Worker를 Send()로 생성 — 끝이면 END."""
    idx = state["current_idx"]
    if idx >= len(PIPELINE_KEYS):
        return END
    return [
        Send(
            "worker",
            {
                "idx": idx,
                "autopm_state": state["autopm_state"],
                "enriched": state["enriched"],
                "feedback_acc": state["feedback_acc"],
            },
        )
    ]


def worker_node(task: WorkerTaskState) -> dict[str, Any]:
    """동적 Worker 1건 — Core PM Agent + 대화 + Supervisor complete."""
    ctx = _PIPELINE_CTX
    apm = AutoPMState.model_validate(task["autopm_state"])
    idx = task["idx"]
    enriched = task["enriched"]
    feedback_acc = task["feedback_acc"]
    on_progress: Callable[[str], None] | None = ctx.get("on_progress")

    new_feedback = execute_pipeline_step(
        apm,
        idx,
        ctx["agent_defs"],
        ctx["task_defs"],
        enriched,
        feedback_acc,
        on_progress=on_progress,
    )

    return {
        "autopm_state": apm.model_dump(),
        "current_idx": idx + 1,
        "feedback_acc": new_feedback,
    }


def build_pipeline_orchestrator_graph():
    """Orchestrator ↔ Worker(Send) 루프 그래프 컴파일."""
    builder = StateGraph(PipelineGraphState)
    builder.add_node("orchestrator", orchestrator_node)
    builder.add_node("worker", worker_node)
    builder.add_edge(START, "orchestrator")
    builder.add_conditional_edges("orchestrator", dispatch_workers, ["worker", END])
    builder.add_edge("worker", "orchestrator")
    return builder.compile()


_COMPILED_GRAPH = None


def get_compiled_graph():
    global _COMPILED_GRAPH
    if _COMPILED_GRAPH is None:
        _COMPILED_GRAPH = build_pipeline_orchestrator_graph()
    return _COMPILED_GRAPH


def run_deep_pipeline_graph(
    state: AutoPMState,
    agent_defs: dict[str, Any],
    task_defs: dict[str, Any],
    enriched: dict[str, str],
    on_progress: Callable[[str], None] | None,
) -> None:
    """Send() 기반 Orchestrator–Worker로 8 Core 파이프라인 실행."""
    _PIPELINE_CTX.clear()
    _PIPELINE_CTX["agent_defs"] = agent_defs
    _PIPELINE_CTX["task_defs"] = task_defs
    _PIPELINE_CTX["on_progress"] = on_progress

    if on_progress:
        on_progress("[Orchestrator] LangGraph Send() — Worker 동적 생성 시작")

    initial: PipelineGraphState = {
        "current_idx": 0,
        "autopm_state": state.model_dump(),
        "enriched": dict(enriched),
        "feedback_acc": enriched.get("feedback_block", "") or "",
    }

    final = get_compiled_graph().invoke(initial)
    updated = AutoPMState.model_validate(final["autopm_state"])
    _copy_autopm_state(state, updated)

    if on_progress:
        on_progress(
            f"[Orchestrator] Core {len(PIPELINE_KEYS)}단계 Worker 완료 "
            f"(Send dispatch × {len(PIPELINE_KEYS)})"
        )


def _copy_autopm_state(target: AutoPMState, source: AutoPMState) -> None:
    """그래프 결과를 기존 state 객체에 반영 — flow.py 참조 유지."""
    for name in source.model_fields:
        setattr(target, name, getattr(source, name))


__all__ = [
    "PipelineGraphState",
    "WorkerTaskState",
    "build_pipeline_orchestrator_graph",
    "dispatch_workers",
    "run_deep_pipeline_graph",
    "_use_send_graph",
]
