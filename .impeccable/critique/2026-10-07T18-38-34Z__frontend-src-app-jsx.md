---
target: CloudCrowd dashboard as an operator-facing monitoring UI
total_score: 20
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 3
target_identity: "file:C:\\Users\\sheza\\Desktop\\DENSITY\\CloudCrowdAnalytics\\frontend\\src\\App.jsx"
target_fingerprint: "sha256:9ab51ad5df7da785215ca75479c4dc995c424c4982b26eb93c0443ec2f1f8c42"
target_path: "C:\\Users\\sheza\\Desktop\\DENSITY\\CloudCrowdAnalytics\\frontend\\src\\App.jsx"
timestamp: 2026-10-07T18-38-34Z
slug: frontend-src-app-jsx
---
# CloudCrowd dashboard critique

Method: single-context (direct source + browser review; one dashboard review kept unsplit).

## Design health score

| # | Heuristic | Score | Key issue |
|---|---|---:|---|
| 1 | Visibility of system status | 2 | Stale banner conflicts with “Live estimate” and current-looking KPIs. |
| 2 | Match system / real world | 3 | Occupancy, queue, and in/out are understandable; telemetry and reporting interval need context. |
| 3 | User control and freedom | 2 | No immediate refresh/recovery path for stale telemetry. |
| 4 | Consistency and standards | 3 | Consistent card treatment; status terms/colors vary across views. |
| 5 | Error prevention | 1 | UI hard-codes 3 as capacity and presents it like an approved facility limit. |
| 6 | Recognition rather than recall | 3 | Core metrics are labeled and visible. |
| 7 | Flexibility and efficiency | 1 | No time-range/filter or keyboard efficiency controls. |
| 8 | Aesthetic and minimalist design | 2 | Movement is repeated across cards, diagram, and activity history. |
| 9 | Error recovery | 2 | Stale state has no nearby action; disconnected state has Retry. |
| 10 | Help and documentation | 1 | No in-context explanation for thresholds, freshness, or capacity basis. |
| **Total** | | **20/40** | **Acceptable (lower end)** |

## Design specificity verdict

The dashboard is grounded in crowd telemetry: occupancy, queue estimate, IN/OUT flow, and a movement field are all relevant. Its oversized editorial “Facility 1” heading, warm neutral palette, generic room diagram, and floating nav still read more like a calm report than an operator console. Product character is strongest in privacy/edge language, but that signal is not surfaced on the overview.

The App.jsx CLI detector returned an empty findings array. Browser overlay found 48 DOM anti-pattern instances, primarily low-contrast and undersized text. The beige palette and progress-bar width transition are subjective/intentional flags rather than defects; small labels and metadata are genuine scanability concerns.

## Overall impression

The first screen is easy to scan when data is fresh, but freshness semantics and the displayed capacity basis undermine trust precisely when an operator needs certainty.

## What's working

- The first viewport prioritizes occupancy, queue time, and latest movement in three clearly separated cards.
- IN/OUT counters and the monitored-space visualization make directional flow legible without exposing camera video.
- The stale-state message and API-vs-telemetry distinction are present; the trend’s empty state explains why a chart is not yet available.

## Priority issues

1. **[P1] Stale data looks actionable.** The inspected page showed telemetry about 39 minutes old, but still displayed “0 min,” “Live estimate,” and ordinary occupancy status; time-of-day forces mental subtraction. Show age (“39 min ago”), freeze/visually demote derived readings, and label them last-known until fresh.
2. **[P1] Capacity denominator is ambiguous.** App.jsx uses a frontend calculation limit of 3 and renders “2 / 3” and “67% of available capacity” as facility facts. Distinguish a display/calculation limit from configured safe capacity or show the real approved capacity.
3. **[P1] Stale state has no nearby recovery action.** The warning says to check the connection, but Retry only appears for API errors and Cloud Status is at the page bottom. Put refresh/diagnostics beside the stale banner and identify the last successful ingest.
4. **[P2] Repeated movement detail lengthens the scan.** Inflow/outflow appears in Latest Movement, the large stick-figure diagram, and session activity. Keep a compact live flow summary above the fold and make the diagram/history secondary or collapsible.
5. **[P2] Functional metadata is too small and low contrast.** Labels and timestamps use small, muted type; browser detector flags these repeatedly. Raise contrast and label size, especially for freshness, update time, and state.

## Cognitive load

Moderate. The three-card metric group is well chunked, but users must reconcile stale status with “Live estimate,” calculate data age from clock times, and scroll to diagnostics. Keep currentness and recovery adjacent to the numbers.

## Emotional journey

The calm, tidy opening feels reassuring; stale telemetry then creates doubt because the remaining numbers still look live. The page ends at diagnostics without a clear stale-state action, leaving the operator informed but not empowered.

## Persona red flags

- **Alex (power user):** no fast refresh or selectable time window; has to scroll to Cloud Status and mentally calculate freshness.
- **Sam (accessibility-dependent user):** low-contrast, small labels make timestamps and status details harder to scan; stale/live distinction leans on subtle color and placement.

## Minor observations

“Peek at flow” is vague; “0 net” needs a labeled time interval. A 0-minute queue estimate should be explicitly marked last-known when telemetry is stale. Mobile cards stack correctly in the inspected 390px viewport.

## Questions to consider

- Should “capacity 3” be a true approved facility capacity, or only the UI calculation reference?
- Should stale readings remain visible as last-known values, or be suppressed until fresh data arrives?
