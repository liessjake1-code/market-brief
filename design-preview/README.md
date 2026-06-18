# design-preview — redesign references (not the production path)

Tracked here so the approved look + the preview loop survive across chats:

- `the_tape_white.html.j2` — the APPROVED "The Tape" (white) email design. The
  production task is to port this into `render/template.html.j2` wired to the real
  viewmodel. See HANDOFF_DESIGN.md.
- `preview_fixture.py` — renders any template against a realistic BriefView fixture
  (good prose, real-looking numbers, citations) so design changes can be judged
  without sending email.
- `preview_shot.py` — headless-Chrome screenshot helper.

Generated scratch (`*.html`, `*.png`) is gitignored. Regenerate with:

    uv run --with jinja2 --python 3.12 python design-preview/preview_fixture.py \
      design-preview/the_tape_white.html.j2 design-preview/out.html
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless \
      --disable-gpu --hide-scrollbars --force-device-scale-factor=2 \
      --window-size=720,3600 --screenshot=/tmp/out.png \
      "file://$(pwd)/design-preview/out.html"
