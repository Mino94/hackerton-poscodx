"""입력·JSON·슬라이드·PPT 파일 존재 검증 — harness 점수 전 단계에서 재사용한다."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# python-pptx는 선택적 import — 없으면 파일 크기/zip 헤더로 대체한다.
try:
    from pptx import Presentation
except Exception:  # noqa: BLE001
    Presentation = None  # type: ignore[misc, assignment]

_RE_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def extract_json_object(raw: str) -> dict[str, Any] | None:
    """LLM 응답에서 첫 JSON 객체를 추출한다 — slide_plan/visual_plan 파싱용."""
    if not raw or not raw.strip():
        return None
    cand = raw.strip()
    m = _RE_JSON_FENCE.search(cand)
    if m:
        cand = m.group(1).strip()
    try:
        obj = json.loads(cand)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    start = cand.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(cand)):
        if cand[i] == "{":
            depth += 1
        elif cand[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(cand[start : i + 1])
                    return obj if isinstance(obj, dict) else None
                except json.JSONDecodeError:
                    return None
    return None


def validate_interview_inputs(inputs: dict[str, str]) -> tuple[bool, list[str]]:
    """인터뷰 완료 후 필수 키 충분성 검사 — 최소 제목·현황·문제·목표(InterviewState는 goals 키를 쓴다)."""
    req = (
        "proposal_title",
        "proposal_purpose",
        "background_context",
        "current_problems",
    )
    missing = [k for k in req if not str(inputs.get(k, "")).strip()]
    return (len(missing) == 0, missing)


def validate_slide_deck_json(obj: dict[str, Any] | None) -> tuple[bool, list[str]]:
    """slide_deck / storyline JSON 최소 구조."""
    errs: list[str] = []
    if not obj:
        return False, ["json_empty"]
    slides = obj.get("slides")
    if not isinstance(slides, list):
        return False, ["slides_not_list"]
    if len(slides) < 10:
        errs.append("slides_lt_10")
    for i, s in enumerate(slides[:20]):
        if not isinstance(s, dict):
            errs.append(f"slide_{i}_not_dict")
            continue
        for f in ("title", "key_message", "objective"):
            if not str(s.get(f, "")).strip():
                errs.append(f"slide_{i}_missing_{f}")
    return (len(errs) == 0, errs)


def validate_visual_plan_json(obj: dict[str, Any] | None, slide_count: int) -> tuple[bool, list[str]]:
    errs: list[str] = []
    if not obj:
        return False, ["visual_json_empty"]
    per = obj.get("per_slide")
    if not isinstance(per, list):
        return False, ["per_slide_not_list"]
    if slide_count and len(per) < slide_count:
        errs.append("per_slide_short")
    for i, row in enumerate(per[:slide_count or len(per)]):
        if not isinstance(row, dict):
            errs.append(f"vs_{i}_bad")
            continue
        vt = str(row.get("visual_type", "")).strip()
        if not vt:
            errs.append(f"vs_{i}_no_visual_type")
    return (len(errs) == 0, errs)


def validate_graphics_json(obj: dict[str, Any] | None) -> tuple[bool, list[str]]:
    if not obj:
        return False, ["graphics_empty"]
    spec = obj.get("graphics_spec")
    if not isinstance(spec, list):
        return False, ["graphics_spec_not_list"]
    if len(spec) < 1:
        return False, ["graphics_spec_empty"]
    return (True, [])


def validate_pptx_file(path: Path | None) -> tuple[bool, int, list[str]]:
    """PPT 파일 존재 및 슬라이드 수(가능 시) — composer 검증."""
    errs: list[str] = []
    if not path or not path.is_file():
        return False, 0, ["pptx_missing"]
    n = 0
    if Presentation is not None:
        try:
            prs = Presentation(str(path))
            n = len(prs.slides)
        except Exception as exc:  # noqa: BLE001
            errs.append(f"pptx_read_error:{exc}")
            n = 0
    else:
        # python-pptx 미설치 시 파일 크기만으로 존재 확인 — 슬라이드 수는 알 수 없음(-1).
        n = -1
    if n == 0:
        errs.append("slide_count_zero")
    elif n > 0 and n < 10:
        errs.append("slides_lt_10")
    ok = not errs or (n == -1 and path.stat().st_size > 512)
    return (ok, n, errs)


def output_file_exists(root: Path, rel: str) -> bool:
    """outputs 상대 경로 존재 — 리포트용."""
    return (root / rel).is_file()
