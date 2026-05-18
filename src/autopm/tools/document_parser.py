"""document_parser — PDF/HWP/Word 확장 전, MVP는 txt/md 및 샘플 파서."""

from __future__ import annotations

from pathlib import Path


def parse_text_file(path: Path) -> str:
    """로컬 텍스트/마크다운 파일을 읽는다 — 향후 바이너리 포맷 파서의 진입점."""
    return path.read_text(encoding="utf-8", errors="replace")


def parse_paste_text(raw: str) -> str:
    """사용자가 붙여 넣은 문자열을 전처리한다 — 공백 정규화만 수행해도 충분하다."""
    return "\n".join(line.rstrip() for line in raw.strip().splitlines()).strip()


def sample_parse_for_demo(title: str, process: str, pain: str) -> str:
    """데모용 초간단 구조화 — 실제 RFP 파서 전 단계의 자리 표시자."""
    return f"[parsed] 제목={title[:80]} | 업무={process[:120]} | 문제={pain[:120]}"
