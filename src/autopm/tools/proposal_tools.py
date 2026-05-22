"""추진계획서 S01~S10 LangChain Tool — RAG + LLM(JSON), API 없으면 규칙 폴백."""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from autopm.chat.proposal_extract import extract_title_metadata
from autopm.services.llm_router import get_langchain_chat_model_or_none, get_ollama_chat_model_or_none
from autopm.tools.proposal_rag import retrieve_reference_context


def _get_model() -> Any | None:
    return get_langchain_chat_model_or_none() or get_ollama_chat_model_or_none()


def _strip_json_fence(text: str) -> str:
    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.I)
    t = re.sub(r"\s*```\s*$", "", t)
    return t.strip()


def _invoke_llm(system: str, user: str) -> str:
    model = _get_model()
    if model is None:
        return ""
    try:
        resp = model.invoke(
            [SystemMessage(content=system), HumanMessage(content=user)]
        )
        return _strip_json_fence(str(getattr(resp, "content", resp)))
    except Exception:
        return ""


def extract_proposal_info(user_input: str) -> str:
    """S01 — 제목/주제에서 회사·전략·시스템·범위 JSON 추출."""
    system = (
        "추진계획서 제목/설명에서 핵심 정보를 추출하여 순수 JSON만 반환하세요.\n"
        '{"company":"회사명","strategy":"전략명","system":"대상 시스템",'
        '"scope":"업무 범위","year":"연도","summary":"한 줄 요약"}'
    )
    out = _invoke_llm(system, user_input)
    if out:
        return out
    meta = extract_title_metadata(user_input)
    fallback = {
        "company": meta.get("target_company", ""),
        "strategy": meta.get("strategy_context", ""),
        "system": meta.get("target_system", ""),
        "scope": user_input[:200],
        "year": "",
        "summary": user_input[:120],
    }
    return json.dumps(fallback, ensure_ascii=False)


def generate_interview_questions(extracted_info: str) -> str:
    """S02 — 추가 인터뷰 질문 5개 JSON 배열."""
    prompt = (
        "다음 추진계획서 기본 정보를 바탕으로 작성자가 빠뜨렸을 핵심 질문 5개를 생성하세요.\n"
        "(현재 업무 방식, 문제 빈도, 관련 부서, 목표 일정, 기대효과 포함)\n\n"
        f"기본 정보: {extracted_info}\n\n"
        '순수 JSON 배열만 반환: ["질문1", "질문2", "질문3", "질문4", "질문5"]'
    )
    out = _invoke_llm("JSON 배열만 반환.", prompt)
    if out:
        return out
    return json.dumps(
        [
            "현재 업무는 어떤 시스템·도구로 처리하나요?",
            "가장 큰 Pain Point의 발생 빈도와 처리 시간은?",
            "관련 부서·담당 인원은 누구인가요?",
            "목표 일정·예산 범위는?",
            "정량적 기대효과(KPI)는 무엇인가요?",
        ],
        ensure_ascii=False,
    )


def generate_requirements(user_input: str, rag_context: str) -> str:
    """S04 — 요구사항·목적·배경 JSON."""
    prompt = (
        "다음 입력과 사내 자료를 바탕으로 추진계획서 요구사항을 분석하세요.\n\n"
        f"입력: {user_input}\n사내 자료: {rag_context[:1200]}\n\n"
        "순수 JSON만 반환:\n"
        '{"purpose":"추진 목적","background":"추진 배경",'
        '"objectives":["목표1"],"stakeholders":["이해관계자1"],'
        '"success_criteria":["성공 기준1"]}'
    )
    out = _invoke_llm("추진계획서 PM 분석가. JSON만.", prompt)
    if out:
        return out
    return json.dumps(
        {
            "purpose": "업무 효율·품질 개선",
            "background": user_input[:400],
            "objectives": ["처리 시간 단축(예상)", "오류율 감소(예상)"],
            "stakeholders": ["현업", "IT", "경영진"],
            "success_criteria": ["KPI 달성(가정)"],
        },
        ensure_ascii=False,
    )


def analyze_as_is(requirements: str, rag_context: str = "") -> str:
    """S05 — AS-IS JSON."""
    prompt = (
        "요구사항과 사내 AS-IS 가이드를 바탕으로 AS-IS 현황을 분석하세요.\n\n"
        f"요구사항: {requirements[:600]}\n가이드: {rag_context[:800]}\n\n"
        "순수 JSON만 반환:\n"
        '{"current_process":["단계1"],"pain_points":["Pain1"],'
        '"bottlenecks":["병목1"],"manual_tasks":["수작업1"],'
        '"metrics":{"time_per_task":"(예상)","frequency":"","error_rate":"(예상)"}}'
    )
    out = _invoke_llm("AS-IS 분석가. 수치는 예상/가정 표기. JSON만.", prompt)
    if out:
        return out
    return json.dumps(
        {
            "current_process": ["데이터 수집", "수작업 검증", "승인"],
            "pain_points": ["시간 소요", "기준 불일치", "오류 누락"],
            "bottlenecks": ["수작업 검증"],
            "manual_tasks": ["엑셀 검증"],
            "metrics": {"time_per_task": "40시간/월(예상)", "error_rate": "10%(가정)"},
        },
        ensure_ascii=False,
    )


def design_to_be(as_is: str, requirements: str, rag_context: str = "") -> str:
    """S06 — TO-BE JSON."""
    prompt = (
        "AS-IS·요구사항·TO-BE 가이드로 개선 방안을 설계하세요.\n\n"
        f"AS-IS: {as_is[:400]}\n요구사항: {requirements[:400]}\n가이드: {rag_context[:600]}\n\n"
        "순수 JSON만 반환:\n"
        '{"improved_process":["단계1"],"automation_scope":["범위1"],'
        '"tech_stack":["기술1"],"improvement_points":["개선1"]}'
    )
    out = _invoke_llm("TO-BE 설계자. JSON만.", prompt)
    if out:
        return out
    return json.dumps(
        {
            "improved_process": ["자동 검증", "알림", "대시보드"],
            "automation_scope": ["룰 엔진", "배치 검증"],
            "tech_stack": ["ERP 연동", "Python"],
            "improvement_points": ["표준화", "실시간 모니터링"],
        },
        ensure_ascii=False,
    )


def define_development_scope(requirements: str, to_be: str) -> str:
    """S07 — 개발 범위 JSON."""
    prompt = (
        "요구사항·TO-BE로 개발 범위를 정의하세요.\n\n"
        f"요구사항: {requirements[:400]}\nTO-BE: {to_be[:400]}\n\n"
        '{"in_scope":[],"out_scope":[],"mvp":[],"phase2":[]}'
    )
    out = _invoke_llm("범위 정의. JSON만.", prompt)
    if out:
        return out
    return json.dumps(
        {
            "in_scope": ["검증 룰", "대시보드", "알림"],
            "out_scope": ["전사 ERP 전면 개편"],
            "mvp": ["핵심 검증 자동화"],
            "phase2": ["AI 이상탐지"],
        },
        ensure_ascii=False,
    )


def generate_wbs(requirements: str, scope: str, rag_context: str = "") -> str:
    """S08 — WBS JSON."""
    prompt = (
        "WBS 가이드에 맞춰 WBS를 작성하세요. 총 14~18주.\n\n"
        f"요구사항: {requirements[:400]}\n범위: {scope[:400]}\n가이드: {rag_context[:600]}\n\n"
        '{"phases":[{"phase":"착수","duration":"2주","tasks":[],"deliverable":""}],'
        '"total_duration":"14주","milestones":[]}'
    )
    out = _invoke_llm("WBS Planner. JSON만.", prompt)
    if out:
        return out
    return json.dumps(
        {
            "phases": [
                {"phase": "착수", "duration": "2주", "tasks": ["요구사항"], "deliverable": "요구사항 정의서"},
                {"phase": "설계", "duration": "3주", "tasks": ["설계"], "deliverable": "설계서"},
                {"phase": "개발", "duration": "6주", "tasks": ["개발"], "deliverable": "소스"},
                {"phase": "테스트", "duration": "2주", "tasks": ["UAT"], "deliverable": "테스트 결과"},
                {"phase": "안정화", "duration": "1주", "tasks": ["배포"], "deliverable": "릴리스"},
            ],
            "total_duration": "14주",
            "milestones": ["M1 설계", "M2 개발", "M3 배포"],
        },
        ensure_ascii=False,
    )


def calculate_budget_roi(requirements: str, wbs: str, rag_context: str = "") -> str:
    """S09 — 예산·ROI JSON (예상/가정 표기)."""
    prompt = (
        "예산·ROI 가이드로 산출. 추정값은 '예상'/'가정' 표기.\n\n"
        f"요구사항: {requirements[:400]}\nWBS: {wbs[:400]}\n가이드: {rag_context[:600]}\n\n"
        '{"total_budget":"","breakdown":{},"kpis":[],"annual_saving":"","roi":"","payback_period":""}'
    )
    out = _invoke_llm("재무 분석. JSON만.", prompt)
    if out:
        return out
    return json.dumps(
        {
            "total_budget": "500만 원 이하(예상)",
            "breakdown": {"인건비": "60%", "인프라": "20%", "외부": "20%"},
            "kpis": [{"metric": "검증 시간", "before": "40시간", "after": "12시간(예상)"}],
            "annual_saving": "1,000만 원/년(가정)",
            "roi": "20%(가정)",
            "payback_period": "18개월(예상)",
        },
        ensure_ascii=False,
    )


def generate_risk_matrix(requirements: str, wbs: str, rag_context: str = "") -> str:
    """S10 — 리스크 JSON."""
    prompt = (
        "리스크 가이드로 매트릭스 작성.\n\n"
        f"요구사항: {requirements[:400]}\nWBS: {wbs[:400]}\n가이드: {rag_context[:600]}\n\n"
        '{"risks":[{"category":"","risk":"","probability":"","impact":"","mitigation":""}]}'
    )
    out = _invoke_llm("리스크 분석. JSON만.", prompt)
    if out:
        return out
    return json.dumps(
        {
            "risks": [
                {
                    "category": "기술",
                    "risk": "데이터 품질 미흡",
                    "probability": "중",
                    "impact": "상",
                    "mitigation": "사전 정합성 점검",
                },
                {
                    "category": "조직",
                    "risk": "현업 저항",
                    "probability": "중",
                    "impact": "중",
                    "mitigation": "변화 관리·교육",
                },
            ]
        },
        ensure_ascii=False,
    )


def run_proposal_quality_pipeline(user_input: str) -> dict[str, str]:
    """
    S01→RAG→S04~S10 순차 실행 — enriched dict에 넣을 JSON 문자열 맵.
    LLM 없어도 RAG+규칙 폴백으로 동작.
    """
    extracted = extract_proposal_info(user_input)
    rag_general = retrieve_reference_context(user_input, k=4)
    rag_as_is = retrieve_reference_context(f"{user_input} AS-IS", k=3)
    rag_wbs = retrieve_reference_context(f"{user_input} WBS 일정", k=2)
    rag_roi = retrieve_reference_context(f"{user_input} ROI 예산", k=2)
    rag_risk = retrieve_reference_context(f"{user_input} 리스크", k=2)

    requirements = generate_requirements(user_input, rag_general)
    as_is = analyze_as_is(requirements, rag_as_is)
    to_be = design_to_be(as_is, requirements, rag_general)
    scope = define_development_scope(requirements, to_be)
    wbs = generate_wbs(requirements, scope, rag_wbs)
    budget = calculate_budget_roi(requirements, wbs, rag_roi)
    risks = generate_risk_matrix(requirements, wbs, rag_risk)
    questions = generate_interview_questions(extracted)

    return {
        "extracted_info_json": extracted,
        "interview_questions_json": questions,
        "requirements_json": requirements,
        "as_is_json": as_is,
        "to_be_json": to_be,
        "scope_json": scope,
        "wbs_json": wbs,
        "budget_roi_json": budget,
        "risk_json": risks,
        "rag_snippet": build_rag_snippet_from_context({"proposal_title": user_input}),
    }


def build_rag_snippet_from_context(context: dict[str, str]) -> str:
    """flow._build_enriched용 — 다주제 RAG 블록."""
    from autopm.tools.proposal_rag import build_multi_topic_rag_block

    return build_multi_topic_rag_block(context, k_per_topic=2)
