"""logger — MVP는 표준 로깅 래퍼, 향후 구조화 로그로 확장."""

from __future__ import annotations

import logging

_logger = logging.getLogger("autopm")
if not _logger.handlers:
    logging.basicConfig(level=logging.INFO)


def get_logger(name: str | None = None) -> logging.Logger:
    return logging.getLogger(name or "autopm")
