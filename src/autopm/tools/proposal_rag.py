"""추진계획서 표준 지식베이스 — Chroma 벡터 RAG + 키워드 폴백."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from autopm.knowledge.proposal_kb_docs import PROPOSAL_KB_DOCUMENTS

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_PERSIST = _PROJECT_ROOT / "data" / "chroma_autopm"

_vector_store: Any | None = None
_vector_store_mode: str = "none"  # chroma | keyword
_keyword_chunks: list[tuple[str, str]] | None = None  # (source, text)


def is_chroma_rag_enabled() -> bool:
    load_dotenv()
    return os.getenv("AUTOPM_USE_CHROMA_RAG", "true").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _persist_dir() -> Path:
    load_dotenv()
    raw = os.getenv("CHROMA_PERSIST_DIR", "").strip()
    return Path(raw) if raw else _DEFAULT_PERSIST


def _collection_name() -> str:
    load_dotenv()
    return os.getenv("AUTOPM_RAG_COLLECTION", "autopm_kb").strip() or "autopm_kb"


def _get_embeddings() -> Any | None:
    """OpenAI 임베딩 — API Key 없으면 None. POSCO 게이트웨이 base_url 동일 적용."""
    from autopm.services.llm_router import get_openai_api_key, get_openai_base_url

    load_dotenv()
    if not get_openai_api_key():
        return None
    try:
        from langchain_openai import OpenAIEmbeddings

        model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small").strip()
        kwargs: dict[str, Any] = {"model": model, "api_key": get_openai_api_key()}
        base = get_openai_base_url()
        if base:
            kwargs["base_url"] = base
        return OpenAIEmbeddings(**kwargs)
    except Exception:
        return None


def _build_keyword_chunks() -> list[tuple[str, str]]:
    global _keyword_chunks
    if _keyword_chunks is not None:
        return _keyword_chunks
    out: list[tuple[str, str]] = []
    for doc in PROPOSAL_KB_DOCUMENTS:
        src = str((doc.metadata or {}).get("source", "kb"))
        out.append((src, doc.page_content))
    _keyword_chunks = out
    return out


def _keyword_similarity_search(query: str, k: int = 4) -> list[tuple[str, str]]:
    """임베딩 없이 토큰 매칭 점수로 상위 k개 청크 반환."""
    qtok = {t for t in query.lower().replace(",", " ").split() if len(t) > 1}
    if not qtok:
        qtok = set(query.lower().split())
    scored: list[tuple[int, str, str]] = []
    for src, text in _build_keyword_chunks():
        low = text.lower()
        score = sum(1 for t in qtok if t in low)
        if score > 0:
            scored.append((score, src, text))
    scored.sort(key=lambda x: -x[0])
    if not scored:
        # 매칭 없으면 표준 양식·AS-IS·WBS·ROI 가이드 우선 노출
        preferred = ("STANDARD-001", "GUIDE-002", "GUIDE-004", "GUIDE-005", "GUIDE-006")
        for pref in preferred:
            for src, text in _build_keyword_chunks():
                if pref in src:
                    scored.append((1, src, text))
        scored = scored[:k]
    return [(s, t) for _, s, t in scored[:k]]


def _init_chroma_store() -> Any | None:
    """Chroma 영속 저장소 로드 또는 생성."""
    embeddings = _get_embeddings()
    if embeddings is None:
        return None
    try:
        from langchain_chroma import Chroma
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        persist = _persist_dir()
        persist.mkdir(parents=True, exist_ok=True)
        collection = _collection_name()

        # 기존 DB가 있으면 로드
        if (persist / "chroma.sqlite3").is_file() or any(persist.iterdir()):
            try:
                return Chroma(
                    collection_name=collection,
                    embedding_function=embeddings,
                    persist_directory=str(persist),
                )
            except Exception:
                pass

        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        splits = splitter.split_documents(PROPOSAL_KB_DOCUMENTS)
        store = Chroma.from_documents(
            splits,
            embedding=embeddings,
            collection_name=collection,
            persist_directory=str(persist),
        )
        return store
    except Exception:
        return None


def get_vector_store() -> tuple[Any | None, str]:
    """
    싱글톤 벡터 스토어.
    반환: (store_or_none, mode) — mode는 chroma | keyword
    """
    global _vector_store, _vector_store_mode
    if _vector_store is not None:
        return _vector_store, _vector_store_mode

    if is_chroma_rag_enabled():
        chroma = _init_chroma_store()
        if chroma is not None:
            _vector_store = chroma
            _vector_store_mode = "chroma"
            return _vector_store, _vector_store_mode

    _vector_store = _build_keyword_chunks()
    _vector_store_mode = "keyword"
    return _vector_store, _vector_store_mode


def retrieve_reference_context(query: str, k: int = 4) -> str:
    """
    사내 표준·가이드 RAG 검색 — Agent/MCP 공용.
    Chroma similarity_search 실패 시 키워드 폴백.
    """
    q = (query or "").strip()
    if not q:
        q = "추진계획서 표준 양식 AS-IS TO-BE WBS ROI 리스크"

    store, mode = get_vector_store()
    if mode == "chroma" and store is not None:
        try:
            results = store.similarity_search(q, k=k)
            if results:
                return "\n\n".join(
                    f"[{d.metadata.get('source', 'kb')}] {d.page_content}"
                    for d in results
                )
        except Exception:
            pass

    parts = [
        f"[{src}] {text[:1200]}"
        for src, text in _keyword_similarity_search(q, k=k)
    ]
    if not parts:
        return "(RAG) 추진계획서 지식베이스 매칭 없음 — 표준 9개 섹션 구조를 따르세요."
    return "\n\n".join(parts)


def build_multi_topic_rag_block(context: dict[str, str], *, k_per_topic: int = 2) -> str:
    """
    주제별 RAG 쿼리를 합쳐 Agent 프롬프트용 블록 생성 — 품질 향상용.
    """
    title = (
        context.get("proposal_title")
        or context.get("idea_title")
        or context.get("user_topic")
        or ""
    )
    problems = context.get("current_problems") or context.get("pain_points") or ""
    base = f"{title} {problems}".strip()

    topics = [
        ("표준 양식 Executive Summary", f"{base} 추진계획서 표준 양식 9개 섹션"),
        ("AS-IS 분석", f"{base} AS-IS Pain Point 정량 지표"),
        ("TO-BE 개선", f"{base} TO-BE 자동화 기술 스택"),
        ("WBS 일정", f"{base} WBS 마일스톤 14주"),
        ("예산 ROI", f"{base} ROI KPI 예상 가정"),
        ("리스크", f"{base} 리스크 매트릭스 ERP"),
    ]
    sections: list[str] = ["## 사내 추진계획서 RAG 참고 (Chroma/키워드)"]
    for label, query in topics:
        ctx = retrieve_reference_context(query, k=k_per_topic)
        sections.append(f"### {label}\n{ctx[:2200]}")
    return "\n\n".join(sections) + "\n"


def get_rag_status() -> dict[str, Any]:
    """Streamlit·디버그용."""
    store, mode = get_vector_store()
    n_docs = len(PROPOSAL_KB_DOCUMENTS)
    return {
        "enabled": True,
        "mode": mode,
        "doc_count": n_docs,
        "chroma_enabled": is_chroma_rag_enabled(),
        "openai_embeddings": _get_embeddings() is not None,
        "persist_dir": str(_persist_dir()),
        "collection": _collection_name(),
        "store_ready": store is not None,
    }
