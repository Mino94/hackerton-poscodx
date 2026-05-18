"""cache_store — 세션/중간 산출물 캐시 스텁."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from autopm.orchestration.state import AutoPMState


class JsonFileCache:
    """간단한 파일 캐시 — Redis 전환 시 인터페이스만 유지하면 된다."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def get(self, key: str) -> Any | None:
        if not self.path.is_file():
            return None
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return data.get(key)

    def set(self, key: str, value: Any) -> None:
        data: dict[str, Any] = {}
        if self.path.is_file():
            data = json.loads(self.path.read_text(encoding="utf-8"))
        data[key] = value
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def save_autopm_checkpoint(project_root: Path, tag: str, state: "AutoPMState") -> Path | None:
    """파이프라인 중간/완료 스냅샷 — 장애 시 재시작 훅을 남기기 위한 MVP용 저장."""
    try:
        out = project_root / "outputs" / ".cache" / f"{tag}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(state.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return out
    except OSError:
        return None
