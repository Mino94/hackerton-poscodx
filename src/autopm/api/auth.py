"""auth — FastAPI/OAuth 전 스텁."""

from __future__ import annotations


def ensure_request_allowed(user_token: str | None) -> bool:
    """MVP는 항상 허용 — 실서비스에서는 JWT/SSO 검증으로 교체."""
    return True
