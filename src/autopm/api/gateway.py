"""gateway — Streamlit이 직접 부르는 어댑터, 이후 FastAPI가 동일 진입점을 재사용."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import TYPE_CHECKING

from autopm.api.rate_limiter import InMemoryRateLimiter

if TYPE_CHECKING:
    from autopm.run_result import AutoPMRunResult

# 프로세스당 단일 RateLimiter — 매 요청마다 새 인스턴스를 만들면 카운터가 리셋되어 한도가 무력화된다.
_rl_n: int | None = None
_rl: InMemoryRateLimiter | None = None


def _rate_allow(client_id: str, max_per_minute: int) -> bool:
    global _rl_n, _rl
    if _rl is None or _rl_n != max_per_minute:
        _rl_n = max_per_minute
        _rl = InMemoryRateLimiter(max_per_minute=max_per_minute)
    return _rl.allow(client_id)


def run_generation_job(
    inputs: dict[str, str],
    *,
    on_progress: Callable[[str], None] | None = None,
    user_token: str | None = None,
    client_id: str = "default",
    phased: str | None = None,
    autopm_state_json: dict | None = None,
    ppt_gen_json: dict | None = None,
) -> "AutoPMRunResult":
    """Streamlit·향후 FastAPI가 동일하게 호출 — L2에서 인증/한도 후 L3로 넘기는 형태로 확장한다."""
    _ = user_token  # 향후 SSO 연동 시 사용
    raw = os.getenv("AUTOPM_RATE_LIMIT_PER_MIN", "").strip()
    if raw:
        try:
            n = int(raw)
            if n > 0 and not _rate_allow(client_id, n):
                from autopm.orchestration.flow import AutoPMFlow

                return AutoPMFlow().rate_limit_result(inputs)
        except ValueError:
            pass

    from autopm.orchestration.supervisor import Supervisor

    return Supervisor().execute(
        inputs,
        on_progress=on_progress,
        phased=phased,
        autopm_state_json=autopm_state_json,
        ppt_gen_json=ppt_gen_json,
    )
