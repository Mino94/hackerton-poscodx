"""AutoPM MCP Server — stdio로 PM 도구를 외부 Agent(Cursor 등)에 노출한다."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from autopm.mcp.registry import (
    tool_estimate_cost,
    tool_extract_proposal_info,
    tool_fp_estimate,
    tool_gantt_outline,
    tool_generate_interview_questions,
    tool_mermaid_process,
    tool_normalize_input,
    tool_rag_search,
    tool_read_slide_plan,
)

mcp = FastMCP(
    "autopm",
    instructions=(
        "AutoPM PM 추진계획서 Multi-Agent용 도구. "
        "RAG 검색, 비용 추정, Mermaid 프로세스·Gantt, slide_plan 조회를 제공한다."
    ),
)


@mcp.tool()
def rag_search(query: str) -> str:
    """사내 추진계획서 표준·가이드 RAG 검색(Chroma/키워드)."""
    return tool_rag_search(query)


@mcp.tool()
def retrieve_reference_context(query: str) -> str:
    """사내 표준 양식·가이드에서 관련 컨텍스트 RAG 검색."""
    return tool_rag_search(query)


@mcp.tool()
def extract_proposal_info(user_input: str) -> str:
    """추진계획서 제목에서 회사명·전략·시스템·범위 JSON 추출."""
    return tool_extract_proposal_info(user_input)


@mcp.tool()
def generate_interview_questions(extracted_info: str) -> str:
    """추출 정보 기반 인터뷰 보완 질문 5개 JSON 배열."""
    return tool_generate_interview_questions(extracted_info)


@mcp.tool()
def estimate_cost(monthly_hours: str = "", headcount: str = "", budget_cap: str = "") -> str:
    """월 소요·인원·예산으로 비용·절감 힌트(가정) 산출."""
    return tool_estimate_cost(monthly_hours, headcount, budget_cap)


@mcp.tool()
def fp_estimate(function_points: int | None = None) -> str:
    """FP 산정 placeholder."""
    return tool_fp_estimate(function_points)


@mcp.tool()
def mermaid_process(steps_csv: str = "") -> str:
    """쉼표 구분 프로세스 단계 → Mermaid flowchart."""
    return tool_mermaid_process(steps_csv)


@mcp.tool()
def gantt_outline(title: str = "", weeks: int = 4) -> str:
    """Mermaid Gantt 일정 템플릿."""
    return tool_gantt_outline(title, weeks)


@mcp.tool()
def normalize_input(text: str) -> str:
    """붙여넣기 텍스트 정규화."""
    return tool_normalize_input(text)


@mcp.tool()
def read_slide_plan() -> str:
    """outputs/slide_plan.json 요약."""
    return tool_read_slide_plan()


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
