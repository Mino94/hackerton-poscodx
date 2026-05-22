"""llm_router — OpenAI(LangChain/Deep Agents)와 mock/ollama 초안·refine을 한곳에서 분기한다."""

from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv


def get_langchain_chat_model_or_none() -> Any | None:
    """API Key가 없으면 None — Deep Agent 파이프라인에서 fallback 분기."""
    load_dotenv()
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        return None
    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
    try:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=model_name, temperature=0.2)
    except Exception:
        return None


def get_openai_llm_or_none() -> Any | None:
    """레거시 import 호환 — CrewAI LLM 대신 LangChain ChatOpenAI를 반환한다."""
    return get_langchain_chat_model_or_none()


_ollama_model_cache: Any | None = None


def is_local_llm_enabled() -> bool:
    """Sub-Agent·로컬 초안에 Ollama를 쓸지 여부 — .env OPEN_SOURCE_LLM_PROVIDER / AUTOPM_USE_LOCAL_LLM."""
    load_dotenv()
    if os.getenv("AUTOPM_USE_LOCAL_LLM", "").strip().lower() in ("1", "true", "yes", "on"):
        return True
    prov = os.getenv("OPEN_SOURCE_LLM_PROVIDER", "mock").strip().lower()
    return prov in ("ollama", "ollama_optional", "local_open_source")


def get_ollama_chat_model_or_none() -> Any | None:
    """LangChain ChatOllama — Sub-Agent·로컬 tier용. Ollama 미실행 시 None."""
    global _ollama_model_cache
    if _ollama_model_cache is not None:
        return _ollama_model_cache
    if not is_local_llm_enabled():
        return None
    load_dotenv()
    host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    model_name = os.getenv("OLLAMA_MODEL", "qwen2.5:7b").strip()
    try:
        from langchain_ollama import ChatOllama

        _ollama_model_cache = ChatOllama(
            base_url=host,
            model=model_name,
            temperature=0.25,
        )
        return _ollama_model_cache
    except Exception:
        return None


def resolve_model_for_tier(tier: str) -> tuple[Any | None, str]:
    """
    tier: local → Ollama 우선 | cloud → OpenAI 우선 | auto → OpenAI→Ollama.
    반환: (model, provider_label)
    """
    t = (tier or "auto").strip().lower()
    if t == "local":
        m = get_ollama_chat_model_or_none()
        if m is not None:
            return m, "ollama"
        m = get_langchain_chat_model_or_none()
        if m is not None:
            return m, "openai"
        return None, "fallback"
    if t == "cloud":
        m = get_langchain_chat_model_or_none()
        if m is not None:
            return m, "openai"
        m = get_ollama_chat_model_or_none()
        if m is not None:
            return m, "ollama"
        return None, "fallback"
    m = get_langchain_chat_model_or_none()
    if m is not None:
        return m, "openai"
    m = get_ollama_chat_model_or_none()
    if m is not None:
        return m, "ollama"
    return None, "fallback"


def invoke_with_tier(
    system: str,
    user: str,
    *,
    tier: str = "auto",
    fallback_key: str = "generic",
    context: dict[str, str] | None = None,
) -> tuple[str, str]:
    """tier별 LLM 호출 — (text, provider) 반환."""
    ctx = context or {}
    model, provider = resolve_model_for_tier(tier)
    if model is None:
        fb = _fallback_for_key(fallback_key, ctx)
        return fb, "fallback"
    try:
        return _coerce_llm_text(_invoke_langchain(model, system, user)), provider
    except Exception:
        return _fallback_for_key(fallback_key, ctx), "fallback"


def _fallback_subagent(sub_key: str, context: dict[str, str]) -> str:
    """Sub-Agent 단위 rule-based 산출 — Ollama/OpenAI 모두 불가 시."""
    title = context.get("proposal_title") or context.get("idea_title", "추진계획서")
    prob = context.get("current_problems") or context.get("pain_points", "")
    ts = context.get("target_system", "")
    imp = context.get("improvement_direction", "")
    base = f"**과제:** {title}\n"
    if "gap" in sub_key or "assumption" in sub_key:
        return base + f"- 누락: 데이터 소스·승인 라인·파일럿 범위 (가정)\n- 문제: {prob[:200]}\n"
    if "as_is" in sub_key or "pain" in sub_key or "stakeholder" in sub_key:
        return base + f"- AS-IS/문제: {prob[:300]}\n- 시스템: {ts}\n"
    if "to_be" in sub_key or "automation" in sub_key or "architecture" in sub_key:
        return base + f"- TO-BE 방향: {imp}\n- 대상: {ts}\n"
    if "scope" in sub_key or "module" in sub_key:
        return base + "- 포함: MVP 검증·룰 엔진 (가정)\n- 제외: ERP 커스터 (가정)\n"
    if "wbs" in sub_key or "milestone" in sub_key or "phase" in sub_key:
        return base + "| 1 | 킥오프 | 3일 | PM | 계획서 |\n| 2 | 구현 | 2주 | IT | MVP |\n"
    if "cost" in sub_key or "kpi" in sub_key or "roi" in sub_key:
        return base + f"| 항목 | 예상 | 설명 |\n| 인력 | {context.get('budget_range', '협의')} | 가정 |\n"
    if "risk" in sub_key or "mitigation" in sub_key or "impact" in sub_key:
        return base + "| 데이터 품질 | 중 | 고 | 사전 점검 |\n"
    if "storyline" in sub_key or "narrative" in sub_key or "slide" in sub_key:
        return '{"slides": []}'
    if "visual" in sub_key or "graphics" in sub_key or "composer" in sub_key:
        return '{"slides": []}'
    if "critic" in sub_key:
        return (
            "CRITIC_SCORE: 70\nSTATUS: FAIL\nFEEDBACK_TARGET: business\n"
            "IMPROVEMENT_NOTES: Sub-Agent fallback — AS-IS 구체화 필요\n"
        )
    return base + f"- Sub-Agent `{sub_key}` fallback 산출 (가정)\n"


def _coerce_llm_text(val: Any) -> str:
    """fallback 템플릿 실수(tuple)나 LangChain 혼합 응답을 Markdown 문자열로 통일한다."""
    if val is None:
        return ""
    if isinstance(val, str):
        return val.strip()
    if isinstance(val, tuple):
        return "\n".join(_coerce_llm_text(x) for x in val if x is not None).strip()
    return str(val).strip()


def _fallback_for_key(fallback_key: str, context: dict[str, str]) -> str:
    if fallback_key.startswith("sub_"):
        return _fallback_subagent(fallback_key[4:], context)
    return _coerce_llm_text(_fallback_task_markdown(fallback_key, context))


def merge_subagent_fallbacks(records: list[Any], parent_label: str) -> str:
    """Synthesizer LLM 없이 Sub-Agent 산출만 이어 붙인다."""
    lines = [f"# {parent_label} (Sub-Agent 통합 · Fallback)\n"]
    for r in records:
        role = getattr(r, "role", None) or (r.get("role") if isinstance(r, dict) else "")
        sid = getattr(r, "subagent_id", None) or (r.get("subagent_id") if isinstance(r, dict) else "")
        out = getattr(r, "output", None) or (r.get("output") if isinstance(r, dict) else "")
        lines.append(f"\n## [{sid}] {role}\n\n{out}\n")
    return "\n".join(lines)


def get_llm_routing_status() -> dict[str, Any]:
    """Streamlit 사이드바·디버그용 — 어떤 LLM이 켜져 있는지."""
    load_dotenv()
    return {
        "openai_configured": bool(os.getenv("OPENAI_API_KEY", "").strip()),
        "openai_model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        "local_llm_enabled": is_local_llm_enabled(),
        "ollama_host": os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434"),
        "ollama_model": os.getenv("OLLAMA_MODEL", "qwen2.5:7b"),
        "open_source_provider": os.getenv("OPEN_SOURCE_LLM_PROVIDER", "mock"),
        "subagents_enabled": os.getenv("AUTOPM_ENABLE_SUBAGENTS", "true").strip().lower()
        not in ("0", "false", "no"),
    }


def get_mcp_routing_status() -> dict[str, Any]:
    """MCP 서버·도구·RAG 상태 — Streamlit 사이드바용."""
    try:
        from autopm.mcp.client import get_mcp_status
        from autopm.tools.proposal_rag import get_rag_status

        out = get_mcp_status()
        out["proposal_rag"] = get_rag_status()
        return out
    except Exception as exc:  # noqa: BLE001
        return {"mcp_enabled": False, "error": str(exc)}


def _content_to_text(content: Any) -> str:
    """LangChain 응답 content가 str·list·dict 혼합일 때 Markdown 문자열로 통일한다."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                parts.append(str(block.get("text") or block.get("content") or ""))
            else:
                parts.append(str(block))
        return "\n".join(p for p in parts if p).strip()
    return str(content).strip()


def _invoke_langchain(model: Any, system: str, user: str) -> str:
    from langchain_core.messages import HumanMessage, SystemMessage

    resp = model.invoke([SystemMessage(content=system), HumanMessage(content=user)])
    content = getattr(resp, "content", None)
    text = _content_to_text(content)
    if text:
        return text
    return _content_to_text(resp)


def _fallback_task_markdown(task_key: str, context: dict[str, str], extra: str = "") -> str:
    """API 없이도 파이프라인이 끊기지 않게 태스크별 최소 Markdown을 만든다."""
    title = context.get("proposal_title") or context.get("idea_title", "추진계획서")
    purpose = context.get("proposal_purpose", "")
    bg = context.get("background_context", "")
    prob = context.get("current_problems") or context.get("pain_points", "")
    ts = context.get("target_system", "")
    scope = context.get("business_scope", "")
    imp = context.get("improvement_direction", "")
    tone = context.get("presentation_tone", "실무 추진계획형")

    templates: dict[str, str] = {
        "orchestrate_task": (
            f"# 추진계획 구조 (Fallback)\n\n"
            f"- **제목:** {title}\n- **목적:** {purpose}\n- **배경:** {bg}\n"
            f"- **문제:** {prob}\n- **대상:** {ts}\n- **범위:** {scope}\n"
            f"- **개선 방향:** {imp}\n- **PPT 톤:** {tone}\n"
            f"- 이후 섹션: 요건→AS-IS→TO-BE→범위→WBS→예산→리스크 (가정)\n"
        ),
        "requirement_task": (
            f"## 요구사항 정리 (Fallback)\n\n| 항목 | 내용 |\n| --- | --- |\n"
            f"| 목적 | {purpose} |\n| 배경 | {bg} |\n| 문제 | {prob} |\n"
            f"| 대상 시스템 | {ts} |\n| 범위 | {scope} |\n\n"
            f"**추가 확인:** 데이터 소스·승인 라인·파일럿 범위 (가정)\n"
        ),
        "business_analysis_task": (
            f"## AS-IS / Pain (Fallback)\n\n- 현황: {bg or context.get('current_process', '')}\n"
            f"- Pain: {prob}\n- 이해관계자: {context.get('related_departments', '')}\n"
        ),
        "solution_design_task": (
            f"## TO-BE (Fallback)\n\n- 목표 시스템: {ts}\n- 개선: {imp}\n"
            f"- MVP: 자동 검증·표준 룰·리포트 (실연동 제외, 가정)\n"
        ),
        "development_scope_task": (
            "## 개발 범위 (Fallback)\n\n**포함:** 룰 엔진, 검증 배치, 대시보드 초안\n"
            "**제외:** ERP 커스터, 대규모 인프라\n"
        ),
        "wbs_task": (
            f"## WBS (Fallback)\n\n| 단계 | 작업 | 기간 | 담당 | 산출물 |\n"
            f"| --- | --- | --- | --- | --- |\n"
            f"| 1 | 킥오프 | 3일 | PM | 계획서 |\n"
            f"| 2 | 분석 | 1주 | 현업/IT | AS-IS |\n"
            f"| 3 | 구현 | 2주 | IT | MVP |\n"
            f"| 4 | 파일럿 | 1주 | 전체 | 리포트 |\n"
        ),
        "budget_roi_task": (
            f"## 예산·ROI (Fallback)\n\n| 항목 | 예상 비용 | 설명 |\n"
            f"| --- | --- | --- |\n| 인력 | {context.get('budget_range', '협의')} | 분석·구현 (가정) |\n"
            f"| 절감 | 월 {context.get('monthly_hours', '?')}h의 30%(가정) | 자동화 |\n"
        ),
        "risk_critic_task": (
            "## 리스크 (Fallback)\n\n| 리스크 | 가능성 | 영향 | 대응 |\n"
            "| --- | --- | --- | --- |\n| 데이터 품질 | 중 | 고 | 사전 정합성 점검 |\n"
            "| 조직 저항 | 중 | 중 | 파일럿·교육 |\n"
        ),
        "critic_task": (
            "CRITIC_SCORE: 72\nSTATUS: FAIL\nFEEDBACK_TARGET: business\n"
            "IMPROVEMENT_NOTES: AS-IS·Pain을 표로 구체화하라.\n"
            "FINAL_RECOMMENDATION: Fallback 모드 — API 연결 후 재평가\n",
        ),
        "documentation_task": (
            f"# AutoPM 추진계획서 (Fallback 조립)\n\n## 1. Executive Summary\n- {title}\n\n"
            f"## 3. 현재 문제점\n{prob}\n\n## 5. TO-BE\n{imp}\n",
        ),
        "slide_storyline_task": '{"slides": []}',
        "visualization_design_task": '{"slides": []}',
        "presentation_graphics_task": '{"graphics_spec": []}',
        "ppt_composition_task": '{"slides": []}',
        "peer_dialogue": extra or "이전 단계 산출을 확인했습니다. 다음 단계에서 보완하겠습니다.",
    }
    return templates.get(task_key, f"## {task_key} (Fallback)\n\n{title}\n")


def invoke_chat_or_fallback(
    system: str,
    user: str,
    *,
    fallback_key: str,
    context: dict[str, str],
    model: Any | None = None,
    extra_fallback: str = "",
) -> str:
    """LangChain Chat 호출 — 실패·키 없음 시 rule-based Markdown."""
    m = model if model is not None else get_langchain_chat_model_or_none()
    if m is None:
        return _fallback_task_markdown(fallback_key, context, extra_fallback)
    try:
        return _invoke_langchain(m, system, user)
    except Exception:
        return _fallback_task_markdown(fallback_key, context, extra_fallback)


def _mock_draft_markdown(inputs: dict[str, str]) -> str:
    """API·로컬 LLM 없이도 데모 가능한 템플릿 초안 — Deep Agent seed용."""
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

    if provider in ("ollama", "ollama_optional", "local_open_source"):
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
    "get_langchain_chat_model_or_none",
    "get_openai_llm_or_none",
    "get_ollama_chat_model_or_none",
    "is_local_llm_enabled",
    "resolve_model_for_tier",
    "invoke_with_tier",
    "invoke_chat_or_fallback",
    "merge_subagent_fallbacks",
    "get_llm_routing_status",
    "generate_draft_with_open_source_llm",
    "refine_with_openai",
    "refine_draft_for_user_choice",
    "generate_with_best_available_model",
]
