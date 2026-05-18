"""visualization_generator — Mermaid/Gantt 문자열 생성 훅."""

from __future__ import annotations


def mermaid_simple_flow(steps: list[str]) -> str:
    """간단한 흐름도 — Streamlit/문서에 그대로 붙일 수 있다."""
    lines = ["flowchart LR"]
    for i, s in enumerate(steps):
        nid = f"S{i}"
        lines.append(f'    {nid}["{s[:40]}"]')
    for i in range(len(steps) - 1):
        lines.append(f"    S{i} --> S{i + 1}")
    return "\n".join(lines)


def markdown_gantt_placeholder(title: str, weeks: int = 4) -> str:
    """Mermaid gantt 템플릿 — 실제 일정은 Agent 산출물과 맞춰 조정한다."""
    return "\n".join(
        [
            "```mermaid",
            "gantt",
            f"    title {title}",
            "    dateFormat  YYYY-MM-DD",
            "    section Phase",
            f"    분석           :a1, 2026-01-01, 7d",
            f"    설계           :a2, after a1, 7d",
            f"    구현/파일럿    :a3, after a2, " + f"{max(1, weeks - 2)}w",
            "```",
        ]
    )
