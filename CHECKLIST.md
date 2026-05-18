# AutoPM 검증 체크리스트 (AGENTS.md PPT MVP)

## 구조·아키텍처

- [x] `src/autopm/ppt/` — `slide_schema.py`, `layout_engine.py`, `visual_builder.py`, `ppt_composer.py`, `deck_json.py`, `theme.py`
- [x] `src/autopm/api/` — gateway, auth, rate_limiter, logger 스텁
- [x] `src/autopm/orchestration/` — `flow.py` 8 Core + Critic + 문서화 + **PPT 3단 Crew**
- [x] `config/agents.yaml` — Core 8 + PPT 3 + Critic + Documentation (AGENTS.md 명명)
- [x] `config/tasks.yaml` — orchestrate … risk → critic → documentation → slide/visualization/ppt_composition

## 동작

- [x] `pip install -r requirements.txt` (python-pptx, pandas, matplotlib 포함)
- [x] `OPENAI_API_KEY` 없이 Fallback Markdown + **`outputs/project_plan.pptx`** (10장+)
- [x] `outputs/slide_plan.json` 생성
- [ ] API Key 있을 때 E2E (네트워크·쿼터 필요)
- [x] Critic 최대 3회, 80점 Gate, `FEEDBACK_TARGET` 확장(orchestration…risk)
- [x] Streamlit: PPT 다운로드 탭, 슬라이드 JSON, §7~12 매핑 탭

## AGENTS.md PPT 항목

- [x] `project_plan.pptx` — 최소 10슬라이드(AS-IS/TO-BE/WBS/예산/리스크 등)
- [x] `project_plan.md`, `wbs.csv`, `budget.csv`, `risk_log.csv`, `critic_review.md`
- [x] Demo Mode에서도 PPT 생성

## 명령으로 빠른 검증

```powershell
$env:PYTHONPATH="src"
$env:OPENAI_API_KEY=""
python -c "from autopm.crew import run_autopm; r=run_autopm({'idea_title':'t','current_process':'c','pain_points':'p','departments':'d','monthly_hours':'1','headcount':'1','goals':'g','target_timeline':'4w','budget_range':'x'}); print(r.state.artifacts)"
```

```powershell
streamlit run app.py
```

## 알려진 제한 (MVP)

- LLM JSON이 크게 깨지면 `build_fallback_slide_deck`로 PPT는 유지된다.
- CSV export는 Markdown 표 휴리스틱(§7 WBS, §8 예산 …).
