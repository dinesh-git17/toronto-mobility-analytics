# TTC Deep Dive Page

| Field        | Value                            |
| ------------ | -------------------------------- |
| Epic ID      | E-1202                           |
| Phase        | PH-12                            |
| Owner        | @dinesh-git17                    |
| Status       | Complete                         |
| Dependencies | [E-1102, E-1103, E-1104, E-1201] |
| Created      | 2026-02-10                       |

---

## Context

The TTC Deep Dive page is PH-12's primary deliverable — it transforms 237,446 delay incidents across subway, bus, and streetcar modes into an interactive analytical interface answering "where, when, and why do delays happen?" Per dashboard-design.md Section 4.2 Page 2, this page surfaces geographic, temporal, and categorical delay patterns through 5 complementary visualization types: a station delay map, a worst-stations bar chart, a delay cause treemap, an hour-of-day x day-of-week heatmap, and a year-over-year monthly trend line chart. All data is sourced exclusively from MARTS tables (`fct_transit_delays`, `dim_station`, `dim_ttc_delay_codes`, `dim_date`) via the E-1102 data access layer, with user-controlled date range and transit mode filters propagating to every chart.

This is the first deep-dive page built on the PH-11 foundation (E-1101 scaffolding, E-1102 data access, E-1103 components, E-1104 Overview page). It validates the full-stack composition pattern — sidebar filters, parameterized queries, tiered caching, component rendering — that PH-13 and PH-14 deep-dive pages replicate. The page replaces the stub module created in E-1101 S004.

---

## Scope

### In Scope

- `dashboard/pages/2_TTC_Deep_Dive.py`: Complete page implementation replacing the E-1101 stub with 5 visualization sections, sidebar filters, and contextual insight annotations
- TTC-specific parameterized queries added to `dashboard/data/queries.py`:
  - Station delay aggregation: top stations by total delay minutes joined to `dim_station` for coordinates
  - Delay cause hierarchy: category-to-description breakdown from `fct_transit_delays` joined to `dim_ttc_delay_codes`
  - Temporal delay pattern: hour-of-day x day-of-week aggregation from `fct_transit_delays` joined to `dim_date`
  - Monthly trend: year x month aggregation from `fct_transit_delays` joined to `dim_date`
- Sidebar filters per dashboard-design.md Section 4.2 Page 2:
  - Date range selector via `date_range_filter()` from `components/filters.py` (default: full data range)
  - Transit mode multiselect via `multiselect_filter()` from `components/filters.py` (default: all 3 modes)
- Cross-filtering: selected date range and transit modes propagate to all 5 chart components and all 4 insight annotations
- 5 visualization types:
  1. Worst stations horizontal bar chart (Altair, top 10 by delay minutes from `fct_transit_delays` joined to `dim_station`)
  2. Delay causes treemap (Plotly, category-to-description hierarchy from `fct_transit_delays` joined to `dim_ttc_delay_codes`)
  3. Hour-of-day x day-of-week heatmap (Altair, from `fct_transit_delays` with `incident_timestamp` hour extraction joined to `dim_date` for day-of-week)
  4. Year-over-year monthly trend line chart (Altair, monthly aggregates from `fct_transit_delays` joined to `dim_date`, color-encoded by year)
  5. Worst stations map (PyDeck ScatterplotLayer, subway stations from `dim_station` with delay-proportional sizing in red gradient)
- 4 contextual insight annotations computed from query results:
  - Bloor-Yonge delay share percentage of total subway delays
  - Operations category dominance percentage of all delays
  - Peak delay time window (day-of-week and hour range with highest delay concentration)
  - Year-over-year trend direction with percentage change (first year vs. last year in range)
- Cache tier alignment: filtered queries at 10-minute TTL via `query_filtered()`, reference data at 24-hour TTL via `query_reference_data()`
- Custom CSS injection from `styles/custom.css` as first rendering action after `st.set_page_config`

### Out of Scope

- Bike Share Deep Dive page (PH-13)
- Weather Impact page (PH-13)
- Station Explorer page (PH-14)
- Mobile-specific layout adjustments or responsive breakpoints (PH-14)
- Click-on-map-point to filter charts interaction (stretch goal — standard Streamlit PyDeck does not support bidirectional click events without custom JavaScript)
- Station-level drill-through navigation links to Station Explorer page
- Animated transitions between filter states
- Loading spinners or skeleton screens during query execution
- PyDeck HeatmapLayer (distinct from Altair heatmap — HeatmapLayer is PH-13 scope)
- Bus and streetcar station-level geographic mapping (surface modes lack station coordinates in `dim_station`)

---

## Technical Approach

### Architecture Decisions

- **All queries filter via `date_key` integer range for partition pruning** — Per DESIGN-DOC.md, `date_key` is an integer FK in YYYYMMDD format optimized for Snowflake micro-partition pruning. The date range filter converts Python `date` objects to integer keys (`int(date.strftime('%Y%m%d'))`) before passing to parameterized queries via `query_filtered()`. This ensures every filtered query benefits from partition elimination on the 237,446-row `fct_transit_delays` table.
- **Transit mode filter uses validated whitelist construction** — Snowflake's Python connector bind variables (`%(param)s`) do not natively support list parameters in `IN` clauses. The query function accepts a `list[str]` of modes, validates each element against the closed set `{'subway', 'bus', 'streetcar'}`, and constructs the SQL `IN` clause from validated literals. This is safe because the input domain is finite, controlled by the `multiselect_filter()` widget, and never accepts user-typed text.
- **Station map scoped to subway records only** — Per PHASES.md, the map renders "75 subway stations with delay-proportional sizing." Bus and streetcar delays lack station-level geographic coordinates in `dim_station` — surface modes use free-text `location` descriptors (intersections) without latitude/longitude. The station map query filters to `transit_mode = 'subway'` and joins `dim_station WHERE station_type = 'TTC_SUBWAY'`. Bar chart, treemap, heatmap, and trend chart include all selected transit modes.
- **Insight annotations derived from existing query results** — The 4 contextual insights (Bloor-Yonge share, Operations dominance, peak window, YoY direction) are computed in Python from DataFrames already fetched for chart rendering. No additional Snowflake queries are executed. Insights update dynamically when filter values change because they derive from the same filtered result sets.
- **Page composition follows E-1104 pattern** — CSS injection first, then sidebar filters, then sequential section rendering (map + bar chart in a 2-column row, treemap + heatmap in a 2-column row, trend chart full-width, insights in a 4-column row). This layout matches the composition pattern validated in the Overview page and ensures visual consistency across dashboard pages.
- **`dashboard-design` skill enforcement** — All chart colors use project palette tokens (TTC red `#DA291C`, accent blue `#2563EB`, neutral slate `#334155`). Altair charts inherit the registered `toronto_mobility` theme. Plotly treemap uses explicit Inter font and project red sequential scale. PyDeck map uses TTC red RGBA. No default Streamlit or library colors appear in any visualization. Section headings use `st.subheader()` with descriptive titles per dashboard-design skill chart standards.

### Integration Points

- **E-1101** — Page file `dashboard/pages/2_TTC_Deep_Dive.py` replaces the stub created in E-1101 S004
- **E-1102** — Consumes `get_connection()` from `data/connection.py`; `query_filtered()` (10-minute TTL) and `query_reference_data()` (24-hour TTL) from `data/cache.py`; `reference_stations()` and `reference_date_bounds()` from `data/queries.py`
- **E-1103** — Consumes `bar_chart()` and `line_chart()` from `components/charts.py`; `date_range_filter()` and `multiselect_filter()` from `components/filters.py`; `render_metric_row()` from `components/metrics.py` for optional KPI summary row; `custom.css` from `styles/`
- **E-1104** — Follows the same page composition pattern: CSS injection → filter widgets → data fetching → component rendering
- **E-1201** — Consumes `scatterplot_map()` from `components/maps.py`; `treemap()` and `heatmap()` from `components/charts.py`
- **MARTS tables consumed**: `fct_transit_delays` (237,446 rows, 10 columns), `dim_station` (76 TTC subway rows with coordinates), `dim_ttc_delay_codes` (334 rows, 4 columns), `dim_date` (2,922 rows, 10 columns)
- **Downstream: PH-13 / PH-14** — Deep-dive pages follow the same composition pattern: CSS injection → sidebar filters → parameterized queries → component rendering → insight annotations

### Repository Areas

- `dashboard/pages/2_TTC_Deep_Dive.py` (replace stub)
- `dashboard/data/queries.py` (modify — add 4 TTC-specific query functions)

### Risks

| Risk                                                                                                                                                                             | Likelihood | Impact | Mitigation                                                                                                                                                                                                                                                                                   |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Transit mode multiselect with 0 selections (user deselects all modes) produces empty query result or SQL syntax error from empty `IN ()` clause                                  | Medium     | Medium | `multiselect_filter()` defaults to all options when none selected per E-1103 S005; add defensive guard: if `len(selected_modes) == 0`, display `st.warning("Select at least one transit mode.")` and return early before query execution                                                     |
| Station delay aggregation returns 0 rows when date range excludes all subway delay data (e.g., range before November 2020), causing empty map and bar chart                      | Medium     | Medium | Check DataFrame length after query execution; display `st.info("No delay data available for the selected date range and transit modes.")` instead of rendering empty visualizations; date range filter defaults to full data range (Nov 2020 – Dec 2024) via `reference_date_bounds()` query |
| Plotly treemap with all 334 delay codes produces unreadable visualization where leaf tiles are too small for labels                                                              | High       | Medium | Aggregate treemap at category-to-description level (8 categories containing ~40-60 descriptions), not individual delay codes; set `textinfo="label+percent parent"` and `maxdepth=2` for readable proportional labeling; individual codes visible on hover via tooltip                       |
| PyDeck map viewport auto-zoom miscalculates when outlier stations (SRT line in Scarborough, northern terminals) stretch the bounding box, making downtown stations too clustered | Medium     | Low    | Set initial viewport to fixed Toronto center coordinates (43.6532, -79.3832) with zoom level 11 per dashboard-design.md map styling; users adjust via PyDeck's built-in scroll-to-zoom and drag-to-pan controls                                                                              |
| Insight annotation for "peak delay window" produces misleading results when filtered to a single transit mode or narrow date range with sparse data                              | Low        | Low    | Display peak window only when the filtered result set contains >= 100 delay records; below that threshold, omit the peak window insight and display the remaining 3 insights                                                                                                                 |

---

## Stories

| ID   | Story                                                                           | Points | Dependencies                   | Status |
| ---- | ------------------------------------------------------------------------------- | ------ | ------------------------------ | ------ |
| S001 | Add TTC-specific parameterized queries to the data layer                        | 5      | None                           | Draft  |
| S002 | Build worst stations map and horizontal bar chart sections                      | 5      | S001, E-1201.S002              | Draft  |
| S003 | Build delay causes treemap and temporal heatmap sections                        | 5      | S001, E-1201.S003, E-1201.S004 | Draft  |
| S004 | Build year-over-year monthly trend and contextual insight annotations           | 5      | S001                           | Draft  |
| S005 | Compose TTC Deep Dive page layout with sidebar filters and validate performance | 5      | S002, S003, S004               | Draft  |

---

### S001: Add TTC-Specific Parameterized Queries to the Data Layer

**Description**: Add 4 parameterized SQL query functions to `dashboard/data/queries.py` covering station delay aggregation, delay cause hierarchy, temporal delay patterns, and monthly trend analysis — all accepting date range and transit mode filter parameters.

**Acceptance Criteria**:

- [ ] Function `ttc_station_delays(modes: list[str]) -> str` in `dashboard/data/queries.py` returns a SQL string that:
  - Selects `station_name`, `latitude`, `longitude`, `COUNT(*) as delay_count`, `SUM(delay_minutes) as total_delay_minutes` from `fct_transit_delays` joined to `dim_station` on `station_key`
  - Filters by `date_key BETWEEN %(start_date)s AND %(end_date)s` using bind variables
  - Filters by `transit_mode IN (...)` from the validated `modes` list
  - Filters to `station_key IS NOT NULL` (excludes bus/streetcar records without station mapping)
  - Groups by `station_name`, `latitude`, `longitude`
  - Orders by `total_delay_minutes DESC`
- [ ] Function `ttc_delay_causes(modes: list[str]) -> str` returns a SQL string that:
  - Selects `delay_category`, `delay_description`, `COUNT(*) as incident_count`, `SUM(delay_minutes) as total_delay_minutes` from `fct_transit_delays` joined to `dim_ttc_delay_codes` on `delay_code_key`
  - Filters by `date_key` range and `transit_mode` using the same pattern
  - Filters to `delay_code_key IS NOT NULL` (excludes records with unknown delay codes)
  - Groups by `delay_category`, `delay_description`
- [ ] Function `ttc_hourly_pattern(modes: list[str]) -> str` returns a SQL string that:
  - Selects `EXTRACT(HOUR FROM incident_timestamp) as hour_of_day`, `day_of_week`, `day_of_week_num`, `COUNT(*) as delay_count` from `fct_transit_delays` joined to `dim_date` on `date_key`
  - Filters by `date_key` range and `transit_mode`
  - Groups by `hour_of_day`, `day_of_week`, `day_of_week_num`
  - Orders by `day_of_week_num`, `hour_of_day`
- [ ] Function `ttc_monthly_trend(modes: list[str]) -> str` returns a SQL string that:
  - Selects `year`, `month_num`, `month_name`, `COUNT(*) as delay_count`, `SUM(delay_minutes) as total_delay_minutes` from `fct_transit_delays` joined to `dim_date` on `date_key`
  - Filters by `date_key` range and `transit_mode`
  - Groups by `year`, `month_num`, `month_name`
  - Orders by `year`, `month_num`
- [ ] All 4 functions validate `modes` against `{'subway', 'bus', 'streetcar'}` and raise `ValueError` for unrecognized values
- [ ] All 4 functions use `%(start_date)s` and `%(end_date)s` bind-variable placeholders for date range parameters — zero string interpolation for date values
- [ ] All functions have type hints and docstrings describing the query purpose, parameters, and return columns

**Technical Notes**: The `modes` parameter constructs a SQL `IN` clause from validated literals (e.g., `IN ('subway', 'bus')`) rather than bind variables because Snowflake's Python connector does not support list-type bind parameters. This is safe because the input set is closed — the `multiselect_filter()` widget constrains selection to 3 fixed options. The date range bind variables (`start_date`, `end_date`) are integers in YYYYMMDD format, converted from Python `date` objects at the page level via `int(date.strftime('%Y%m%d'))`.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] All 4 query functions return valid SQL strings
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S002: Build Worst Stations Map and Horizontal Bar Chart Sections

**Description**: Implement the worst stations geographic map (PyDeck ScatterplotLayer) and the top 10 worst stations horizontal bar chart (Altair) as two linked sections sharing the same station delay aggregation query result.

**Acceptance Criteria**:

- [ ] TTC Deep Dive page renders a PyDeck ScatterplotLayer map displaying subway stations from `dim_station` with delay-proportional point sizing
- [ ] Map uses `scatterplot_map()` from `components/maps.py` with parameters:
  - `lat_col="latitude"`, `lon_col="longitude"` from `dim_station` coordinates
  - `size_col="total_delay_minutes"` for delay-proportional point radius
  - `color=[218, 41, 28, 180]` (TTC red with 70% opacity) per dashboard-design.md Section 6.4
  - `tooltip_cols=["station_name", "delay_count", "total_delay_minutes"]`
  - `center_lat=43.6532`, `center_lon=-79.3832` (Toronto center), `zoom=11`
- [ ] Map renders up to 75 subway stations (excluding ST_000 Unknown which has NULL coordinates)
- [ ] Page renders a horizontal bar chart showing top 10 stations by total delay minutes using `bar_chart()` from `components/charts.py` with `horizontal=True`
- [ ] Bar chart x-axis displays `total_delay_minutes`, y-axis displays `station_name` sorted by descending delay
- [ ] Map and bar chart display in a 2-column layout using `st.columns([3, 2])` (map wider than chart)
- [ ] Both visualizations share the same `ttc_station_delays()` query result — no duplicate Snowflake queries
- [ ] Map section includes a descriptive heading: "Delay Distribution by Station"
- [ ] Bar chart section includes a descriptive heading: "Top 10 Delay Stations"
- [ ] Both respond to sidebar date range and transit mode filter selections (cross-filtering)
- [ ] Station map renders within 2 seconds per dashboard-design.md Section 5.6 map render target

**Technical Notes**: The station delay query returns all stations with their aggregated delay metrics. The bar chart slices the top 10 rows from the same DataFrame (`df.head(10)`). The map uses the full DataFrame for geographic coverage. Filter the query result to rows where `latitude IS NOT NULL` and `longitude IS NOT NULL` before passing to `scatterplot_map()` to exclude the ST_000 Unknown placeholder. When `transit_mode` filter includes only bus or streetcar (no subway), the station map section should display `st.info("Station map available for subway mode only.")` since surface modes lack station coordinates.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Map renders subway stations with delay-proportional sizing from live MARTS data
- [ ] Bar chart renders top 10 stations from the same query result
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S003: Build Delay Causes Treemap and Temporal Heatmap Sections

**Description**: Implement the delay cause hierarchical treemap (Plotly) and the hour-of-day x day-of-week temporal heatmap (Altair) as two linked sections showing categorical and temporal delay patterns.

**Acceptance Criteria**:

- [ ] TTC Deep Dive page renders a Plotly treemap showing delay causes in a category-to-description hierarchy using `treemap()` from `components/charts.py`
- [ ] Treemap `path_cols=["delay_category", "delay_description"]`, `value_col="incident_count"`, `color_col="total_delay_minutes"`
- [ ] Treemap displays 8 top-level category tiles (Mechanical, Signal, Passenger, Infrastructure, Operations, Weather, Security, General) with description-level subtiles
- [ ] Treemap rendered via `st.plotly_chart(fig, use_container_width=True)`
- [ ] TTC Deep Dive page renders an Altair heatmap showing delay count by hour-of-day (x-axis, 0-23) and day-of-week (y-axis, Monday-Sunday) using `heatmap()` from `components/charts.py`
- [ ] Heatmap `x="hour_of_day"`, `y="day_of_week"`, `color="delay_count"` with `y_sort=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]`
- [ ] Heatmap x-axis sorts numerically from 0 to 23; y-axis sorts from Monday to Sunday per ISO 8601
- [ ] Heatmap rendered via `st.altair_chart(chart, use_container_width=True)`
- [ ] Treemap and heatmap display in a 2-column layout using `st.columns(2)`
- [ ] Treemap section includes heading: "Delay Causes"
- [ ] Heatmap section includes heading: "Delay Patterns by Hour and Day"
- [ ] Both respond to sidebar date range and transit mode filter selections (cross-filtering)
- [ ] Both query results sourced from `ttc_delay_causes()` and `ttc_hourly_pattern()` respectively via `query_filtered()` (10-minute TTL)

**Technical Notes**: The delay cause query joins `fct_transit_delays` to `dim_ttc_delay_codes` on `delay_code_key`. Records with NULL `delay_code_key` are excluded (no code to resolve). The treemap hierarchy has 2 levels: category (8 values) and description (~40-60 distinct values). Individual delay codes are omitted from the treemap to prevent unreadable tiny tiles — they appear in the tooltip on hover. The hourly pattern query extracts `HOUR FROM incident_timestamp` and joins `dim_date` for `day_of_week` and `day_of_week_num`. The `day_of_week_num` column enables numeric sorting while `day_of_week` provides display labels.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Treemap renders category/description hierarchy from live MARTS data
- [ ] Heatmap renders 24x7 grid from live MARTS data
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S004: Build Year-over-Year Monthly Trend and Contextual Insight Annotations

**Description**: Implement the year-over-year monthly trend line chart (Altair) and 4 contextual insight annotations computed from the filtered query results, providing narrative context alongside the visualizations.

**Acceptance Criteria**:

- [ ] TTC Deep Dive page renders an Altair line chart showing monthly delay counts by year using `line_chart()` from `components/charts.py`
- [ ] Chart sourced from `ttc_monthly_trend()` query via `query_filtered()` (10-minute TTL)
- [ ] Chart `x="month_name"` (ordinal, sorted Jan-Dec), `y="delay_count"` (quantitative), `color="year"` (nominal, cast to string for proper Altair encoding)
- [ ] X-axis displays month abbreviations (Jan through Dec), y-axis displays delay count
- [ ] Each year appears as a distinct line with color differentiation from the project palette
- [ ] Chart section includes heading: "Year-over-Year Trend"
- [ ] Chart rendered via `st.altair_chart(chart, use_container_width=True)`
- [ ] Chart responds to sidebar date range and transit mode filter selections
- [ ] Insight 1 — Bloor-Yonge share: computes `Bloor-Yonge total delay minutes / all subway delay minutes * 100` from station delays DataFrame; displays as `st.metric` or `st.markdown` with text: "Bloor-Yonge accounts for {X}% of subway delays"
- [ ] Insight 2 — Operations dominance: computes `Operations category incident count / total incident count * 100` from delay causes DataFrame; displays with text: "Operations issues cause {X}% of delays"
- [ ] Insight 3 — Peak delay window: identifies the day-of-week + hour range with highest delay concentration from hourly pattern DataFrame; displays with text: "{Day} {H1}-{H2} is peak delay time"
- [ ] Insight 4 — YoY direction: computes percentage change between the earliest and latest full year in the monthly trend DataFrame; displays with text: "Delays {↑/↓} {X}% since {first_year}"
- [ ] Insights display in a horizontal row using `st.columns(4)` below the trend chart
- [ ] Insights render as styled metric cards using `render_metric_card()` with `border_variant="ttc"`
- [ ] All insights dynamically update when sidebar filters change
- [ ] Peak delay window insight omitted (replaced with `st.empty()`) when filtered result set contains fewer than 100 delay records

**Technical Notes**: The year column from `dim_date` is an integer. Cast to string before passing to `line_chart()` to ensure Altair treats it as nominal (discrete color encoding) rather than quantitative (continuous gradient). Month sorting uses `alt.X('month_name:O', sort=['Jan', 'Feb', ..., 'Dec'])` — pass the sort list from the charts.py `line_chart` call or apply sorting in the DataFrame before charting. The YoY percentage change computes `(last_year_total - first_year_total) / first_year_total * 100`. If only one year exists in the filtered range, display the absolute count instead of a percentage change.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Trend chart renders multi-year lines from live MARTS data
- [ ] All 4 insight annotations compute and display correct values
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S005: Compose TTC Deep Dive Page Layout with Sidebar Filters and Validate Performance

**Description**: Assemble all TTC Deep Dive sections into the final page layout — sidebar filters, station map + bar chart, treemap + heatmap, monthly trend, insight annotations — with CSS injection, cross-filtering propagation, empty-state handling, and end-to-end performance validation.

**Acceptance Criteria**:

- [ ] `dashboard/pages/2_TTC_Deep_Dive.py` composes all sections in a structured layout:
  1. `st.set_page_config(page_title="TTC Deep Dive | Toronto Mobility", layout="wide")` as first Streamlit command
  2. CSS injection from `styles/custom.css` via `st.markdown`
  3. `st.title("TTC Deep Dive")`
  4. Sidebar: date range filter (default: full data range from `reference_date_bounds()`), transit mode multiselect (default: `['subway', 'bus', 'streetcar']`)
  5. Section 1: Station map (3-column) + worst stations bar chart (2-column) in `st.columns([3, 2])`
  6. Section 2: Delay causes treemap (left) + temporal heatmap (right) in `st.columns(2)`
  7. Section 3: Year-over-year trend chart (full width)
  8. Section 4: 4 insight annotations in `st.columns(4)`
- [ ] Date range filter converts `date` objects to integer `date_key` values (`int(date.strftime('%Y%m%d'))`) and passes as `start_date`/`end_date` parameters to all query functions
- [ ] Transit mode multiselect passes the selected modes list to all query functions
- [ ] Changing any filter value triggers re-execution of all chart sections with updated parameters (standard Streamlit rerun behavior)
- [ ] Empty-state handling: when any query returns 0 rows, the corresponding section displays `st.info("No data available for the selected filters.")` instead of an empty or errored visualization
- [ ] When transit mode selection excludes subway, the station map section displays `st.info("Station map available for subway mode only.")` and the bar chart renders with available modes
- [ ] `streamlit run dashboard/app.py` renders the TTC Deep Dive page with all 5 visualization types and 4 insight annotations from live Snowflake data
- [ ] Filter interaction response completes within 2 seconds on warm cache per dashboard-design.md Section 5.6
- [ ] PyDeck map renders 75 subway stations within 2 seconds per dashboard-design.md Section 5.6
- [ ] No Python `ImportError`, `ModuleNotFoundError`, or Streamlit rendering warnings in the terminal output
- [ ] All Snowflake queries use parameterized execution via `query_filtered()` — zero string interpolation in SQL date values
- [ ] Page layout is visually consistent with dashboard-design.md Section 4.2 Page 2 component hierarchy
- [ ] All chart sections have descriptive headings per dashboard-design skill chart standards

**Technical Notes**: This story is the integration point for all E-1202 stories and E-1201 components. Performance measurement should target warm-cache scenarios (subsequent filter interactions after initial page load). The 2-second filter response target applies to cached query re-execution + chart re-rendering. Cold start may exceed 2 seconds due to first-time query execution; this is acceptable per dashboard-design.md Section 5.6 which sets cold start target at 5 seconds. The date range filter should pull min/max dates from `reference_date_bounds()` (24-hour cached) to avoid a Snowflake round-trip on every page load.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] `streamlit run dashboard/app.py` → navigate to TTC Deep Dive → all 5 chart types render with live data
- [ ] Filter interactions respond within 2 seconds on warm cache
- [ ] PR opened with linked issue
- [ ] CI checks green

---

## Exit Criteria

This epic is complete when:

- [ ] `dashboard/pages/2_TTC_Deep_Dive.py` replaces the E-1101 stub with a complete interactive page
- [ ] `dashboard/data/queries.py` contains 4 TTC-specific parameterized query functions (`ttc_station_delays`, `ttc_delay_causes`, `ttc_hourly_pattern`, `ttc_monthly_trend`) with bind-variable date range parameters and validated transit mode construction
- [ ] Date range and transit mode sidebar filters propagate to all 5 chart components and all 4 insight annotations (cross-filtering operational)
- [ ] Worst stations map renders up to 75 subway stations via PyDeck ScatterplotLayer with delay-proportional sizing and TTC red coloring
- [ ] Worst stations bar chart renders top 10 stations by delay minutes via Altair horizontal bar
- [ ] Delay causes treemap renders category-to-description hierarchy via Plotly with project red sequential color scale
- [ ] Hour-of-day x day-of-week heatmap renders 24x7 grid via Altair with sequential red color encoding
- [ ] Year-over-year monthly trend renders multi-year lines via Altair with per-year color differentiation
- [ ] 4 contextual insights display and update dynamically: Bloor-Yonge share, Operations dominance, peak delay window, YoY trend direction
- [ ] Filter interaction response completes within 2 seconds on warm cache per dashboard-design.md Section 5.6
- [ ] PyDeck station map renders within 2 seconds for 75 points per dashboard-design.md Section 5.6
- [ ] All queries source exclusively from MARTS tables — zero RAW or STAGING schema access
- [ ] Empty-state handling displays informative messages instead of empty or errored visualizations
- [ ] Design system applied consistently: project colors, Inter typography, `toronto_mobility` Altair theme, no default framework styling visible
- [ ] No import errors, rendering warnings, or uncaught exceptions during page navigation or filter interaction
