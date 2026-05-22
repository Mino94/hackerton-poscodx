"""app.py _render_guided_panel 들여쓰기 복구 스크립트."""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"


def _extract_old_fn() -> list[str]:
    text = subprocess.check_output(
        ["git", "show", "e1dc131:app.py"],
        encoding="utf-8",
        errors="replace",
    )
    lines = text.splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith("def _render_guided_panel"))
    end = next(
        i
        for i in range(start + 1, len(lines))
        if lines[i].startswith('if st.session_state.run_mode == "Guided"')
    )
    return lines[start:end]


def _build_new_fn(old_lines: list[str]) -> str:
    # e1dc131: 8줄 헤더 이후가 본문 (def _mark_steps 부터)
    body = old_lines[8:]

    # input_confirm 블록을 render_input_confirm_table 버전으로 교체
    new_body: list[str] = []
    skip_until = None
    for i, line in enumerate(body):
        if skip_until is not None:
            if i < skip_until:
                continue
            skip_until = None
        if line.strip() == 'if gu == "input_confirm":':
            new_body.append(line)
            new_body.append('        st.markdown("##### 3) 입력 정보 확인")')
            new_body.append("        render_input_confirm_table(_get_iv)")
            new_body.append('        st.markdown("**세부 승인**")')
            # 기존 for lb, dp 루프 ~ columns(3) 직전까지 스킵
            j = i + 1
            while j < len(body) and "a, b, c = st.columns(3)" not in body[j]:
                j += 1
            skip_until = j
            continue
        new_body.append(line)

    header = '''def _render_guided_panel() -> None:
    """Guided — 한번에 진행 프리셋 + (선택) 단계별 세부."""
    gu = st.session_state.guided_ui_step
    pg = _get_pg()

    with st.expander("수정 요청 (선택)", expanded=False):
        st.text_area(
            "수정 요청",
            height=48,
            key="guided_revision_box",
            placeholder="프리셋·단계 실행 시 반영할 지시",
            label_visibility="collapsed",
        )
    rev = st.session_state.get("guided_revision_box", "") or ""

    bulk_preset = render_guided_bulk_bar(
        gu,
        interview_started=st.session_state.interview_started,
    )
    if bulk_preset:
        _execute_guided_bulk(bulk_preset, rev)
        return

    with st.expander(f"단계별 세부 — {GUIDED_UI_TITLE.get(gu, gu)}", expanded=False):
        st.caption("프리셋 대신 한 단계씩 진행할 때만 펼치세요.")
'''
    indented = []
    for line in new_body:
        if line.strip():
            indented.append("    " + line)
        else:
            indented.append("")

    # overall_progress 가드 (e1dc131에는 없음)
    fixed = []
    for line in indented:
        if line.strip() == "overall_progress.progress(1.0)":
            fixed.append("            if overall_progress is not None:")
            fixed.append("                overall_progress.progress(1.0)")
        else:
            fixed.append(line)

    # done 단계 문구
    for i, line in enumerate(fixed):
        if 'elif gu == "done":' in line or 'if gu == "done":' in line:
            # 다음 st.info 교체
            for j in range(i + 1, min(i + 5, len(fixed))):
                if "st.info" in fixed[j]:
                    fixed[j] = '            st.info("Guided 완료 — **산출물** 탭에서 PPT 다운로드.")'
                    break

    return header + "\n".join(fixed) + "\n"


def main() -> None:
    app_text = APP.read_text(encoding="utf-8")
    lines = app_text.splitlines(keepends=True)
    start = next(i for i, l in enumerate(lines) if l.startswith("def _render_guided_panel"))
    end = len(lines)
    # 함수 끝 = 파일 끝 (tab hook 제거됨)
    new_fn = _build_new_fn(_extract_old_fn())
    new_lines = lines[:start] + [new_fn] + lines[end:]
    APP.write_text("".join(new_lines), encoding="utf-8")
    print(f"Replaced _render_guided_panel at line {start + 1}, {len(new_fn.splitlines())} lines")


if __name__ == "__main__":
    main()
