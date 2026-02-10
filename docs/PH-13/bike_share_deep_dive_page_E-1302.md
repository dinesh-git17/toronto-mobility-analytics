# Bike Share Deep Dive Page

| Field        | Value                            |
| ------------ | -------------------------------- |
| Epic ID      | E-1302                           |
| Phase        | PH-13                            |
| Owner        | @dinesh-git17                    |
| Status       | Complete                         |
| Dependencies | [E-1102, E-1103, E-1104, E-1301] |
| Created      | 2026-02-10                       |

---

## Context

The Bike Share Deep Dive page is PH-13's first major deliverable — it transforms 21.8 million trip records and 1,009 docking stations into an interactive analytical interface answering "where do Torontonians ride, how is ridership growing, and who is riding?" Per dashboard-design.md Section 4.2 Page 3, this page surfaces geographic station activity, multi-year growth, user composition, seasonal patterns, and top station rankings through 6 visualization types: a PyDeck HeatmapLayer map, an area chart, a stacked bar chart, a multi-year seasonality line chart, a sortable data table, and contextual insight annotations. All Bike Share queries MUST use pre-aggregated data from fct_daily_mobility or bounded GROUP BY with date_key partition pruning — no unbounded scans of fct_bike_trips (21.8M rows) per PHASES.md performance mandate.

This is the first dashboard page to visualize Bike Share ridership data and the second deep-dive page built on the PH-11 foundation. It validates the PyDeck HeatmapLayer component (E-1301) with 1,009 stations and extends the composition pattern established in E-1202. The page replaces the stub module created in E-1101 S004.

---

## Scope

### In Scope

- `dashboard/pages/3_Bike_Share.py`: Complete page implementation replacing the E-1101 stub with 6 visualization sections, sidebar filters, and contextual insight annotations
- Bike Share parameterized queries added to `dashboard/data/queries.py`:
  - Station activity aggregation: trip counts per station from `fct_bike_trips` joined to `dim_station` for coordinates and neighborhood, bounded by `date_key` and `user_type`
  - Yearly growth summary: annual totals from `fct_daily_mobility` joined to `dim_date` with member and casual breakdowns plus total duration
  - Monthly seasonality: year x month aggregation from `fct_daily_mobility` joined to `dim_date` with member and casual breakdowns
- Sidebar filters per dashboard-design.md Section 4.2 Page 3:
  - Date range selector via `date_range_filter()` from `components/filters.py` (default: full data range)
  - User type multiselect via `multiselect_filter()` from `components/filters.py` (default: all user types)
- Cross-filtering: selected date range and user types propagate to station heatmap, growth chart, seasonality overlay, top stations table, and insight annotations; member vs casual stacked bar is exempt from user type filter (shows both types by definition)
- 6 visualization types:
  1. Station activity heatmap (PyDeck HeatmapLayer, 1,009 Bike Share stations with trip-count-weighted density in green gradient)
  2. Yearly growth area chart (Altair, total trips by year from `fct_daily_mobility`)
  3. Member vs casual stacked bar chart (Altair, annual `member_trips` vs `casual_trips` from `fct_daily_mobility`)
  4. Multi-year seasonality overlay line chart (Altair, monthly totals by year from `fct_daily_mobility`, color-encoded by year)
  5. Top 20 start stations sortable table (`st.dataframe`, sliced from station activity query)
  6. 4 contextual insight annotations computed from query results
- Cache tier alignment: station activity query at 10-minute TTL via `query_filtered()`; yearly and monthly aggregations at 30-minute TTL via `query_aggregation()`; reference data at 24-hour TTL via `query_reference_data()`
- Custom CSS injection from `styles/custom.css` as first rendering action after `st.set_page_config`

### Out of Scope

- Weather Impact page (E-1303)
- Station Explorer page (PH-14)
- Click-on-heatmap-region to filter charts interaction (standard Streamlit PyDeck does not support bidirectional events)
- Station-level drill-through navigation links to Station Explorer page
- Mobile-specific layout adjustments or responsive breakpoints (PH-14)
- Animated transitions between filter states
- Loading spinners or skeleton screens during query execution
- Individual trip-level data display or trip path visualization
- Real-time GBFS station availability data
- Predictive ridership forecasting

---

## Technical Approach

### Architecture Decisions

- **Station activity query uses `fct_bike_trips` with mandatory `date_key` partition pruning** — The station-level heatmap requires trip counts per station, which is not available in `fct_daily_mobility` (daily-level only, no station dimension). The query groups `fct_bike_trips` by `start_station_key` joined to `dim_station` for coordinates. The WHERE clause enforces `date_key BETWEEN %(start_date)s AND %(end_date)s` for partition pruning on the 21.8M-row table. Expected execution: 1-3 seconds on X-Small for a single-year range; 3-5 seconds for the full 5-year range. This is the only query in E-1302 that touches `fct_bike_trips`.
- **Yearly and monthly aggregations use `fct_daily_mobility` exclusively** — Growth charts, member vs casual breakdowns, and seasonality overlays aggregate from the 1,827-row `fct_daily_mobility` table joined to `dim_date`. These queries return 5 rows (yearly) or ~60 rows (monthly) and execute in under 100ms. User type filtering happens in Python by selecting between `member_trips`, `casual_trips`, or their sum — no SQL modification required for filter changes, maximizing cache hit rate.
- **User type filter validates against closed set** — The `user_types` parameter for the station activity query validates against `{'Annual Member', 'Casual Member'}` and constructs a SQL `IN` clause from validated literals. This follows the same pattern as `_validate_modes()` in E-1202 TTC queries.
- **Member vs casual stacked bar exempt from user type filter** — The stacked bar's purpose is cross-type composition comparison. Filtering to a single user type would produce a single-color non-stacked chart, defeating the visualization's analytical purpose. The stacked bar always shows both user types regardless of the sidebar selection.
- **Station activity DataFrame serves both heatmap and top-20 table** — The station activity query returns all stations with trip counts, sorted by `trip_count DESC`. The heatmap renders the full DataFrame (1,009 points). The top-20 table slices `df.head(20)` from the same result. No duplicate Snowflake queries executed.
- **Insight annotations derived from existing query results** — The 4 contextual insights (casual rider share, summer vs winter ratio, top station, average trip duration) are computed in Python from DataFrames already fetched for chart rendering. No additional Snowflake queries executed. Insights update dynamically when filter values change.
- **Page composition follows E-1202 pattern** — CSS injection first, then sidebar filters, then sequential section rendering (heatmap + growth area in a 2-column row, stacked bar + seasonality in a 2-column row, top stations table full-width, insights in a 4-column row).
- **`dashboard-design` skill enforcement** — All chart colors use project palette tokens. HeatmapLayer uses Bike Share green gradient per Section 6.4. Area chart uses accent blue fill. Stacked bar uses Bike Share green (#43B02A) for Annual Member and neutral slate (#334155) for Casual Member. Altair charts inherit the registered `toronto_mobility` theme. Section headings use `st.subheader()` with descriptive titles per dashboard-design skill chart standards.

### Integration Points

- **E-1101** — Page file `dashboard/pages/3_Bike_Share.py` replaces the stub created in E-1101 S004
- **E-1102** — Consumes `get_connection()` from `data/connection.py`; `query_filtered()` (10-minute TTL), `query_aggregation()` (30-minute TTL), and `query_reference_data()` (24-hour TTL) from `data/cache.py`; `reference_date_bounds()` from `data/queries.py`
- **E-1103** — Consumes `line_chart()` from `components/charts.py`; `date_range_filter()` and `multiselect_filter()` from `components/filters.py`; `render_metric_card()` from `components/metrics.py`; `custom.css` from `styles/`
- **E-1104** — Follows the same page composition pattern: CSS injection → filter widgets → data fetching → component rendering
- **E-1301** — Consumes `heatmap_map()` from `components/maps.py`; `area_chart()` and `bar_chart(stack=True)` from `components/charts.py`
- **MARTS tables consumed**: `fct_bike_trips` (21,795,223 rows — station activity query only), `fct_daily_mobility` (1,827 rows — all aggregation queries), `dim_station` (1,009 BIKE_SHARE rows with coordinates), `dim_date` (2,922 rows)
- **Downstream: PH-14** — Station Explorer reuses query patterns and filter components

### Repository Areas

- `dashboard/pages/3_Bike_Share.py` (replace stub)
- `dashboard/data/queries.py` (modify — add 3 Bike Share query functions)

### Risks

| Risk                                                                                                                                                                                | Likelihood | Impact | Mitigation                                                                                                                                                                                                                                                                                                        |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `fct_bike_trips` station aggregation exceeds 2-second interaction target on X-Small warehouse for the full date range (21.8M rows), degrading user experience during filter changes | High       | Medium | Use 10-minute cache tier to avoid re-execution on repeated interactions; `date_key` partition pruning limits scan to selected year range; cold-start 3-5 seconds is acceptable per dashboard-design.md Section 5.6 (5-second cold start target); display `st.spinner("Loading station data...")` during execution |
| PyDeck HeatmapLayer with 1,009 weighted points renders a uniform green blob due to station density in downtown Toronto overwhelming the color gradient dynamic range                | Medium     | Medium | Set HeatmapLayer `radius=200` meters for fine-grained heat patches that separate downtown clusters; apply `np.log1p(trip_count)` weighting if linear weights produce insufficient visual differentiation; center viewport at zoom 12 for downtown detail                                                          |
| User type multiselect with 0 selections (user deselects all types) produces empty query result or SQL syntax error from empty `IN ()` clause                                        | Medium     | Medium | `multiselect_filter()` defaults to all options when none selected per E-1103; add defensive guard: if `len(selected_types) == 0`, display `st.warning("Select at least one user type.")` and return early before query execution                                                                                  |
| Seasonality overlay chart with 5 years x 12 months = 60 lines produces tangled lines that are difficult to distinguish, especially for middle years (2021-2023)                     | Low        | Medium | Use `year` as nominal color encoding with sequential shade differentiation; most recent year rendered in accent blue, older years in progressively lighter neutral shades for visual hierarchy; set line width to 2px for readability                                                                             |
| Top 20 stations table renders with Snowflake UPPER_CASE column headers and unformatted integer trip counts                                                                          | Medium     | Low    | Normalize column names to lowercase after fetch; rename columns for display (`trip_count` → `Trips`, `station_name` → `Station`); format numeric columns with comma separators via `st.dataframe` style configuration                                                                                             |

---

## Stories

| ID   | Story                                                                        | Points | Dependencies                   | Status   |
| ---- | ---------------------------------------------------------------------------- | ------ | ------------------------------ | -------- |
| S001 | Add Bike Share parameterized queries to the data layer                       | 5      | None                           | Complete |
| S002 | Build station activity heatmap and yearly growth sections                    | 5      | S001, E-1301.S001, E-1301.S003 | Complete |
| S003 | Build member vs casual stacked bar and seasonality overlay sections          | 5      | S001, E-1301.S004              | Complete |
| S004 | Build top 20 stations table and contextual insight annotations               | 5      | S001                           | Complete |
| S005 | Compose Bike Share page layout with sidebar filters and validate performance | 5      | S002, S003, S004               | Complete |

---

### S001: Add Bike Share Parameterized Queries to the Data Layer

**Description**: Add 3 parameterized SQL query functions to `dashboard/data/queries.py` covering station activity aggregation, yearly growth summary, and monthly seasonality — sourced from `fct_bike_trips` (station-level) and `fct_daily_mobility` (temporal aggregations).

**Acceptance Criteria**:

- [ ] Function `bike_station_activity(user_types: list[str]) -> str` in `dashboard/data/queries.py` returns a SQL string that:
  - Selects `station_name`, `latitude`, `longitude`, `neighborhood`, `COUNT(*) as trip_count` from `fct_bike_trips` joined to `dim_station` on `start_station_key = station_key`
  - Filters by `date_key BETWEEN %(start_date)s AND %(end_date)s` using bind variables
  - Filters by `user_type IN (...)` from the validated `user_types` list
  - Uses INNER JOIN to `dim_station` which restricts to stations with matching `station_key` (excludes 91 unmatchable station_ids)
  - Groups by `station_name`, `latitude`, `longitude`, `neighborhood`
  - Orders by `trip_count DESC`
- [ ] Function `bike_yearly_summary() -> str` returns a SQL string that:
  - Selects `year`, `SUM(total_bike_trips) as total_trips`, `SUM(member_trips) as member_trips`, `SUM(casual_trips) as casual_trips`, `SUM(total_bike_duration_seconds) as total_duration_seconds` from `fct_daily_mobility` joined to `dim_date` on `date_key`
  - Filters by `date_key BETWEEN %(start_date)s AND %(end_date)s`
  - Filters to `total_bike_trips IS NOT NULL` (excludes transit-only dates)
  - Groups by `year`
  - Orders by `year`
- [ ] Function `bike_monthly_seasonality() -> str` returns a SQL string that:
  - Selects `year`, `month_num`, `month_name`, `SUM(total_bike_trips) as total_trips`, `SUM(member_trips) as member_trips`, `SUM(casual_trips) as casual_trips` from `fct_daily_mobility` joined to `dim_date` on `date_key`
  - Filters by `date_key BETWEEN %(start_date)s AND %(end_date)s`
  - Filters to `total_bike_trips IS NOT NULL`
  - Groups by `year`, `month_num`, `month_name`
  - Orders by `year`, `month_num`
- [ ] `bike_station_activity()` validates `user_types` against `{'Annual Member', 'Casual Member'}` and raises `ValueError` for unrecognized values
- [ ] `bike_station_activity()` uses `%(start_date)s` and `%(end_date)s` bind-variable placeholders — zero string interpolation for date values
- [ ] `bike_yearly_summary()` and `bike_monthly_seasonality()` use bind-variable placeholders for date range — no `user_types` parameter (filtering handled in Python from returned `member_trips` and `casual_trips` columns)
- [ ] All functions have type hints and docstrings describing query purpose, parameters, and return columns

**Technical Notes**: The `bike_station_activity()` query is the only Bike Share query that touches `fct_bike_trips` (21.8M rows). The INNER JOIN to `dim_station` on `start_station_key` automatically excludes trips with unmatchable stations (91 station_ids not in GBFS snapshot). The `user_types` parameter constructs a SQL `IN` clause from validated literals following the same pattern as `_validate_modes()` in TTC queries. The yearly and monthly queries use `fct_daily_mobility` (1,827 rows) — `member_trips` and `casual_trips` columns enable user-type filtering in Python without re-querying Snowflake.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] All 3 query functions return valid SQL strings
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S002: Build Station Activity Heatmap and Yearly Growth Sections

**Description**: Implement the station activity heatmap (PyDeck HeatmapLayer) and the yearly growth area chart (Altair) as two sections showing geographic distribution and temporal growth trajectory of Bike Share ridership.

**Acceptance Criteria**:

- [ ] Bike Share page renders a PyDeck HeatmapLayer map displaying station activity density from `dim_station` Bike Share entries with trip-count-weighted intensity
- [ ] Map uses `heatmap_map()` from `components/maps.py` with parameters:
  - `lat_col="latitude"`, `lon_col="longitude"` from `dim_station` coordinates
  - `weight_col="trip_count"` for trip-count-weighted density
  - Green color gradient per dashboard-design.md Section 6.4 (default `heatmap_map()` color range)
  - `center_lat=43.6532`, `center_lon=-79.3832` (Toronto center), `zoom=12`
  - `radius=200` meters for fine-grained downtown station separation
- [ ] Map renders up to 1,009 Bike Share stations (all stations with valid coordinates from `dim_station`)
- [ ] Map section includes a descriptive heading: "Station Activity"
- [ ] Page renders a yearly growth area chart using `area_chart()` from `components/charts.py`
- [ ] Area chart `x="year"` (ordinal, cast to string), `y` column reflects user type filter: `total_trips`, `member_trips`, or `casual_trips`
- [ ] Area chart uses accent blue (#2563EB) fill per default `area_chart()` styling
- [ ] Area chart section includes a descriptive heading: "Ridership Growth"
- [ ] Heatmap and area chart display in a 2-column layout using `st.columns([3, 2])` (map wider than chart)
- [ ] Both respond to sidebar date range filter selections (cross-filtering)
- [ ] Heatmap responds to user type multiselect (re-queries `fct_bike_trips` with updated `user_type` filter)
- [ ] Area chart responds to user type multiselect (Python column selection, no re-query)
- [ ] Heatmap renders 1,009 station points within 2 seconds per dashboard-design.md Section 5.6 map render target

**Technical Notes**: The station activity query returns all stations with their aggregated trip counts. The heatmap renders the full DataFrame. Stations with higher trip counts produce brighter heat signatures due to weight-based intensity. Log-scale transformation on `trip_count` via `np.log1p(trip_count)` may improve visual differentiation if the dynamic range between downtown and suburban stations is too large — test visually and adjust. For the area chart, the yearly summary query returns `total_trips`, `member_trips`, and `casual_trips`; the page selects the appropriate column based on user type filter state in Python: both selected → `total_trips`, only Annual → `member_trips`, only Casual → `casual_trips`.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Heatmap renders station density from live MARTS data with green gradient
- [ ] Area chart renders yearly growth from `fct_daily_mobility`
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S003: Build Member vs Casual Stacked Bar and Seasonality Overlay Sections

**Description**: Implement the member vs casual stacked bar chart (Altair) and the multi-year seasonality overlay line chart (Altair) as two sections showing ridership composition and monthly cycling patterns across years.

**Acceptance Criteria**:

- [ ] Bike Share page renders an Altair stacked bar chart showing annual member vs casual trip counts using `bar_chart(stack=True)` from `components/charts.py`
- [ ] Stacked bar data sourced from `bike_yearly_summary()` query, pivoted from wide format (`member_trips`, `casual_trips` columns) to long format (`user_type`, `trip_count` columns) via `pd.melt()`
- [ ] Stacked bar `x="year"` (ordinal, cast to string), `y="trip_count"` (quantitative), `color="user_type"` (nominal)
- [ ] Stacked bar color encoding: `Annual Member` in Bike Share green (#43B02A), `Casual Member` in neutral slate (#334155) via explicit Altair color scale configuration
- [ ] Stacked bar is EXEMPT from user type filter — always displays both user types for composition analysis
- [ ] Stacked bar section includes heading: "Member vs Casual Riders"
- [ ] Page renders an Altair multi-year line chart showing monthly trip totals by year using `line_chart()` from `components/charts.py`
- [ ] Seasonality chart `x="month_name"` (ordinal, sorted Jan-Dec), `y` column reflects user type filter, `color="year"` (nominal, cast to string)
- [ ] X-axis displays month names sorted chronologically via `pd.Categorical(month_name, categories=_MONTH_ORDER, ordered=True)` following E-1202 S004 pattern
- [ ] Each year renders as a distinct line with color differentiation from the project palette
- [ ] Seasonality chart reflects user type filter: displays `total_trips`, `member_trips`, or `casual_trips` based on selected user types
- [ ] Seasonality chart section includes heading: "Seasonal Ridership Patterns"
- [ ] Stacked bar and seasonality chart display in a 2-column layout using `st.columns(2)`
- [ ] Seasonality chart responds to sidebar date range and user type filter selections

**Technical Notes**: The stacked bar uses the same `bike_yearly_summary()` data as the growth area chart (S002). The melting operation transforms `{year, member_trips, casual_trips}` rows into `{year, user_type, trip_count}` rows suitable for Altair color encoding. For the seasonality chart, the `bike_monthly_seasonality()` query returns both member and casual columns; the page applies user type filtering in Python before charting. Month ordering uses `pd.Categorical(month_name, categories=[...], ordered=True)` following the E-1202 S004 pattern. For explicit stacked bar colors, use `alt.Color('user_type:N', scale=alt.Scale(domain=['Annual Member', 'Casual Member'], range=['#43B02A', '#334155']))` at the page level.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Stacked bar renders annual member vs casual composition from live MARTS data
- [ ] Seasonality chart renders multi-year monthly overlay
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S004: Build Top 20 Stations Table and Contextual Insight Annotations

**Description**: Implement the top 20 start stations sortable table (`st.dataframe`) and 4 contextual insight annotations computed from the filtered query results, providing tabular evidence and narrative context alongside the visualizations.

**Acceptance Criteria**:

- [ ] Bike Share page renders a sortable table showing the top 20 start stations by trip count using `st.dataframe()`
- [ ] Table data sliced from station activity DataFrame: `df.head(20)` (already sorted by `trip_count DESC`)
- [ ] Table columns displayed: Station Name, Neighborhood, Trip Count — with human-readable headers via `df.rename(columns={...})`
- [ ] Trip count column formatted with comma separators (e.g., `142,387`)
- [ ] Table is full-width (not inside a column split)
- [ ] Table supports native Streamlit column sorting when user clicks column headers
- [ ] Table section includes heading: "Top 20 Stations"
- [ ] Table responds to sidebar date range and user type filter selections (station activity query re-executes with updated parameters)
- [ ] Insight 1 — Casual share: computes `casual_trips / total_trips * 100` from yearly summary for the most recent year in the filtered range; displays with text: "Casual riders account for {X}% of trips in {year}"
- [ ] Insight 2 — Summer vs winter ratio: computes ratio of peak summer month (Jul+Aug average) trips to winter trough (Jan+Feb average) from monthly seasonality; displays with text: "Summer ridership is {X}x winter"
- [ ] Insight 3 — Top station: extracts `station_name` from first row of station activity DataFrame; displays with text: "{Station Name} leads with {N} trips"
- [ ] Insight 4 — Average trip duration: computes `SUM(total_duration_seconds) / SUM(total_trips) / 60` from yearly summary DataFrame; displays with text: "Average trip: {X} minutes"
- [ ] Insights display in a horizontal row using `st.columns(4)` below the top stations table
- [ ] Insights render as styled metric cards using `render_metric_card()` with `border_variant="bike"`
- [ ] All insights dynamically update when sidebar filters change
- [ ] When filtered date range or user type produces no data, insights display placeholder text instead of NaN or division-by-zero errors

**Technical Notes**: The top 20 table reuses the station activity DataFrame (no additional query). Column renaming for display uses `df.rename(columns={...})`. The average trip duration insight uses `total_duration_seconds` from `bike_yearly_summary()` — this column is included in the S001 query specification. Insights handle edge cases: check `df.empty` before accessing `.iloc[0]`; check divisor > 0 before computing percentages; use `NULLIF` pattern in Python (`total_trips or 1`) to prevent `ZeroDivisionError`.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Top 20 table renders with formatted columns and sorting
- [ ] All 4 insight annotations compute and display correct values
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S005: Compose Bike Share Page Layout with Sidebar Filters and Validate Performance

**Description**: Assemble all Bike Share sections into the final page layout — sidebar filters, station heatmap + growth area chart, stacked bar + seasonality, top stations table, insight annotations — with CSS injection, cross-filtering propagation, empty-state handling, and end-to-end performance validation.

**Acceptance Criteria**:

- [ ] `dashboard/pages/3_Bike_Share.py` composes all sections in a structured layout:
  1. `st.set_page_config(page_title="Bike Share | Toronto Mobility", layout="wide")` as first Streamlit command
  2. CSS injection from `styles/custom.css` via `st.markdown`
  3. `st.title("Bike Share Deep Dive")`
  4. Sidebar: date range filter (default: full data range from `reference_date_bounds()`), user type multiselect (default: `['Annual Member', 'Casual Member']`)
  5. Section 1: Station activity heatmap (3-column) + yearly growth area chart (2-column) in `st.columns([3, 2])`
  6. Section 2: Member vs casual stacked bar (left) + seasonality overlay (right) in `st.columns(2)`
  7. Section 3: Top 20 stations table (full width)
  8. Section 4: 4 insight annotations in `st.columns(4)`
- [ ] Date range filter converts `date` objects to integer `date_key` values (`int(date.strftime('%Y%m%d'))`) and passes as `start_date`/`end_date` parameters to all query functions
- [ ] User type multiselect passes the selected types to `bike_station_activity()` SQL filter and controls Python-level column selection for growth, seasonality, and insight computations
- [ ] Changing any filter value triggers re-execution of all chart sections with updated parameters (standard Streamlit rerun behavior)
- [ ] Empty-state handling: when any query returns 0 rows, the corresponding section displays `st.info("No data available for the selected filters.")` instead of an empty or errored visualization
- [ ] When user type selection is empty, display `st.warning("Select at least one user type.")` and stop rendering via `st.stop()`
- [ ] `streamlit run dashboard/app.py` renders the Bike Share page with all 6 visualization types and 4 insight annotations from live Snowflake data
- [ ] Filter interaction response completes within 2 seconds on warm cache per dashboard-design.md Section 5.6
- [ ] PyDeck HeatmapLayer renders 1,009 station points within 2 seconds per dashboard-design.md Section 5.6
- [ ] No Python `ImportError`, `ModuleNotFoundError`, or Streamlit rendering warnings in the terminal output
- [ ] All Snowflake queries use parameterized execution via `query_filtered()` or `query_aggregation()` — zero string interpolation in SQL date values
- [ ] Page layout is visually consistent with dashboard-design.md Section 4.2 Page 3 component hierarchy
- [ ] All chart sections have descriptive headings per dashboard-design skill chart standards

**Technical Notes**: This story integrates all E-1302 stories and E-1301 components. The station activity query (`fct_bike_trips`) is the performance-critical path — it benefits from `date_key` partition pruning and 10-minute caching. Yearly and monthly aggregation queries (`fct_daily_mobility`) execute in under 100ms. Cold start may exceed 2 seconds due to first-time station activity query execution; this is acceptable per dashboard-design.md Section 5.6 cold start target of 5 seconds. The date range filter pulls min/max dates from `reference_date_bounds()` (24-hour cached) to avoid a Snowflake round-trip on every page load.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] `streamlit run dashboard/app.py` → navigate to Bike Share → all 6 visualization types render with live data
- [ ] Filter interactions respond within 2 seconds on warm cache
- [ ] PR opened with linked issue
- [ ] CI checks green

---

## Exit Criteria

This epic is complete when:

- [ ] `dashboard/pages/3_Bike_Share.py` replaces the E-1101 stub with a complete interactive page
- [ ] `dashboard/data/queries.py` contains 3 Bike Share query functions (`bike_station_activity`, `bike_yearly_summary`, `bike_monthly_seasonality`) with bind-variable date range parameters and validated user type construction
- [ ] Date range and user type sidebar filters propagate to all 6 visualization sections and 4 insight annotations (member vs casual chart exempt from user type filter)
- [ ] Station activity heatmap renders 1,009 Bike Share stations via PyDeck HeatmapLayer with trip-count-weighted green density gradient
- [ ] Yearly growth area chart renders annual ridership trajectory via Altair area chart with accent blue fill
- [ ] Member vs casual stacked bar renders annual composition breakdown via Altair stacked bar with Bike Share green and neutral slate colors
- [ ] Multi-year seasonality overlay renders monthly patterns by year via Altair line chart with per-year color differentiation
- [ ] Top 20 stations sortable table renders station names, neighborhoods, and formatted trip counts via `st.dataframe`
- [ ] 4 contextual insights display and update dynamically: casual share, summer vs winter ratio, top station, average trip duration
- [ ] Filter interaction response completes within 2 seconds on warm cache per dashboard-design.md Section 5.6
- [ ] PyDeck HeatmapLayer renders within 2 seconds for 1,009 points per dashboard-design.md Section 5.6
- [ ] All queries source exclusively from MARTS tables — zero RAW or STAGING schema access
- [ ] No unbounded scans of `fct_bike_trips` — all queries use `date_key BETWEEN` partition pruning
- [ ] Empty-state handling displays informative messages instead of empty or errored visualizations
- [ ] Design system applied consistently: project colors, Inter typography, `toronto_mobility` Altair theme, no default framework styling visible
- [ ] No import errors, rendering warnings, or uncaught exceptions during page navigation or filter interaction
