"""llm_router — OpenAI(CrewAI)와 mock/ollama 초안·refine을 한곳에서 분기한다."""

from __future__ import annotations

import json
import os
from typing import Any

from crewai import LLM
from dotenv import load_dotenv


def get_openai_llm_or_none() -> LLM | None:
    """API Key가 없으면 None — CrewAI 상위에서 fallback 분기."""
    load_dotenv()
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        return None
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
    return LLM(model=model, temperature=0.2)


def _mock_draft_markdown(inputs: dict[str, str]) -> str:
    """API·로컬 LLM 없이도 데모 가능한 템플릿 초안 — Crew seed용."""
    title = inputs.get("proposal_title") or inputs.get("idea_title", "")
    return f"""# 추진계획 초안 (Mock / local_open_source)

## 한 줄 요약
- 제목/주제: **{title}**
- 목적: {inputs.get("proposal_purpose", "")}
- 배경: {inputs.get("background_context", "")}
- 개선 방향: {inputs.get("improvement_direction", "")} / 강조: {inputs.get("key_emphasis", "")}
- 보고 대상: {inputs.get("target_audience", "")} / PPT 톤: {inputs.get("presentation_tone", "")}
- 일정: {inputs.get("timeline") or inputs.get("target_timeline", "")} / 예산: {inputs.get("budget_range", "")}

## AS-IS·현황 (인터뷰 기반)
{inputs.get("current_process", "(미입력)")}

## 문제·Pain
{inputs.get("current_problems") or inputs.get("pain_points", "(미입력)")}

## 대상 시스템·범위
- 시스템: {inputs.get("target_system", "")}
- 범위: {inputs.get("business_scope", "")}

## 이해관계자
- 관련 부서: {inputs.get("related_departments") or inputs.get("departments", "")}
- 월간 투입: 약 {inputs.get("monthly_hours", "?")}h / {inputs.get("headcount", "?")}명

## 다음 액션(가정)
1) 범위·RACI 확정
2) 파일럿 데이터·보안 합의
3) 4주 내 검증 리포트
"""


def _ollama_generate(prompt: str) -> str | None:
    """Ollama HTTP API — 설치·실행 중일 때만 성공."""
    try:
        import urllib.error
        import urllib.request

        host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
        model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b").strip()
        body = json.dumps(
            {"model": model, "prompt": prompt, "stream": False},
            ensure_ascii=False,
        ).encode("utf-8")
        req = urllib.request.Request(
            f"{host}/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        return (raw.get("response") or "").strip() or None
    except Exception:
        return None


def generate_draft_with_open_source_llm(inputs: dict[str, str]) -> tuple[str, str]:
    """
    1차 초안: ollama → 실패 시 mock.
    반환: (markdown, provider_used)
    """
    load_dotenv()
    provider = os.getenv("OPEN_SOURCE_LLM_PROVIDER", "mock").strip().lower()
    prompt = (
        "다음은 추진계획서 주제·제목과 인터뷰 맥락이다. 한국어로 간단한 추진계획 초안을 Markdown 불릿으로 작성하라. "
        "비기술 경영진이 읽기 쉬운 톤으로, 목적·배경·문제·개선 방향이 드러나게 하라.\n\n"
        f"{json.dumps(inputs, ensure_ascii=False, indent=2)}"
    )

    if provider == "ollama" or provider == "ollama_optional":
        out = _ollama_generate(prompt)
        if out:
            return out, "ollama"

    if provider == "local_open_source":
        out = _ollama_generate(prompt)
        if out:
            return out, "ollama"

    return _mock_draft_markdown(inputs), "mock"


def refine_with_openai(draft: str, inputs: dict[str, str]) -> str | None:
    """OpenAI Chat Completions로 초안 정제 — 키 없으면 None."""
    load_dotenv()
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        return None
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
    try:
        from openai import OpenAI

        client = OpenAI(api_key=key)
        sys_msg = (
            "당신은 PMO 전문가다. 주어진 초안을 한국어 Markdown으로 다듬되, "
            "새로운 환각 수치를 만들지 말고 입력의 가정을 유지하라."
        )
        user_msg = f"[입력]\n{json.dumps(inputs, ensure_ascii=False, indent=2)}\n\n[초안]\n{draft[:12000]}"
        r = client.chat.completions.create(
            model=model,
            temperature=0.2,
            messages=[
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": user_msg},
            ],
        )
        choice = r.choices[0].message.content
        return (choice or "").strip() or None
    except Exception:
        return None


def refine_draft_for_user_choice(
    draft: str,
    inputs: dict[str, str],
    choice: str,
    extra_user_text: str = "",
) -> str:
    """
    Decision Point 2 — 사용자 톤 선택을 초안 Markdown에 반영한다.
    API Key가 없으면 톤 지시문을 붙인 형태로 데모를 유지한다.
    """
    choice = (choice or "proceed").strip()
    extra = (extra_user_text or "").strip()
    if choice == "proceed" and not extra:
        return draft

    guides = {
        "tone_pro": "전문 PMO·추진계획서 톤으로 다듬고, 섹션 구조는 유지하라.",
        "tone_concise": "불필요한 수식어를 줄이고 핵심 bullet 위주로 간결하게 하라.",
        "tone_exec": "경영진 보고용: 결론·요청·리스크·수치(가정)를 앞에 두어라.",
        "tone_custom": (extra or "사용자 요청을 반영해 초안을 수정하라."),
    }
    guide = guides.get(choice, guides["tone_custom"] if choice == "tone_custom" else "사용자 선택에 맞게 다듬어라.")
    if choice == "tone_custom" and extra:
        guide = extra

    load_dotenv()
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        return (
            f"{draft.rstrip()}\n\n---\n### 톤 조정 적용(API 없음 — 수동 반영용 메모)\n{guide}\n{extra}\n"
        )

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
    try:
        from openai import OpenAI

        client = OpenAI(api_key=key)
        sys_msg = (
            "당신은 PMO다. 주어진 초안을 한국어 Markdown으로 수정하라. "
            "새로운 환각 수치를 만들지 말 것. 지시: " + guide
        )
        user_msg = f"[컨텍스트]\n{json.dumps(inputs, ensure_ascii=False, indent=2)[:8000]}\n\n[초안]\n{draft[:12000]}"
        if extra and choice != "tone_custom":
            user_msg += f"\n\n[추가 요청]\n{extra}"
        r = client.chat.completions.create(
            model=model,
            temperature=0.25,
            messages=[
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": user_msg},
            ],
        )
        out = (r.choices[0].message.content or "").strip()
        return out or draft
    except Exception:
        return draft + f"\n\n### (OpenAI 톤 조정 실패 — 원문 유지)\n{guide}\n"


def generate_with_best_available_model(inputs: dict[str, str]) -> dict[str, Any]:
    """
    mock/ollama 초안 → (가능하면) OpenAI refine.
    어떤 단계도 예외로 전체 실행을 죽이지 않는다.
    """
    draft, prov = generate_draft_with_open_source_llm(inputs)
    refined: str | None = None
    try:
        refined = refine_with_openai(draft, inputs)
    except Exception:
        refined = None
    return {
        "draft_markdown": draft,
        "refined_markdown": refined,
        "provider_used": prov,
        "refined_with_openai": bool(refined),
    }


__all__ = [
    "get_openai_llm_or_none",
    "generate_draft_with_open_source_llm",
    "refine_with_openai",
    "refine_draft_for_user_choice",
    "generate_with_best_available_model",
]
