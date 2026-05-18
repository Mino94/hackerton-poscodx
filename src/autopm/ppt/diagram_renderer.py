"""프로세스·아키텍처 등 도식 PNG — networkx/graphviz는 선택, 실패 시 상위에서 도형 fallback."""

from __future__ import annotations

import traceback
from pathlib import Path
from typing import Any

from autopm.ppt.chart_renderer import _matplotlib_warnings_compat


def render_process_flow_png(
    out_path: Path,
    steps: list[str],
    *,
    title: str = "",
) -> bool:
    """수평 박스 다이어그램을 matplotlib으로 그려 저장한다."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

        steps = [s.strip() for s in steps if s.strip()][:8]
        if len(steps) < 2:
            steps = ["단계 A", "단계 B"]

        out_path.parent.mkdir(parents=True, exist_ok=True)
        fig, ax = plt.subplots(figsize=(9, 2.8), dpi=120)
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 3)
        ax.axis("off")
        if title:
            ax.text(5, 2.75, title[:90], ha="center", fontsize=11, fontweight="bold")

        n = len(steps)
        w_box = 8.0 / max(n, 1)
        y0 = 1.0
        h = 0.9
        for i, lab in enumerate(steps):
            x0 = 0.8 + i * w_box * 0.95
            bw = w_box * 0.72
            box = FancyBboxPatch(
                (x0, y0),
                bw,
                h,
                boxstyle="round,pad=0.03,rounding_size=0.08",
                linewidth=1.2,
                edgecolor="#2E5090",
                facecolor="#E8EEF7",
            )
            ax.add_patch(box)
            ax.text(x0 + bw / 2, y0 + h / 2, lab[:18], ha="center", va="center", fontsize=9)
            if i < n - 1:
                arr = FancyArrowPatch(
                    (x0 + bw + 0.02, y0 + h / 2),
                    (x0 + w_box * 0.95, y0 + h / 2),
                    arrowstyle="-|>",
                    mutation_scale=12,
                    color="#2E5090",
                    linewidth=1.2,
                )
                ax.add_patch(arr)

        fig.subplots_adjust(left=0.04, right=0.96, top=0.94, bottom=0.06)
        with _matplotlib_warnings_compat():
            fig.savefig(str(out_path), bbox_inches="tight", facecolor="white", pad_inches=0.04)
        plt.close(fig)
        return out_path.is_file()
    except Exception:
        traceback.print_exc()
        return False


def render_architecture_blocks_png(
    out_path: Path,
    layers: list[str],
    *,
    title: str = "참조 아키텍처(블록)",
) -> bool:
    """단순 세로 스택 블록 — 솔루션 개요 슬라이드용."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Rectangle

        layers = [s.strip() for s in layers if s.strip()][:6]
        if not layers:
            layers = ["UI/리포트", "검증 엔진", "ERP/데이터"]

        out_path.parent.mkdir(parents=True, exist_ok=True)
        fig, ax = plt.subplots(figsize=(6, 4), dpi=120)
        ax.set_xlim(0, 6)
        ax.set_ylim(0, 8)
        ax.axis("off")
        ax.text(3, 7.5, title[:80], ha="center", fontsize=11, fontweight="bold")
        y = 6.5
        for lay in layers:
            ax.add_patch(Rectangle((0.8, y - 0.85), 4.4, 0.75, facecolor="#DDEBF7", edgecolor="#2E5090"))
            ax.text(3.0, y - 0.47, lay[:40], ha="center", va="center", fontsize=9)
            y -= 1.05

        fig.subplots_adjust(left=0.04, right=0.96, top=0.94, bottom=0.06)
        with _matplotlib_warnings_compat():
            fig.savefig(str(out_path), bbox_inches="tight", facecolor="white", pad_inches=0.04)
        plt.close(fig)
        return out_path.is_file()
    except Exception:
        traceback.print_exc()
        return False


def try_render_graphviz_dot(out_path: Path, dot_source: str) -> bool:
    """
    graphviz가 설치되어 있을 때만 PNG 생성 — 없으면 False.
    해커톤 PC에 dot이 없을 수 있어 필수 경로에서 호출하지 않는다.
    """
    try:
        import graphviz  # type: ignore

        g = graphviz.Source(dot_source)
        g.format = "png"
        base = out_path.with_suffix("")
        rendered = g.render(filename=str(base), cleanup=True)
        return Path(rendered).is_file()
    except Exception:
        traceback.print_exc()
        return False
