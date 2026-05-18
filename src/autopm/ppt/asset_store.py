"""생성된 시각 자산 경로 관리 — outputs/assets/ 고정."""

from __future__ import annotations

from pathlib import Path


def ensure_assets_dir(project_root: Path) -> Path:
    """슬라이드별 PNG 등을 둘 디렉터리를 보장한다 — 해커톤에서 경로 혼선을 막기 위함."""
    d = project_root / "outputs" / "assets"
    d.mkdir(parents=True, exist_ok=True)
    return d


def asset_path_for_slide(assets_dir: Path, slide_no: int, suffix: str, kind: str) -> Path:
    """일관된 파일명 규칙 — slide_03_process_flow.png 형태."""
    return assets_dir / f"slide_{slide_no:02d}_{kind}.{suffix}"
