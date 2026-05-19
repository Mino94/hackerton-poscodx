"""export_service — Markdown/CSV 산출물을 outputs/에 기록한다."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

from autopm.orchestration.state import AutoPMState
from autopm.ppt.asset_manifest import VisualAssetsManifest
from autopm.ppt.slide_schema import SlideDeckSpec


def export_visual_assets_json(out_dir: Path, manifest: VisualAssetsManifest) -> str:
    """visual_assets.json — Streamlit Visual Asset Plan 및 재현용 manifest."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "visual_assets.json"
    path.write_text(manifest.model_dump_json(indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path.resolve())


def _project_root() -> Path:
    # src/autopm/services/export_service.py -> 레포 루트는 parents[3]
    return Path(__file__).resolve().parents[3]


def _extract_section(md: str, pattern: str) -> str:
    """정규식으로 ## N. 섹션 블록을 잘라낸다 — 단순하지만 MVP에 충분하다."""
    m = re.search(pattern, md, re.MULTILINE | re.DOTALL)
    if not m:
        return ""
    return m.group(1).strip()


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def append_ppt_slide_section(markdown: str, deck: SlideDeckSpec) -> str:
    """AGENTS.md §12 PPT 슬라이드 표를 덧붙인다 — Composer 이후 최종 MD를 만든다."""
    lines = [
        "## 12. PPT 슬라이드 구성",
        "",
        "| 슬라이드 | 제목 | 핵심 메시지 | 시각자료 |",
        "| --- | --- | --- | --- |",
    ]
    for s in deck.slides:
        km = (s.key_message or "").replace("|", "\\|")[:120]
        lines.append(f"| {s.slide_no} | {s.title.replace('|', '/')} | {km} | {s.visual_type} |")
    return markdown.rstrip() + "\n\n" + "\n".join(lines) + "\n"


def export_slide_plan_json(out_dir: Path, deck: SlideDeckSpec) -> str:
    """slide_plan.json — Streamlit·재실행용 구조화 산출물."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "slide_plan.json"
    path.write_text(deck.model_dump_json(indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path.resolve())


def export_evaluation_reports(out_dir: Path, report: dict[str, Any]) -> dict[str, str]:
    """
    Evaluation Harness 최종 리포트 — 발표·회귀·Streamlit이 동일 JSON/MD를 참조한다.
    휴리스틱 점수만 있어도 파일은 항상 생성해 API Key 없는 모드에서도 데모가 끊기지 않게 한다.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}
    jp = out_dir / "evaluation_report.json"
    mp = out_dir / "evaluation_report.md"
    try:
        jp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        paths["evaluation_report.json"] = str(jp.resolve())
    except OSError:
        pass
    lines = [
        "# AutoPM Evaluation Report",
        "",
        "## Overall Score",
        f"- **{report.get('overall_score', '—')}** / 100 (임계: {report.get('pass_threshold', '—')})",
        f"- **Status**: {'PASS' if report.get('final_passed') else 'FAIL'}",
        "",
        "## Agent Scores",
    ]
    for ag, sc in (report.get("agent_scores") or {}).items():
        lines.append(f"- **{ag}**: {sc}")
    lines.extend(
        [
            "",
            "## Failed Criteria",
        ]
    )
    for fc in report.get("failed_criteria") or []:
        lines.append(f"- {fc}")
    if not (report.get("failed_criteria") or []):
        lines.append("- (없음)")
    lines.extend(
        [
            "",
            "## Improvement Actions",
            f"- 개선 루프 실행 횟수: **{report.get('improvement_attempts', 0)}** / {report.get('max_improvement_attempts', 3)}",
            f"- Harness 피드백 타깃: `{report.get('feedback_target') or '—'}`",
            "",
            "## Final Pass/Fail",
            f"- **{'PASS' if report.get('final_passed') else 'FAIL'}**",
            "",
            "## Recommendations",
        ]
    )
    for r in report.get("recommendations") or []:
        lines.append(f"- {r}")
    for w in report.get("warnings") or []:
        lines.append(f"- ⚠ {w}")
    try:
        mp.write_text("\n".join(lines) + "\n", encoding="utf-8")
        paths["evaluation_report.md"] = str(mp.resolve())
    except OSError:
        pass
    return paths


def export_business_plan_json(out_dir: Path, business_plan: dict[str, Any]) -> str:
    """business_plan.json — Agent·fallback 통합 구조."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "business_plan.json"
    path.write_text(json.dumps(business_plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path.resolve())


def export_content_coverage_json(out_dir: Path, report: dict[str, Any]) -> str:
    """슬라이드 내용 충만도 리포트."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "content_coverage_report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path.resolve())


def export_run_artifacts(state: AutoPMState, final_markdown: str) -> dict[str, str]:
    """AGENTS.md가 요구한 파일명으로 저장 — 실패해도 경로는 artifacts에 남긴다."""
    root = _project_root() / "outputs"
    paths: dict[str, str] = {}

    plan_path = root / "project_plan.md"
    try:
        write_text(plan_path, final_markdown)
        paths["project_plan.md"] = str(plan_path)
    except OSError:
        state.errors.append("export project_plan.md failed")

    critic_path = root / "critic_review.md"
    try:
        critic_sec = _extract_section(final_markdown, r"##\s+11\.\s*Critic Review\s*\n(.*?)(?=\n##\s+|\Z)")
        write_text(critic_path, critic_sec or state.critic_review or "(empty)")
        paths["critic_review.md"] = str(critic_path)
    except OSError:
        state.errors.append("export critic_review.md failed")

    try:
        dlg_path = root / "agent_dialogue.json"
        dlg_path.write_text(
            json.dumps(
                {
                    "dialogue": state.agent_dialogue_as_dicts(),
                    "agent_outputs_keys": sorted(state.agent_outputs.keys()),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        paths["agent_dialogue.json"] = str(dlg_path.resolve())
    except OSError:
        state.errors.append("export agent_dialogue.json failed")

    try:
        from autopm.orchestration.supervisor_manager import supervisor_report_dict

        sup_path = root / "supervisor_report.json"
        sup_path.write_text(
            json.dumps(supervisor_report_dict(state), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        paths["supervisor_report.json"] = str(sup_path.resolve())
    except OSError:
        state.errors.append("export supervisor_report.json failed")

    # Sub-Agent 실행 기록 — Parent별 세분화 산출(UI·디버그)
    try:
        sub_path = root / "subagent_outputs.json"
        sub_path.write_text(
            json.dumps(dict(state.subagent_outputs), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        paths["subagent_outputs.json"] = str(sub_path.resolve())
    except OSError:
        state.errors.append("export subagent_outputs.json failed")

    # 표 기반 CSV는 단순 휴리스틱 — 완전 파싱이 아니라 데모용 스켈레톤
    wbs_block = _extract_section(final_markdown, r"##\s+7\.\s*WBS\s*\n(.*?)(?=\n##\s+|\Z)")
    try:
        wbs_csv = root / "wbs.csv"
        wbs_path = _table_to_csv(wbs_block, wbs_csv, ["phase", "task", "duration", "owner", "deliverable"])
        if wbs_path:
            paths["wbs.csv"] = wbs_path
    except OSError:
        state.errors.append("export wbs.csv failed")

    budget_block = _extract_section(final_markdown, r"##\s+8\.\s*예산 및 ROI\s*\n(.*?)(?=\n##\s+|\Z)")
    try:
        budget_csv = root / "budget.csv"
        bpath = _table_to_csv(budget_block, budget_csv, ["item", "cost", "note"])
        if bpath:
            paths["budget.csv"] = bpath
    except OSError:
        state.errors.append("export budget.csv failed")

    risk_block = _extract_section(final_markdown, r"##\s+10\.\s*리스크 매트릭스\s*\n(.*?)(?=\n##\s+|\Z)")
    try:
        risk_csv = root / "risk_log.csv"
        rpath = _table_to_csv(risk_block, risk_csv, ["risk", "probability", "impact", "mitigation"])
        if rpath:
            paths["risk_log.csv"] = rpath
    except OSError:
        state.errors.append("export risk_log.csv failed")

    state.artifacts.update(paths)
    return paths


def _table_to_csv(md_table: str, out: Path, default_headers: list[str]) -> str | None:
    """Markdown 표의 첫 테이블만 CSV로 변환한다 — 표가 없으면 스킵."""
    if not md_table.strip():
        return None
    lines = [ln for ln in md_table.splitlines() if ln.strip().startswith("|")]
    if len(lines) < 2:
        return None
    rows: list[list[str]] = []
    for ln in lines:
        if re.match(r"^\|\s*[-:]+", ln):
            continue
        cells = [c.strip() for c in ln.strip("|").split("|")]
        rows.append(cells)
    if not rows:
        return None
    headers = rows[0]
    if len(headers) < 2:
        headers = default_headers[: max(1, len(rows[0]))]
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(headers)
        for r in rows[1:]:
            w.writerow(r + [""] * max(0, len(headers) - len(r)))
    return str(out)
