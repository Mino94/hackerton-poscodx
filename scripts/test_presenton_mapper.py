"""Presenton 슬라이드 매핑 단위 테스트 — HTTP 없이 실행."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from autopm.services.presenton_export import (  # noqa: E402
    deck_dict_to_slides_markdown,
    prefer_composer_deck,
)


def main() -> int:
    deck = {
        "project_title": "ERP 검증",
        "slides": [
            {
                "slide_no": 1,
                "title": "Executive Summary",
                "key_message": "월마감 검증 자동화",
                "content": {"bullets": ["40시간→12시간", "오류 사전 탐지"]},
            },
        ],
    }
    composer = '{"slides":[{"slide_no":2,"title":"AS-IS","key_message":"수작업"}]}'
    merged = prefer_composer_deck(deck, composer)
    assert len(merged["slides"]) == 1
    assert merged["slides"][0]["title"] == "AS-IS"

    md_list = deck_dict_to_slides_markdown(deck)
    assert len(md_list) == 1
    assert "Executive Summary" in md_list[0]
    assert "40시간" in md_list[0]
    print("presenton_mapper: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
