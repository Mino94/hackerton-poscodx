"""추진계획서 RAG 지식베이스(Chroma) 사전 구축 — OPENAI_API_KEY 필요."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from autopm.tools.proposal_rag import get_rag_status, get_vector_store  # noqa: E402


def main() -> int:
    status = get_rag_status()
    print("RAG status:", status)
    store, mode = get_vector_store()
    if mode != "chroma":
        print(
            "Chroma 미구축 — OPENAI_API_KEY 설정 후 재실행. "
            "키워드 폴백은 Agent 실행 시 자동 사용됩니다."
        )
        return 0 if mode == "keyword" else 1
    print(f"Chroma ready: {status.get('persist_dir')} ({status.get('doc_count')} docs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
