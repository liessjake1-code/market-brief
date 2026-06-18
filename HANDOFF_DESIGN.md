# Handoff — email redesign ("The Tape") + sourcing + charts

Transfer prompt for a fresh Claude Code session. The brief is fully built, merged
to `main`, and the daily-brief.yml crons are live. This handoff covers a **look +
content redesign** the human approved through visual previews. Item 1 of 9 is done
and shipped; items 2-9 remain. Everything below is pre-decided — do NOT re-litigate.

## How to resume (paste to the new session)

> Read CLAUDE.md, progress.md, and HANDOFF_DESIGN.md in full before doing anything.
> We are on branch `build/phases`; `main` is the live default branch and the two are
> kept in sync (human waived the no-main rule for this project — mirror every change
> to main too). Confirm the two-track split (human does ALL external/Track A steps —
> GitHub UI, secrets, triggering workflows, watching mornings; you write code ONLY
> and never claim to have done a human step). 149+ tests on Python 3.12 via:
> `uv run --with pytest --with pyyaml --with requests --with pandas --with feedparser --with jinja2 --with matplotlib --python 3.12 python -m pytest -q`
> The redesign decisions are locked in HANDOFF_DESIGN.md. Resume at item 2. Use the
> preview loop (below) to screenshot every change for the human before shipping.
> Standing git rule: push build/phases at every commit/gate and mirror to main; no
> auto-PR; keep progress.md updated. allow_repeat_send is TEMPORARILY true — restore
> to false at go-live (see progress.md).

## The preview loop (USE THIS — no email needed to see changes)

The human does NOT want to send a real email to see each change. Render the template
against a realistic fixture and screenshot it with headless Chrome, then show the PNG
in chat. Proven working this session.

```bash
cd /Users/jakeliess/market-brief
chrome="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
# render a template variant against the realistic fixture:
uv run --with jinja2 --python 3.12 python design-preview/preview_fixture.py <template.j2> design-preview/out.html
# screenshot it:
"$chrome" --headless --disable-gpu --hide-scrollbars --force-device-scale-factor=2 \
  --window-size=720,3600 --screenshot=/tmp/out.png "file://$(pwd)/design-preview/out.html"
# then Read /tmp/out.png to show the human, and `open design-preview/out.html` to pop it in their browser.
```

- `design-preview/preview_fixture.py` builds a realistic BriefView (good prose,
  real-looking numbers, populated watchlist + live zone + demo source citations) and
  renders any template path. It also passes `text_rows` (the At-a-Glance text rows).
- `design-preview/the_tape_white.html.j2` is the **APPROVED LOOK** — the white "The
  Tape" template the human signed off on. The production task is to port this into
  `render/template.html.j2`, wired to the real viewmodel.
- `design-preview/` is gitignored (scratch). The `.j2` + fixture are kept there as
  references; you may commit them if useful, but they are not the production path.

## APPROVED DECISIONS (do not re-ask)

### Look — "The Tape", WHITE
- **Name:** "The Tape" (was "Morning Market Brief"). Use in masthead + email subject.
  Masthead: small uppercase kicker "Your daily market brief", large serif wordmark
  "The Tape", date/time right-aligned, under a 2px ink rule.
- **Palette (WHITE):** page `#FFFFFF`, outer margin `#F4F4F2`, ink `#1b1a17`,
  secondary `#3c3a33`, muted `#8a877f`/`#9b978d`, hairline `#E7E5E0`, tint blocks
  `#F6F5F2`, green `#0b7a3d`, red `#c0392b`, chart-blue `#3a6ea5`. This warm-near-black
  ink + white is the human's choice; it REPLACES the spec's navy `#13202E`/paper
  `#FBFAF7`. Still honors spec §6.5 "one accent, green/red for direction only" — the
  blue is confined to chart lines + source links, not body color.
- **Fonts (web-safe with real-name-first fallback):**
  MONO = `'IBM Plex Mono', Consolas, 'SFMono-Regular', monospace` (numbers — the
  protected signature, keep on every figure).
  SERIF = `'Newsreader', Georgia, 'Times New Roman', serif` (masthead + section headings).
  SANS = `'Libre Franklin', 'Helvetica Neue', Helvetica, Arial, sans-serif` (body).
  Real web-font names are first so webmail that honors them gets the real face;
  Outlook falls back to Georgia/Helvetica/Consolas. Web fonts are a nice-to-have, not
  a dependency (spec §6.5).
- **Section separation:** serif heading per section, hairline divider between, Top
  Story in its own tinted `#F6F5F2` block with a 3px ink left border + "TOP STORY"
  kicker. (The human's design used this; it reads as "each section is its own thing".)

### Structure fixes (carry into the production template)
1. **Live "This morning so far" zone promoted** to right under At a Glance (was at the
   very bottom). Stays fenced + tinted + timestamped (spec §3.1/§6.5). Empty state
   reads "Markets pre-open; no overnight moves to report yet." (not a bare "no figures").
2. **At a Glance split:** the 5 figure rows (Markets, Rates and dollar, Commodities,
   Crypto, Volatility) keep figures + a SHORT 3-5 word "why" tag (NOT the full prose
   sentence). The 4 text rows (Today's events, Earnings, Washington, Bottom line) render
   as label|text rows below — no empty figure cells. The live "This morning" row LEAVES
   the glance table (it's promoted to the fenced zone). The fixture passes these as
   `text_rows` = tuple[(label, text)]; the production viewmodel must build them.
3. **"What to Watch Today" rendered ONCE.** Currently it's both body section #11 AND a
   dedicated forward block = duplicate. Fix: in `render/viewmodel.py::build_sections`,
   SKIP `what_to_watch_today` so it is never a body section; the template's dedicated
   forward block owns it. Leave `FALLBACK_ORDER` in engine/top_story.py UNTOUCHED (the
   Top Story engine still reasons over all 11; spec §4.2).
4. **De-dup:** glance = numbers + short tag; the full causal read lives ONCE in the body
   section. Stop feeding `_first_sentence(prose)` into the glance "why"; use a short
   direction/quiet tag instead.

### Sourcing — EVERY pulled fact links to its source (the human stressed this)
- **DONE (item 1, shipped):** `engine/narrative.py` `SectionResult.cited_sources` now
  carries the matched article `{title, url}` resolved from the validated
  `cause_source_id`. Empty when no cause claim. The validator already guarantees a
  cited source_id was actually supplied (never invented) — so a "Source ->" link always
  points at a real matched article.
- **TODO in template + viewmodel:** render a clickable **"Source: <headline> ->"** line
  (blue `#3a6ea5`) under each section's prose, from `cited_sources`. Macro shape is in
  `design-preview/the_tape_white.html.j2` (`sources_line`, `chart_caption`).
- Figure links already exist (`render/source_links.py`): At-a-Glance numbers, live
  figures, section figures -> Yahoo quote / FRED series page; Movers/Watchlist tickers
  -> Yahoo + favicon. Keep all of these.
- **Charts** carry a "Chart: yfinance / FRED ->" caption with a link (macro shown).
- **Calendar/earnings events** -> link to provider page where a URL exists (check
  sources/calendar.py for an event URL field; add link if present, else plain text).
- **No empty "Source:" labels** — when a section has no article, show nothing for the
  article citation but still show the figure/data links.

### No empty sections — rich computed fallback (NEVER manufacture a cause)
- The human dislikes bare one-line sections. BUT spec §2/§5.6 + CLAUDE.md are firm:
  "No clear catalyst" is correct; NEVER manufacture a cause. Reconciliation the human
  approved: every section ALWAYS shows real computed substance — **level-in-context
  (vs 5/20-day range), the move, the streak/range, and a forward hook** — built from
  numbers, even when there is no news. ONLY the causal "why" is omitted when no article
  matched. This is the spec's "four ingredients" (§5.6); the current templated fallback
  was lazily collapsing to one line. Enrich the fallback (engine `templated.py` /
  the `_section_template_line` path in brief.py + viewmodel) so a quiet section is
  short but substantive, not empty. Do NOT add a fake cause.

### WSJ / FT
- Human has a Tulane WSJ/FT subscription and asked about pulling full articles.
  **DECISION: free RSS feeds + clickable headline links ONLY.** Do NOT build credential
  storage or paywall scraping — it violates publisher ToS + the school license and risks
  the institutional subscription. The model only needs headline+summary anyway (§5.6).
  Add whatever free WSJ/FT RSS section feeds still publish to `sources/news.py` feed
  list (with the same graceful-fail as other feeds, and a `_prefix_for` entry). Their
  headlines can then appear, cite, and link out; the human reads the full piece on their
  own access in-browser. Verify the feed URLs resolve at build time.

### Charts — HYBRID, inline within sections, every chart has a text fallback
- **HTML/CSS charts (no image, never blocked):** index daily %-change bar (in the US
  Equities / Top Story block) and watchlist sparklines. Drawn with table cells /
  stacked divs. Macros `hbar` and `sparkline` are in the approved preview template —
  port them. These render identically everywhere incl. Outlook.
- **PNG charts (matplotlib, CID-embedded):** yield curve + 10Y trend (Rates), WTI
  1-month trend (Commodities). RESTYLE `render/charts.py` to WHITE background, blue
  `#3a6ea5` trend line, mono tick labels, no chart-junk. Each PNG gets `alt` text + a
  one-line text summary so a blocked image still leaves a readable line.
- **Placement:** inline within the relevant section (matches the human's design).
- **Charts default-on** per config.yaml: index_bar, yield_curve, oil_trend,
  watchlist_sparklines true.

### Outlook CID fix (the broken "chart" boxes in the human's screenshot)
- `render/send.py::build_message` currently attaches related images onto the HTML
  sub-part via `msg.get_payload()[-1].add_related(...)`. Outlook desktop often won't
  traverse that. Restructure to the Outlook-reliable tree:
  `multipart/related[ multipart/alternative[text, html], image, image ]` — images as
  SIBLINGS of the alternative, not children of the html part. Add `Content-Disposition:
  inline` + angle-bracketed `Content-ID`. Add a test asserting the MIME tree shape.
  NOTE: only a real Outlook send proves the fix renders — that is the human's test send.

### Favicon-as-text fallback (the broken-checkbox glyphs)
- Google s2 favicons are REMOTE images; Outlook blocks them -> broken-box glyphs that
  look like checkboxes. Make the baseline clean text (ticker names, mono, separated by
  " · "); the `<img>` loads only where remote images are allowed. Spec §6.5 requires the
  row still reads from text. Macro `tickers_text` in the preview template does this.

## Production file map (items 2-9)
- `engine/narrative.py` — DONE (cited_sources).
- `engine/templated.py` + brief.py `_section_template_line` / `_brief_lines` — richer
  computed fallback (level/range/move/forward-hook). `_brief_lines` currently returns
  `dict[str,str]`; you likely need to widen the data passed to the view so citations +
  fallbacks flow (a `SectionContent` struct, or pass narrative_results through).
- `sources/news.py` — add WSJ/FT free feeds + `_prefix_for` entries.
- `render/viewmodel.py` — SectionView gains `sources` (tuple[{title,url}]) + chart data
  + html-chart data; build glance figure-rows + text-rows; skip what_to_watch in body;
  favicon-as-text. `build_sections` signature will change — update brief.py `_build_view`.
- `render/template.html.j2` — REPLACE with the white "The Tape" (port from
  `design-preview/the_tape_white.html.j2`, swap the demo data for real view fields,
  swap the dashed PNG placeholders for real `cid:` imgs + captions).
- `render/charts.py` — white restyle + blue trend; html bar/sparkline data can be
  computed in viewmodel (pure, no matplotlib) so it's unit-testable.
- `render/send.py` — CID multipart/related restructure.
- `brief.py` `_build_view` / `_build_charts` — wire new view fields + html-chart inputs.
- Tests: `test_viewmodel.py`, `test_template_render.py`, `test_send_inline.py`,
  `test_charts.py`, `test_narrative.py` (add a cited_sources resolution test),
  `test_calendar.py`. New assertions: every section with a cause renders a clickable
  source; what_to_watch renders exactly once; MIME tree shape; favicon degrades to text;
  quiet section is non-empty.

## State at this handoff
- Branch `build/phases` == `origin/build/phases`; `main` == `origin/main`; both have the
  item-1 narrative citation change (build/phases commit 14def7b; merged to main 764fd8d).
- 19 narrative tests green after item 1. Full suite was 149 green before this session;
  re-run the full suite after items 2-9.
- TEMPORARY: `config.yaml monitoring.allow_repeat_send: true` — RESTORE to false at
  go-live (progress.md item 4).
- Remaining human punch-list (progress.md): watch 2-3 scheduled mornings (cron timing +
  runner-IP + second price source); confirm heartbeat on a simulated miss.
