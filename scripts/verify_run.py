"""AutoPM end-to-end verification — API Key 없이 fallback 경로 포함."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from autopm.evaluation.test_cases import GOLDEN_ERP_INPUTS
from autopm.orchestration.flow import AutoPMFlow, _merge_inputs_bundle
from autopm.agents.deep_agent_sdk import is_deep_agents_sdk_enabled
from autopm.services.llm_router import get_llm_routing_status


def main() -> int:
    out_dir = ROOT / "outputs"
    inputs = dict(GOLDEN_ERP_INPUTS)
    _merge_inputs_bundle(inputs)

    print("=== LLM routing ===")
    print(json.dumps(get_llm_routing_status(), ensure_ascii=False, indent=2))
    print(f"=== Deep Agents SDK (create_deep_agent) enabled: {is_deep_agents_sdk_enabled()} ===")

    print("\n=== AutoPMFlow.run() ===")
    result = AutoPMFlow().run(inputs)
    st = result.state

    checks: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, ok, detail))
        mark = "OK" if ok else "FAIL"
        print(f"  [{mark}] {name}" + (f" — {detail}" if detail else ""))

    check("no_fatal_errors", not any("tuple" in e for e in st.errors), str(st.errors[:3]))
    check("agent_outputs", len(st.agent_outputs) >= 8, f"count={len(st.agent_outputs)}")
    check("subagent_outputs", len(st.subagent_outputs) >= 8, f"tasks={len(st.subagent_outputs)}")
    check("agent_dialogue", len(st.agent_dialogue) >= 1, f"count={len(st.agent_dialogue)}")

    ppt = out_dir / "project_plan.pptx"
    check("project_plan.pptx", ppt.is_file() and ppt.stat().st_size > 5000, f"{ppt.stat().st_size if ppt.is_file() else 0} bytes")

    for fname in (
        "project_plan.md",
        "slide_plan.json",
        "subagent_outputs.json",
        "agent_dialogue.json",
        "wbs.csv",
        "budget.csv",
        "risk_log.csv",
    ):
        p = out_dir / fname
        check(fname, p.is_file(), f"{p.stat().st_size} bytes" if p.is_file() else "missing")

    # slide count from pptx
    slide_count = 0
    if ppt.is_file():
        try:
            from pptx import Presentation

            slide_count = len(Presentation(str(ppt)).slides)
        except Exception as exc:
            slide_count = -1
            check("pptx_slide_count", False, str(exc))
        else:
            check("pptx_min_10_slides", slide_count >= 10, f"slides={slide_count}")

    # slide_plan topics
    sp = out_dir / "slide_plan.json"
    if sp.is_file():
        data = json.loads(sp.read_text(encoding="utf-8"))
        slides = data.get("slides") or []
        titles = " ".join((s.get("title") or "") for s in slides)
        for kw in ("AS-IS", "TO-BE", "WBS", "예산", "리스크"):
            check(f"slide_topic_{kw}", kw in titles or kw.replace("-", "") in titles, "")

    failed = [c for c in checks if not c[1]]
    print(f"\n=== Summary: {len(checks) - len(failed)}/{len(checks)} passed ===")
    if failed:
        for name, _, detail in failed:
            print(f"  FAILED: {name} {detail}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
