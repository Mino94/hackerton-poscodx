"""template_manager — 문서 템플릿/섹션 규칙 버전 관리 자리(MVP 스텁)."""

from __future__ import annotations

DOC_TEMPLATE_VERSION = "autopm-v2-16-sections"


def get_template_version() -> str:
    """export·문서화 Agent가 동일한 템플릿 세대를 쓰는지 표시한다."""
    return DOC_TEMPLATE_VERSION
