---
target: current crowd-monitoring dashboard
total_score: 23
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 1
target_identity: "file:C:\\Users\\sheza\\Desktop\\DENSITY\\CloudCrowdAnalytics\\frontend\\src\\App.jsx"
target_fingerprint: "sha256:9ab51ad5df7da785215ca75479c4dc995c424c4982b26eb93c0443ec2f1f8c42"
target_path: "C:\\Users\\sheza\\Desktop\\DENSITY\\CloudCrowdAnalytics\\frontend\\src\\App.jsx"
timestamp: 2026-10-07T18-36-37Z
slug: frontend-src-app-jsx
---
# Dashboard UX Critique — desktop overview

> ⚠️ DEGRADED: single-context (separate assessment agents were not used under the review-scope constraints)

Target: `frontend/src/App.jsx`; live desktop view at `http://localhost:5173/#overview`; product context: facility operators need fast, trustworthy occupancy, flow, and queue signals.

## Design health — 23/40 (Acceptable)

| # | Heuristic | Score | Evidence |
|---|---|---:|---|
| 1 | Visibility of system status | 2 | Stale state is shown, but “Live estimate” remains on the queue card and status detail says API Healthy. |
| 2 | Match to real world | 3 | Occupancy, queue, inflow and outflow are familiar; “latest interval” has no duration. |
| 3 | User control and freedom | 3 | Two clear navigation choices; no trapped workflow in the overview. |
| 4 | Consistency and standards | 2 | Same yellow status is “Moderate” on metric cards and “yellow” in the activity row. |
| 5 | Error prevention | 2 | Stale warning exists, but stale metric values still look current and actionable. |
| 6 | Recognition rather than recall | 3 | Occupancy has a denominator and progress bar; flow and freshness context repeat unevenly. |
| 7 | Flexibility and efficiency | 2 | Key cards scan quickly, but the repeated movement visualization pushes status/history lower. |
| 8 | Aesthetic and minimalist design | 3 | Calm, coherent palette and strong occupancy figure; multiple sections restate the same facts. |
| 9 | Error recovery | 2 | Stale message says to check the connection, but gives no immediate remedy when the API is healthy. |
| 10 | Help and documentation | 1 | No in-context explanation for thresholds, stale-vs-healthy states, or interval length. |
| **Total** | | **23/40** | **Acceptable (57.5%)** |

## Design specificity verdict

The content is unmistakably crowd-monitoring data, and the monitored-space illustration gives it some product character. The visual language itself—warm neutral surfaces, lavender accents, editorial headings, floating navigation—could be reused for many analytics products; the overview does not strongly express this product’s edge-first/privacy-aware distinction. The information design is stronger than the product-specific visual identity.

## Live page and detector evidence

On the actual desktop view (about 1240 px wide), the first scan is clear: the largest card is occupancy (2/3, 67%), followed by queue time (0 min) and latest movement (0 in / 0 out). This is an effective ordering for quick awareness. The header and intro both say telemetry is stale, but the queue card still says “Minimal delay expected” and “Live estimate”; system status later says API “Healthy” while cloud telemetry is “Stale.” The visible timestamp was 11:28 PM while current time was about 12:04 AM, so these were old readings, not merely a momentary delay.

The static `impeccable detect --json frontend/src/App.jsx` scan returned an empty findings array. The injected browser detector did run and reported 55 anti-pattern hits, prominently repeated “low contrast text” and “undersized functional text” labels; its overlay also flagged the beige palette, a width transition, a glow/shadow accent, and kicker/eyebrow labels. The text-size/contrast flags align with the small, muted captions and metadata visible in the page and are worth checking. The palette, eyebrow, transition, and shadow rules are not by themselves evidence of poor hierarchy; the 55 count includes repeated per-element labels, not 55 distinct UX defects. The detector overlay itself is intentionally noisy and should not be mistaken for app clutter.

## Overall impression

The main operational numbers are easy to find and occupancy is sufficiently emphasized. The view is visually calm rather than cluttered, but trust in those numbers is weakened by stale-state language, and a tall secondary visualization repeats information already in the metric cards. The biggest opportunity is to make freshness inseparable from the readings and then reclaim space from repeated flow data.

## What's working

- Occupancy is the strongest visual element, with “2 / 3,” a percentage, progress bar, and status in one card.
- Queue time receives its own prominent card rather than being buried in history.
- The first viewport limits navigation to Overview and Input Sources and keeps the three main metric groups distinct.

## Priority issues

1. **[P1] Stale readings still read as live.** The intro warns not to act on old readings, while the queue card calls 0 minutes a “Live estimate” and “Minimal delay expected”; the lower status panel distinguishes API health from telemetry freshness only after scrolling. **Fix:** show a consistent stale badge/age on the metric group or each card, replace “Live estimate” when stale, and make “API reachable; telemetry stale” explicit near the readings. **Suggested command:** `$impeccable clarify`.
2. **[P2] Flow data is repeated and vertically expensive.** Latest Movement shows in/out values and net; Live Movement repeats in/out and occupancy in a 330px diagram; the session activity row repeats the same interval again. The screenshot’s first viewport reaches only the beginning of that diagram. **Fix:** keep one compact flow summary; reserve the larger illustration for new movement or collapse it when there is no activity. **Suggested command:** `$impeccable distill`.
3. **[P2] Small, muted supporting labels are hard to scan.** The live detector repeatedly flags low-contrast and undersized text; the header timestamps, card captions, status labels, and metadata are visibly much quieter than the numbers. In a monitoring view, stale time and status are operational data, not decoration. **Fix:** raise contrast and size for freshness/status labels while retaining hierarchy for nonessential metadata. **Suggested command:** `$impeccable audit`.
4. **[P2] One status has two vocabularies.** Cards translate `yellow` to “Moderate,” but the activity row displays the raw “yellow”; the same sample therefore appears to have different labels. **Fix:** use one shared user-facing status label and keep raw status codes out of the interface. **Suggested command:** `$impeccable clarify`.

## Cognitive load and emotional journey

No wall of controls or choices: navigation has two options and the first row has three cards. But the same interval is represented across cards, a large diagram, and activity history, so a quick scan sees several versions of the same counts instead of a single authoritative reading. The experience opens with a confident, large occupancy number, then undercuts confidence with a stale warning and freshness-neutral card copy. The later “not enough data for a trend” state is accurate but does little to restore confidence; the stale explanation and timestamp should travel with the key numbers.

## Persona red flags

- **Operator checking conditions between tasks:** can find occupancy and queue immediately, but may mistake stale 0-minute wait for current because its own card says “Live estimate.”
- **Manager scanning for a staffing response:** must reconcile “Moderate” with “yellow” and scroll past repeated flow displays to reach session history and cloud freshness.
- **First-time facility user:** sees 2/3 and 67%, but cannot tell from the view whether 3 is the site’s real capacity or a display calculation limit, or how long “latest interval” covers.

## Minor observations

- “Latest interval” lacks its time span, making 0/0 movement hard to interpret.
- The trend empty state is honest about needing two readings, but older/stale data is still presented as the current session’s top-line value.
- Frontend implementation sets `CALCULATION_OCCUPANCY_LIMIT = 3` and derives displayed capacity, utilization, and status from that value. The screenshot’s 2/3 is prominent; ensure operators understand that denominator’s meaning if 3 is a calculation/display limit rather than site capacity.

## Questions to consider

- Should stale telemetry demote or visually freeze the queue and occupancy cards until readings resume?
- Can the large movement diagram be conditional on actual movement, leaving the first scan focused on occupancy, queue, and freshness?
