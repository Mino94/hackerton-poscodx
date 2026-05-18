# AGENTS.md

## Project Name

AutoPM

## Mission

AutoPM은 업무 개선 아이디어를 입력하면 Multi-Agent PM 팀이 협업하여 **최종 추진계획서 PPT(.pptx)** 를 자동 생성하는 해커톤용 CrewAI MVP다.

가장 중요한 결과물은 Markdown 문서가 아니라, **설명에 맞는 장표 구조와 그림/도표가 포함된 발표 가능한 PPT 파일**이다.

핵심 컨셉:

> 업무 아이디어 → Agent 분석 → 슬라이드 스토리라인 설계 → 시각자료 구성 → 최종 PPT 생성

---

## Product Goal

기존 AI 문서 생성기는 텍스트 중심으로 결과를 만든다.

AutoPM은 다음 산출물을 자동 생성한다.

1. 추진계획서 PPTX
2. 슬라이드별 스토리라인
3. AS-IS / TO-BE 장표
4. WBS / 추진 일정 장표
5. 예산 / ROI 장표
6. 리스크 매트릭스 장표
7. 기대효과 장표
8. Critic Review
9. Markdown 중간 산출물
10. CSV 보조 산출물

최종 핵심 파일:

```txt
outputs/project_plan.pptx
```

---

## Tech Stack

- Python
- CrewAI
- Streamlit
- OpenAI API
- python-pptx
- pandas
- python-dotenv
- pydantic
- pyyaml
- matplotlib, optional
- DB, 로그인, 결제, 실제 사내 시스템 연동은 구현하지 않는다.
- 오늘 해커톤 MVP로 로컬 실행 가능한 수준을 목표로 한다.

---

## Execution Command

```bash
pip install -r requirements.txt
streamlit run app.py
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
streamlit run app.py
```

---

## Environment Variables

`.env.example` 파일을 만들고 아래 내용을 포함한다.

```env
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
```

API Key가 없어도 Demo Mode fallback으로 실행되어야 한다.

---

## Required Project Structure

현재 코드가 이미 있다면 새로 갈아엎지 말고 분석 후 개선한다.

최종 구조는 아래에 최대한 맞춘다.

```txt
autopm-crewai/
  AGENTS.md
  .env.example
  requirements.txt
  README.md
  ARCHITECTURE.md
  CHECKLIST.md
  app.py
  outputs/
    project_plan.pptx
    project_plan.md
    slide_plan.json
    wbs.csv
    budget.csv
    risk_log.csv
    critic_review.md
  src/
    autopm/
      __init__.py
      crew.py
      models.py
      config/
        agents.yaml
        tasks.yaml
      ppt/
        __init__.py
        slide_schema.py
        ppt_composer.py
        layout_engine.py
        visual_builder.py
        theme.py
      services/
        __init__.py
        export_service.py
        llm_router.py
        prompt_manager.py
        observability.py
      tools/
        __init__.py
        calculation_engine.py
        rag_engine.py
        document_parser.py
        visualization_generator.py
      knowledge/
        sample_project_template.md
```

---

## Core Requirement

이번 MVP의 우선순위는 아래 순서다.

1. 실행 안정성
2. 슬라이드 구조 생성
3. PPTX 파일 생성
4. Streamlit 다운로드 기능
5. PPT 장표 안에 들어가는 표/도형/프로세스/카드 시각화
6. 결과 품질 개선
7. 프론트 디자인 개선

Markdown 출력은 보조 산출물이다.  
최종 결과물은 반드시 `.pptx`여야 한다.

---

## Agent Architecture

AutoPM은 기존 7개 PM Agent에 PPT 생성 전용 3개 Agent를 추가한다.

총 구조:

- Supervisor / PM Orchestrator
- 7 Core PM Agents
- 3 PPT Production Agents

---

# 1. Supervisor / PM Orchestrator

## Role

PM Orchestrator Agent

## Goal

전체 작업 흐름을 관리하고, 각 Agent의 산출물을 통합하여 PPT 생성까지 이어지도록 조정한다.

## Responsibilities

- 사용자 입력 분석
- 전체 산출물 구조 정의
- Agent 실행 순서 관리
- 최종 슬라이드 구성 검토
- Critic 결과에 따라 보완 필요 여부 판단
- PPT Composer Agent 호출

---

# 2. Core PM Agents

## 2.1 Requirement Interview Agent

### Role

Requirement Interview Agent

### Goal

사용자 입력에서 부족한 정보를 식별하고 합리적인 가정값과 추가 질문을 생성한다.

### Output

- 입력 요약
- 누락 정보
- 추가 확인 질문
- 합리적 가정값

---

## 2.2 Business Analyst Agent

### Role

Business Analyst Agent

### Goal

현재 업무 방식, AS-IS 프로세스, 문제점, 이해관계자 영향도를 분석한다.

### Output

- 현재 문제점
- AS-IS 프로세스
- Pain Point
- 이해관계자 영향도

---

## 2.3 Solution Architect Agent

### Role

Solution Architect Agent

### Goal

TO-BE 프로세스, 개선방안, 자동화 범위, 시스템 구성 방향을 정의한다.

### Output

- TO-BE 프로세스
- 개선 방향
- 시스템 구성 방향
- 자동화 범위

---

## 2.4 Development Scope Agent

### Role

Development Scope Agent

### Goal

추진 과제의 개발 범위, 포함 기능, 제외 범위, 주요 모듈을 정의한다.

### Output

- 개발 범위
- 포함 기능
- 제외 기능
- 주요 모듈
- MVP 범위

---

## 2.5 WBS Planner Agent

### Role

WBS Planner Agent

### Goal

단계별 추진 일정, 마일스톤, 담당 역할, 산출물을 WBS 형태로 생성한다.

### Output

- WBS
- 단계별 일정
- 마일스톤
- 담당 조직
- 산출물

---

## 2.6 Budget & ROI Agent

### Role

Budget & ROI Agent

### Goal

예상 비용, 기대효과, 시간 절감, 인건비 절감, KPI를 산출한다.

### Output

- 예산 항목
- 예상 비용
- ROI
- KPI
- 정량 기대효과

모든 수치는 반드시 “예상” 또는 “가정”으로 표시한다.

---

## 2.7 Risk & Critic Agent

### Role

Risk & Critic Agent

### Goal

리스크 매트릭스를 만들고, 전체 추진계획서의 논리성, 완결성, 실행 가능성을 검토한다.

### Output

- 리스크 목록
- 발생 가능성
- 영향도
- 대응 방안
- 품질 점수
- 누락 항목
- 보완 제안
- 최종 의견

---

# 3. PPT Production Agents

## 3.1 Storyline / Slide Planning Agent

### Role

Storyline / Slide Planning Agent

### Goal

추진계획서 내용을 발표 가능한 PPT 장표 흐름으로 재구성한다.

### Responsibilities

- 전체 슬라이드 개수 결정
- 슬라이드별 제목 정의
- 각 슬라이드의 핵심 메시지 작성
- 각 슬라이드의 목적 작성
- 각 슬라이드에 적합한 레이아웃 타입 지정
- 각 슬라이드에 필요한 시각자료 타입 지정

### Output

슬라이드 단위 구조화 데이터.

---

## 3.2 Visualization Agent

### Role

Visualization Agent

### Goal

각 슬라이드의 설명에 맞는 그림, 표, 도형, 프로세스, 매트릭스, KPI 카드 구성을 설계한다.

### Responsibilities

- AS-IS / TO-BE 프로세스 다이어그램 설계
- WBS 일정표 설계
- 예산/ROI 표 설계
- KPI 카드 설계
- 리스크 매트릭스 설계
- Before/After 비교 구조 설계
- 슬라이드별 visual_type 지정

### Visual Types

아래 visual_type을 사용한다.

```txt
summary_cards
problem_cards
process_flow
before_after
scope_matrix
wbs_table
timeline
budget_table
kpi_cards
risk_matrix
conclusion_box
```

---

## 3.3 PPT Composer Agent

### Role

PPT Composer Agent

### Goal

슬라이드 구조화 데이터를 기반으로 실제 `.pptx` 파일을 생성한다.

### Responsibilities

- python-pptx 사용
- 슬라이드 생성
- 제목/부제/본문 배치
- 표 생성
- 도형 생성
- 프로세스 흐름 그림 생성
- KPI 카드 생성
- 리스크 매트릭스 생성
- PPT 파일 저장
- Streamlit 다운로드 가능하도록 파일 경로 반환

### Required Output

```txt
outputs/project_plan.pptx
```

---

## Required Slide Structure

최소 10장의 PPT를 생성한다.

```txt
1. Executive Summary
2. 현재 문제점
3. AS-IS 프로세스
4. TO-BE 프로세스
5. 개발 범위
6. WBS / 추진 일정
7. 예산 및 ROI
8. 리스크 및 대응방안
9. 기대효과
10. 결론 / 요청사항
```

가능하면 11~12장까지 확장해도 된다.

추가 가능 슬라이드:

```txt
11. Critic Review
12. 추가 확인 질문
```

---

## Slide Schema

슬라이드 데이터는 반드시 구조화된 형태로 만든다.

`src/autopm/ppt/slide_schema.py`에 Pydantic 모델 또는 dataclass로 정의한다.

예시 구조:

```python
class SlideSpec(BaseModel):
    slide_no: int
    title: str
    objective: str
    key_message: str
    layout_type: str
    visual_type: str
    content: dict
    notes: str | None = None

class SlideDeckSpec(BaseModel):
    project_title: str
    subtitle: str
    slides: list[SlideSpec]
```

LLM 결과가 JSON으로 깨질 수 있으므로, JSON 파싱 실패 시 fallback slide deck을 생성한다.

---

## PPT Design Requirements

PPT는 완벽한 디자인보다 **업무 보고용 장표로 보이는 구조**가 중요하다.

기본 디자인 방향:

- 16:9 와이드 슬라이드
- 흰색 배경
- 짙은 남색 제목
- 회색 보조 텍스트
- 카드형 박스
- 표와 도형 중심
- 아이콘 대신 간단한 도형 사용
- 장표마다 핵심 메시지 1개 명확히 표시

각 슬라이드에는 아래 중 하나 이상의 시각요소가 들어가야 한다.

- 카드
- 표
- 프로세스 화살표
- 2열 비교
- 일정표
- KPI 숫자 카드
- 리스크 매트릭스
- 결론 박스

---

## PPT Layout Rules

`src/autopm/ppt/layout_engine.py`에 레이아웃 함수를 구현한다.

필수 함수 예시:

```python
def add_title(slide, title: str, subtitle: str | None = None):
    pass

def add_key_message(slide, message: str):
    pass

def add_summary_cards(slide, cards: list[dict]):
    pass

def add_problem_cards(slide, problems: list[str]):
    pass

def add_process_flow(slide, steps: list[str]):
    pass

def add_before_after(slide, before: list[str], after: list[str]):
    pass

def add_scope_matrix(slide, included: list[str], excluded: list[str]):
    pass

def add_wbs_table(slide, rows: list[dict]):
    pass

def add_budget_table(slide, rows: list[dict]):
    pass

def add_kpi_cards(slide, kpis: list[dict]):
    pass

def add_risk_matrix(slide, risks: list[dict]):
    pass

def add_conclusion_box(slide, text: str):
    pass
```

---

## PPT Composer Requirements

`src/autopm/ppt/ppt_composer.py`에 아래 함수를 구현한다.

```python
def create_project_plan_ppt(deck_spec: dict, output_path: str = "outputs/project_plan.pptx") -> str:
    """
    deck_spec을 기반으로 PPTX 파일을 생성하고 파일 경로를 반환한다.
    """
```

요구사항:

- outputs 폴더가 없으면 생성한다.
- PPTX 생성 실패 시 예외를 잡고 fallback PPT를 생성한다.
- 각 slide.visual_type에 따라 적절한 layout_engine 함수를 호출한다.
- 최소 10장 생성한다.
- 결과 파일 경로를 반환한다.

---

## Export Requirements

아래 파일을 생성한다.

```txt
outputs/project_plan.pptx
outputs/project_plan.md
outputs/slide_plan.json
outputs/wbs.csv
outputs/budget.csv
outputs/risk_log.csv
outputs/critic_review.md
```

PPTX는 필수다.  
CSV/Markdown은 실패해도 앱이 죽으면 안 된다.

---

## Streamlit UI Requirements

`app.py`는 Streamlit 기반 UI를 제공한다.

## Header

```txt
AutoPM
업무 아이디어를 발표 가능한 추진계획서 PPT로 바꾸는 Multi-Agent PM 팀
```

## Input Form

아래 입력 필드를 만든다.

- 아이디어 제목
- 현재 업무 방식
- 현재 문제점
- 관련 부서
- 월 소요 시간
- 관련 인원
- 목표
- 희망 일정
- 예산 범위

## Default Sample Values

폼에는 아래 샘플값을 기본으로 넣는다.

```txt
제목:
ERP 월마감 데이터 검증 자동화

현재 업무 방식:
월마감 시 ERP에서 품목 단가, 재고 수량, BOM 누락 여부를 엑셀로 다운로드하여 수작업 검증한다.

문제점:
검증 시간이 오래 걸리고 담당자별 기준이 달라 오류가 누락될 수 있다.

관련 부서:
회계팀, 생산관리팀, IT팀

월 소요 시간:
40

관련 인원:
3

목표:
월마감 데이터 검증 시간을 줄이고 오류를 사전에 탐지한다.

희망 일정:
4주

예산 범위:
500만 원 이하
```

## Generate Button

버튼 문구:

```txt
🚀 AutoPM PPT 생성하기
```

버튼 클릭 시:

1. CrewAI Agent 실행
2. 슬라이드 스토리라인 생성
3. 시각자료 타입 생성
4. PPTX 생성
5. Streamlit 화면에 다운로드 버튼 표시

---

## Agent Progress Panel

Generate 클릭 시 아래 단계가 보이게 한다.

```txt
[1/10] PM Orchestrator: 전체 추진계획 구조 설계
[2/10] Requirement Interview: 요구사항 및 누락 정보 분석
[3/10] Business Analyst: AS-IS / Pain Point 분석
[4/10] Solution Architect: TO-BE / 개선 방향 설계
[5/10] Development Scope: 개발 범위 정의
[6/10] WBS Planner: 추진 일정 생성
[7/10] Budget & ROI: 예산 및 기대효과 산출
[8/10] Risk & Critic: 리스크 및 품질 검토
[9/10] Storyline Agent: PPT 장표 흐름 설계
[10/10] PPT Composer: 최종 PPTX 생성
```

---

## Result Tabs

결과 화면은 탭으로 구성한다.

- PPT 다운로드
- 슬라이드 구성
- 추진계획서 Markdown
- WBS
- 예산/ROI
- 리스크
- Critic Review
- Raw JSON

## PPT Download Tab

반드시 아래를 제공한다.

- 생성된 PPT 파일명
- 슬라이드 개수
- 다운로드 버튼

Streamlit 예시:

```python
with open(pptx_path, "rb") as f:
    st.download_button(
        label="📥 추진계획서 PPT 다운로드",
        data=f,
        file_name="project_plan.pptx",
        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )
```

---

## Fallback / Demo Mode

API Key가 없어도 앱이 죽으면 안 된다.

조건:

- OPENAI_API_KEY가 없을 때
- CrewAI 실행 실패
- JSON 파싱 실패
- PPT 생성 실패

위 상황에서는 fallback 데이터를 사용한다.

Fallback에서도 반드시 생성되어야 하는 것:

```txt
outputs/project_plan.pptx
outputs/project_plan.md
outputs/slide_plan.json
```

Fallback PPT는 샘플 시나리오 기반으로 최소 10장 생성한다.

---

## Required Output Markdown Structure

PPT와 별도로 `outputs/project_plan.md`도 생성한다.

```md
# AutoPM 추진계획서

## 1. Executive Summary

## 2. 추진 배경

## 3. 현재 문제점

## 4. AS-IS

## 5. TO-BE

## 6. 개발 범위

## 7. WBS

| 단계 | 작업 | 기간 | 담당 | 산출물 |
| --- | --- | --- | --- | --- |

## 8. 예산 및 ROI

| 항목 | 예상 비용 | 설명 |
| --- | --- | --- |

## 9. KPI

| 지표 | 현재 | 목표 |
| --- | --- | --- |

## 10. 리스크 매트릭스

| 리스크 | 발생 가능성 | 영향도 | 대응 방안 |
| --- | --- | --- | --- |

## 11. Critic Review

- 품질 점수:
- 누락 항목:
- 보완 제안:
- 최종 의견:

## 12. PPT 슬라이드 구성

| 슬라이드 | 제목 | 핵심 메시지 | 시각자료 |
| --- | --- | --- | --- |
```

---

## CrewAI Requirements

`src/autopm/config/agents.yaml`과 `tasks.yaml`을 PPT 생성형 AutoPM 기준으로 업데이트한다.

## Agents

최소 아래 Agent를 정의한다.

1. pm_orchestrator_agent
2. requirement_interview_agent
3. business_analyst_agent
4. solution_architect_agent
5. development_scope_agent
6. wbs_planner_agent
7. budget_roi_agent
8. risk_critic_agent
9. storyline_slide_planning_agent
10. visualization_agent
11. ppt_composer_agent

PPT Composer Agent는 실제 파일 생성은 LLM이 아니라 Python 코드가 수행한다.  
Agent는 slide spec을 만들고, `ppt_composer.py`가 이를 실제 PPTX로 변환한다.

---

## Tasks

최소 아래 Task를 정의한다.

1. orchestrate_task
2. requirement_task
3. business_analysis_task
4. solution_design_task
5. development_scope_task
6. wbs_task
7. budget_roi_task
8. risk_critic_task
9. slide_storyline_task
10. visualization_design_task
11. ppt_composition_task

---

## Structured Output Requirement

CrewAI 결과는 최종적으로 아래 구조로 변환되어야 한다.

```json
{
  "project_title": "ERP 월마감 데이터 검증 자동화",
  "executive_summary": "",
  "business_sections": {
    "background": "",
    "current_problems": [],
    "as_is": [],
    "to_be": [],
    "scope_included": [],
    "scope_excluded": []
  },
  "wbs": [
    {
      "phase": "1단계",
      "task": "현행 업무 분석",
      "duration": "1주",
      "owner": "IT/현업",
      "deliverable": "AS-IS 분석서"
    }
  ],
  "budget": [
    {
      "item": "분석 및 설계",
      "cost": "100만 원",
      "description": "현행 업무 분석 및 요구사항 정의"
    }
  ],
  "kpis": [
    {
      "name": "월 검증 소요 시간",
      "current": "40시간",
      "target": "12시간"
    }
  ],
  "risks": [
    {
      "risk": "ERP 데이터 품질 미흡",
      "probability": "Medium",
      "impact": "High",
      "response": "검증 룰 적용 전 데이터 정합성 점검"
    }
  ],
  "critic_review": {
    "score": 85,
    "missing_items": [],
    "suggestions": [],
    "final_opinion": ""
  },
  "slide_deck": {
    "project_title": "",
    "subtitle": "",
    "slides": []
  }
}
```

JSON 파싱 실패 시 fallback 구조를 반환한다.

---

## Requirements.txt

`requirements.txt`에는 최소 아래를 포함한다.

```txt
crewai
crewai-tools
streamlit
python-dotenv
pydantic
pyyaml
openai
python-pptx
pandas
matplotlib
```

---

## README.md Requirements

README.md에 반드시 아래 내용을 포함한다.

1. AutoPM 소개
2. 문제 정의
3. 솔루션 컨셉
4. 왜 PPT 생성이 핵심인지
5. Multi-Agent 구조
6. PPT 생성 파이프라인
7. 생성되는 슬라이드 목록
8. 출력 파일 목록
9. 실행 방법
10. 환경변수 설정
11. Demo Mode / Fallback 설명
12. 향후 확장 방향

README에 들어갈 핵심 문구:

```txt
AutoPM은 업무 개선 아이디어를 단순 텍스트 문서가 아니라 발표 가능한 추진계획서 PPT로 변환하는 Multi-Agent PM 시스템입니다. 각 Agent는 요구사항 분석, 현황 분석, 개선방안, WBS, 예산/ROI, 리스크 검토를 담당하고, Storyline Agent와 Visualization Agent가 장표 흐름과 시각자료를 설계합니다. 최종적으로 PPT Composer가 python-pptx를 이용해 project_plan.pptx 파일을 생성합니다.
```

---

## ARCHITECTURE.md Requirements

ARCHITECTURE.md에는 아래 흐름을 설명한다.

```txt
User Input
→ CrewAI PM Agents
→ Business Plan Structure
→ Slide Storyline
→ Visualization Plan
→ PPT Composer
→ project_plan.pptx
```

또한 아래 표를 포함한다.

| Layer | 역할 | MVP 구현 |
| --- | --- | --- |
| Input Layer | 업무 아이디어 입력 | Streamlit Form |
| Agent Layer | 추진계획서 내용 생성 | CrewAI Agents |
| Storyline Layer | 장표 흐름 설계 | Slide Planning Agent |
| Visualization Layer | 장표별 그림/표 설계 | Visualization Agent |
| Composition Layer | PPT 파일 생성 | python-pptx |
| Output Layer | 산출물 다운로드 | Streamlit Download |

---

## CHECKLIST.md Requirements

CHECKLIST.md에 검증 항목을 작성한다.

필수 체크리스트:

```md
# AutoPM PPT MVP Checklist

- [ ] streamlit run app.py 실행 가능
- [ ] 샘플 입력값 기본 제공
- [ ] Generate 버튼 동작
- [ ] CrewAI Agent 실행 또는 fallback 실행
- [ ] slide_plan.json 생성
- [ ] project_plan.pptx 생성
- [ ] project_plan.md 생성
- [ ] wbs.csv 생성
- [ ] budget.csv 생성
- [ ] risk_log.csv 생성
- [ ] Streamlit에서 PPT 다운로드 가능
- [ ] PPT가 최소 10장 이상 생성됨
- [ ] AS-IS / TO-BE 장표가 있음
- [ ] WBS 장표가 있음
- [ ] 예산/ROI 장표가 있음
- [ ] 리스크 매트릭스 장표가 있음
- [ ] API Key 없이도 fallback PPT 생성 가능
```

---

## Sample Demo Scenario

기본 샘플은 아래로 유지한다.

```txt
ERP 월마감 데이터 검증 자동화

월마감 시 ERP에서 품목 단가, 재고 수량, BOM 누락 여부를 엑셀로 다운로드하여 수작업 검증한다.
검증 시간이 오래 걸리고 담당자별 기준이 달라 오류가 누락될 수 있다.
관련 부서는 회계팀, 생산관리팀, IT팀이다.
월 소요 시간은 40시간이고 관련 인원은 3명이다.
목표는 월마감 데이터 검증 시간을 줄이고 오류를 사전에 탐지하는 것이다.
희망 일정은 4주이며 예산 범위는 500만 원 이하이다.
```

---

## Important Constraints

- 오늘 해커톤 MVP가 목적이다.
- 최종 산출물은 반드시 PPTX다.
- Markdown은 보조 산출물이다.
- PPT 디자인을 완벽하게 만들려고 하지 말고, 먼저 실제 파일이 생성되게 하라.
- PPT 안에는 슬라이드별 설명에 맞는 표/그림/도형이 들어가야 한다.
- 로그인, DB, 결제, 실제 사내 시스템 연동은 하지 않는다.
- 복잡한 이미지 생성 AI는 사용하지 않는다.
- python-pptx의 도형, 표, 텍스트 박스, 선, 화살표를 활용한다.
- 실행 안정성이 디자인보다 우선이다.
- API Key가 없어도 fallback PPT가 생성되어야 한다.
- Cursor는 현재 코드를 먼저 분석하고, 기존 기능을 유지하면서 개선해야 한다.

---

## Completion Criteria

작업 완료 조건은 아래와 같다.

1. `pip install -r requirements.txt` 가능
2. `streamlit run app.py` 가능
3. 샘플 데이터가 기본 입력되어 있음
4. Generate 클릭 가능
5. Agent 실행 또는 fallback 실행 가능
6. 최소 10장짜리 PPTX 생성
7. `outputs/project_plan.pptx` 생성
8. Streamlit에서 PPT 다운로드 가능
9. `outputs/slide_plan.json` 생성
10. `outputs/project_plan.md` 생성
11. `outputs/wbs.csv` 생성
12. `outputs/budget.csv` 생성
13. `outputs/risk_log.csv` 생성
14. PPT 안에 AS-IS/TO-BE, WBS, 예산/ROI, 리스크 장표가 포함됨
15. README.md 업데이트
16. ARCHITECTURE.md 생성
17. CHECKLIST.md 생성
18. API Key가 없어도 Demo Mode로 PPT 생성 가능

---

## Final Instruction for Cursor Agent

이 AGENTS.md를 기준으로 현재 AutoPM CrewAI MVP를 **PPT 생성형 AutoPM**으로 개선해라.

새로 갈아엎지 말고 현재 코드를 먼저 분석하라.

작업 우선순위는 다음과 같다.

1. 현재 코드 구조 파악
2. PPT 생성에 필요한 의존성 추가
3. 슬라이드 데이터 구조 정의
4. PPT Composer 구현
5. fallback slide deck 구현
6. CrewAI 결과를 slide deck으로 변환
7. Streamlit에서 PPT 다운로드 구현
8. outputs 파일 생성
9. README / ARCHITECTURE / CHECKLIST 업데이트
10. 실행 검증

작업 완료 후 아래 형식으로 보고하라.

## 수정한 파일 목록

## PPT 생성 구조

## 생성되는 슬라이드 목록

## 출력 파일 목록

## 실행 방법

## 검증 결과

## 남은 개선점

## Agent Progress UI Requirement

Streamlit UI에는 10개 Agent의 진행 상태를 한눈에 볼 수 있는 Agent Progress Dashboard를 포함한다.

표시 대상 Agent:

1. PM Orchestrator Agent
2. Requirement Interview Agent
3. Business Analyst Agent
4. Solution Architect Agent
5. Development Scope Agent
6. WBS Planner Agent
7. Budget & ROI Agent
8. Risk & Critic Agent
9. Storyline / Slide Planning Agent
10. Visualization Agent
11. Presentation Graphics Agent
12. PPT Composer Agent

각 Agent는 아래 상태를 가진다.

- pending: 대기
- running: 실행 중
- complete: 완료
- error: 오류

UI 요구사항:

- 각 Agent를 카드 형태로 표시한다.
- 전체 Progress Bar를 표시한다.
- 완료된 Agent 수 / 전체 Agent 수를 표시한다.
- Generate 버튼 클릭 시 순차적으로 상태가 변경되는 것처럼 보여준다.
- 오류 발생 시 해당 Agent를 error로 표시하고 fallback PPT 생성을 수행한다.
- PPT 생성 완료 후 PPT Composer Agent는 complete 상태가 되어야 한다.