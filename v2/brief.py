from __future__ import annotations
import argparse
import sys
from datetime import date
from pathlib import Path
from marketbrief.core.enums import RunMode
from marketbrief.core.config import load_config
from marketbrief.core.context import BriefContext
from marketbrief.core.pipeline import run_pipeline
from marketbrief.core.state import load_state, commit_state
from marketbrief.render.html import render_brief, render_unavailable_notice
from marketbrief.assemble.brief_view import build_brief_view
from marketbrief.assemble.diff_line import build_diff_line
from marketbrief.assemble.glance import build_glance_rows

EXIT_OK = 0
EXIT_HARD_FLOOR = 2


def build_brief(*, mode: RunMode, config_path, state_path, today: date | None = None) -> tuple[int, str]:
    today = today or date.today()
    config = load_config(config_path)
    prev_state = load_state(state_path)
    ctx = BriefContext(run_date=today, mode=mode, config=config, prev_state=prev_state)
    ctx = run_pipeline(ctx)

    if ctx.health.hard_floor_tripped:
        return EXIT_HARD_FLOOR, render_unavailable_notice()

    diff_line = build_diff_line(ctx)
    glance_rows = build_glance_rows(ctx, ctx.sections)
    view = build_brief_view(ctx, ctx.sections, glance_rows, diff_line, live=None)
    html = render_brief(view)
    commit_state(state_path, {"run_date": today.isoformat()}, mode=mode)
    return EXIT_OK, html


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Market Brief v2")
    parser.add_argument("--no-send", action="store_true", help="build only, no send, no state write")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--state", default="last_run.json")
    args = parser.parse_args(argv)
    mode = RunMode.NO_SEND if args.no_send else RunMode.SEND
    code, html = build_brief(mode=mode, config_path=args.config, state_path=args.state)
    Path("brief.preview.html").write_text(html)
    print(f"mode={mode.value} exit={code} bytes={len(html)}")
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
