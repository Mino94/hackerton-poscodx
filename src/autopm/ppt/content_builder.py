"""Crew/fallback Markdown·인터뷰 입력을 business_plan 하나로 통합 — slide_builder·PPT가 동일 소스를 쓰게 한다."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any

# 데모·API 없음·파싱 실패 시에도 비지 않도록 최소 골격(포스코 제목 키워드면 풍부 샘플).
_POSCO_SAMPLE_BUSINESS_PLAN: dict[str, Any] = {
    "project_title": "포스코 2026년 미래전략을 위한 Mini ERP 원가시스템 개선 추진계획서",
    "executive_summary": {
        "summary": "2026년 미래전략 대응을 위해 원가 데이터의 신뢰성과 실시간성을 강화한다.",
        "key_points": [
            "Mini ERP와 원가시스템 간 데이터 정합성을 높인다.",
            "수작업 검증 중심의 결산 업무를 자동 검증·모니터링 체계로 전환한다.",
            "원가 분석, 결산 검증, 경영 의사결정 지원 수준을 개선한다.",
            "원가 데이터는 제품 수익성·생산·경영전략 수립의 핵심 기반이다.",
        ],
    },
    "background": {
        "context": "원가 데이터는 제품 수익성, 생산 의사결정, 경영전략 수립의 핵심 기반이다.",
        "why_now": "2026년 미래전략을 위해 데이터 기반 원가관리 체계가 필요하다.",
        "strategic_alignment": "미래전략과 연계해 원가 신뢰성·실시간성을 확보한다.",
    },
    "current_problems": [
        {
            "title": "데이터 정합성 부족",
            "description": "ERP, 원가 리포트, 엑셀 검증 자료 간 기준이 다를 수 있음",
            "impact": "결산 지연, 원인 분석 시간 증가",
        },
        {
            "title": "수작업 검증 부담",
            "description": "품목 단가, BOM, 재고수불, 평가단가를 수작업으로 확인",
            "impact": "오류 누락 가능, 담당자 과중",
        },
        {
            "title": "실시간 분석 한계",
            "description": "결산 후 결과 확인 중심으로 운영",
            "impact": "사전 대응보다 사후 조치에 의존",
        },
        {
            "title": "기준 표준화 부족",
            "description": "담당자별 검증 기준·대응 방식 차이",
            "impact": "보고 품질 편차",
        },
    ],
    "as_is": {
        "summary": "ERP 다운로드 후 엑셀·수작업 검증으로 결산 리포트를 완성한다.",
        "steps": [
            "ERP 데이터 다운로드",
            "엑셀 기반 품목/단가/재고/BOM 검증",
            "담당자별 오류 여부 판단",
            "원인 확인을 위해 관련 부서 문의",
            "결산 리포트 수작업 보정",
            "최종 보고서 작성",
        ],
        "pain_points": ["수작업·반복 검증", "기준 편차", "결산 리드타임"],
    },
    "to_be": {
        "summary": "표준 검증 룰과 자동화로 정합성·속도를 확보한다.",
        "steps": [
            "Mini ERP 원가 데이터 자동 수집",
            "표준 검증 룰 기반 자동 점검",
            "단가/BOM/재고수불 이상값 자동 탐지",
            "오류 원인·조치 가이드 자동 제시",
            "대시보드 기반 실시간 모니터링",
            "결산 리포트 자동 생성 및 이력 관리",
        ],
        "improvements": ["자동 검증", "실시간 모니터링", "이력·감사 추적"],
    },
    "development_scope": {
        "included": [
            "원가 데이터 표준 검증 룰 관리",
            "품목 평가단가 검증",
            "BOM 누락 검증",
            "재고수불 정합성 검증",
            "결산 오류 리포트 자동 생성",
            "관리자 대시보드",
            "조치 이력 관리",
        ],
        "excluded": [
            "ERP 원천 데이터 직접 수정",
            "회계 정책 자동 판단",
            "전사 ERP 전체 재구축",
            "외부 시스템 실시간 양방향 연동",
        ],
        "modules": ["검증 엔진", "리포트", "대시보드"],
    },
    "wbs": [
        {"phase": "1단계", "task": "현행 업무 분석", "duration": "1주", "owner": "원가팀+IT팀", "deliverable": "AS-IS 분석서"},
        {"phase": "2단계", "task": "검증 룰 정의", "duration": "1주", "owner": "원가팀", "deliverable": "검증 기준표"},
        {"phase": "3단계", "task": "데이터 연계 및 모델링", "duration": "2주", "owner": "IT팀", "deliverable": "데이터 매핑 정의서"},
        {"phase": "4단계", "task": "자동 검증 기능 개발", "duration": "3주", "owner": "개발팀", "deliverable": "검증 모듈"},
        {"phase": "5단계", "task": "대시보드 및 리포트 구현", "duration": "2주", "owner": "개발팀", "deliverable": "화면 및 리포트"},
        {"phase": "6단계", "task": "테스트 및 시범 적용", "duration": "1주", "owner": "원가팀+현업", "deliverable": "테스트 결과서"},
        {"phase": "7단계", "task": "운영 전환", "duration": "1주", "owner": "IT팀+운영팀", "deliverable": "운영 가이드"},
    ],
    "budget": [
        {"item": "업무 분석 및 설계", "cost": "300만 원", "description": "현행 프로세스 분석 및 개선안 설계"},
        {"item": "데이터 연계 개발", "cost": "500만 원", "description": "Mini ERP 데이터 추출 및 정합성 처리"},
        {"item": "검증 룰 엔진 개발", "cost": "700만 원", "description": "단가/BOM/재고 검증 로직 구현"},
        {"item": "대시보드 및 리포트", "cost": "500만 원", "description": "원가 검증 결과 시각화"},
        {"item": "테스트 및 안정화", "cost": "300만 원", "description": "사용자 검증 및 오류 보완"},
    ],
    "kpis": [
        {"name": "월마감 검증 시간", "current": "40시간", "target": "12시간", "effect": "약 70% 절감"},
        {"name": "오류 탐지율", "current": "담당자 수작업 의존", "target": "주요 오류 90% 이상 탐지", "effect": "품질·감사 대응"},
        {"name": "리포트 작성 시간", "current": "8시간", "target": "2시간", "effect": "보고 자동화"},
        {"name": "데이터 불일치 대응", "current": "건별 1~2일", "target": "당일 원인 확인", "effect": "결산 리드타임 단축"},
    ],
    "risks": [
        {"risk": "ERP 데이터 품질 미흡", "probability": "Medium", "impact": "High", "response": "사전 데이터 프로파일링 및 예외 룰 정의"},
        {"risk": "현업 검증 기준 불일치", "probability": "Medium", "impact": "Medium", "response": "표준 검증 기준 워크숍"},
        {"risk": "초기 사용자 저항", "probability": "Low", "impact": "Medium", "response": "시범 적용 후 개선 반영"},
        {"risk": "예외 케이스 과다", "probability": "Medium", "impact": "High", "response": "단계적 룰 확장"},
        {"risk": "일정 지연", "probability": "Medium", "impact": "Medium", "response": "MVP 범위 우선 적용"},
    ],
    "critic_review": {
        "score": 86,
        "missing_items": [
            "실제 데이터 샘플 기준의 검증 룰 상세화 필요",
            "운영 조직과 권한 체계 추가 정의 필요",
        ],
        "suggestions": [
            "초기 MVP는 품목 단가, BOM, 재고수불 3개 검증 영역에 집중",
            "결산 리포트 자동화는 2차 고도화 범위로 분리",
        ],
        "final_opinion": "본 추진계획은 경영진 보고용 초안으로 활용 가능하며, 실제 데이터 샘플과 현업 검증 기준을 추가하면 승인 가능성이 높아진다.",
    },
    "recommendations": ["RACI·데이터 접근 범위 확정", "파일럿 품목·기간 합의", "보안·감사 로그 정책 반영"],
}


def _title_suggests_posco_sample(title: str) -> bool:
    t = (title or "").lower()
    return "포스코" in (title or "") or ("mini erp" in t and "원가" in (title or ""))


def _empty_bp_shell() -> dict[str, Any]:
    """필드만 갖춘 빈 껍데기 — 이후 입력·파싱·fallback으로 채운다."""
    return {
        "project_title": "",
        "executive_summary": {"summary": "", "key_points": []},
        "background": {"context": "", "why_now": "", "strategic_alignment": ""},
        "current_problems": [],
        "as_is": {"summary": "", "steps": [], "pain_points": []},
        "to_be": {"summary": "", "steps": [], "improvements": []},
        "development_scope": {"included": [], "excluded": [], "modules": []},
        "wbs": [],
        "budget": [],
        "kpis": [],
        "risks": [],
        "critic_review": {"score": 0, "missing_items": [], "suggestions": [], "final_opinion": ""},
        "recommendations": [],
    }


def _deep_merge_dict(base: dict[str, Any], patch: dict[str, Any]) -> None:
    for k, v in patch.items():
        if k not in base:
            base[k] = v
            continue
        if isinstance(v, dict) and isinstance(base[k], dict):
            _deep_merge_dict(base[k], v)
        elif isinstance(v, list) and v:
            base[k] = v
        elif v not in (None, "", [], {}):
            base[k] = v


def _normalize_problem(p: Any) -> dict[str, str]:
    if isinstance(p, dict):
        return {
            "title": str(p.get("title", "")),
            "description": str(p.get("description", "")),
            "impact": str(p.get("impact", "")),
        }
    s = str(p).strip()
    return {"title": f"이슈", "description": s, "impact": ""}


def _from_inputs(inputs: dict[str, str]) -> dict[str, Any]:
    """인터뷰 Crew placeholder만 있어도 business_plan 초안을 만든다."""
    title = (inputs.get("proposal_title") or inputs.get("idea_title") or "").strip() or "추진계획서 과제"
    out: dict[str, Any] = _empty_bp_shell()
    out["project_title"] = title[:500]
    summ = (inputs.get("proposal_purpose") or "").strip()
    kpts = [x.strip() for x in (inputs.get("improvement_direction") or "").split("|") if x.strip()]
    if inputs.get("key_emphasis"):
        kpts.append(inputs["key_emphasis"].strip())
    if not kpts and inputs.get("goals"):
        kpts = [inputs["goals"].strip()[:200]]
    out["executive_summary"]["summary"] = summ or f"{title} 추진을 통한 업무·시스템 개선"
    out["executive_summary"]["key_points"] = kpts or [
        out["executive_summary"]["summary"],
        (inputs.get("background_context") or "")[:200],
        (inputs.get("timeline") or inputs.get("target_timeline") or "일程 협의") + " 내 단계적 적용",
    ]
    out["background"]["context"] = (inputs.get("background_context") or inputs.get("current_process") or "").strip()
    out["background"]["why_now"] = (inputs.get("current_problems") or inputs.get("pain_points") or "")[:300]
    out["background"]["strategic_alignment"] = (inputs.get("proposal_purpose") or "").strip()
    prob_txt = (inputs.get("current_problems") or inputs.get("pain_points") or "").strip()
    if prob_txt:
        out["current_problems"] = [{"title": "핵심 문제", "description": prob_txt[:400], "impact": "품질·리드타임"}]
    out["as_is"]["summary"] = (inputs.get("current_process") or out["background"]["context"])[:500]
    for line in (inputs.get("current_process") or "").split("\n"):
        line = line.strip().lstrip("-•").strip()
        if line:
            out["as_is"]["steps"].append(line)
    if len(out["as_is"]["steps"]) < 3:
        out["as_is"]["steps"] = ["데이터 수집", "수작업 검증", "리포트 작성"]
    out["as_is"]["pain_points"] = [prob_txt[:200]] if prob_txt else ["반복 작업", "기준 편차"]
    goal = (inputs.get("improvement_direction") or inputs.get("goals") or "").strip()
    out["to_be"]["summary"] = goal or "자동화·표준화를 통한 운영 개선"
    out["to_be"]["steps"] = [
        "데이터 자동 수집",
        "검증 룰 적용",
        "이상 탐지·알림",
        "리포트·대시보드",
    ]
    out["to_be"]["improvements"] = ["자동 검증", "가시성", "이력 관리"]
    dept = inputs.get("related_departments") or inputs.get("departments") or ""
    out["development_scope"]["included"] = [
        (inputs.get("business_scope") or inputs.get("target_system") or "MVP 범위")[:200],
        "검증·리포트(가정)",
    ]
    out["development_scope"]["excluded"] = ["전사 시스템 전면 교체(가정)", "실연동 제외 영역"]
    out["development_scope"]["modules"] = [inputs.get("target_system") or "대상 시스템"]
    out["wbs"] = [
        {"phase": "1", "task": "킥오프·범위", "duration": "1주", "owner": "PM", "deliverable": "범위 합의"},
        {"phase": "2", "task": "설계", "duration": "1주", "owner": dept or "현업", "deliverable": "설계서"},
        {"phase": "3", "task": "구현", "duration": "2주", "owner": "IT", "deliverable": "모듈"},
        {"phase": "4", "task": "테스트", "duration": "1주", "owner": "전체", "deliverable": "결과"},
    ]
    br = inputs.get("budget_range") or "내부 협의"
    out["budget"] = [
        {"item": "분석·설계", "cost": "300만 원(가정)", "description": "범위·룰 정의"},
        {"item": "개발", "cost": "500만 원(가정)", "description": "MVP 구현"},
        {"item": "테스트·안정화", "cost": "200만 원(가정)", "description": br[:80]},
    ]
    mh = inputs.get("monthly_hours") or "40"
    hc = inputs.get("headcount") or "3"
    out["kpis"] = [
        {"name": "월간 검증 시간", "current": f"{mh}h", "target": "-30%(가정)", "effect": "업무 부하 감소"},
        {"name": "오류 누락", "current": "수작업", "target": "주요 오류 조기 탐지", "effect": "품질"},
        {"name": "참여 인력", "current": f"{hc}명", "target": "동일 대비 산출↑", "effect": "효율"},
    ]
    out["risks"] = [
        {"risk": "데이터 품질", "probability": "중", "impact": "중", "response": "샘플 검증"},
        {"risk": "일정", "probability": "중", "impact": "중", "response": "MVP 단순화"},
        {"risk": "변경 관리", "probability": "저", "impact": "중", "response": "교육·가이드"},
    ]
    out["critic_review"]["score"] = 75
    out["critic_review"]["missing_items"] = ["상세 룰·샘플 데이터"]
    out["critic_review"]["suggestions"] = ["파일럿 범위 확정"]
    out["critic_review"]["final_opinion"] = "초안으로 경영·IT 합의 후 단계 추진을 권고한다."
    out["recommendations"] = ["승인 범위·RACI", "데이터 접근 권한"]
    return out


def _extract_numbered_sections(md: str) -> dict[int, str]:
    """## N. 형식 섹션을 번호→본문으로 분리한다."""
    if not md or not md.strip():
        return {}
    sections: dict[int, str] = {}
    pattern = re.compile(r"^##\s+(\d+)\.\s*[^\n]*\n", re.MULTILINE)
    matches = list(pattern.finditer(md))
    for i, m in enumerate(matches):
        num = int(m.group(1))
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(md)
        sections[num] = md[start:end].strip()
    return sections


def _bullets_from_text(block: str, max_n: int = 8) -> list[str]:
    lines: list[str] = []
    for line in block.splitlines():
        line = line.strip()
        if re.match(r"^[-*•]\s+", line):
            lines.append(re.sub(r"^[-*•]\s+", "", line).strip())
        elif re.match(r"^\d+\.\s+", line):
            lines.append(re.sub(r"^\d+\.\s+", "", line).strip())
    return [x for x in lines if x][:max_n]


def _parse_markdown_patch(md: str) -> dict[str, Any]:
    """AutoPM Markdown 번호 목차를 business_plan 필드에 억지 매핑(있으면 채움)."""
    sec = _extract_numbered_sections(md)
    patch: dict[str, Any] = {}
    if 1 in sec:
        bullets = _bullets_from_text(sec[1], 6)
        patch["executive_summary"] = {"summary": sec[1][:500], "key_points": bullets or [sec[1][:240]]}
    if 2 in sec:
        patch["background"] = {
            "context": sec[2][:800],
            "why_now": _bullets_from_text(sec[2], 2)[0] if _bullets_from_text(sec[2], 2) else "",
            "strategic_alignment": "",
        }
    if 3 in sec:
        b = _bullets_from_text(sec[3], 10)
        patch["current_problems"] = [{"title": f"항목 {i+1}", "description": t, "impact": ""} for i, t in enumerate(b)] if b else []
    if 4 in sec:
        patch["as_is"] = {
            "summary": sec[4][:400],
            "steps": _bullets_from_text(sec[4], 12) or [],
            "pain_points": [],
        }
    if 5 in sec:
        patch["to_be"] = {
            "summary": sec[5][:400],
            "steps": _bullets_from_text(sec[5], 12) or [],
            "improvements": [],
        }
    if 6 in sec:
        patch["development_scope"] = {
            "included": _bullets_from_text(sec[6], 15),
            "excluded": [],
            "modules": [],
        }
    if 7 in sec:
        rows = []
        for line in sec[7].splitlines():
            if "|" in line and not line.strip().startswith("|---"):
                parts = [c.strip() for c in line.split("|") if c.strip()]
                if len(parts) >= 2:
                    rows.append(
                        {
                            "phase": parts[0][:40],
                            "task": parts[1][:80] if len(parts) > 1 else "",
                            "duration": parts[2] if len(parts) > 2 else "",
                            "owner": parts[3] if len(parts) > 3 else "",
                            "deliverable": parts[4] if len(parts) > 4 else "",
                        }
                    )
        if rows:
            patch["wbs"] = rows
    if 8 in sec:
        patch["budget"] = []
        patch["kpis"] = []
        for line in _bullets_from_text(sec[8], 12):
            if "원" in line or "비용" in line.lower():
                patch.setdefault("budget", []).append({"item": line[:40], "cost": "", "description": line})
            else:
                patch.setdefault("kpis", []).append(
                    {"name": line[:40], "current": "", "target": "", "effect": ""}
                )
    if 9 in sec:
        risks = []
        for line in _bullets_from_text(sec[9], 10):
            risks.append({"risk": line[:100], "probability": "", "impact": "", "response": ""})
        if risks:
            patch["risks"] = risks
    if 10 in sec:
        patch["critic_review"] = {
            "score": 80,
            "missing_items": _bullets_from_text(sec[10], 5),
            "suggestions": [],
            "final_opinion": sec[10][:1200],
        }
    return patch


def ensure_nonempty(bp: dict[str, Any], inputs: dict[str, str]) -> None:
    """리스트·문자열 빈 값을 입력·최소 문장으로 메운다 — slide_builder가 멈추지 않게."""
    if not (bp.get("project_title") or "").strip():
        bp["project_title"] = (inputs.get("proposal_title") or inputs.get("idea_title") or "AutoPM 과제")[:500]
    es = bp.get("executive_summary") or {}
    kpts = es.get("key_points") or []
    if not kpts:
        es["key_points"] = [
            bp["project_title"],
            (inputs.get("proposal_purpose") or "추진 목적 확정 필요")[:200],
        ]
    if not (es.get("summary") or "").strip():
        es["summary"] = kpts[0] if kpts else "추진 요약"
    bp["executive_summary"] = es
    if not bp.get("current_problems"):
        bp["current_problems"] = [
            _normalize_problem(inputs.get("current_problems") or inputs.get("pain_points") or "문제 정의 필요"),
        ]
    else:
        bp["current_problems"] = [_normalize_problem(x) for x in bp["current_problems"]]
    as_is = bp.get("as_is") or {}
    if len(as_is.get("steps") or []) < 3:
        as_is["steps"] = (as_is.get("steps") or []) + ["분석", "검증", "보고"][: 3 - len(as_is.get("steps") or [])]
    bp["as_is"] = as_is
    to_be = bp.get("to_be") or {}
    if len(to_be.get("steps") or []) < 3:
        to_be["steps"] = (to_be.get("steps") or []) + ["자동화", "모니터링", "리포트"][: 3 - len(to_be.get("steps") or [])]
    bp["to_be"] = to_be
    scope = bp.get("development_scope") or {}
    if not scope.get("included"):
        scope["included"] = ["MVP 기능", "검증·리포트"]
    if not scope.get("excluded"):
        scope["excluded"] = ["범위 외 연동"]
    bp["development_scope"] = scope
    if len(bp.get("wbs") or []) < 3:
        bp["wbs"] = _from_inputs(inputs)["wbs"]
    if len(bp.get("budget") or []) < 3:
        bp["budget"] = _from_inputs(inputs)["budget"]
    if len(bp.get("kpis") or []) < 3:
        bp["kpis"] = _from_inputs(inputs)["kpis"]
    if len(bp.get("risks") or []) < 3:
        bp["risks"] = _from_inputs(inputs)["risks"]
    cr = bp.get("critic_review") or {}
    if not (cr.get("final_opinion") or "").strip():
        cr["final_opinion"] = "문서·데이터를 보완한 뒤 승인 절차를 진행한다."
    if not cr.get("score"):
        cr["score"] = 78
    bp["critic_review"] = cr
    if not bp.get("recommendations"):
        bp["recommendations"] = ["범위·일정·RACI 확정"]


def build_business_plan(inputs: dict[str, str], agent_outputs: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    인터뷰 입력 + (선택) Agent Markdown/structured를 business_plan으로 통합.
    agent_outputs: markdown, structured(dict) 등
    """
    agent_outputs = agent_outputs or {}
    title = (inputs.get("proposal_title") or inputs.get("idea_title") or "").strip()

    if _title_suggests_posco_sample(title):
        bp = deepcopy(_POSCO_SAMPLE_BUSINESS_PLAN)
        if title:
            bp["project_title"] = title[:500]
    else:
        bp = _from_inputs(inputs)

    md = (agent_outputs.get("markdown") or "").strip()
    if md:
        _deep_merge_dict(bp, _parse_markdown_patch(md))

    structured = agent_outputs.get("structured")
    if isinstance(structured, dict) and structured:
        try:
            _deep_merge_dict(bp, structured)
        except Exception:
            pass

    ensure_nonempty(bp, inputs)
    return bp


def business_plan_to_json_str(bp: dict[str, Any]) -> str:
    return json.dumps(bp, ensure_ascii=False, indent=2)
