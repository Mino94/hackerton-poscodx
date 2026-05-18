"""Pydantic 입력 모델 — Streamlit 폼과 Crew 입력을 동일한 스키마로 맞춘다."""

from __future__ import annotations

from pydantic import BaseModel, Field


class IdeaInput(BaseModel):
    """레거시 폼용 — 신규는 InterviewState.to_autopm_inputs()가 proposal 중심으로 내보낸다."""

    proposal_title: str = Field(default="", description="추진계획서 주제/제목")
    idea_title: str = Field(default="", description="과제 제목(레거시 alias)")
    current_process: str = Field(default="", description="현재 업무 방식(합성 가능)")
    pain_points: str = Field(default="", description="문제점(레거시)")
    departments: str = Field(default="", description="관련 부서")
    monthly_hours: str = Field(default="", description="월 소요 시간")
    headcount: str = Field(default="", description="관련 인원")
    goals: str = Field(default="", description="목표(합성)")
    target_timeline: str = Field(default="", description="희망 일정")
    budget_range: str = Field(default="", description="예산 범위")

    def to_crew_inputs(self) -> dict[str, str]:
        # CrewAI 템플릿과 맞추기 — proposal_title이 있으면 idea_title에 미러링한다.
        title = self.proposal_title or self.idea_title
        return {
            "proposal_title": title,
            "idea_title": title,
            "current_process": self.current_process,
            "pain_points": self.pain_points,
            "departments": self.departments,
            "monthly_hours": self.monthly_hours,
            "headcount": self.headcount,
            "goals": self.goals,
            "target_timeline": self.target_timeline,
            "budget_range": self.budget_range,
        }
