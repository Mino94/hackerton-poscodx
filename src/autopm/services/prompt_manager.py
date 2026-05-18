"""prompt_manager — 향후 프롬프트 버전관리/실험 분기의 단일 진입점."""

from __future__ import annotations

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
