# AutoPM (Deep Agents + Sub-Agent + PPT MVP)

AutoPM은 업무 개선 아이디어를 단순 텍스트 문서가 아니라 **발표 가능한 추진계획서 PPT**로 변환하는 Multi-Agent PM 시스템입니다. 각 **Parent Agent**는 요구사항 분석, 현황 분석, 개선방안, WBS, 예산/ROI, 리스크 검토를 담당하고, 그 아래 **Sub-Agent 팀**이 세분화 분석을 수행합니다. **Storyline Agent**와 **Visualization Agent**가 장표 흐름과 시각 유형(`visual_type`)을 정한 뒤, **Presentation Graphics Agent**가 `graphics_spec`·선택적 **PNG 에셋**을 설계합니다. 최종적으로 **python-pptx** Composer가 `outputs/project_plan.pptx`에 도형·이미지를 배치합니다.

> AutoPM은 업무 개선 아이디어를 단순 텍스트 문서가 아니라 발표 가능한 추진계획서 PPT로 변환하는 Multi-Agent PM 시스템입니다. 각 Agent는 요구사항 분석, 현황 분석, 개선방안, WBS, 예산/ROI, 리스크 검토를 담당하고, Storyline Agent와 Visualization Agent가 장표 흐름과 시각자료를 설계합니다. 최종적으로 PPT Composer가 python-pptx를 이용해 `project_plan.pptx` 파일을 생성합니다.

## 문제 정의

- PM 산출물(추진계획서, WBS, 예산, 리스크) 작성에 시간이 걸리고 승인용 **PPT 장표**까지 별도 작업이 필요하다.
- 단일 LLM 호출로는 섹션 간 일관성·검증 루프·**슬라이드 구조**를 동시에 맞추기 어렵다.
- 하나의 거대한 Agent 프롬프트보다 **역할별·세분화된 분석**이 품질과 재현성에 유리하다.

## 솔루션 컨셉

- **5-Layer 구조**(Presentation → Gateway → Orchestration → Tools/PPT → Data)를 코드로 유지한다.
- **Supervisor(`AutoPMFlow`)** 가 Deep Agents 파이프라인 → **Critic Loop(80점, 최대 3회)** → 문서화 → **PPT 4단계** → 파일 export 순으로 조율한다.
- 각 Parent Agent 아래 **Sub-Agent**가 `local`(Ollama 우선) / `cloud`(OpenAI 우선) tier로 나뉘어 실행되고, **synthesizer**가 통합한다.
- `OPENAI_API_KEY`·Ollama가 없어도 **rule-based fallback**으로 Markdown·PPT(10장 이상) 데모가 끊기지 않게 한다.

## 왜 PPT 생성이 핵심인가

- 승인·발표 현장에서 필요한 것은 긴 Markdown이 아니라 **장표 구조·표·도형·프로세스**가 갖춰진 `.pptx`이다.
- AutoPM은 Agent 산출을 `business_plan` → `SlideDeckSpec` JSON → `python-pptx` 렌더링으로 이어 **다운로드 가능한 PPT**를 최우선 산출물로 둔다.

## Multi-Agent 구조

### Parent Agent (12단계 + Critic + 문서화)

1. PM Orchestrator → 2. Requirement Interview → 3. Business Analyst → 4. Solution Architect → 5. Development Scope → 6. WBS Planner → 7. Budget & ROI → 8. Risk & Critic → **Critic 평가** → **Documentation** → 9. Storyline → 10. Visualization → 11. Presentation Graphics → 12. PPT Composer

### Sub-Agent 팀 (`config/subagents.yaml`)

각 Parent Agent마다 2~4개의 Sub-Agent가 순차 실행된다.

| Sub-Agent 역할 | LLM tier | 예시 |
| --- | --- | --- |
| 세분화 분석 | `local` | `gap_finder`, `as_is_mapper`, `cost_estimator` |
| 통합 synthesizer | `cloud` | `requirement_synthesizer`, `business_synthesizer` |
| Parent 최종 정리 | `cloud` | `tasks.yaml` 기대 형식(Markdown/JSON) |

실행 흐름:

```text
Sub-Agent₁(local) → Sub-Agent₂(local) → … → synthesizer(cloud)
  → Parent Agent가 tasks.yaml 형식으로 통합 → agent_outputs[task_key]
```

정의 파일: `src/autopm/config/subagents.yaml` · 실행기: `src/autopm/agents/subagent_runner.py`

### Agent 간 대화 (피어 리뷰)

다음 단계 Parent Agent가 이전 산출을 짧게 검토해 `agent_dialogue`에 기록한다. 피어 리뷰는 **`local` tier**(Ollama 우선)로 실행해 비용·지연을 줄인다.

### Visualization vs Presentation Graphics

- **Visualization Agent**: 슬라이드마다 `visual_type`과 `content` 딕셔너리를 정한다.
- **Presentation Graphics Agent**: `graphics_spec`(도형 시퀀스, `render_mode`)·선택적 PNG(`outputs/assets/`)를 설계한다.

## LLM 라우팅 (`llm_router.py`)

| tier | 우선 순위 | 용도 |
| --- | --- | --- |
| `local` | Ollama → OpenAI → fallback | Sub-Agent 세분화, Agent 간 대화 |
| `cloud` | OpenAI → Ollama → fallback | synthesizer, Parent 통합 |
| `auto` | OpenAI → Ollama → fallback | 기타 |

Streamlit 사이드바에서 OpenAI / 로컬(Ollama) / Sub-Agent 활성 여부를 확인할 수 있다.

## PPT 생성 파이프라인

```text
User Input (제목·인터뷰)
  → Deep Agents 8 Core (+ Sub-Agent 팀)
  → Agent 간 대화 · Critic Loop
  → Documentation (Markdown §1~11)
  → Storyline → Visualization → Presentation Graphics
  → SlideDeckSpec JSON → python-pptx
  → outputs/project_plan.pptx
```

단계별 태스크:

- `slide_storyline_task`: 슬라이드 뼈대 JSON
- `visualization_design_task`: `visual_type` + `content` 보강
- `presentation_graphics_task`: `graphics_spec` 슬라이드별 추가
- `ppt_composition_task`: 최종 `SlideDeckSpec` JSON
- `ppt/ppt_composer.py`: `create_project_plan_ppt()` — 이미지 → graphics elements → `visual_builder` 폴백

### Business Plan → Slide Plan → PPT 렌더링

1. **`build_business_plan()`** — 인터뷰·Agent Markdown을 `business_plan.json`으로 통합
2. **`build_slide_deck_spec()`** — 최소 10장 `SlideDeckSpec`, `visual_type`·`content` 강제 채움
3. **`validate_slide_deck_content` + `ensure_valid_deck`** — 실패 시 재생성·hardcoded 최소 덱
4. **Composer** — `layout_engine` / `visual_builder`로 표·프로세스·카드 렌더링

## 생성 슬라이드 (최소 10장)

Executive Summary, 현재 문제점, AS-IS, TO-BE, 개발 범위, WBS/일정, 예산/ROI, 리스크, 기대효과(KPI), 결론/요청사항 (+ 확장 시 Critic Review 등 11~12장)

## 출력 파일 (`outputs/`)

| 파일 | 설명 |
| --- | --- |
| `project_plan.pptx` | **핵심 산출물** |
| `business_plan.json` | Agent·fallback 통합 구조 |
| `slide_plan.json` | 슬라이드 스펙 |
| `subagent_outputs.json` | Parent별 Sub-Agent 실행 기록 |
| `agent_dialogue.json` | Agent 간 피어 리뷰 로그 |
| `content_coverage_report.json` | 슬라이드 본문·표·WBS/예산/리스크 검증 |
| `project_plan.md` | 추진계획서 Markdown |
| `wbs.csv`, `budget.csv`, `risk_log.csv` | 표 export |
| `critic_review.md` | Critic 섹션 |
| `visual_assets.json`, `assets/*.png` | 시각 에셋 manifest |
| `evaluation_report.json` / `.md` | Evaluation Harness 리포트 |

## 대화형 입력 (Rule-based Interview Bot)

- Streamlit에서 **추진계획서 주제/제목**을 중심으로 인터뷰한다. (한 줄 아이디어가 아닌 **제안·계획 제목** 중심)
- `src/autopm/chat/` Rule-based 봇이 목적·배경·문제·범위·톤 등을 순서대로 수집한다.
- `InterviewState.to_autopm_inputs()`로 Deep Agent placeholder에 매핑한다.
- 필드가 비어도 **가정값**으로 PPT 생성이 가능하다.

## Evaluation Harness

- 코어 본문은 **Harness 개선 루프(최대 3회)** 후 Critic이 이어진다.
- `src/autopm/evaluation/rubrics.py` — 단계별 통과 임계 점수
- Streamlit **Evaluation Report** 탭 + `outputs/evaluation_report.*`
- API Key 없이도 Fallback 산출에 대해 경고용 리포트를 남긴다.

## Guided Mode / User Decision State

- **`PPTGenerationState`**: 단계별 승인·수정 요청·`user_decisions`
- **Guided Mode**: `run_autopm_phased(PHASE_*)` 단계 실행
- **Auto Mode**: `run_autopm` 한 번에 전체 파이프라인
- 사용자 선택은 `apply_decisions_to_enriched()`로 `tasks.yaml` placeholder에 주입

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

### Ollama 로컬 LLM (Sub-Agent용, 선택)

```powershell
# Ollama 설치 후
ollama pull qwen2.5:7b
```

`.env` 예시:

```env
OPEN_SOURCE_LLM_PROVIDER=ollama
AUTOPM_USE_LOCAL_LLM=true
AUTOPM_ENABLE_SUBAGENTS=true
OLLAMA_MODEL=qwen2.5:7b
OLLAMA_HOST=http://127.0.0.1:11434
OPENAI_API_KEY=sk-...          # synthesizer·Parent 통합 (선택)
OPENAI_MODEL=gpt-4o-mini
```

## 환경 변수

| 변수 | 설명 |
| --- | --- |
| `OPENAI_API_KEY` | 없으면 cloud tier는 fallback; 있으면 synthesizer·Parent 통합에 사용 |
| `OPENAI_MODEL` | 예: `gpt-4o-mini` |
| `OPEN_SOURCE_LLM_PROVIDER` | `mock`(기본) / `ollama` / `ollama_optional` / `local_open_source` |
| `AUTOPM_USE_LOCAL_LLM` | `true`이면 Ollama를 local tier에 사용 |
| `AUTOPM_ENABLE_SUBAGENTS` | `false`이면 Sub-Agent 없이 Parent 단일 호출 (기본 `true`) |
| `OLLAMA_MODEL` | 예: `qwen2.5:7b` |
| `OLLAMA_HOST` | 기본 `http://127.0.0.1:11434` |
| `AUTOPM_RATE_LIMIT_PER_MIN` | (선택) Gateway rate limit |

## Demo Mode / Fallback

| 상황 | 동작 |
| --- | --- |
| API Key 없음 | Deep Agents + Sub-Agent **rule-based fallback** → PPT·Markdown·JSON 생성 |
| Ollama 없음 (`mock`) | local tier도 fallback; 데모·해커톤 오프라인 실행 가능 |
| Ollama만 | Sub-Agent·피어 리뷰는 로컬, synthesizer는 fallback 또는 Ollama |
| Ollama + OpenAI | **권장**: 로컬 세분화 + 클라우드 통합 |

반드시 생성되는 파일: `project_plan.pptx`, `project_plan.md`, `slide_plan.json` (실패 시에도 fallback 경로)

## Streamlit UI

- **Agent Progress Dashboard**: Parent Agent 12단계 진행 상태
- **Agent별 결과물**: 태스크별 Markdown/JSON
- **Sub-Agent 상세**: Sub-Agent별 `provider`(`ollama` / `openai` / `fallback`)·산출
- **Agent 간 대화**: 피어 리뷰 메시지
- **PPT Download** 등 기존 결과 탭

## 전체 워크플로 (발표용)

사용자 제목 입력 → Rule-based Interview → `to_autopm_inputs()` → (선택) mock/Ollama 초안 → (선택) OpenAI refine → **Deep Agents 8 Core + Sub-Agent 팀** → Agent 간 대화 → Critic Loop → 문서화 → Storyline → Visualization → Graphics → **project_plan.pptx**

## Vercel 배포 (랜딩 페이지)

Streamlit 앱 전체는 Vercel 서버리스에 맞지 않습니다. **`vercel-site/`** 정적 랜딩만 배포합니다.

- 본 앱 배포: [DEPLOY_STREAMLIT_DEMO.md](./DEPLOY_STREAMLIT_DEMO.md), [PUBLIC_URL_DEPLOY.md](./PUBLIC_URL_DEPLOY.md)
- [Streamlit Community Cloud](https://streamlit.io/cloud): Main file `app.py`, `requirements.txt`

## 프롬프트 (System Prompt · Few-shot)

| 파일 | 내용 |
| --- | --- |
| `src/autopm/config/system_prompts.yaml` | **전역 System Prompt** + **경계 케이스 Few-shot** (태스크·Sub-Agent·피어 리뷰) |
| `src/autopm/services/prompt_manager.py` | 프롬프트 조립 — `build_agent_system_prompt`, `build_task_user_prompt` |

- Parent Agent: **System** = global 규칙 + role/goal/backstory · **User** = Few-shot → 실제 과제
- Sub-Agent: System에 Sub-Agent Few-shot 포함 (`gap_finder`, `as_is_mapper` 등)
- 경계 예시: 제목만 입력, 일정·범위 모순, 예산 "협의", JSON 형식 오류, Critic 키 누락 등

Few-shot 예시 수치는 **복사 금지** — 형식·구조만 참고하도록 프롬프트에 명시되어 있다.

## 문서

| 파일 | 내용 |
| --- | --- |
| **ARCHITECTURE.md** | 레이어·Sub-Agent·Ollama·워크플로 |
| **CHECKLIST.md** | MVP 검증 항목 |
| **AGENTS.md** | 제품 스펙 원본 |

## 사용 라이브러리

| 패키지 | 용도 |
| --- | --- |
| `langchain`, `langchain-openai`, `langchain-ollama` | Deep Agents·LLM 라우팅 |
| `deepagents`, `langgraph` | Agent 오케스트레이션 |
| `python-pptx` | PPT 생성 |
| `streamlit` | UI |
| `matplotlib`, `Pillow` | 차트·PNG 에셋 |
| `pandas`, `pydantic`, `pyyaml` | 데이터·설정 |

## 시각자료 유형 (`visual_type`)

`summary_cards`, `problem_cards`, `process_flow`, `before_after`, `scope_matrix`, `wbs_table`, `timeline`, `budget_table`, `kpi_cards`, `risk_matrix`, `conclusion_box` 등 — `AGENTS.md` 및 `visual_registry.py` 참고

## Fallback 전략

- **Sub-Agent**: Ollama/OpenAI 불가 시 `llm_router._fallback_subagent` 규칙 기반 산출
- **Parent**: Sub-Agent 병합 후에도 짧으면 `merge_subagent_fallbacks` 사용
- **Business plan / Slide**: `build_business_plan` · `build_slide_deck_spec` · 검증 실패 시 hardcoded 최소 덱
- **PPT**: LLM JSON 실패 시 `build_fallback_slide_deck` + `layout_engine` 결정론 렌더링

## 향후 확장

- Sub-Agent별 전용 tool(RAG, 계산 엔진) 연결
- 조직 템플릿 PPT·브랜드 테마
- graphviz/networkx 고급 도식
- Jira/Confluence/Slack 연동
