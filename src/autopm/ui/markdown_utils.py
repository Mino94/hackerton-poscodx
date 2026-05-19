"""Markdown·JSON 산출물 파싱 — Streamlit 결과 탭에서 공통 사용."""

from __future__ import annotations

import json
import re
from pathlib import Path


def split_numbered_sections(text: str) -> dict[int, str]:
    sections: dict[int, list[str]] = {}
    current: int | None = None
    preamble: list[str] = []

    for line in text.splitlines():
        m = re.match(r"^##\s+(\d+)\.\s+.*$", line)
        if m:
            idx = int(m.group(1))
            current = idx
            sections.setdefault(idx, []).append(line)
            continue
        if current is None:
            preamble.append(line)
        else:
            sections[current].append(line)

    out = {k: "\n".join(v).strip() for k, v in sections.items()}
    if preamble:
        pre = "\n".join(preamble).strip()
        if pre:
            out[0] = pre
    return out


def join_sections(parts: dict[int, str], start: int, end: int) -> str:
    chunks = []
    for i in range(start, end + 1):
        if i in parts:
            chunks.append(parts[i])
    return "\n\n".join(chunks).strip()


def outline_json(text: str) -> str:
    sections = split_numbered_sections(text)
    outline: dict[str, str] = {}
    for num in sorted(k for k in sections if k > 0):
        first = sections[num].splitlines()[0] if sections[num] else ""
        outline[str(num)] = first
    return json.dumps(outline, ensure_ascii=False, indent=2)


def slide_count_from_json(path_str: str | None) -> int | None:
    if not path_str:
        return None
    p = Path(path_str)
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        slides = data.get("slides")
        if isinstance(slides, list):
            return len(slides)
    except (OSError, json.JSONDecodeError):
        return None
    return None
