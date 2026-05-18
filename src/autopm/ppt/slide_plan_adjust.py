"""스토리라인 JSON의 슬라이드 수를 사용자 선택(6/10/12)에 맞게 조정한다."""

from __future__ import annotations

import json
from typing import Any

from autopm.ppt.deck_json import extract_json_object


def adjust_storyline_slide_count(storyline_text: str, target: int) -> str:
    """LLM 스토리라인 출력 문자열에서 slides 배열 길이를 target에 맞춘다 — MVP는 자르기·패딩만."""
    data = extract_json_object(storyline_text) or {}
    slides: list[dict[str, Any]] = []
    raw_slides = data.get("slides")
    if isinstance(raw_slides, list):
        for s in raw_slides:
            if isinstance(s, dict):
                slides.append(dict(s))

    target = max(3, min(24, int(target)))
    if len(slides) > target:
        slides = slides[:target]
    elif len(slides) < target:
        n0 = len(slides)
        for i in range(n0, target):
            slides.append(
                {
                    "slide_no": i + 1,
                    "title": f"보강 슬라이드 {i + 1}",
                    "objective": "사용자 선택(간략/상세)에 따른 자동 패딩 — 내용은 Composer에서 다듬는다.",
                    "key_message": "추가 메시지 placeholder",
                    "layout_type": "blank",
                    "visual_type": "summary_cards",
                    "content": {},
                }
            )
    for idx, s in enumerate(slides, start=1):
        s["slide_no"] = idx
    data["slides"] = slides
    return json.dumps(data, ensure_ascii=False, indent=2)
