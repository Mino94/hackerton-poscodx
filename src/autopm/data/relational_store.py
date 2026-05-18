"""relational_store — JSON 파일 기반 메타데이터 스텁."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def save_project_meta(root: Path, meta: dict[str, Any]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "project_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def load_project_meta(root: Path) -> dict[str, Any] | None:
    p = root / "project_meta.json"
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8"))
