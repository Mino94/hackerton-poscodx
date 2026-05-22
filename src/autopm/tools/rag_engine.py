"""rag_engine — Chroma RAG(권장) + 레거시 키워드·템플릿 검색."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


def keyword_search(query: str, knowledge_path: Path, max_lines: int = 40) -> str:
    """sample_project_template.md 키워드 검색 — 최후 폴백."""
    if not knowledge_path.is_file():
        return "(RAG) knowledge 파일 없음"
    text = knowledge_path.read_text(encoding="utf-8", errors="replace")
    qtok = {t for t in query.lower().replace(",", " ").split() if len(t) > 1}
    picked: list[str] = []
    for line in text.splitlines():
        low = line.lower()
        if any(t in low for t in qtok):
            picked.append(line)
        if len(picked) >= max_lines:
            break
    if not picked:
        return "(RAG) 매칭 줄 없음 — 템플릿 전체를 참고하세요."
    return "\n".join(picked)


def retrieve_context(query: str, knowledge_path: Path | None = None, *, k: int = 4) -> str:
    """
    추진계획서 지식 검색 — proposal_rag(Chroma/키워드) 우선, 실패 시 템플릿 md.
    """
    try:
        from autopm.tools.proposal_rag import retrieve_reference_context

        return retrieve_reference_context(query, k=k)
    except Exception:
        pass
    if knowledge_path and knowledge_path.is_file():
        return keyword_search(query, knowledge_path)
    return "(RAG) 지식베이스를 사용할 수 없습니다."


def is_rag_quality_pipeline_enabled() -> bool:
    """S01~S10 LLM 파이프라인 — API 있을 때 품질 강화."""
    load_dotenv()
    if os.getenv("AUTOPM_RAG_QUALITY_PIPELINE", "false").strip().lower() not in (
        "1",
        "true",
        "yes",
        "on",
    ):
        return False
    from autopm.services.llm_router import get_langchain_chat_model_or_none

    return get_langchain_chat_model_or_none() is not None
