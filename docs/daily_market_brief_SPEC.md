# Daily Market Brief: Project Specification

**Status:** Design settled, ready to build.
**Purpose of this file:** the single source of truth for the project. It describes one design in the present tense. There are no versions, no changelog, and no "what changed" history. When the idea is refined, edit this file in place so it always describes the current intended build.

---

## 1. Purpose

A market brief emailed automatically every weekday morning at 8:30 AM Central. It is built for a fast skim: the reader gets the full picture in about 30 seconds from the top block, then drills into sections only when something catches their eye. Every number is paired with a short reason it moved, and every number links back to a source page so it can be verified.

**The core promise.** This document exists to deliver two things and to protect them above all else:

1. **Accurate, sourced numbers.** Every figure is computed in Python from a named source and links back to the page it came from. The model that writes the prose never invents or alters a number.
2. **A smart, accurate "why."** Every causal explanation traces to either a number computed in Python or a sentence a reporter actually wrote. The brief never asserts a cause it cannot point to. When the news does not support a clean cause, it says so out loud.

"100 percent accurate" on free, scraped data is not literally achievable; data feeds have bad ticks and delays. The achievable and non-negotiable standard is: **every number sourced and verifiable, every cause traced to real reporting, and uncertainty flagged honestly rather than hidden.** A brief that says "no clear catalyst" is doing its job; a brief that invents a plausible story is failing. Every design decision below serves this standard.

The whole pipeline is designed to run for free. The only paid-in-theory component is one small model call per weekday, which costs under a dollar a month. See Section 9.

---

## 2. Design principles (the rules of taste)

These are firm. They override convenience.

- **Professional tone.** No em dashes. No emojis. Plain, direct, declarative.
- **Numbers plus the why.** Every data point is followed by a brief explanation of why it is where it is, and why it changed if applicable. The why is grounded: it traces to either a number computed in Python or a sentence a reporter actually wrote. See Section 5.6.
- **Settled facts and live snapshots are never mixed.** The brief reports a finished trading day (yesterday's settled close, plus overnight moves where data has settled) as fact, and reports this-morning's pre-market action as a clearly labeled, timestamped live snapshot. The two are visually and verbally fenced apart. Pre-market numbers are real but provisional, so they are always marked as a snapshot, never presented as settled. See Section 3 and Section 4.
- **Grounding over fluency.** A confident sentence with no source behind it is the central failure mode in a money document. The pipeline would rather print "no clear catalyst" than a plausible invented cause. Honesty about an empty tape builds more trust than a manufactured story.
- **Skim first, depth second.** The "At a Glance" block and the diff line carry every key number in one screen. The sections below expand on it. The why lines in the summary stay to one line so the summary never duplicates the sections.
- **Depth is earned, not fixed.** All sections always appear, but length scales with what actually happened. A quiet section gets one honest line. A section with a real move and real news gets the full read. Padding a quiet section is the same sin as inventing a number, only softer.
- **Signal over completeness.** If a section or chart stops earning attention after a couple of weeks, cut it.
- **Verifiable.** Every figure hyperlinks to the page it came from.
- **Lean by default.** Charts and optional sections are config toggles, off unless turned on.
- **Importance lives at the top, not in the order.** Because the diff line and Top Story slot put the headline at the very top of the email, the section order below them is free to follow reading logic instead of carrying importance.

---

## 3. Delivery and schedule

- **Mechanism:** a Python script run on a schedule by GitHub Actions (free, cloud-hosted, no machine needs to be on). The script gathers data, builds an HTML email, and sends it.
- **Send time:** 8:30 AM Central, weekdays only, before the US cash open. Delivered inside a guard window to absorb GitHub scheduler lag. See Section 8.3.
- **Holidays:** skip US market holidays (check a market calendar before sending).
- **Destination:** your Outlook inbox.

### 3.1 Timing rationale: morning brief about a finished day, plus a live snapshot

The brief sends in the morning, when it will actually be read, but its trustworthy core describes a **finished, settled trading day**, not an unfinished one. This is deliberate and it is what makes the accuracy promise keepable:

- Yesterday's closing prices are final.
- FRED has updated overnight **for Treasury yields**, so the 10-year and 2-year are a **primary source** by morning, not a stale fallback. (The H.15 release posts late afternoon Eastern, so by morning FRED reflects yesterday's close.)
- **Oil is the exception, and this matters.** FRED's WTI series (`DCOILWTICO`, sourced from EIA) frequently lags several business days and is not reliably yesterday's settled close by morning. Treating it as morning-primary would print a stale oil number as a settled fact, which is the exact failure this whole document exists to prevent. **For oil, yfinance (`CL=F`) is the morning-primary source and FRED is a cross-check, not the source of record.** See Section 7 and 7.5.
- Yesterday's narrative is fully written; reporters had all evening, so the "why" paraphrases reported conclusions rather than anticipating an unstarted day.

On top of that settled core, the 8:30 AM send folds in a **clearly fenced "This morning so far" snapshot**: pre-market index futures and anything that broke overnight or early. This is the only part built on unsettled data, so it follows one strict rule: **every figure in it is labeled as a live pre-market snapshot with the timestamp it was pulled** (for example, "Pre-market as of 8:25 AM CT: S&P futures +0.4%"). The accuracy bar for this zone is not "the number is final" (it cannot be) but "the number is honestly labeled as a live snapshot and sourced." The thin-volume movers floor (Section 7) still applies here so a garbage pre-market tick is never headlined as this-morning's action.

**The label must follow the actual pull time, not the scheduled time.** The cash open is 8:30 AM CT and the guard window (Section 8.3) can fire as late as 9:15 AM CT, so on a late run the "pre-market" futures read is in fact 30 to 45 minutes into live cash trading and the word "pre-market" would be false. The snapshot logic is therefore time-aware: if the pull happens before 8:30 CT it labels "Pre-market as of HH:MM CT"; if it happens after, it labels "Early session as of HH:MM CT" and prefers the cash index over the future. The honesty of this zone depends on the label matching reality, not the schedule.

The brief therefore has three parts in reading order: the settled recap (yesterday and settled overnight) which is the trustworthy bulk, then the fenced timestamped this-morning snapshot, then today's schedule (events with known times, the only forward-looking part, and pure schedule rather than prediction).

### 3.2 Why not send through Outlook directly

Outlook is the destination, not the sender. As of March 1, 2026 Microsoft began rejecting Basic Authentication for SMTP AUTH client submission in Exchange Online and Outlook.com, with full enforcement on April 30, 2026. Regular passwords and app passwords are both rejected. The only native path left is OAuth2 with an Azure app registration and token refresh, which is far too much friction for a free daily cron job, and for personal Outlook.com accounts it is not cleanly supported at all.

Gmail is not a way around this. Google disabled plain-password SMTP for consumer Gmail in 2022; the remaining paths are app passwords (require 2FA, increasingly restricted, same deprecated-auth fragility) or OAuth2 (same friction as the Azure path). Sending from Gmail is the same problem wearing a different logo, so it is not used.

**Decision: send through a free transactional email provider and address the message to your Outlook inbox.** Outlook receives it like any other mail. This decouples sending from the destination mailbox and keeps the code to a simple SMTP relay or HTTP API call with one API key. If a "from me" appearance is ever wanted, the relay can set the `From` to your own verified address without touching Gmail's auth at all.

### 3.3 Provider choice and the free-to-inbox path

Pick one provider with a free tier that allows single-sender verification (so you do not need to own a domain) and covers one email per weekday with room to spare.

- **Primary recommendation: Brevo.** It verifies a single sender address (no domain needed), exposes a simple SMTP relay (`smtp-relay.brevo.com`) and an HTTP API, and its free tier (300 emails per day, permanent, no card) is far larger than one email a day needs.
- **SendGrid is no longer a free option.** Twilio retired SendGrid's permanent free tier on May 27, 2025; new accounts get only a 60-day trial (100 emails/day) and then require a paid plan starting near 20 dollars a month. Do not pick SendGrid for a free build unless you hold a grandfathered free account.
- **Documented free fallbacks if Brevo cuts its tier:** Resend (3,000 emails/month free, clean SMTP and API, newer and smaller company), Mailtrap (4,000/month free), or Amazon SES (effectively free at this volume at roughly 0.10 dollars per 1,000, but more setup friction). Keeping the send path a thin SMTP relay call (Section 13) makes swapping any of these a credentials change, not a rewrite.
- Verify the current free-tier limits at build time, as they change.

Use the provider's SMTP relay so the send code stays a simple `smtplib` call: connect to the relay host on port 587 with STARTTLS, authenticate with the provider username and the API key as the password, set the `From` to your verified sender and the `To` to your Outlook address. (Username conventions differ by provider: Brevo uses your account login or a dedicated SMTP login; SendGrid used the literal `apikey`. Confirm the username your chosen provider expects.)

**Deliverability and the one-time trust step.** A free single-sender setup has no custom domain, so it cannot fully align DKIM/DMARC, and Outlook's filter is more likely to junk the first few sends. This is expected and it is a one-time fix, not a recurring cost:

- When the first brief lands in Junk, mark it **"not junk"** and add the sender to your **Outlook safe-senders list** (Settings, Junk email, Safe senders).
- After that, Outlook routes it to the inbox consistently, because the address is explicitly trusted and the DKIM weakness stops mattering.

This keeps the project genuinely free and in the inbox, trading a two-minute setup and a possible day or two of fishing it out of Junk for the cost of a domain. If Outlook ever junks it again after a quiet stretch, the fix is the same safe-senders entry.

- **Alternatives considered and rejected:** local cron or Task Scheduler (requires your computer on); Zapier or Make (free tiers too limited); direct Outlook or Gmail SMTP (basic-auth deprecations make both fragile); a paid custom domain (buys away the junk risk for about 10 dollars a year, but is not needed given the safe-senders step, and "free" is a firm requirement). Telegram or Discord were considered as the most reliable, never-junk delivery and remain a strong fallback if email deliverability ever proves more trouble than it is worth, at the cost of the editorial HTML look. Email to the inbox is chosen because the inbox is where the brief is wanted.

---

## 4. Document structure

The email reads top to bottom in three zones: the **settled recap** (diff line, At a Glance, and the deep sections, all describing the finished day), the **fenced "This morning so far" snapshot** (timestamped live pre-market), and **today's schedule** (What to Watch Today). The settled recap is the bulk and carries the accuracy promise; the snapshot is small and clearly marked as live.

### 4.1 Top of email: diff line, then At a Glance

**Diff line ("What changed since yesterday").** A single highlighted line at the very top, above the table. It states only what flipped over the finished day: direction changes, levels broken, streaks extended, and the one event reframing things. It is computed from the cached previous payload (Section 5.5), so it costs nothing. This is the first thing the reader sees and the highest-signal element in the brief.

**At a Glance (top block).** A three-column table read in 30 seconds. The why column is intentionally brief because the depth lives in the sections.

Columns: `Category | Latest (level and change) | Why, in brief`

Rows: Markets, Rates and dollar, Commodities, Crypto, Volatility, This morning (live snapshot), Today's events, Earnings (pre-open), Washington, Bottom line.

The "This morning" row is the one live row and is labeled with its pull timestamp; every other row is the settled finished-day reading.

### 4.2 Section order and the floating Top Story

The body uses a **floating Top Story slot**: whatever the rules engine (Section 5) decides is the single biggest driver goes first, then the rest follow in a fixed order. The brief always leads with what matters most.

**Fixed fallback order when no override fires:**

1. US Equities
2. Rates and the Dollar
3. Commodities
4. Washington and Policy
5. Movers
6. Economic Data Scorecard
7. Earnings on Deck
8. Watchlist
9. Crypto
10. Volatility and Breadth
11. What to Watch Today

Rationale: positions 1 through 3 are the macro spine and are causally chained (oil moves rates, rates move equity rotation), so the drill-down opens where the day's story usually lives. Washington sits at 4, the seam where macro becomes micro, and most of its content (energy and the Fed) is the cause of what was just read above it, so it reads as explanation rather than preamble. Single names follow (5, 8), then context (6, 7), gut-checks (9, 10), and the only forward-looking section closes (11).

**One placement left deliberately swappable:** Movers (5) and Washington (4). If you prefer the index-then-stock zoom (Equities straight into Movers), swap them. Everything else is firm.

When the Top Story slot promotes a section, that section is pulled to the top and removed from its fallback position; the rest keep their relative order.

### 4.3 Section catalog

All eleven sections always appear. Length is earned, not fixed (Section 2 and 5.6): a section with no real move and no matched article gets one honest line, a section with a real move and real news gets the full read. For each below: what it holds, why it earns a place, and whether a chart is available.

| Section | Contents | Why it matters | Chart option |
|---|---|---|---|
| US Equities | Dow, S&P 500, Nasdaq, Russell 2000: settled close, change, rotation story; plus a labeled pre-market line. | The headline read on risk appetite; the spread between indices reveals the type of move. | Daily percent-change bar (default on) |
| Rates and the Dollar | 10-year, 2-year, DXY (settled, FRED-primary in the morning). | The engine room; drives valuations, commodities, currencies. | Yield curve plus 10-year trend (default on) |
| Commodities | WTI crude, gold. | Real-time inflation and growth signal; oil feeds straight into rates and the Fed. | WTI 1-month trend (default on) |
| Washington and Policy | Fed, tariffs, fiscal and shutdown risk, regulation, geopolitics, all framed through market impact. Trump and government are merged into this one section on purpose. | Policy is the standing risk backdrop and is the headline on event days. | Rate path or dot plot (low priority, data harder to get free) |
| Movers | Top 3 winners and losers from the curated liquid universe over the day, the week, and the month, so a name running hot or cold over any window is visible at a glance (email cannot toggle, so the three windows are shown stacked). Gated behind a volume floor. Best-effort: defaults to watchlist-movers-only and upgrades when universe data is reliable. | The most actionable single-stock section. | Horizontal bar of percent moves (optional) |
| Economic Data Scorecard | Releases, actual vs expected. | Tells you how far data beat or missed and what it implies. | Actual vs expected bar (optional) |
| Earnings on Deck | Who reports before open, after close, and notable later in the week. | Single-stock surprises drive intraday volatility. | none |
| Watchlist | Your tickers: price, change, one-line catalyst. | Turns a generic newsletter into your own tool. | Per-ticker 5-day sparklines (on once populated) |
| Crypto | BTC, ETH. | Risk-appetite gut check. | 7-day trend (optional) |
| Volatility and Breadth | VIX. (Breadth deferred, see Section 10.) | Sentiment into and out of risk events. | VIX 1-month trend (optional) |
| What to Watch Today | The day's scheduled events with times. | The only forward-looking section; keeps you from being blindsided. | Optional event timeline (decorative) |

---

## 5. Top Story rules engine (free, deterministic)

This engine decides **what leads**. It is plain Python, no model. The logic picks the Top Story slot in priority order and stops at the first match. The model never participates in this choice.

1. **Tier-one calendar event today?** If the static tier-one calendar (Section 7) shows FOMC decision, CPI, jobs report (nonfarm payrolls), PCE, or GDP, the related section becomes the Top Story. FOMC and policy releases promote Washington and Policy; data releases promote the Economic Data Scorecard.
2. **Large move in a core metric?** If none of the above, compute the standardized move for each core metric (Section 5.1) and promote the largest if it clears its trigger:
   - 10-year Treasury yield: trigger at more than 8 basis points, promote Rates and the Dollar.
   - WTI crude: trigger at more than 3 percent, promote Commodities.
   - S&P 500 (settled session move, with the pre-market futures read as confirmation): trigger at more than 1 percent, promote US Equities.
   - VIX: trigger at more than 15 percent, promote Volatility and Breadth.
   If several trip, pick the largest standardized move, not the largest raw move.
3. **Quiet tape floor.** No tier-one event and nothing clears its trigger: do not manufacture a headline out of Washington. Use the fallback order (US Equities first) and set the diff line and Bottom Line to read "quiet tape." This keeps a flat day honest.

The engine runs on settled finished-day data, so its decision is never driven by a noisy pre-market tick.

**Mechanical-move guard.** Before step 2 promotes a large move, the engine checks the static `data/mechanical_moves.yaml` calendar (Section 7.7). If today is a known mechanical date (index reconstitution, quad witching, a rebalance), a qualifying move in the affected metric is annotated as mechanical and is not promoted to Top Story, because there is no news story to ground it. This prevents the engine from manufacturing a cause for a calendar artifact.

### 5.1 Standardizing moves (the comparability fix)

Raw thresholds are not comparable across metrics: 8 bps on the 10-year and 3 percent on WTI are different kinds of large. For step 2's tie-break, convert each metric's move into a z-score against that metric's own recent daily changes (a rolling 20-trading-day standard deviation of daily moves). Compare z-scores to decide which section wins the slot. The raw triggers above still act as the floor that a move must clear to be eligible at all; the z-score only decides the ranking among those that qualify.

This captures the large majority of the value of a true judgment call, with no API cost and no risk of a model inventing a number. Note that a single large move temporarily inflates the 20-day standard deviation; the raw-trigger floor mostly absorbs this, but it is worth knowing the z-score can understate the next move for a few weeks after a shock.

### 5.5 State caching (required for the diff line, streaks, and rolling history)

GitHub Actions is stateless between runs. To compute the diff line, detect streaks ("5th straight session"), standardize moves, and verify range claims ("three-week low"), the pipeline must remember recent history.

- After a successful run, write a compact `last_run.json` (key levels, changes, the chosen Top Story, the sent-today flag and date, and a short rolling history per metric: recent daily closes sufficient for 5-day and 20-day high/low and streak counts) and commit it back to the repo. See Section 8.3 for why the commit is authored with a personal access token.
- **Backfill on first run.** History does not have to accumulate over a month. On the very first run (or whenever `last_run.json` is missing), pull 20-plus trading days of historical daily closes per metric and seed the rolling history, so streaks, z-scores, and range claims work from day one. **Seed and maintain each metric's rolling history from the same source that is morning-primary for that metric:** FRED (`DGS10`, `DGS2`) for Treasury yields and yfinance for everything else. Mixing bases (a z-score computed off yfinance `^TNX` history while the daily print comes from FRED `DGS10`) introduces a small but real basis mismatch, so keep the history source aligned with the daily-value source.
- On each run, load the previous `last_run.json` first. If it is missing or stale (older than a few trading days) and a backfill is not possible, skip the diff line gracefully rather than printing wrong deltas, and treat range claims as unverified rather than guessing them.
- **"Yesterday" always means the last trading day, never the literal calendar day.** After a holiday or a long weekend, the diff line and every "since yesterday" comparison reference the last session that actually closed (Tuesday after a Monday holiday compares to Friday). The comparison is driven off the rolling history, not the calendar, so a three-day gap is never printed as a one-day move.
- Keep this file small and human-readable so a bad run can be diagnosed by eye.

### 5.6 Explanation engine (the why lines and the deep section reads)

This is the subsystem that writes prose. It exists because a deterministic engine can rank moves but cannot explain them, and the brief's core promise is "numbers plus the why." The design goal is sample-quality causal reads with numbers exactly as trustworthy as a pure-Python version would produce.

**The core principle.** Depth and accuracy both come from feeding the model more computed facts, never from asking the model to know more. Every sentence must trace to either a number computed in Python or a sentence a reporter actually wrote. The model is a writer with two sources on its desk and a rule that it may not write anything it cannot point to.

**Why one call, not eleven.** The model receives the whole picture in a single call and emits a structured object with one entry per section. Per-section calls would blind it to the causal chain the brief is built around (oil feeds rates, rates move equity rotation, per Section 4.2). It must see everything at once to write the cross-links, but it is forced into structured output so each claim stays tagged to its source.

**The pipeline:**

1. **Compute richer inputs.** Today's numbers plus, per metric: the 5-day and 20-day high and low, the streak count, the prior close, and the change. This is the single biggest lever on quality and it is a build implication: the pulls and the state cache must carry short rolling history, not just today's snapshot (Sections 5.5 and 7). **Pre-compute the derived figures you want the model allowed to cite**, because the number check (step 6) rejects any number not present in the input set, and that includes legitimately derived ones. The cross-asset reads the design is built around need figures that are not any single metric's daily value: the weekly and multi-day sums ("up 12 bps on the week"), the 2s10s spread, and the index-versus-index gaps that describe rotation ("Russell lagged the S&P by 0.8 points"). If these are not pre-computed and added to the input set, the validator will reject exactly the synthesis you are paying a capable model to produce, retry, and collapse the section to a flat template. Compute them in Python and hand them to the model as inputs; do not ask the model to derive them.
2. **Match news from RSS headlines and summaries.** The launch build grounds the prose on RSS headlines plus the short description each RSS item carries, which is free and already parsed. Full article-body fetching is deliberately not in the launch build: scraping article HTML is the second-most-fragile dependency in the project (paywalls, bot detection, per-fetch latency and hangs), and headlines plus summaries, combined with the model's licensed "no clear catalyst" honesty, get most of the grounding value at a fraction of the fragility. Body-fetching is the first post-launch enhancement, behind a config flag, added once the pipeline runs clean.
3. **Make the matching explicit and auditable.** Matching is a simple, inspectable rule, not a black box: a per-section keyword and ticker map scores each candidate article by title and summary overlap, and the top 2 to 3 are attached **with their match scores** so a bad match is visible in the structured output rather than silently grounding the wrong story.
4. **Assemble a per-section context bundle.** Hand the model JSON per section: the section's numbers (with the rolling context from step 1), its 2 to 3 matched articles with scores, and a one-line evergreen domain primer (for example, "small caps are the most rate-sensitive index"). The primer is the only place structural knowledge enters, and you control it, so it cannot go stale.
5. **Extract, then write, in that one call.** The model first extracts the explicit causal claims reporters made (for example, "Reuters: yields fell on soft auction demand"), then writes each section using only those extracted reasons plus your numbers. Separating "what was reported" from "how it is phrased" is the trust boundary.
6. **Validate, then render.** The model emits structured JSON per section: `{level, change, context, cause, cause_source_id, confidence, prose}`. Nothing ships before validation:
   - **Number check (tolerant, not exact).** The check verifies that every number in the prose is consistent with an input number, not digit-for-digit identical to it. Specifically: round both the model's number and the candidate input to the same precision and accept a match inside a tolerance band (for example, plus or minus 0.05 for a percentage, a small band for a price the model was told to approximate). The model is instructed to round and approximate ("about 76 dollars," never "76.23"), which shrinks the validator's job to "is this rounded figure consistent with an input." A whitelist of token types is skipped entirely: clock times, calendar dates, and spelled-out ordinals ("fifth straight session"). A number that matches nothing in the input set after tolerance and whitelist is rejected; retry once, then fall back to a flat templated line. This is what makes invented numbers fail to ship. An exact-match check would instead reject normal rounded prose every day and collapse the brief into templates, so the tolerance is load-bearing and must be built first. The input set the check matches against is the **full** set of computed numbers including the pre-computed derived figures from step 1 (weekly sums, spreads, index gaps); a derived figure absent from that set is treated as invented and rejected, which is why step 1 must compute everything the model is allowed to say.
   - **Cause check (honest about what it proves).** Every causal claim must carry a `cause_source_id` pointing to a supplied article; a causal verb ("because," "on," "as," "after") with no source tag is flagged or stripped. This guarantees a cause is *tagged to a real article*; it does **not** verify that the article actually supports the cause (that would require an entailment check that is not performed). So the check prevents untagged invented causes, not mistagged ones, and should be trusted only that far. The match scores from step 3 are the cheap mitigation: a low-scoring match is a warning that the tagged article may not support the claim.
   - **Render from validated fields.** The template, not the model's discretion, enforces the no-em-dash, one-accent, tabular-numeral house style (Section 6.5).

The structured intermediate is human-readable, so a bad morning is diagnosable by eye, the same value `last_run.json` provides. Each run's structured JSON is also written to a `runs/` folder in the repo (Section 8) so prose quality can be audited by reading files rather than by re-reading the inbox.

**What a deep section read must contain.** A deep read is not a longer table line. It is four ingredients, supplied to the model as the rubric for each section:

1. **Level in context.** Not just "4.44%" but where that sits in the recent range (requires the rolling history from step 1).
2. **The move's driver.** Grounded in a matched article, hedged when the news does not support a clean cause.
3. **The cross-link.** How this section connects to the chain (for example, "this falling-oil move is why the Dow is rotating into value"). The model can only write this because it saw the full picture in one call.
4. **The forward hook.** What to watch next in this specific area.

**Depth scales with signal.** All eleven sections always appear, but length is earned. A section with no move and no matched article gets one honest line ("VIX flat, no hedging demand, nothing to read into it"), not a forced paragraph. The `confidence` field drives this: low confidence and no source means short and honest. The model is explicitly allowed, and encouraged, to write "no clear catalyst" when the news is empty. In a market note that is the most trust-building thing it can say.

**Model choice.** Build on a capable model (Claude Sonnet) rather than the smallest one. For eleven deep causal reads with real cross-asset synthesis, the smallest model tends to produce the generic filler the design is trying to avoid. Since this is one call a day, the cost difference is rounding error (Section 9). Downgrade to Haiku only if Sonnet proves overkill in practice.

**Failure fallback.** If the model call fails entirely (timeout, API error, validation failure that survives the retry), the brief still ships using flat templated why lines built from the numbers and direction alone, and the run is logged as degraded and flagged in the email itself (Section 7.5). The brief never blocks on the model.

---

## 6. Charts

- **Generation:** rendered inside the Python pipeline as static PNG images (matplotlib), then embedded in the email as inline (CID) attachments so they display even when a client blocks remote images.
- **Why static, not interactive:** email clients do not run scripts; a static image is the only reliable cross-client option.
- **Caveat that drove the design:** images are the most fragile part of email and a chart in every section kills the 30-second skim. Therefore charts are selective toggles, not one per section.

Default on:
- Equities: daily percent-change bar across the four indices (instantly shows rotation).
- Rates: 10-year trend and yield curve snapshot (the typical daily driver).
- Commodities: WTI 1-month trend (current macro driver).

Off by default, one flag away:
- VIX trend, movers bar, crypto trend, data scorecard bar, watchlist sparklines (sparklines turn on automatically once the watchlist is populated).

### 6.5 Visual design and email rendering

**The look.** A dark trading-terminal aesthetic: near-black panels, ledger-style monospace figures, one amber accent. Authority without marketing gloss. One accent, not a palette.

> **Design reversal (June 2026).** The original §6.5 look was a cream/navy/gold broadsheet (paper `#FBFAF7`, ink navy `#13202E`, gold `#B0892F`). The shipped v2 design is the dark terminal below, chosen on review of side-by-side mockups. The broadsheet palette is retired; the rules (one accent, direction-only green/red, fenced live block, tabular monospace figures) carry over unchanged.

- **Palette (hex):** page background `#0B0E14` (near-black); content panel `#11151F`; inset panels (figure rows, live fence, diff line) `#0E121B`; primary text and figure values off-white `#E6E3DA`; body prose `#C9C6BD`; hairline `#232A36`; a single amber rule/accent `#E8A33D`; direction green `#4FB477`; direction red `#E5594F`; muted grey `#7A828F` for captions and flat readings.
- **Type, with the signature:** a **monospace with tabular numerals for every figure** so numbers align in a column like a terminal, used for the masthead and headings as well to carry the terminal feel, and a clean sans for body prose. The tabular monospace numerals are the signature element; protect them. Design-target faces are IBM Plex Mono (masthead, headings, numbers) and Inter or Helvetica Neue (body).
- **Email-safe build constraints.** The design target above is what it should look like; the shipped template is constrained. Email clients strip `<style>` blocks, ignore flex and grid, and block web fonts. Therefore the production `template.html.j2` uses a single-column table layout, fully inline styles, and web-safe stacks: a `Consolas, "SFMono-Regular", Menlo, monospace` stack for the masthead, headings, and figures, and a `"Helvetica Neue", Arial, sans-serif` stack for body prose. The look survives this stack; the web fonts are a nice-to-have, not a dependency. (Note: a few clients force light mode and may not honor the dark background; the layout still reads, since direction color and structure do not depend on it.)
- **The live snapshot is visually fenced.** The "This morning so far" zone is set apart from the settled recap (for example, a tinted block or a labeled rule) and every figure in it carries its pull timestamp, so a reader never confuses a provisional pre-market number for a settled fact.
- **The degraded banner.** When the run is degraded (model failed, or too many stale fields), a small marked banner appears at the top of the brief itself, not only in the Actions log. See Section 7.5.
- **Color discipline.** Green and red carry direction only. Everything else is near-black, off-white, grey, and the one amber rule. Resist adding a second accent.

**Logos: the disciplined version.** No logos scattered through the body. They are images with the same blocked-image fragility as charts, the free sourcing options got worse (Clearbit's free logo API shut down at the end of 2025; logo.dev forbids re-hosting and requires remote images), and a logo next to a ticker adds recognition, not information. The one place a small mark earns its keep is a list you scan fast by name:

- Show a 16px favicon glyph as a leading element **only in Movers and Watchlist rows.**
- Source it from Google's favicon service (`https://www.google.com/s2/favicons?domain=<domain>&sz=64`), which is free and needs no key. Accept that it is a low-resolution favicon, not a brand logo; at 16px that is fine.
- Maintain a small ticker-to-domain map for the names you cover. If a favicon fails to load, the row still reads correctly from the ticker and text.

---

## 7. Data sources

Every figure in the email links to the page it came from. yfinance figures link to the matching Yahoo Finance quote page; FRED figures link to the FRED series page; calendar and earnings link to the provider page; headlines link to the article URL carried in the RSS item.

| Data | Provider | Link | Notes |
|---|---|---|---|
| Indices, futures, VIX, crypto, commodities, movers | yfinance (Yahoo Finance) | https://github.com/ranaroussi/yfinance | Free, no key. Quote pages like https://finance.yahoo.com/quote/%5EGSPC . Pulls also carry short rolling history for range and streak claims, and supply the first-run backfill (Section 5.5). |
| Treasury yields, official WTI, macro series | FRED (St. Louis Fed) | https://fred.stlouisfed.org | Authoritative and, in the morning, **primary for Treasury yields** since H.15 has updated overnight. **Not morning-primary for oil**: the WTI series `DCOILWTICO` often lags several business days, so yfinance `CL=F` is primary for oil and FRED is a cross-check only (see 7.5). Free API key: https://fredaccount.stlouisfed.org/apikeys . API docs: https://fred.stlouisfed.org/docs/api/fred/ |
| Tier-one event dates (FOMC, CPI, jobs, PCE, GDP) | Static file in repo | Published a year ahead by the Fed, BLS, BEA | `data/tier_one_calendar.yaml`. Strictly more reliable than any free API for the most consequential engine trigger. Refresh quarterly. |
| Minor economic events and earnings calendar | Financial Modeling Prep (free tier) | https://site.financialmodelingprep.com/developer/docs | Free key (`FMP_API_KEY`). Used only for secondary "What to Watch" events and earnings, not for the tier-one trigger. Finnhub is the backup (`FINNHUB_API_KEY`): https://finnhub.io/docs/api . Degrade quietly when down. |
| Second price source (yfinance backup) | Stooq (primary backup) / Twelve Data (alt) | https://stooq.com/db/ ; https://twelvedata.com/docs | Stooq: free CSV, no key, but low daily quota and CAPTCHA history; best-effort, verify in Phase 0. Twelve Data: free Basic 800/day, covers crypto and equities but not indices (paid tier). See Section 7.5. |
| News and narrative (RSS headlines and summaries) | CNBC, MarketWatch, Federal Reserve | CNBC markets: https://www.cnbc.com/id/100003114/device/rss/rss.html ; MarketWatch top stories: http://feeds.marketwatch.com/marketwatch/topstories/ ; Fed press releases: https://www.federalreserve.gov/feeds/press_all.xml | Free, no rate limits. The explanation engine grounds on headlines and the summary each RSS item carries (Section 5.6). Article-body fetching is a later, flagged enhancement, not in the launch build. Verify exact feed URLs at build time as they change occasionally. |
| Market holidays | pandas-market-calendars | https://pypi.org/project/pandas-market-calendars/ | Used to skip non-trading days. |
| Company favicons (Movers, Watchlist only) | Google favicon service | https://www.google.com/s2/favicons?domain=<domain>&sz=64 | Free, no key. 16px favicons, not brand logos. |
| Narrative prose | Anthropic API (Claude Sonnet) | https://docs.claude.com | One constrained call per run. Numbers fenced off and validated (Section 5.6). Cost under a dollar a month (Section 9). |

### Symbol and series mapping

| Metric | Source | Symbol or series |
|---|---|---|
| S&P 500 (index / futures) | yfinance | `^GSPC` / `ES=F` |
| Nasdaq Composite / Nasdaq 100 fut | yfinance | `^IXIC` / `NQ=F` |
| Dow Jones / futures | yfinance | `^DJI` / `YM=F` |
| Russell 2000 / futures | yfinance | `^RUT` / `RTY=F` |
| VIX | yfinance | `^VIX` |
| WTI crude | yfinance (primary) / FRED (cross-check, lags) | `CL=F` / `DCOILWTICO` |
| Gold | yfinance | `GC=F` |
| US Dollar Index (DXY) | yfinance | `DX-Y.NYB` |
| Bitcoin / Ethereum | yfinance | `BTC-USD` / `ETH-USD` |
| 10-year Treasury yield | FRED (primary) / yfinance | `DGS10` / `^TNX` |
| 2-year Treasury yield | FRED | `DGS2` |
| Broad dollar index (alt to DXY) | FRED | `DTWEXBGS` |

### Movers universe and the best-effort rule

yfinance has no clean free gainers and losers screener, and pre-market volume in particular is thin, so raw percent moves are noisy and easy to misread. Movers is therefore treated as a **best-effort section, not a headline guarantee.**

- **Default:** watchlist-movers-only. The section always has something honest to show from names you already track.
- **Upgrade:** when the curated-universe screen is reliable on a given morning, it upgrades the section to the fuller board: top 3 winners and top 3 losers over each of three trailing windows (day, week, month), computed in Python from the rolling closes already pulled (1-session, ~5-session, ~21-session returns), then ranked and sliced. No window is fabricated when history is thin; a window with no usable data simply renders nothing. Universe is a curated list of liquid names (roughly 50 to 150) plus the watchlist, defined in config. Do not screen the full index live; it is slow and rate-limit prone.
- **Volume floor:** gate every reported move behind a minimum volume threshold, so a 9 percent "move" on 300 shares is never headlined. The floor applies to the pre-market snapshot too.
- **Degrade path:** if the universe screen is unreliable, ship watchlist-movers-only rather than printing noise. This is the default, so a bad screen morning is a non-event.

### 7.5 Resilience (yfinance is the single point of failure)

yfinance scrapes Yahoo and can break without warning. The pipeline must not silently send a brief full of blanks.

- **Health check.** After pulling, validate that each core field is present and numeric. Core fields: the four indices or their futures, the 10-year, WTI, and the dollar index.
- **GitHub Actions amplifies this single point of failure.** Yahoo rate-limits and sometimes outright blocks cloud-runner IP ranges far more aggressively than a home IP, and a block hits everything at once. FRED only backstops two core fields (the 10-year and, imperfectly, WTI); it does nothing for the indices, futures, VIX, gold, crypto, or the dollar index. So a runner-IP block does not degrade gracefully into FRED, it sends almost every field to "stale" and trips the hard floor. Mitigate with a second price source, but pick it with eyes open. **Stooq** is the conventional free yfinance backup (free CSV endpoints at `stooq.com`/`stooq.pl` covering indices and futures), but it is a best-effort backup, not a robust one: it enforces a low, undocumented daily request quota (it returns "Exceeded the daily hits limit" instead of data when tripped) and it has previously gated its bulk endpoints behind CAPTCHA. For one daily pull of roughly fifteen symbols the quota is likely fine, but its US-futures and `^VIX` coverage is uneven, so verify it actually serves the runner during Phase 0 alongside the yfinance test. **Twelve Data** (free Basic tier: 8 calls/minute, 800/day) is a cleaner-API alternative for crypto and individual equities, but its free tier does not cover indices (those require its paid Grow plan), so it does not directly replace the `^GSPC`/`^VIX` pulls. If you choose to add no second source at all, state plainly that a Yahoo block equals no brief that day and that this is accepted.
- **Fallback (rates).** Fall back to FRED `DGS10`/`DGS2` when the yfinance yield pull is missing or NaN. In the morning brief FRED reflects yesterday's settled close, which is exactly what the settled recap wants, so this fallback is clean for rates. A FRED value standing in for a live pre-market figure is still flagged as prior-session.
- **Fallback (oil) is last-resort, not clean.** Because `DCOILWTICO` lags several business days (Section 3.1), FRED is not a clean stand-in for yesterday's WTI close. If the yfinance `CL=F` pull fails, prefer marking oil **stale** over substituting a possibly multi-day-old FRED print as if it were yesterday's settle. Only use the FRED value as an explicitly date-stamped last resort, never silently.
- **Stale-field flagging.** Any field that could not be refreshed renders with a small "stale" marker and is excluded from the diff line, the Top Story engine, and the explanation engine, rather than being shown as a real move.
- **News and model degradation.** If RSS is unavailable, the explanation engine falls back to flat templated lines. If the model call fails, the brief ships with templated why lines and is logged as degraded. The brief never blocks on news or the model.
- **Degraded banner in the email.** Whenever the run is degraded (model failed, or at least `resilience.degraded_stale_threshold` fields are stale), a small banner at the top of the brief itself says so. Logs are not read daily; the brief is. The reader must never mistake a degraded brief for a clean one.
- **Hard floor.** If more than `resilience.hard_floor_missing_threshold` core fields are missing, send a short "data unavailable this morning" notice instead of a broken brief, and exit non-zero so the run is visibly failed in the Actions log.

### 7.6 Monitoring and the silent-failure problem (the dead-man's switch)

Every mechanism in 7.5 fires **when the brief runs**. None of them fire when it stops running at all, and that is the failure most likely to end the project's usefulness over a span of years. The three ways it goes fully silent:

- The scheduled workflow is auto-disabled (the 60-day inactivity rule, Section 8.3) or GitHub's scheduler simply skips.
- Yahoo permanently breaks the pinned yfinance and the hard floor exits non-zero every morning.
- The email provider's free tier is cut or the sender is de-verified, so sends fail upstream of the brief.

In all three, the symptom is the same: no email arrives, and **the absence of an email is the easiest thing in the world not to notice.** A degraded banner cannot help, because nothing is delivered to carry it. The fix is a heartbeat on a channel independent of the email path:

- **Expected-send ledger.** On every successful send, the run already stamps `last_sent_date` (Section 8.3). A heartbeat check reads that stamp and, on any trading day where it is not today by a chosen cutoff (for example 10:00 AM CT), fires an alert.
- **Independent alert channel.** The alert must not travel the same path that may be broken. A Telegram bot message or a GitHub Actions failure notification (email-on-workflow-failure is built in and free) is ideal precisely because it does not depend on the transactional email provider. This is the role Telegram earns at launch: not delivery, monitoring.
- **Cheapest viable version.** If a separate heartbeat job is too much for v1, at minimum rely on GitHub's built-in "notify on workflow failure" setting and make sure the hard floor and any fatal error exit non-zero so a broken morning shows up as a failed run in your inbox. The non-negotiable property is that a total stoppage reaches you within a day, not three weeks.

### 7.7 Recurring mechanical moves the engine must not mistake for news

Some large moves are calendar artifacts with no story behind them, and the rules engine (Section 5) will otherwise promote them as a Top Story and the explanation engine will hunt for a cause that does not exist. Maintain a small static companion to the tier-one calendar, `data/mechanical_moves.yaml`, listing dates where a mechanical move is expected:

- Russell reconstitution (late June) and other index reconstitution and rebalance dates.
- Quadruple witching (third Friday of March, June, September, December).
- S&P and other index add/drop effective dates.
- Month-end and quarter-end rebalancing where it reliably distorts.

On a listed date, the engine still reports the move but **annotates it as mechanical and suppresses promotion** ("Russell moved on reconstitution, not on news, discount it"), the same honesty discipline as the quiet-tape floor. Refresh this file when you refresh the tier-one calendar.

---

## 8. Tech stack and setup

### 8.1 Repository layout (planned)

```
market-brief/
  brief.py              main entry: gather, build, send
  sources/
    prices.py           yfinance pulls (+ FRED fallback hooks, rolling history, first-run backfill)
    fred.py             FRED pulls
    calendar.py         FMP or Finnhub minor events and earnings calendar
    news.py             RSS parsing (headlines + summaries; body-fetch behind a flag, later)
  engine/
    top_story.py        rules engine (Section 5), z-score standardization
    narrative.py        explanation engine (Section 5.6): match, bundle, call, validate
    diff.py             "what changed since yesterday" (Section 4.1, 5.5)
    state.py            load/save last_run.json (levels, history, sent flag, backfill)
  render/
    charts.py           matplotlib chart functions
    template.html.j2    Jinja2 email template (table layout, inline styles, fenced live zone, degraded banner)
  data/
    tier_one_calendar.yaml   FOMC, CPI, jobs, PCE, GDP dates (refresh quarterly)
    mechanical_moves.yaml    index reconstitution, quad witching, rebalances (Section 7.7)
  runs/                 per-run structured JSON dumps for quality auditing
  config.yaml           toggles, watchlist, recipients, movers universe, ticker-to-domain map
  last_run.json         cached previous payload (committed back by the workflow)
  requirements.txt
  .github/workflows/
    daily-brief.yml     scheduled run
    smoke-test.yml      manual build-without-send check
```

### 8.2 Dependencies (requirements.txt)

Pin versions to protect against a silent breaking change at send time. Resolve exact pins at build time. Pin `anthropic` as deliberately as `yfinance`: a major-version SDK bump can change call signatures or default behaviors and is exactly the silent year-two failure Section 13 warns about. Treat its pin as load-bearing, not incidental.

```
yfinance==<pin>
pandas
requests
matplotlib
feedparser
jinja2
python-dateutil
pandas-market-calendars
pyyaml
anthropic==<pin>
```

### 8.3 GitHub Actions workflow (example)

```yaml
name: Daily Market Brief
on:
  schedule:
    # Two lines to cover US daylight and standard time. The script also guards
    # on a local-time window and skips if today has already sent.
    - cron: "30 13 * * 1-5"   # 8:30 CT during CDT (13:30 UTC)
    - cron: "30 14 * * 1-5"   # 8:30 CT during CST (14:30 UTC)
  workflow_dispatch: {}        # allows manual runs for testing
jobs:
  send:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          # Use a PAT so the state commit counts as repo activity and the
          # scheduled workflow is not auto-disabled after 60 days.
          token: ${{ secrets.STATE_COMMIT_PAT }}
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt
      - run: python brief.py
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          FMP_API_KEY:   ${{ secrets.FMP_API_KEY }}
          FINNHUB_API_KEY: ${{ secrets.FINNHUB_API_KEY }}
          FRED_API_KEY:  ${{ secrets.FRED_API_KEY }}
          SMTP_HOST:     ${{ secrets.SMTP_HOST }}
          SMTP_USER:     ${{ secrets.SMTP_USER }}
          SMTP_PASS:     ${{ secrets.SMTP_PASS }}
          EMAIL_FROM:    ${{ secrets.EMAIL_FROM }}
          EMAIL_TO:      ${{ secrets.EMAIL_TO }}
```

**Cron guard (window plus idempotency).** An exact-minute match silently never-fires on the many mornings GitHub's scheduler runs 10 to 40 minutes late or skips a run. The guard:

- Fires if local Central time is inside a window (roughly 8:25 to 9:15 AM, ending before the 8:30 open's data fully settles but wide enough to absorb scheduler lag) and the `last_sent_date` in `last_run.json` is not today.
- After a successful send, stamps `last_sent_date` to today so the second cron line and any retry are idempotent and cannot double-send.
- If it somehow fires after the window, still sends but stamps the brief as late; a late brief before or just after the open beats no brief.
- Prints the actual send time in the footer, not a hardcoded time, so real delivery times can be observed and the window tuned.

DST note: GitHub cron runs in UTC and does not follow daylight saving. The two cron lines plus the in-script local-time window mean exactly one fires inside the window year round; the other falls outside it and exits.

**State commit and the 60-day auto-disable.** Scheduled workflows are disabled after 60 days of repo inactivity, and the only writes here are the bot pushing `last_run.json`. Commits authored with the default `GITHUB_TOKEN` have historically not reliably counted as activity. Author the state commit with a personal access token (`STATE_COMMIT_PAT`) so it counts as user activity. Verify current behavior at build time and keep a calendar reminder as a cheap backstop. (Note: the daily state commit accumulates history over a year; this is livable, and the commit cannot be moved off-repo because the commit itself is the anti-auto-disable mechanism. Squash occasionally if the history bloats.)

A second workflow, `smoke-test.yml`, runs `python brief.py --no-send` on `workflow_dispatch` so you can validate a full build without emailing anything.

### 8.4 Secrets and config

- **GitHub Secrets (never in code):** `ANTHROPIC_API_KEY`, `FRED_API_KEY`, `FMP_API_KEY`, `FINNHUB_API_KEY`, `SMTP_HOST`, `SMTP_USER`, `SMTP_PASS`, `EMAIL_FROM`, `EMAIL_TO`, and `STATE_COMMIT_PAT` (a fine-grained personal access token with contents write on this repo only). `SMTP_*` are your transactional provider's relay credentials. For Brevo, `SMTP_USER` is your account/SMTP login and `SMTP_PASS` is the API key or SMTP key; confirm the exact username convention for whichever provider you pick (Section 3.3). `EMAIL_FROM` is your verified sender at the provider; `EMAIL_TO` is your Outlook address. `FINNHUB_API_KEY` is optional and only needed if you wire the Finnhub backup for the minor calendar; the calendar degrades quietly without it. Set these yourself in repo Settings, Secrets and variables, Actions. They are not handled inside this project's chat.
- **config.yaml (example):**

```yaml
send_time: "08:30"
send_window_end: "09:15"   # local-time guard window upper bound
timezone: "America/Chicago"
# Recipient and sender are the EMAIL_TO / EMAIL_FROM GitHub Secrets, not config,
# so there is a single source of truth for the destination (Sections 8.4, 13).
resilience:
  degraded_stale_threshold: 2      # this many stale core fields trips the degraded banner
  hard_floor_missing_threshold: 4  # more missing than this sends "data unavailable" and exits non-zero
  second_price_source: true        # best-effort yfinance backup for indices/futures/VIX (Section 7.5, Decision 18)
  second_price_provider: "stooq"   # "stooq" (no key, low quota) or "twelvedata" (key, no free indices)
monitoring:
  heartbeat_enabled: true          # dead-man's switch (Section 7.6, Decision 15)
  heartbeat_cutoff: "10:00"        # local-time cutoff; if last_sent_date is not today by now on a trading day, alert
  heartbeat_channel: "github"      # "github" (workflow-failure notify, built in) or "telegram"
  # TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID live in GitHub Secrets if heartbeat_channel is "telegram"
narrative:
  enabled: true            # explanation engine (Section 5.6)
  model: "claude-sonnet-4-6"
  articles_per_section: 3
  use_article_bodies: false   # later, flagged enhancement; launch grounds on headlines + summaries
  number_tolerance_pct: 0.05  # tolerant number check band for percentages
charts:
  index_bar: true
  yield_curve: true
  oil_trend: true
  vix_trend: false
  movers_bar: false
  crypto_trend: false
  data_scorecard: false
  watchlist_sparklines: true
sections:
  breadth: false           # deferred, see Section 10
movers_universe:           # curated liquid names, best-effort upgrade over watchlist-only
  - AAPL
  - NVDA
  - MSFT
  - AMD
  - TSLA
movers_min_volume: 50000   # volume floor; below this a move is not headlined
watchlist: []              # add tickers, for example: [AAPL, NVDA, MSFT]
ticker_domains:            # for the Movers/Watchlist favicon glyph
  NVDA: nvidia.com
  AMD: amd.com
  KMX: carmax.com
```

### 8.5 Running locally (for testing)

```
pip install -r requirements.txt
export ANTHROPIC_API_KEY=... FRED_API_KEY=... FMP_API_KEY=... SMTP_HOST=... SMTP_USER=... SMTP_PASS=... EMAIL_FROM=... EMAIL_TO=...
python brief.py --no-send     # build only, writes the HTML to disk for inspection
python brief.py               # full run, sends
```

`--no-send` also implies no state write: it does not write `last_run.json` and never touches the `last_sent_date` flag, so a partial or test build cannot poison the next day's diff or the idempotency guard. A local full run (`python brief.py`) sends and writes state locally but does not need `STATE_COMMIT_PAT`; the PAT is workflow-only, since the commit-back to the repo only happens on Actions. Use the `workflow_dispatch` button in the Actions tab to trigger a real run on demand.

---

## 9. Cost

- **Pipeline: effectively free.** GitHub Actions, yfinance, FRED, RSS, matplotlib, and the transactional provider's free tier cost nothing. FMP and Finnhub free tiers cover the minor calendar and earnings. The inbox is reached for free via the safe-senders step (Section 3.3), with no domain purchase required.
- **Explanation engine:** one model call per weekday, roughly 5,000 input and 1,500 output tokens. On Claude Sonnet (`claude-sonnet-4-6`) this is on the order of a few cents per run, under a dollar a month. On Claude Haiku 4.5 (`claude-haiku-4-5`) it is roughly a cent per run, well under 50 cents a month. Sonnet is the recommended build target for the depth the brief requires (Section 5.6); Haiku is the fallback if Sonnet proves overkill.
- **Why the model is included rather than avoided.** The temptation is to skip the model out of fear it will invent a number. The validation harness in Section 5.6 prevents an invented number from shipping: the model is told to round, the tolerant number check rejects any figure not consistent with an input, and a failed check falls back to a templated line. The numbers stay as deterministic as a pure-Python build. The model only writes the connective tissue, which a rules engine cannot write at all. The cost was never the obstacle; the trust mechanism was, and it now exists.

---

## 10. Decisions and deferrals

Settled decisions:

1. **Delivery: free transactional relay (Brevo), single verified sender, addressed to Outlook, with the one-time safe-senders step.** No domain, no payment. SendGrid is no longer free (its permanent free tier was retired May 27, 2025), so Brevo is the primary; Resend, Mailtrap, or Amazon SES are the documented free fallbacks. See Section 3.3.
2. **Timing: 8:30 AM Central.** Settled recap of the finished day (yesterday and settled overnight) plus a fenced, timestamped live pre-market snapshot, then today's schedule. See Section 3.1.
3. **The why lines: a single constrained model call.** Numbers fenced off and validated with a tolerant check; the model never picks importance; failure falls back to templated lines. See Section 5.6.
4. **Number check is tolerant, not exact**, with a whitelist for times, dates, and ordinals, and the model instructed to round. See Section 5.6.
5. **News grounds on RSS headlines and summaries at launch**; article-body fetching is a later flagged enhancement. See Sections 5.6 and 7.
6. **Movers is best-effort**, defaulting to watchlist-only and upgrading when the universe screen is reliable. See Section 7.
7. **History is backfilled on first run** so the engine works day one. See Section 5.5.
8. **A degraded banner appears in the email**, and each run's structured JSON is dumped to `runs/`. See Sections 6.5, 7.5, and 8.1.
9. **All eleven sections kept, depth earned not fixed.** Quiet sections get one honest line; the model may say "no clear catalyst." See Sections 2, 4.3, 5.6.
10. **Tier-one calendar is a static file in the repo.** FMP and Finnhub used only for minor events and earnings. See Sections 5 and 7.
11. **State commit authored with a personal access token** to survive the 60-day workflow auto-disable. See Sections 8.3 and 8.4.
12. **DST handled by two cron lines plus an in-script local-time window guard.** See Section 8.3.
13. **Default-on chart set: index bar, yield curve, oil trend.** No additions.
14. **Oil is yfinance-primary, FRED is a cross-check only**, because FRED's WTI series lags several business days and cannot be trusted as yesterday's settled close. Treasury yields remain FRED-primary. See Sections 3.1, 7, 7.5.
15. **A heartbeat on an independent channel guards against silent total failure**, so a full stoppage reaches you within a day rather than weeks. See Section 7.6.
16. **A static mechanical-moves calendar keeps the engine from manufacturing a cause for calendar artifacts** (reconstitution, quad witching, rebalances). See Sections 5 and 7.7.
17. **The pre-market snapshot is labeled by actual pull time**, relabeling to "early session" if the send slips past the 8:30 cash open. See Section 3.1.
18. **A second price source for indices, futures, and VIX is in the build, gated on the Phase 0 finding.** A cloud-runner Yahoo block hits every field at once and FRED backstops only two, so a second source is treated as core rather than optional. Stooq is the conventional free choice but a best-effort one (low daily quota, CAPTCHA history, uneven futures/VIX coverage), so verify it serves the runner during Phase 0; Twelve Data is a cleaner-API alternative that covers crypto and equities but not indices on its free tier. If Phase 0 (Section 11) shows the runner is never blocked, the second source is dropped and a Yahoo block is accepted as "no brief that day." See Section 7.5.

Watchlist tickers are still yours to provide; until populated, the section ships as a placeholder template and its sparklines stay off.

---

## 11. Build order

Dependency-ordered. Build top to bottom.

0. **Prove the boring external pieces work first (the test send).** Before building anything smart, write a throwaway script that pulls about five numbers, drops them in a plain table, and sends one real email to your Outlook inbox. Run it for about three mornings **via `workflow_dispatch` (and a temporary schedule) on GitHub Actions, not locally** -- the cloud runner is the only place that reveals whether Yahoo blocks the runner IP and whether the scheduler fires near 8:30, neither of which a local run can show. This answers the things you cannot reason your way to and that everything else sits on top of: does a free-relay email actually land in your inbox (after the safe-senders step), does yfinance give usable correct numbers at send time from the runner, does Yahoo serve the runner without blocking it, and does the GitHub Actions schedule actually fire near 8:30. If delivery junks or the data is garbage, you learn it after 30 throwaway lines, not after building the whole engine on a cracked foundation. Delete the script once it has answered. (If you would rather build the real thing and fix delivery and data issues as they surface, that is a defensible choice; the test send's only value is isolating these unknowns up front.)
1. **Safety net: pin yfinance and add the smoke-test workflow.** Pin every fragile dependency and add `smoke-test.yml` (build without send on `workflow_dispatch`). Make `--no-send` imply no state write from the start. This protects every later step and lets you validate builds without emailing yourself.
2. **State caching (`state.py`, `last_run.json`), with first-run backfill.** Nothing downstream can reference yesterday until this exists. Carry the rolling history and the sent-today flag. Backfill 20-plus days on first run. Commit `last_run.json` back to the repo with the personal access token at the end of a successful run.
3. **The diff line (`diff.py`).** Depends on step 2. Compute direction flips, broken levels, and streaks from the cached payload.
4. **Top Story engine (`top_story.py`).** Z-score standardization against rolling 20-day volatility for the tie-break, the quiet-tape floor, and the static tier-one calendar driving step 1.
5. **Resilience (`prices.py`, `fred.py`).** Core-field health check, FRED fallback where the mapping exists, stale-field flagging, the degraded banner, the news and model degradation paths, and the hard floor that sends a short notice rather than a broken brief.
6. **Explanation engine (`narrative.py`, `news.py`).** Depends on steps 2 through 5, because it consumes the numbers, the rolling history, the chosen Top Story, and the matched headlines. Build the auditable matcher, the context bundle, the single constrained call, the structured output, the **tolerant** number check and the cause check, the retry, the templated fallback, and the `runs/` JSON dump. This is where the brief's voice lives, so build it after the data it speaks about is trustworthy.
7. **The email-safe template (`template.html.j2`) and charts.** Build using the section order, table layout, inline styles, the web-safe font stack, the fenced live-snapshot zone, the degraded banner, and favicons confined to Movers and Watchlist. Render from validated fields only. Wire the three default-on charts last.

Order logic: prove the external unknowns, then the safety net, then state, then deterministic intelligence, then resilience, then the explanation layer, then presentation. The data and delivery layers are the real risk, and the explanation layer is only trustworthy once the data beneath it is, so prove the boring parts first, write prose late, and style last.

---

## 12. Future ideas

Not in the launch build; revisit only if the brief earns the investment.

- Article-body fetching for deeper grounding (the first enhancement, already specced behind a config flag in Section 5.6).
- Sector heatmap (sector ETF performance).
- Week-ahead preview on Mondays.
- Personal portfolio P and L if holdings are provided.
- Market-implied rate path or dot plot chart for the Washington section once a free source is identified.
- Breadth (advancers vs decliners), if the brief proves it would be missed. It is the one free data point that needs extra plumbing for the least marginal signal, so it waits.
- A confidence-tuned narrative that learns which causal phrasings later proved right or wrong (long-term).
- Telegram or Discord delivery as a never-junk alternative if email deliverability ever proves more trouble than it is worth.

---

## 13. Longevity and maintenance

The sections above describe a correct build. This one describes keeping it correct and read for years, which is a different problem. These are the slow failures that do not show up on day one and are the real reason daily tools get abandoned.

**Dependencies die slowly; plan the obituary, not just the pin.**
- Pinning yfinance (Section 8.2) is double-edged. A pin protects against a bad release but freezes you on a broken version when Yahoo changes its backend, at which point the pin *is* the bug and the fix is to unpin and bump. Set a standing reminder (quarterly) to run `smoke-test.yml` against a fresh yfinance and bump the pin deliberately. Pin-and-forget is how this project silently dies in year two.
- Free tiers get cut. Brevo has tightened its tier before, and SendGrid removed its permanent free tier entirely in May 2025, which is the cautionary case: a provider you depend on can withdraw the free path outright. Treat the provider as replaceable: keep the send path a thin SMTP relay call (Section 3.3) so swapping to a documented fallback (Resend, Mailtrap, Amazon SES) is a credentials change, not a rewrite. If the provider cuts you off, the heartbeat (Section 7.6) is what tells you before three weeks pass.
- The model string dies. `claude-sonnet-4-6` will eventually be retired; when it is, the narrative engine fails into templated lines (Section 5.6 fallback) and keeps shipping, so the only warning is the degraded banner. Heed the banner, and re-check the current model name when you do your quarterly maintenance pass.
- Keys rotate or get disabled (FMP, Finnhub, Anthropic, the email provider, and the Telegram bot token if used for the heartbeat). The degraded paths absorb this without crashing, which means a dead key can hide for weeks behind a quietly degraded brief. The quarterly pass should confirm every secret still authenticates.

**Repo hygiene, or the diagnosis tools drown.**
- `runs/` grows unbounded at about 250 files a year. The "diagnose by reading files" value (Sections 5.6 and 8) erodes once there are thousands. Add a retention step: keep roughly the last 90 days in `runs/` and delete older dumps (or move them to a compressed archive). The daily state commit has a squash plan (Section 8.3); `runs/` needs the same discipline.
- Keep the repo **public** if you can: public repos get unlimited Actions minutes, private repos draw down the 2,000-minute monthly free bucket (one short daily run is well within it, but it is not free-forever the way public is).
- `config.yaml` carries your watchlist in plaintext, which in a public repo is exposed. The recipient address is already a GitHub Secret (`EMAIL_TO`), not config, so it is not exposed. The watchlist is low-stakes, but if it bothers you, move `watchlist` into GitHub Secrets and read it from the environment, the same way the API keys and `EMAIL_TO` are handled (Section 8.4).

**The editorial half, which decides whether you keep reading it.**
- Ship with a real watchlist, not `[]`. The watchlist is the section that turns a generic newsletter into your tool (Section 4.3), and an empty one is the most-skipped block in the brief. Populate it before first send.
- Prose fatigue is the likeliest reason you stop reading, and it arrives in quiet stretches when every flat day reads the same. The design already licenses the cure (Section 2: cut a section that stops earning attention; the model may say "no clear catalyst"). Make it a habit: skim the `runs/` dumps about once a month, and when a section has been one honest line for weeks, cut it or fold it. A leaner brief you read beats a complete one you skim.
- The causal reads are only worth trusting if they hold up. There is no launch-time scoring of whether the "why" was right (that is deferred, Section 12), so the lightweight substitute is the monthly `runs/` skim: spot-check whether the brief called the cause correctly on a few big days. If it is consistently reaching for thin causes instead of saying "no clear catalyst," tighten the match-score threshold (Section 5.6).

---

## Appendix A: Structure reference (not a worked example)

This shows the **shape** of the brief, not real numbers. A full worked example with illustrative numbers is deliberately omitted at this stage, because an invented sample tends to get treated as real once it is on the page. The first real worked example should come from actual pipeline output, audited against source pages. What follows is the skeleton the template and the explanation engine fill in.

```
Morning Market Brief
[Weekday, Date] | Sent [actual send time] CT
[degraded banner appears here only if the run was degraded]

What changed since yesterday: [diff line: direction flips, levels broken,
streaks extended, the one reframing event; or "quiet tape"]

At a Glance
| Category          | Latest (level and change)        | Why, in brief |
| Markets           | [settled closes + changes]       | [one line]    |
| Rates and dollar  | [settled, FRED-primary]          | [one line]    |
| Commodities       | [settled]                        | [one line]    |
| Crypto            | [settled / weekly]               | [one line]    |
| Volatility        | [VIX settled]                    | [one line]    |
| This morning      | [LIVE pre-market snapshot as of HH:MM CT] | [one line] |
| Today's events    | [scheduled, with times]          | [one line]    |
| Earnings (pre-open)| [names]                         | [one line]    |
| Washington        | [standing policy risks]          | [one line]    |
| Bottom line       | [the take]                       |               |

Top Story: [section promoted by the rules engine, or US Equities by fallback]
- [deep read: level in context, grounded driver, cross-link, forward hook]

Settled recap, sections 1-10 in order (Top Story pulled out above):
  Each section is one honest line when quiet, a full four-ingredient read
  when there is a real move and real news. Numbers are settled and sourced.

This morning so far  [visually fenced, every figure timestamped LIVE]
- [pre-market index futures, overnight headlines; provisional, labeled]

11. What to Watch Today  [the only forward-looking section, pure schedule]
- [today's events with times]

Footer: data sources (automated), actual send time.
```

The settled recap is the trustworthy bulk and carries the accuracy promise. The "This morning so far" block is the only place provisional pre-market data appears, and it is always fenced and timestamped so it can never be mistaken for a settled fact.
