"""보고용 PPT 색상 상수 — AGENTS.md(짙은 남색 제목·회색 보조)를 단순 RGB로 표현한다."""

from __future__ import annotations

from pptx.dml.color import RGBColor

# 업무 보고용 톤 — 완벽한 디자인보다 가독성 우선
TITLE_RGB: RGBColor = RGBColor(0x1A, 0x2B, 0x4A)
SUBTITLE_RGB: RGBColor = RGBColor(0x44, 0x44, 0x44)
BODY_RGB: RGBColor = RGBColor(0x33, 0x33, 0x33)
KEY_MSG_RGB: RGBColor = RGBColor(0x0D, 0x47, 0xA1)
CARD_FILL: RGBColor = RGBColor(0xF5, 0xF7, 0xFA)
ACCENT: RGBColor = RGBColor(0x15, 0x65, 0xC0)
# 키 메시지 밴드·좌측 악센트 — 가독성용 보조색(너무 튀지 않게).
KEY_BAND_FILL: RGBColor = RGBColor(0xE8, 0xF4, 0xFC)
ACCENT_MUTED: RGBColor = RGBColor(0x8F, 0xAE, 0xD9)
