"""vector_store — 로컬 지식 검색 스텁."""

from __future__ import annotations

from pathlib import Path


def search_stub(query: str, base: Path) -> list[str]:
    """파일 목록만 반환 — 향후 임베딩 검색으로 교체."""
    if not base.is_dir():
        return []
    return [str(p) for p in base.glob("**/*.md") if query.lower() in p.name.lower()]
