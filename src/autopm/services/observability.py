"""observability — LangSmith 등 외부 관측 연동 자리, MVP는 state.logs 적재."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from autopm.orchestration.state import AutoPMState


def log(state: "AutoPMState", message: str) -> None:
    """타임스탬프 로그 — Streamlit/파일 로거로 넘기기 전 1차 저장소."""
    state.logs.append(f"{time.strftime('%H:%M:%S')} | {message}")


def agent_span(state: "AutoPMState", agent: str, phase: str) -> None:
    """Agent 구간 시작 표시 — 추후 OpenTelemetry span으로 치환 가능."""
    log(state, f"[{phase}] start {agent}")


def agent_done(state: "AutoPMState", agent: str, phase: str) -> None:
    log(state, f"[{phase}] done {agent}")


def record_phase_ms(state: "AutoPMState", key: str, seconds: float) -> None:
    """구간 경과 시간을 ms로 누적 저장 — UI에 그대로 노출 가능."""
    state.timings_ms[key] = round(seconds * 1000.0, 2)
    log(state, f"[timing] {key} {state.timings_ms[key]}ms")
