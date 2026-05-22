"""vector_store — proposal_rag Chroma/키워드 검색 위임."""

from __future__ import annotations

from pathlib import Path


def search_stub(query: str, base: Path) -> list[str]:
    """레거시 호환 — RAG 검색 결과를 줄 단위 리스트로."""
    try:
        from autopm.tools.proposal_rag import retrieve_reference_context

        text = retrieve_reference_context(query, k=4)
        return [ln for ln in text.splitlines() if ln.strip()]
    except Exception:
        if not base.is_dir():
            return []
        return [str(p) for p in base.glob("**/*.md") if query.lower() in p.name.lower()]
