"""agent_factory — YAML Agent 정의 + LLM으로 CrewAI Agent를 생성한다."""

from __future__ import annotations

from typing import Any

from crewai import Agent, LLM


def build_agent(
    key: str,
    agent_defs: dict[str, Any],
    llm: LLM,
    tools: list[Any] | None = None,
) -> Agent:
    """agents.yaml의 단일 키를 CrewAI Agent로 변환 — Tool은 MVP에서 빈 리스트도 허용한다."""
    spec = agent_defs[key]
    return Agent(
        role=spec["role"],
        goal=spec["goal"].strip(),
        backstory=spec["backstory"].strip(),
        llm=llm,
        tools=tools or [],
        verbose=False,
        allow_delegation=False,
    )


def build_all_agents(agent_defs: dict[str, Any], llm: LLM) -> dict[str, Agent]:
    """7개 전문 Agent를 한 번에 생성 — Supervisor는 YAML에 없고 코드 전용이다."""
    return {key: build_agent(key, agent_defs, llm) for key in agent_defs}
