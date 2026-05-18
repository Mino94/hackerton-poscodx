"""object_storage — outputs/ 디렉터리에 산출물을 둔다."""

from __future__ import annotations

from pathlib import Path


def outputs_dir(project_root: Path) -> Path:
    d = project_root / "outputs"
    d.mkdir(parents=True, exist_ok=True)
    return d
