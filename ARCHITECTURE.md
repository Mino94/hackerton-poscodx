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

## 전체 워크플로

```text
User Input (Streamlit)
  → Interview (Rule-based) — Harness: 입력 충분성
  → Draft (mock/OpenAI) — Harness: 초안 길이·구조
  → Gateway (rate limit / auth 스텁)
  → AutoPMFlow: 8 Core PM Agents (Deep Agents + Sub-Agent 팀, 순차)
  → Evaluation Harness — 코어 산출 루브릭 + Improvement Loop (최대 3회)
  → Critic Agent (점수 / FEEDBACK_TARGET) + Self-Correction (최대 3회, 80점 Gate)
  → Documentation Agent → Markdown §1~11
  → Storyline → Evaluation Harness (슬라이드 구조)
  → Visualization → Evaluation Harness (시각 유형)
  → **Presentation Graphics** → PPT Composer (JSON SlideDeckSpec)
  → enrich_graphics_pipeline (PNG / graphics_spec 보강) → `outputs/visual_assets.json` + `outputs/assets/`
  → python-pptx Composer → outputs/project_plan.pptx
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
