"""agent_factory — agents.yaml 정의 로드(Deep Agents는 deep_runner가 직접 호출)."""

from __future__ import annotations

from typing import Any

from autopm.services.prompt_manager import load_agents


def build_all_agent_defs() -> dict[str, Any]:
    """YAML Agent 정의 전체 — CrewAI Agent 객체 대신 스펙 dict만 반환한다."""
    return load_agents()


__all__ = ["build_all_agent_defs"]
