# Overview Landing Page

| Field        | Value                    |
| ------------ | ------------------------ |
| Epic ID      | E-1104                   |
| Phase        | PH-11                    |
| Owner        | @dinesh-git17            |
| Status       | Complete                 |
| Dependencies | [E-1101, E-1102, E-1103] |
| Created      | 2026-02-10               |

---

## Context

The Overview page is the dashboard's first impression — it answers "is Toronto mobility getting better?" within 3 seconds of page load. Per dashboard-design.md Section 4.2, Page 1 displays 4 hero metrics (Total Delay Hours, Total Bike Trips, Worst Station, Data Freshness), a year-over-year trend sparkline sourced from `fct_daily_mobility`, and a transit mode comparison bar chart sourced from `fct_transit_delays`. This is the only page with content implemented in PH-11; the 4 deep-dive pages (TTC Deep Dive, Bike Share, Weather Impact, Station Explorer) are deferred to PH-12 through PH-14.

This epic integrates the data access layer (E-1102), design system, and component library (E-1103) into a fully functional landing page with live Snowflake data. It validates the entire PH-11 stack end-to-end — Snowflake connection, parameterized queries, tiered caching, CSS styling, Altair theming, metric cards, chart builders — and establishes the page composition pattern that all subsequent deep-dive pages follow.

---

## Scope

### In Scope

- `dashboard/pages/1_Overview.py`: Complete Overview page replacing the routing stub from E-1101
- 4 hero metrics in a horizontal row: Total Delay Hours (`SUM(delay_minutes)/60` from `fct_transit_delays`), Total Bike Trips (`COUNT(*)` from `fct_bike_trips`), Worst Station (highest total delay minutes from `fct_transit_delays` joined to `dim_station`), Data Freshness (`MAX` date from `fct_daily_mobility`)
- Year-over-year trend sparkline or line chart: monthly aggregation from `fct_daily_mobility` with years as color-encoded overlaid lines per dashboard-design.md Section 4.2
- Transit mode comparison horizontal bar chart: delay counts and total delay minutes by `transit_mode` from `fct_transit_delays`
- Date range context footer: "Data coverage: {min_date} to {max_date}" sourced from `dim_date`
- Cache tier alignment: hero metrics at 1-hour TTL, chart aggregations at 30-minute TTL, date range metadata at 24-hour TTL
- Page-level `st.set_page_config` with `page_title="Overview | Toronto Mobility"` and `layout="wide"`
- Custom CSS injection from `styles/custom.css`

### Out of Scope

- "9 years of delays" custom HTML callout banner (stretch goal — deferred if time-constrained)
- Interactive date filters or transit mode filters on the Overview page (this is a summary page per dashboard-design.md: "Interactivity: Minimal")
- PyDeck map visualization of stations
- Cross-page drill-through navigation links to deep-dive pages
- Real-time data refresh, auto-reload, or WebSocket updates
- Server-side rendering or pre-computation of hero metrics
- Loading spinners or skeleton screens during initial data fetch

---

## Technical Approach

### Architecture Decisions

- **Composition over monolith** — The Overview page composes reusable components from E-1103 (`render_metric_row`, `line_chart`, `bar_chart`) and data functions from E-1102 (hero metric queries, aggregation queries, reference queries) rather than implementing inline SQL or custom rendering. This validates the component contracts and ensures later pages can follow the same pattern.
- **Hero metrics sourced from dedicated query functions** — Each of the 4 hero metrics has a dedicated query function in `data/queries.py` (E-1102 S002). The Overview page calls these functions through the 1-hour cache tier (`query_hero_metrics`), ensuring the most expensive computations (full-table `COUNT(*)` on 21.8M bike trips) are cached aggressively.
- **YoY trend from `fct_daily_mobility`** — The pre-aggregated `fct_daily_mobility` table (1,827 rows, one per date) eliminates the need for expensive joins against fact tables. Monthly aggregation (`GROUP BY year, month`) produces ~60 rows per metric — efficient for both Snowflake and Altair rendering.
- **Transit mode comparison from `fct_transit_delays`** — The mode comparison query groups 237,446 delay records by `transit_mode` (3 categories: subway, bus, streetcar), producing exactly 3 rows. This is a lightweight aggregation suitable for the 30-minute cache tier.
- **CSS injection at page level** — Each page loads `custom.css` via `st.markdown` as its first rendering action. This ensures design system consistency regardless of which page the user navigates to first (Streamlit allows direct page URL access, bypassing `app.py`).

### Integration Points

- **E-1101** — Page file `dashboard/pages/1_Overview.py` replaces the stub created in E-1101 S004
- **E-1102** — Consumes `get_connection()`, hero metric query functions, monthly aggregation query, mode comparison query, date range query from `data/queries.py`; uses `query_hero_metrics()` (1h TTL), `query_aggregation()` (30m TTL), `query_reference_data()` (24h TTL) from `data/cache.py`
- **E-1103** — Consumes `render_metric_row()` from `components/metrics.py`, `line_chart()` and `bar_chart()` from `components/charts.py`, `custom.css` from `styles/`
- **MARTS tables consumed**: `fct_transit_delays` (hero metric: delay hours, mode comparison), `fct_bike_trips` (hero metric: total trips), `fct_daily_mobility` (hero metric: data freshness, YoY trend), `dim_station` (hero metric: worst station name), `dim_date` (date range footer)
- **Downstream: PH-12 through PH-14** — Deep-dive pages follow the same composition pattern: load CSS → fetch data via cache tiers → render components

### Repository Areas

- `dashboard/pages/1_Overview.py` (replace stub from E-1101)

### Risks

| Risk                                                                                                                                                                          | Likelihood | Impact | Mitigation                                                                                                                                                                                                                                            |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Cold-start hero metric load exceeds 3-second target when cache is empty, particularly the `COUNT(*)` on `fct_bike_trips` (21.8M rows)                                         | High       | Medium | Use `fct_daily_mobility.total_bike_trips` (pre-aggregated, 1,827 rows) as the primary source for total bike trips instead of raw `COUNT(*)` on `fct_bike_trips`; fall back to `fct_bike_trips` only if `fct_daily_mobility` lacks the required column |
| Worst Station computation requires a full-table `GROUP BY` + `ORDER BY` + `LIMIT 1` on `fct_transit_delays` joined to `dim_station`, which may exceed 3 seconds on first load | Medium     | Medium | Cache the worst station result at 1-hour TTL; the query scans 237,446 rows (far smaller than bike trips) and should complete in <1 second based on E-902 benchmark results (max 0.954s for comparable analytical queries on X-Small)                  |
| Altair chart rendering fails silently when the YoY trend DataFrame contains NULL values in the `y` encoding column for months with no data                                    | Medium     | Low    | Apply `.dropna()` on the aggregation DataFrame before passing to `line_chart()`; verify all months in the `fct_daily_mobility` date range have non-NULL aggregation values                                                                            |

---

## Stories

| ID   | Story                                                            | Points | Dependencies             | Status |
| ---- | ---------------------------------------------------------------- | ------ | ------------------------ | ------ |
| S001 | Implement hero metrics row with 4 KPI cards sourced from MARTS   | 5      | E-1102.S002, E-1103.S003 | Complete |
| S002 | Build year-over-year trend visualization from fct_daily_mobility | 5      | E-1102.S002, E-1103.S004 | Complete |
| S003 | Build transit mode comparison bar chart from fct_transit_delays  | 3      | E-1102.S002, E-1103.S004 | Complete |
| S004 | Compose Overview page layout and validate end-to-end performance | 5      | S001, S002, S003         | Complete |

---

### S001: Implement Hero Metrics Row with 4 KPI Cards Sourced from MARTS

**Description**: Build the hero metrics section of the Overview page displaying 4 KPI cards in a horizontal row — Total Delay Hours, Total Bike Trips, Worst Station, and Data Freshness — sourced from MARTS tables via the data access layer and rendered with the metric card factory component.

**Acceptance Criteria**:

- [ ] Overview page displays 4 hero metrics in a single horizontal row using `render_metric_row()` from `components/metrics.py`
- [ ] Metric 1 — "Total Delay Hours": computed as `SUM(delay_minutes) / 60` from `fct_transit_delays`, formatted as integer with thousands separator (e.g., "77,929"), rendered with `border_variant="ttc"`
- [ ] Metric 2 — "Total Bike Trips": computed from `fct_daily_mobility` SUM of daily bike trips or `COUNT(*)` from `fct_bike_trips`, formatted with "M" suffix for millions (e.g., "21.8M"), rendered with `border_variant="bike"`
- [ ] Metric 3 — "Worst Station": station with highest total delay minutes from `fct_transit_delays` WHERE `transit_mode = 'subway'` joined to `dim_station`, displayed as station name string (e.g., "Bloor-Yonge")
- [ ] Metric 4 — "Data Freshness": maximum date from `fct_daily_mobility`, formatted as "MMM YYYY" (e.g., "Dec 2024")
- [ ] All hero metric queries executed via `query_hero_metrics()` from `data/cache.py` (1-hour TTL)
- [ ] All 4 metrics render within 3 seconds on warm cache per dashboard-design.md Section 5.6

**Technical Notes**: The "Total Bike Trips" metric should prefer `fct_daily_mobility` (pre-aggregated, 1,827 rows) over `fct_bike_trips` (21.8M rows) for cold-start performance. If `fct_daily_mobility` provides a `total_bike_trips` column at the daily grain, summing it produces the lifetime total. The "Worst Station" query filters to `transit_mode = 'subway'` because bus and streetcar delays lack station-level resolution in `dim_station` (bus/streetcar use intersection-level `location` descriptors).

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] 4 hero metrics render with live Snowflake data
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S002: Build Year-over-Year Trend Visualization from fct_daily_mobility

**Description**: Build the year-over-year trend section of the Overview page displaying a line chart with monthly aggregations from `fct_daily_mobility`, color-encoded by year, showing multi-year trends in transit delays and bike ridership.

**Acceptance Criteria**:

- [ ] Overview page displays a year-over-year trend chart below the hero metrics row
- [ ] Data sourced from `fct_daily_mobility` aggregated to monthly granularity: columns `year`, `month`, and at least one metric column (total delay count or total bike trips)
- [ ] Chart rendered via `line_chart()` from `components/charts.py` with `x="month"`, `y=<metric>`, `color="year"`
- [ ] X-axis displays month labels (Jan through Dec), Y-axis displays the aggregated metric value
- [ ] Each year appears as a distinct line, color-encoded for visual differentiation
- [ ] Chart has a descriptive heading (e.g., "Year-over-Year Trend")
- [ ] Chart inherits the registered `toronto_mobility` Altair theme
- [ ] Query executed via `query_aggregation()` from `data/cache.py` (30-minute TTL)
- [ ] NULL values in aggregation columns handled via `.dropna()` or `.fillna(0)` before charting

**Technical Notes**: The `fct_daily_mobility` table contains daily-grain records with both transit and bike metrics. Aggregation to monthly grain (`GROUP BY year, month`) produces approximately 12 rows per year across the data range (2020-2024 for transit, 2019-2024 for bike). The Altair `color` encoding on the `year` field creates separate lines per year. Integer `year` values should be cast to string for proper nominal encoding in Altair.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] YoY trend chart renders with multi-year lines from live Snowflake data
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S003: Build Transit Mode Comparison Bar Chart from fct_transit_delays

**Description**: Build the transit mode comparison section of the Overview page displaying a horizontal bar chart showing total delay counts and delay minutes by transit mode (subway, bus, streetcar) from `fct_transit_delays`.

**Acceptance Criteria**:

- [ ] Overview page displays a transit mode comparison bar chart
- [ ] Data sourced from `fct_transit_delays` grouped by `transit_mode`: `COUNT(*)` as delay count, `SUM(delay_minutes)` as total delay minutes
- [ ] Chart rendered via `bar_chart()` from `components/charts.py` with `horizontal=True`
- [ ] Y-axis displays transit mode labels (subway, bus, streetcar), X-axis displays total delay minutes
- [ ] Bars color-coded by transit mode using the project palette (subway = TTC red `#DA291C`, bus/streetcar differentiated via the registered theme color scale)
- [ ] Chart has a descriptive heading (e.g., "Transit Delays by Mode")
- [ ] Chart inherits the registered `toronto_mobility` Altair theme
- [ ] Query returns exactly 3 rows (one per transit mode)
- [ ] Query executed via `query_aggregation()` from `data/cache.py` (30-minute TTL)

**Technical Notes**: The `fct_transit_delays` table contains 237,446 records across 3 transit modes. The `GROUP BY transit_mode` aggregation produces exactly 3 rows — a lightweight query even without caching. The horizontal bar chart orientation is standard for categorical comparisons with text labels on the Y-axis.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Mode comparison bar chart renders with 3 transit modes from live Snowflake data
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S004: Compose Overview Page Layout and Validate End-to-End Performance

**Description**: Assemble all Overview page components into a cohesive layout — hero metrics row, YoY trend chart, mode comparison bar chart, and date range footer — with CSS injection, design system application, and end-to-end performance validation against the 3-second target.

**Acceptance Criteria**:

- [ ] `dashboard/pages/1_Overview.py` composes all sections in a single-column layout: hero metrics row → YoY trend chart → mode comparison bar chart → date range footer
- [ ] Page loads `custom.css` from `styles/custom.css` via `st.markdown` as its first rendering action after `st.set_page_config`
- [ ] Date range footer displays "Data coverage: {min_date} to {max_date}" sourced from `dim_date` using `query_reference_data()` (24-hour TTL), with dates formatted as `YYYY-MM-DD`
- [ ] `st.set_page_config(page_title="Overview | Toronto Mobility", layout="wide")` called as the first Streamlit command
- [ ] `streamlit run dashboard/app.py` renders the Overview page with live Snowflake data — all 4 hero metrics, both charts, and the footer display correctly
- [ ] Hero metrics load within 3 seconds on warm cache (measured from page navigation to metric render completion) per dashboard-design.md Section 5.6
- [ ] No Python `ImportError`, `ModuleNotFoundError`, or Streamlit rendering warnings in the terminal output
- [ ] Page layout is visually consistent with dashboard-design.md Section 4.2 component hierarchy
- [ ] All Snowflake queries use parameterized execution — zero string interpolation in SQL construction

**Technical Notes**: This story is the integration point for all PH-11 epics. It validates that E-1101 (scaffolding), E-1102 (data access), and E-1103 (design system) produce a working, styled, performant page. Performance measurement should use `time.time()` instrumentation around the data-fetching section, or Streamlit's built-in performance metrics. The 3-second target applies to warm cache (subsequent page loads after initial cold start). Cold start may exceed 3 seconds due to first-time query execution; this is acceptable.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] `streamlit run dashboard/app.py` renders complete Overview page with live data
- [ ] Hero metrics load within 3 seconds on warm cache
- [ ] PR opened with linked issue
- [ ] CI checks green

---

## Exit Criteria

This epic is complete when:

- [ ] `streamlit run dashboard/app.py` renders the Overview page with live Snowflake data
- [ ] 4 hero metrics display: Total Delay Hours, Total Bike Trips, Worst Station, Data Freshness — all sourced from MARTS tables
- [ ] Year-over-year trend chart displays monthly aggregations with per-year color encoding from `fct_daily_mobility`
- [ ] Transit mode comparison bar chart displays delay totals for subway, bus, and streetcar from `fct_transit_delays`
- [ ] Date range footer displays the data coverage period from `dim_date`
- [ ] Hero metrics load within 3 seconds on warm cache per dashboard-design.md Section 5.6
- [ ] Design system (project colors, Inter typography, Altair theme) applied consistently across all rendered components
- [ ] `secrets.toml.example` committed with zero credentials exposed
- [ ] No import errors, rendering warnings, or uncaught exceptions during page navigation
