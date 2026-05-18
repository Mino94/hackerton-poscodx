"""추진계획서 제목에서 키워드·엔티티를 휴리스틱으로 추출 — LLM 없이 초기 state를 보강한다."""

from __future__ import annotations

import re
from typing import Any


def extract_title_metadata(title: str) -> dict[str, Any]:
    """
    제목/주제 문자열에서 프로젝트 맥락을 추출한다 — 틀리면 이후 인터뷰 답으로 교정된다.
    """
    t = (title or "").strip()
    if not t:
        return {}
    out: dict[str, Any] = {}

    # 회사/조직명 — 「OOO 2026년」 패턴 또는 알려진 토큰
    m_org = re.search(r"^([가-힣A-Za-z][가-힣A-Za-z0-9·\s]{0,22}?)\s+\d{4}년", t)
    if m_org:
        out["target_company"] = m_org.group(1).strip()
    elif "포스코" in t:
        out["target_company"] = "포스코"

    if "미래전략" in t or "미래 전략" in t:
        out["strategy_context"] = "2026년 미래전략 대응"

    systems: list[str] = []
    if re.search(r"mini\s*ERP|Mini\s*ERP", t, re.I):
        systems.append("Mini ERP")
    if re.search(r"\bERP\b|erp", t, re.I):
        systems.append("ERP 시스템")
    if "원가" in t:
        systems.append("원가시스템")
    if systems:
        out["target_system"] = ", ".join(dict.fromkeys(systems))

    if "추진계획서" in t:
        out["output_type"] = "추진계획서 PPT"
        if "개선" in t and "제안" in t:
            out["proposal_type"] = "개선 제안 추진계획서"
        elif "개선" in t:
            out["proposal_type"] = "개선 추진계획서"
        elif "제안" in t:
            out["proposal_type"] = "제안 추진계획서"
        else:
            out["proposal_type"] = "추진계획서"

    if re.search(r"ERP|erp", t) and ("개선" in t or "제안" in t):
        out.setdefault("likely_purpose", "시스템(ERP)·원가 등 정보계 개선 제안")
    elif "제안" in t:
        out.setdefault("likely_purpose", "제안·승인 목적")

    # 보고/제안 톤 힌트 — 목적 질문은 사용자 답변을 우선한다.
    if any(k in t for k in ("경영", "전략", "미래전략", "C-level")):
        out["likely_tone"] = "경영진 보고형 또는 컨설팅 제안서형"
    elif "제안" in t or "고객" in t:
        out["likely_tone"] = "컨설팅 제안서형"

    return out
