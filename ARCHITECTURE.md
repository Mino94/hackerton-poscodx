# AutoPM 아키텍처 (Deep Agents + Sub-Agent + PPT MVP)

이 문서는 **PPT 생성형 AutoPM** 기준으로 현재 레포 구현을 설명합니다.

## Sub-Agent · 로컬 LLM

각 Parent Agent(`agents.yaml`) 아래 **Sub-Agent 팀**이 `config/subagents.yaml`에 정의된다.

| tier | 우선 LLM | 용도 |
| --- | --- | --- |
| `local` | Ollama (`langchain-ollama`) | 세분화 분석·피어 리뷰 |
| `cloud` | OpenAI | synthesizer 통합·최종 형식 정리 |
| `auto` | OpenAI → Ollama → rule fallback | 기타 |

실행 순서: Sub-Agent 순차 실행 → Parent가 `tasks.yaml` 기대 형식으로 통합(`subagent_runner.py`).  
산출은 `AutoPMState.subagent_outputs` · `outputs/subagent_outputs.json`에 기록된다.

환경 변수: `OPEN_SOURCE_LLM_PROVIDER=ollama`, `AUTOPM_USE_LOCAL_LLM=true`, `AUTOPM_ENABLE_SUBAGENTS=true`(기본).

## MCP (Model Context Protocol)

PM Agent가 **구조화된 도구**를 호출해 RAG·비용 추정·Mermaid·slide_plan을 참고한다.

| 구성 | 경로 | 역할 |
| --- | --- | --- |
| MCP Server | `python -m autopm.mcp` (stdio) | Cursor·외부 클라이언트용 |
| Tool Registry | `src/autopm/mcp/registry.py` | in-process·서버 공용 핸들러 |
| Agent Policy | `config/mcp_agent_tools.yaml` | Agent/Task별 도구 매핑 |
| Integration | `mcp/integration.py` | `invoke_for_agent()` prefetch + 선택 ReAct |

**실행 모드**

1. **Prefetch (기본, `AUTOPM_ENABLE_MCP=true`)** — Agent 호출 전 in-process로 도구 실행 → 프롬프트에 결과 블록 삽입 (`deep_runner`, `subagent_runner`)
2. **ReAct (`AUTOPM_MCP_REACT=true`)** — OpenAI `bind_tools` + `langchain-mcp-adapters` stdio 클라이언트로 LLM이 도구 직접 호출

도구: `rag_search`, `estimate_cost`, `fp_estimate`, `mermaid_process`, `gantt_outline`, `normalize_input`, `read_slide_plan`

## Orchestrator–Worker (LangGraph `Send`)

8 Core PM 파이프라인은 **`orchestrator_worker_graph.py`** 에서 LangGraph로 실행한다.

```text
START → orchestrator → conditional_edges(dispatch_workers)
         ↓ Send(worker, { idx, autopm_state, … })  × 8단계 동적 생성
       worker → execute_pipeline_step() → orchestrator → … → END
```

- **Orchestrator**: `current_idx`를 보고 다음 Worker에 `Send()` 디스패치, Supervisor 체크포인트
- **Worker**: Parent Agent + Sub-Agent + 피어 대화 1단계 처리 후 `current_idx += 1`
- 공통 로직: `deep_pipeline.execute_pipeline_step()` (그래프·레거시 for-loop 공유)
- 끄기: `AUTOPM_USE_SEND_GRAPH=false` → 기존 for-loop

## 전체 워크플로

```text
User Input (Streamlit)
  → Interview (Rule-based) — Harness: 입력 충분성
  → Draft (mock/OpenAI) — Harness: 초안 길이·구조
  → Gateway (rate limit / auth 스텁)
  → AutoPMFlow: 8 Core PM Agents (Orchestrator–Worker Send + Sub-Agent 팀)
  → Evaluation Harness — 코어 산출 루브릭 + Improvement Loop (최대 3회)
  → Critic Agent (점수 / FEEDBACK_TARGET) + Self-Correction (최대 3회, 80점 Gate)
  → Documentation Agent → Markdown §1~11
  → Storyline → Evaluation Harness (슬라이드 구조)
  → Visualization → Evaluation Harness (시각 유형)
  → **Presentation Graphics** → PPT Composer (JSON SlideDeckSpec)
  → enrich_graphics_pipeline (PNG / graphics_spec 보강) → `outputs/visual_assets.json` + `outputs/assets/`
  → OpenAI 슬라이드 JSON 고도화 (`ppt_openai_enhancer`, `AUTOPM_OPENAI_ENHANCE_PPT`)
  → python-pptx Composer → outputs/project_plan.pptx
  → Gamma API (선택) → outputs/project_plan_gamma.pptx
  → Final Evaluation Harness → `outputs/evaluation_report.json` + `.md`
  → slide_plan.json + CSV/Markdown export
```

`*` 슬라이드/Visual 단계별 Harness 점수는 최종 합산 리포트에 포함되며, Streamlit **Evaluation Report** 탭에서 확인한다.

## AGENTS.md Output Layer 표

| Layer | 역할 | MVP 구현 |
| --- | --- | --- |
| Input Layer | 업무 아이디어 입력 | Streamlit Form |
| Agent Layer | 추진계획서 본문 | Deep Agents 8 Core + Sub-Agent + Critic + Documentation |
| Storyline Layer | 장표 흐름 설계 | `slide_storyline_task` |
| Visualization Layer | visual_type·content | `visualization_design_task` |
| **Presentation Graphics Layer** | graphics_spec·에셋 계획 | `presentation_graphics_task` + `ppt/graphics_agent.py` |
| Composition Layer | PPT 파일 생성 | `ppt/ppt_composer.py` (python-pptx, 이미지·도형 우선) |
| Output Layer | 다운로드 | Streamlit + `outputs/` |

## 디렉터리 (요약)

```text
app.py
outputs/   # project_plan.pptx, .md, slide_plan.json, *.csv
src/autopm/
  evaluation/   # harness, rubrics, validators, scoring, regression_suite, test_cases
  ppt/       # slide_schema, layout_engine, visual_builder, graphics_*, chart/diagram_renderer, visual_registry, ppt_composer, deck_json
  orchestration/flow.py  # 파이프라인 + Critic + PPT 체인 + finalize
  services/export_service.py
  config/agents.yaml, tasks.yaml, subagents.yaml
  agents/subagent_runner.py, deep_runner.py
  services/llm_router.py  # invoke_with_tier, Ollama
```

## AutoPMState

- Core 산출: `orchestration_brief`, `requirement_analysis`, `business_analysis`, … `risk_management`
- PPT 중간: `slide_storyline_raw`, `visualization_raw`, **`presentation_graphics_raw`**, `ppt_composer_raw`
- `artifacts`에 `project_plan.pptx`, `slide_plan.json`, **`visual_assets.json`** 등 경로 누적

## Critic 계약

`FEEDBACK_TARGET`: `orchestration` | `requirement` | `business` | `solution` | `scope` | `wbs` | `budget` | `risk` | `none`

## 순환 import

`autopm.orchestration.__init__`는 비움. `AutoPMRunResult`는 `run_result.py`.
