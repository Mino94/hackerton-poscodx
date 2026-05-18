"""rag_engine — 조직 지식 RAG 자리, MVP는 키워드 + 로컬 템플릿 검색."""

from __future__ import annotations

from pathlib import Path


def keyword_search(query: str, knowledge_path: Path, max_lines: int = 40) -> str:
    """sample_project_template.md에서 토큰 매칭 줄만 뽑는 초간단 RAG — 데모 안정용."""
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
