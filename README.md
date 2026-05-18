# AutoPM (CrewAI + PPT MVP)

AutoPM은 업무 개선 아이디어를 단순 텍스트 문서가 아니라 **발표 가능한 추진계획서 PPT**로 변환하는 Multi-Agent PM 시스템입니다. 각 Agent는 요구사항 분석, 현황 분석, 개선방안, WBS, 예산/ROI, 리스크 검토를 담당하고, **Storyline Agent**와 **Visualization Agent**가 장표 흐름과 시각 유형(`visual_type`)을 정한 뒤, **Presentation Graphics Agent**가 `graphics_spec`(도형 시퀀스)·선택적 **PNG 에셋**을 설계합니다. 최종적으로 **python-pptx** Composer가 `project_plan.pptx`에 도형·이미지를 배치합니다.

## 문제 정의

- PM 산출물(추진계획서, WBS, 예산, 리스크) 작성에 시간이 걸리고 승인용 **PPT 장표**까지 별도 작업이 필요하다.
- 단일 LLM 호출로는 섹션 간 일관성·검증 루프·**슬라이드 구조**를 동시에 맞추기 어렵다.

## 솔루션 컨셉

- **5-Layer 구조**(Presentation → Gateway → Orchestration → Tools/PPT → Data)를 코드로 유지한다.
- **Supervisor(`AutoPMFlow`)** 가 8개 Core Crew → **Critic Loop(80점, 최대 3회)** → 문서화 → **PPT 4단 Crew** → 파일 export 순으로 조율한다.
- `OPENAI_API_KEY` 가 없어도 **Fallback Markdown + Fallback PPT(10장 이상)** 로 데모가 끊기지 않게 한다.

## Multi-Agent 구조

1. PM Orchestrator → 2. Requirement Interview → 3. Business Analyst → 4. Solution Architect → 5. Development Scope → 6. WBS Planner → 7. Budget & ROI → 8. Risk → **Critic** → **Documentation** → 9. Storyline → 10. Visualization → 11. **Presentation Graphics** (`graphics_spec` / 에셋) → 12. PPT Composer(JSON 스펙) → **python-pptx**

### Visualization vs Presentation Graphics

- **Visualization Agent**: 슬라이드마다 **어떤 유형**의 그림이 맞는지(`visual_type`)와 `content` 딕셔너리를 정한다.
- **Presentation Graphics Agent**: 위 결과를 받아 **PPT에 직접 옮길 수 있는** `graphics_spec`(예: `elements` 도형 체인, `render_mode`)을 만들고, 시스템이 **matplotlib / Pillow** 등으로 PNG를 시도해 `outputs/assets/` 에 둘 수 있다.

## PPT 생성 파이프라인

- `slide_storyline_task`: 슬라이드 뼈대 JSON
- `visualization_design_task`: `visual_type` + `content` 보강
- `presentation_graphics_task`: `graphics_spec` 슬라이드별 추가
- `ppt_composition_task`: 최종 `SlideDeckSpec` JSON (`graphics_spec` 유지)
- `ppt/graphics_agent.py` + `visual_registry.py`: PNG·manifest 보강 → `outputs/visual_assets.json`
- `ppt/ppt_composer.py`: `create_project_plan_ppt()` — **이미지 → graphics elements → `visual_builder` 폴백** 순으로 배치

## Evaluation Harness (품질 안정화)

- **왜 필요한가**: Multi-Agent·PPT 체인은 API/프롬프트에 따라 산출이 흔들릴 수 있어, **단계별 루브릭(휴리스틱)**으로 점수를 내고, 코어 본문은 **Harness 개선 루프(최대 3회, `run_harness_improvement_loop`)**로 먼저 보강한 뒤 Critic이 이어진다.
- **Agent별 기준**: `src/autopm/evaluation/rubrics.py` — Requirement/Business/Solution/Scope/WBS/Budget/Risk/Storyline/Visualization/Presentation Graphics/Composer별 **통과 임계(75~85점)** 정의.
- **최종 PPT 기준**: `project_plan.pptx`, 10장+, 필수 토픽 키워드 커버리지, 시각 요소·가정 표기 등 — `FINAL_PPT_PASS_SCORE`(85) 이상이면 최종 PASS.
- **Improvement Loop**: `evaluation_score`, `failed_criteria`, `feedback_target`, `improvement_attempts` 등은 **`PPTGenerationState`**와 `outputs/evaluation_report.*`에 반영된다.
- **리포트**: Streamlit **Evaluation Report** 탭 + `outputs/evaluation_report.json` / `evaluation_report.md`.
- **API Key 없음**: Crew는 생략되어도 Fallback Markdown/PPT에 대해 **동일 Harness가 경고용 리포트**를 남긴다.

## 생성 슬라이드(최소 10장)

Executive Summary, 현재 문제점, AS-IS, TO-BE, 개발 범위, WBS/일정, 예산/ROI, 리스크, 기대효과(KPI), 결론/요청사항 (+ LLM이 확장 시 11~12장 가능)

## 출력 파일 (`outputs/`)

| 파일 | 설명 |
| --- | --- |
| `project_plan.pptx` | **핵심 산출물** |
| `slide_plan.json` | 슬라이드 스펙 |
| `project_plan.md` | 추진계획서 Markdown (§12 슬라이드 표 포함) |
| `wbs.csv`, `budget.csv`, `risk_log.csv` | 표 휴리스틱 export |
| `critic_review.md` | Critic 섹션 추출 |
| `visual_assets.json` | 슬라이드별 `render_mode`, 에셋 경로 manifest |
| `assets/*.png` | 선택적 PNG (matplotlib 또는 Pillow 폴백) |
| `evaluation_report.json` | Harness 종합 점수·미달 기준·개선 루프 메타 |
| `evaluation_report.md` | 발표/공유용 요약 Markdown |

## 대화형 입력 (Rule-based Interview Bot)

- Streamlit 첫 화면에서는 **한 문장**만 입력하면 됩니다. (예: "월마감 때 ERP 데이터 검증을 자동화하고 싶어")
- **Rule-based 챗봇**이 `src/autopm/chat/` 에서 부족한 필드만 고정 순서로 질문합니다. (LLM 자유 대화 아님)
- 수집 상태는 `InterviewState`에 저장되며, `to_autopm_inputs()`로 기존 Crew placeholder 키(`departments`, `headcount` 등)로 변환됩니다.
- 정보가 일부 비었어도 **PPT 생성하기**는 가능하며, UI에 **가정값 사용** 경고가 표시됩니다.

### Open-source LLM 초안 → OpenAI 고도화

1. `AutoPMFlow.run()` 시작 시 `generate_with_best_available_model()`이 **mock / Ollama(선택) 초안**을 만들고 `open_source_draft`로 주입합니다.
2. `OPENAI_API_KEY`가 있으면 같은 함수에서 **OpenAI로 refine**하여 `openai_refined_brief`를 채웁니다. 없으면 초안만으로 이후 단계가 진행됩니다.
3. **API Key 없음**: 8 Core + PPT Crew는 실행되지 않고, **Fallback Markdown + Fallback PPT** 로 데모가 유지됩니다(초안 Markdown은 문서에 부록으로 포함).

### 전체 워크플로 (발표용)

사용자 한 줄 입력 → Rule-based Interview Bot이 부족 정보 질문 → Interview State 완성 → Open-source/mock LLM으로 1차 추진계획 초안 생성 → OpenAI API로 고도화(선택, 키 있을 때만) → CrewAI Multi-Agent가 분석/계획/리스크/슬라이드 설계 → Presentation Graphics Agent가 장표 시각자료 설계 → PPT Composer가 `project_plan.pptx` 생성

## Guided Mode / User Decision State

- **`PPTGenerationState`** (`src/autopm/state/ppt_generation_state.py`): 인터뷰 외에 PPT 생성 전용 플래그·`user_decisions`·`revision_requests`·`selected_options`·`step_statuses`를 보관한다.
- **Guided Mode** (기본): Streamlit **User Decision Panel**에서 단계별로 승인·선택 후 `run_autopm_phased(PHASE_*, ...)` 를 호출한다 — 초안만(DRAFT_ONLY) → 톤 수정(REFINE_DRAFT) → Core+문서(CORE_DOC) → 스토리라인·비주얼·그래픽·컴포저 순.
- **Auto Mode**: `PPTGenerationState.for_auto_mode()` 프리셋을 붙여 기존과 같이 **한 번에** `run_autopm` 전체 파이프라인을 실행한다.
- 사용자 선택은 `apply_decisions_to_enriched()`를 통해 `tasks.yaml`의 `{user_decision_context}`, `{slide_deck_instruction}`, `{visual_style_instruction}`, `{visual_asset_instruction}`, `{budget_risk_emphasis}`, `{composer_user_notes}`, `{ppt_revision_notes}` 로 Agent 프롬프트에 주입된다.
- **PPT 개선 루프**: `PHASE_IMPROVE_CHAIN`이 스토리라인 이후 산출을 비우고 동일 Markdown(`workspace_markdown`) 기준으로 PPT 체인을 재실행한다(API 키 필요).

### Decision Point (UI 요약)

1. 입력 정보 확인 → 2. 1차 초안 → 3. 초안 톤/수정 → 4. Core+문서 → 5. 슬라이드 장 수 → 6. Storyline → 7. 장표 스타일 → 8. Visual Asset 방향 → 9. Visualization → 10. 승인 → 11. Graphics → 12. Composer(PPT) → 13. 사후 개선 요청

## 실행 방법 (Windows PowerShell)

```powershell
cd autopm-agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
$env:PYTHONUTF8 = "1"
streamlit run app.py
```

## 환경 변수

- `OPENAI_API_KEY` — 없으면 Core/PPT Crew 대신 Fallback + PPT fallback (초안은 mock/ollama 경로로 생성 가능)
- `OPENAI_MODEL` — 예: `gpt-4o-mini`
- `OPEN_SOURCE_LLM_PROVIDER` — `mock`(기본) / `local_open_source` / `ollama` / `ollama_optional`
- `OLLAMA_MODEL` — 예: `qwen2.5:7b` (Ollama 사용 시)
- `OLLAMA_HOST` (선택) — 기본 `http://127.0.0.1:11434`
- `AUTOPM_RATE_LIMIT_PER_MIN` (선택)

## Demo / Fallback

- API 없이도 `project_plan.pptx`, `slide_plan.json`, `project_plan.md` 가 생성된다.

## 문서

- **ARCHITECTURE.md** — 레이어·워크플로
- **CHECKLIST.md** — 검증 항목
- **AGENTS.md** — 제품 스펙 원본

## 사용 라이브러리 (장표)

- **python-pptx**: 표·도형·이미지 삽입
- **matplotlib** (선택): 막대/요약 차트 PNG — 없거나 실패 시 **Pillow** 텍스트 PNG 폴백
- **Pillow**: 폴백 PNG
- **pandas**: 데이터 처리(향후 확장)
- **networkx**: 설치만 표기, 복잡 네트워크 도식 확장용(MVP에서는 미사용 가능)

## 시각자료 유형 (`visual_type`)

`summary_cards`, `problem_cards`, `process_flow`, `before_after`, `scope_matrix`, `wbs_table`, `gantt_like_timeline`, `budget_table`, `kpi_cards`, `risk_matrix`, `org_role_map`, `architecture_block_diagram`, `swimlane_process`, `comparison_table`, `priority_matrix`, `funnel_diagram`, `roadmap_timeline`, `conclusion_box`

## Fallback 전략

- LLM/API 실패: Markdown + 기본 10장 슬라이드 덱 + `graphics_spec` 결정론 보강
- matplotlib 실패: Pillow PNG 또는 python-pptx 도형만 사용
- 그래픽 단계 전체 실패: `apply_visual` / `layout_engine` 기존 경로

## 향후 확장

- 조직 프로젝트 DB RAG, PPT 템플릿 고도화, **graphviz/networkx** 고급 도식, Jira/Confluence/Slack 연동
