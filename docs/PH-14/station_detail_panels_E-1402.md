# Station Explorer Detail Panels & Comparison

| Field        | Value                    |
| ------------ | ------------------------ |
| Epic ID      | E-1402                   |
| Phase        | PH-14                    |
| Owner        | @dinesh-git17            |
| Status       | Complete                 |
| Dependencies | [E-1401, E-1102, E-1103] |
| Created      | 2026-02-10               |

---

## Context

The Station Explorer page presents station-level analytics through conditional detail panels: TTC subway stations display delay incident timelines and delay cause breakdowns from `fct_transit_delays` (237,446 rows); Bike Share stations display trip volume timelines and usage patterns from `fct_bike_trips` (21,795,223 rows). Dashboard-design.md Section 4.2 Page 5 specifies station stats metric cards, delay/trip history line charts, and a nearby stations table — all responding to the selected station and filtered by date range. This epic delivers the 4 parameterized query functions, conditional metric cards, timeline charts, nearby stations table, and station comparison panels that populate these detail sections.

The data access pattern differs fundamentally between station types. TTC delay queries filter 237K rows by `station_key` + `date_key` — expected execution under 500ms on X-Small. Bike Share trip queries filter 21.8M rows by `start_station_key` + `date_key` with mandatory partition pruning — expected execution 1-2 seconds for a single-year range per PHASES.md performance mandate. Station comparison extends single-station panels to support side-by-side analysis of up to 3 stations per dashboard-design.md stretch goal, reusing individual station queries with per-station cache isolation.

---

## Scope

### In Scope

- `dashboard/data/queries.py`: 4 parameterized SQL query functions:
  - `station_delay_metrics(station_key)` — aggregate delay statistics for a single TTC subway station (total incidents, total minutes, average delay, top cause)
  - `station_trip_metrics(station_key)` — aggregate trip statistics for a single Bike Share station (total trips, average duration, dominant user type)
  - `station_delay_timeline(station_key)` — monthly delay trend for a single TTC subway station (year, month, delay count, total minutes)
  - `station_trip_timeline(station_key)` — monthly trip trend for a single Bike Share station (year, month, trip count, average duration)
- Station summary metric cards: 4 conditional cards rendered via `render_metric_row()` from `components/metrics.py`:
  - TTC variant (red border): total delay incidents, total delay minutes, average delay per incident, most frequent delay category
  - Bike Share variant (green border): total trips, average trip duration, busiest month, neighborhood name
- Conditional detail timeline charts: monthly delay count line chart for TTC stations and monthly trip count line chart for Bike Share stations via `line_chart()` from `components/charts.py`
- Nearby stations sortable table: top 10 stations by geographic proximity via `st.dataframe()` with columns for station name, type, distance (km), and activity metric (delay count or trip count)
- Station comparison panels: side-by-side metric cards and overlaid timeline charts for up to 3 selected stations of the same type

### Out of Scope

- Map rendering and geospatial visualization (E-1401 scope)
- Page-level layout, sidebar controls, and filter integration (E-1403 scope)
- Bus and streetcar station-level analysis (`dim_station` contains TTC subway and Bike Share only)
- Individual trip-level or incident-level detail tables (grain is monthly aggregation)
- Station-to-station trip flow analysis or origin-destination matrices
- Predictive delay or trip forecasting for selected stations
- Real-time station availability or capacity data from GBFS live feeds

---

## Technical Approach

### Architecture Decisions

- **Separate query functions per station type** — TTC and Bike Share stations source from fundamentally different fact tables (`fct_transit_delays` vs `fct_bike_trips`), return different column schemas (delay_minutes vs duration_seconds), and carry different performance profiles (237K vs 21.8M rows). Separate functions eliminate conditional SQL branching and enable type-specific optimization. The page calls the appropriate function based on the selected station's `station_type` value from `dim_station`.
- **Station-level queries use station_key + date_key dual filtering** — All queries filter by `station_key = %(station_key)s` AND `date_key BETWEEN %(start_date)s AND %(end_date)s`. The `date_key` filter provides Snowflake partition pruning on the large fact tables. For `fct_bike_trips`, a single-station + single-year query reduces 21.8M to approximately 20K rows; expected execution 1-2 seconds on X-Small. For `fct_transit_delays`, a single-station + full-range query reduces 237K to approximately 3K rows; expected execution under 500ms.
- **Timeline queries group by year and month** — Monthly aggregation provides sufficient granularity for station-level trend analysis without producing excessive data points. A 5-year range yields approximately 60 data points per station — ideal for Altair `line_chart()`. The timeline uses a combined `YYYY-MM` ordinal axis for clear chronological ordering across multi-year ranges.
- **Metric cards adapt content to station type** — TTC metric cards use `border_variant="ttc"` (red) and display delay-specific values. Bike Share metric cards use `border_variant="bike"` (green) and display trip-specific values. Both render via `render_metric_row()` from E-1103 with 4 cards per row. The rendering function accepts the station type and query result DataFrame, handling conditional logic internally.
- **Nearby stations table enriched from page-level aggregation queries** — The nearby table combines geographic proximity data from `find_nearby_stations()` (E-1401) with an activity metric per station. Rather than issuing 10 individual Snowflake queries per nearby station, the activity metric comes from existing page-level aggregation queries: `ttc_station_delays()` (E-1202) for TTC stations and `bike_station_activity()` (E-1302) for Bike Share stations. A DataFrame merge on `station_key` enriches the nearby table without additional Snowflake round-trips.
- **Station comparison uses cached individual queries** — Comparing 2-3 stations issues separate `query_filtered()` calls per station. Each call is independently cached at 10-minute TTL — switching between stations reuses previously-cached results with zero Snowflake latency. Timeline overlay concatenates per-station DataFrames with an added `station_name` column and renders via `line_chart(color="station_name")`.
- **`dashboard-design` skill enforcement** — Metric card border variants match station type (red/green). Timeline charts inherit `toronto_mobility` Altair theme. Table columns formatted with comma separators and human-readable headers. All colors from Section 6.1 palette. Section headings use `st.subheader()` with descriptive, type-adaptive titles.

### Integration Points

- **E-1401** — `find_nearby_stations()` from `utils/geo.py` provides the nearby stations DataFrame with `distance_km` column; `STATION_COLORS`, `STATION_TYPE_LABELS`, and `STATION_HEX_COLORS` from `maps.py` inform conditional rendering colors and labels
- **E-1102** — `query_filtered()` (10-minute TTL) executes station-level queries with station_key + date_key parameters; `query_aggregation()` (30-minute TTL) provides page-level station aggregations for nearby table enrichment; `query_reference_data()` (24-hour TTL) provides station coordinate DataFrame
- **E-1103** — `line_chart()` from `charts.py` renders timeline trends; `render_metric_card()` and `render_metric_row()` from `metrics.py` render station summary cards; `toronto_mobility` Altair theme applies to all chart output
- **E-1202** — `ttc_station_delays()` query provides per-station delay counts for nearby table TTC activity enrichment
- **E-1302** — `bike_station_activity()` query provides per-station trip counts for nearby table Bike Share activity enrichment
- **E-1403** — Page composition consumes all detail panel rendering functions and arranges them within the page layout
- **MARTS tables consumed** (via queries): `fct_transit_delays` (237,446 rows — TTC station queries), `fct_bike_trips` (21,795,223 rows — Bike Share station queries), `dim_station` (1,084 searchable stations), `dim_date` (2,922 rows for timeline joins), `dim_ttc_delay_codes` (334 rows for delay category lookup)

### Repository Areas

- `dashboard/data/queries.py` (modify — add 4 station-level query functions)
- `dashboard/pages/5_Station_Explorer.py` (modify — detail panel rendering helpers)

### Risks

| Risk                                                                                                                                                                          | Likelihood | Impact | Mitigation                                                                                                                                                                                                                                                                                                          |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `fct_bike_trips` single-station query exceeds 2-second interaction target for popular downtown stations with 50K+ annual trips when the full 5-year date range is selected    | Medium     | Medium | 10-minute cache tier via `query_filtered()` prevents re-execution on repeated interactions; `date_key` partition pruning bounds the scan; cold-start 2-3 seconds is within the 5-second cold start target per Section 5.6; display `st.spinner("Loading station data...")` during execution                         |
| Station comparison with 3 stations issues 6 separate Snowflake queries (metrics + timeline per station) causing cumulative latency above the 2-second warm interaction target | Medium     | High   | Cache individual station queries at 10-minute TTL — switching between stations reuses previously-cached results with zero latency; first comparison cold-start may reach 3-4 seconds (within 5-second cold start target); subsequent interactions for previously-viewed stations require zero Snowflake round-trips |
| TTC stations with zero delay incidents in the selected date range produce empty metric cards and blank timeline charts, creating a visually broken section                    | Medium     | Low    | Empty-state handling: display `st.info("No delay incidents recorded for this station in the selected period.")` and render metric cards with "0" values rather than blank or NaN fields; expected for stations on newer lines (SHP, SRT) with minimal recorded delays                                               |
| Nearby stations table mixes TTC delay counts and Bike Share trip counts in the Activity column — semantically different metrics create potential user confusion               | Medium     | Medium | Display station type in the Type column for context; add parenthetical unit label to Activity column header: "Activity (delays/trips)"; alternatively, show the metric appropriate to each station's type with the unit appended: "1,247 delays" or "14,287 trips"                                                  |

---

## Stories

| ID   | Story                                                              | Points | Dependencies            | Status |
| ---- | ------------------------------------------------------------------ | ------ | ----------------------- | ------ |
| S001 | Add station explorer parameterized queries to the data layer       | 5      | None                    | Complete |
| S002 | Build station summary metric cards with type-conditional content   | 5      | S001                    | Complete |
| S003 | Build conditional detail timeline charts with temporal aggregation | 5      | S001                    | Complete |
| S004 | Build nearby stations sortable table with distance ranking         | 5      | E-1401.S002             | Complete |
| S005 | Build station comparison panels for up to 3 stations               | 5      | S002, S003, E-1401.S004 | Complete |

---

### S001: Add Station Explorer Parameterized Queries to the Data Layer

**Description**: Add 4 parameterized SQL query functions to `dashboard/data/queries.py` providing station-level aggregate metrics and monthly timeline data for individual TTC subway and Bike Share stations, all with mandatory `date_key` partition pruning.

**Acceptance Criteria**:

- [ ] Function `station_delay_metrics() -> str` in `dashboard/data/queries.py` returns a SQL string that:
  - Selects `COUNT(*) as delay_count`, `SUM(delay_minutes) as total_delay_minutes`, `ROUND(AVG(delay_minutes), 1) as avg_delay_minutes` from `fct_transit_delays`
  - Includes a subquery or window function to identify the most frequent `delay_category` for the station in the date range via ranked aggregation
  - Filters by `station_key = %(station_key)s` AND `date_key BETWEEN %(start_date)s AND %(end_date)s`
  - Returns a single-row result with 4 columns: `delay_count`, `total_delay_minutes`, `avg_delay_minutes`, `top_delay_category`
- [ ] Function `station_trip_metrics() -> str` returns a SQL string that:
  - Selects `COUNT(*) as trip_count`, `ROUND(AVG(duration_seconds) / 60, 1) as avg_duration_minutes` from `fct_bike_trips`
  - Includes a subquery or window function to identify the most common `user_type` for the station
  - Filters by `start_station_key = %(station_key)s` AND `date_key BETWEEN %(start_date)s AND %(end_date)s`
  - Returns a single-row result with 3 columns: `trip_count`, `avg_duration_minutes`, `top_user_type`
- [ ] Function `station_delay_timeline() -> str` returns a SQL string that:
  - Selects `d.year`, `d.month_num`, `d.month_name`, `COUNT(*) as delay_count`, `SUM(f.delay_minutes) as total_delay_minutes` from `fct_transit_delays f` joined to `dim_date d` on `date_key`
  - Filters by `f.station_key = %(station_key)s` AND `f.date_key BETWEEN %(start_date)s AND %(end_date)s`
  - Groups by `d.year`, `d.month_num`, `d.month_name`
  - Orders by `d.year`, `d.month_num`
- [ ] Function `station_trip_timeline() -> str` returns a SQL string that:
  - Selects `d.year`, `d.month_num`, `d.month_name`, `COUNT(*) as trip_count`, `ROUND(AVG(f.duration_seconds) / 60, 1) as avg_duration_minutes` from `fct_bike_trips f` joined to `dim_date d` on `date_key`
  - Filters by `f.start_station_key = %(station_key)s` AND `f.date_key BETWEEN %(start_date)s AND %(end_date)s`
  - Groups by `d.year`, `d.month_num`, `d.month_name`
  - Orders by `d.year`, `d.month_num`
- [ ] All 4 functions use `%(station_key)s`, `%(start_date)s`, and `%(end_date)s` bind-variable placeholders — zero string interpolation for any parameter values
- [ ] All functions have type hints and docstrings describing query purpose, parameters, return columns, and source table
- [ ] `station_trip_metrics()` and `station_trip_timeline()` use `start_station_key` (trip origin) consistent with the existing `bike_station_activity()` pattern from E-1302

**Technical Notes**: The `station_key` is a surrogate key (MD5 hash from `generate_surrogate_key(['station_type', 'station_id'])`). The page resolves `station_key` from the user's station name selection via the cached `reference_stations()` DataFrame. The most frequent delay category in `station_delay_metrics()` uses a ranked window: `SELECT delay_category FROM (SELECT delay_category, ROW_NUMBER() OVER (ORDER BY COUNT(*) DESC) as rn FROM ... GROUP BY delay_category) WHERE rn = 1`. The `station_trip_metrics()` function uses `start_station_key` only — matching the E-1302 pattern where station activity measures trip origins.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] All 4 query functions return valid SQL strings with bind-variable placeholders
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S002: Build Station Summary Metric Cards with Type-Conditional Content

**Description**: Implement station summary metric cards that adapt content based on the selected station's type — delay-centric cards with red border for TTC subway stations and trip-centric cards with green border for Bike Share stations — using `render_metric_row()` from `components/metrics.py`.

**Acceptance Criteria**:

- [ ] TTC subway station selection renders 4 metric cards:
  - "Delay Incidents": total count formatted with comma separators (e.g., "1,247")
  - "Total Delay Minutes": sum formatted with comma separators (e.g., "5,832")
  - "Avg Delay": average per incident formatted to 1 decimal place with unit (e.g., "4.2 min")
  - "Top Cause": most frequent delay category text (e.g., "Operations")
- [ ] Bike Share station selection renders 4 metric cards:
  - "Total Trips": count formatted with comma separators (e.g., "14,287")
  - "Avg Duration": average trip duration formatted with unit (e.g., "12.3 min")
  - "Busiest Month": month and year with highest trip count (e.g., "July 2023") derived from `station_trip_timeline()` results
  - "Neighborhood": station neighborhood name from `dim_station` reference data (e.g., "The Annex")
- [ ] TTC metric cards render with `border_variant="ttc"` (red left border per `custom.css`)
- [ ] Bike Share metric cards render with `border_variant="bike"` (green left border per `custom.css`)
- [ ] Metric cards render in a horizontal row using `render_metric_row()` with 4 cards per row
- [ ] Metric values source from `station_delay_metrics()` or `station_trip_metrics()` query results (S001)
- [ ] Busiest month for Bike Share derived from `station_trip_timeline()` result: the month with highest `trip_count` value
- [ ] Neighborhood value sourced from `dim_station` via cached `reference_stations()` DataFrame — not from a separate query
- [ ] When query returns 0 rows (no activity), metric cards display "0" for count/duration fields and "N/A" for text fields — no NaN, division-by-zero, or empty card rendering
- [ ] Metric cards update dynamically on station selection change and date range filter change
- [ ] Section heading adapts to station type: "Station Metrics" for both types

**Technical Notes**: The rendering function accepts the station type string and query result DataFrame, returning the appropriate metric card configuration. The pattern follows E-1302 insight card helpers: extract values from DataFrame, check for empty results, format strings, pass to `render_metric_card()`. The neighborhood value comes directly from `dim_station` (via `reference_stations()`) rather than a computed metric — it is a static attribute of the station. For the busiest month, sort the timeline DataFrame by `trip_count` descending and take the first row's `month_name` and `year`.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] TTC station selection renders delay-centric metric cards with red border variant
- [ ] Bike Share station selection renders trip-centric metric cards with green border variant
- [ ] Empty-state (zero query results) renders cards with "0" / "N/A" placeholder values
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S003: Build Conditional Detail Timeline Charts with Temporal Aggregation

**Description**: Implement conditional timeline charts that render a monthly delay trend line chart for TTC subway stations or a monthly trip trend line chart for Bike Share stations, using `line_chart()` from `components/charts.py` with data from S001 timeline query functions.

**Acceptance Criteria**:

- [ ] TTC station selection renders a line chart of monthly delay counts via `line_chart()` from `components/charts.py`
- [ ] TTC timeline chart uses `x` = combined `YYYY-MM` string (ordinal, chronologically ordered), `y` = `delay_count` (quantitative), with optional `color` = `year` (nominal, cast to string) when the date range spans multiple years
- [ ] Bike Share station selection renders a line chart of monthly trip counts via `line_chart()`
- [ ] Bike Share timeline chart uses `x` = combined `YYYY-MM` string, `y` = `trip_count` (quantitative), with optional `color` = `year` when multi-year
- [ ] Timeline data sourced from `station_delay_timeline()` or `station_trip_timeline()` (S001) based on the selected station's `station_type`
- [ ] Combined x-axis string computed as `year.astype(str) + "-" + month_num.astype(str).str.zfill(2)` for consistent chronological ordering without multi-year overlap
- [ ] Section heading adapts to station type: "Delay History" for TTC, "Trip History" for Bike Share
- [ ] Chart axes have descriptive titles: x-axis = "Month", y-axis = "Delay Incidents" (TTC) or "Trips" (Bike Share)
- [ ] Timeline chart inherits the `toronto_mobility` Altair theme with Inter typography and `width="container"` responsive sizing
- [ ] Empty timeline (station with no activity in the selected date range) displays `st.info("No data recorded for this station in the selected period.")` instead of an empty or errored chart
- [ ] Chart responds to date range filter changes and station selection changes via standard Streamlit rerun behavior
- [ ] Timeline renders within 2 seconds per dashboard-design.md Section 5.6 filter response target

**Technical Notes**: For the combined x-axis, a `YYYY-MM` string (e.g., "2023-01") provides clean chronological ordering without the multi-year month-name overlap issue encountered in seasonality charts. For single-year ranges, the chart produces 12 data points. For the full 5-year range, approximately 60 data points. Both are well within Altair's rendering capacity. The `line_chart()` function from E-1103 supports `color` encoding for multi-line overlays when multiple years are present.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] TTC station renders monthly delay count timeline from live MARTS data
- [ ] Bike Share station renders monthly trip count timeline from live MARTS data
- [ ] Empty-state displays informative message instead of blank chart
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S004: Build Nearby Stations Sortable Table with Distance Ranking

**Description**: Implement a sortable table displaying the 10 nearest stations to the selected station, ranked by geographic proximity, with station type, distance in kilometers, and a context-appropriate activity metric sourced from cached page-level aggregation data.

**Acceptance Criteria**:

- [ ] Nearby stations table renders via `st.dataframe()` displaying up to 10 rows
- [ ] Data sourced from `find_nearby_stations()` (E-1401 S002) with `n=10` nearest stations and `exclude_key` set to the selected station's `station_key`
- [ ] Table columns: Rank (1-10), Station Name, Type (TTC Subway / Bike Share), Distance (km), Activity
- [ ] Activity metric sourced from pre-existing page-level query DataFrames:
  - TTC station activity from `ttc_station_delays()` (E-1202) matched by `station_key` — displays delay count
  - Bike Share station activity from `bike_station_activity()` (E-1302) matched by `station_key` — displays trip count
  - Avoids issuing per-station Snowflake queries for the 10 nearby stations
- [ ] Activity column displays the count with unit suffix: "1,247 delays" for TTC or "14,287 trips" for Bike Share
- [ ] Column headers are human-readable: "Station", "Type", "Distance (km)", "Activity"
- [ ] Distance column formatted to 2 decimal places (e.g., "0.34")
- [ ] Count values in Activity column formatted with comma separators
- [ ] Table supports native Streamlit column sorting when user clicks column headers
- [ ] Table is full-width (not inside a column split), placed below the timeline chart section
- [ ] Section heading: "Nearby Stations"
- [ ] Table responds to station selection changes — recomputes nearby stations via `find_nearby_stations()` and re-enriches activity metrics
- [ ] Stations without a matching activity metric (e.g., a newly-added station not in the aggregation query results) display "—" in the Activity column

**Technical Notes**: The `find_nearby_stations()` function from E-1401 returns a DataFrame with `distance_km` already computed. Activity metric enrichment performs a left join (DataFrame merge) with the page-level station query results on `station_key`. The page-level queries (`ttc_station_delays()` and `bike_station_activity()`) are executed once per filter change and cached at 30-minute TTL via `query_aggregation()` — the nearby table enrichment adds zero Snowflake overhead. Column renaming: `df.rename(columns={"station_name": "Station", ...})`. Rank column: `df.insert(0, "Rank", range(1, len(df) + 1))`.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Nearby stations table renders 10 rows with distance and activity metrics from live reference and aggregation data
- [ ] Table responds to station selection changes with updated distances
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S005: Build Station Comparison Panels for Up to 3 Stations

**Description**: Implement station comparison capability with side-by-side metric cards and overlaid timeline charts for up to 3 selected stations of the same type, extending the single-station detail panels to multi-station analytical comparison per dashboard-design.md stretch goal.

**Acceptance Criteria**:

- [ ] Comparison mode activates via a `st.multiselect()` component in the sidebar, labeled "Compare stations", offering stations of the same `station_type` as the primary selection (excluding the primary station itself)
- [ ] Maximum of 2 additional stations selectable (3 total including the primary selection)
- [ ] Comparison multiselect dynamically filters its options to match the primary station's `station_type` — TTC stations compare with TTC, Bike Share with Bike Share
- [ ] Metric cards render in parallel columns: `st.columns(n)` where n = number of selected stations (1, 2, or 3)
- [ ] Each column displays the station name as a `st.subheader()` above its metric cards for identification
- [ ] Timeline charts overlay all selected stations on a single `line_chart()` with `color` encoding by station name
- [ ] Timeline legend differentiates stations by color: primary station in accent blue (#2563EB), second station in neutral slate (#334155), third station in warning amber (#F59E0B) — all from Section 6.1 palette
- [ ] Comparison mode reuses the same query functions (S001) — one query per station, each individually cached at 10-minute TTL via `query_filtered()`
- [ ] When a comparison station has no data in the selected period, its column displays `st.info("No data for the selected period")` while other stations render normally
- [ ] Comparison mode is optional — single-station layout (full-width metric cards, single-line timeline) remains the default interaction pattern
- [ ] Deselecting all comparison stations returns to single-station layout without requiring page reload
- [ ] 3-station comparison queries complete within 5 seconds on cold cache per Section 5.6 cold start target; within 2 seconds on warm cache

**Technical Notes**: The multiselect for comparison filters the `reference_stations()` DataFrame by `station_type == primary_type` and excludes the primary station's `station_key`. Query caching means switching primary stations preserves cached results for previously-viewed comparison stations, reducing cumulative latency. Timeline overlay: concatenate per-station timeline DataFrames with an added `station_name` column, then pass to `line_chart(data, x="period", y="delay_count", color="station_name")`. Metric card column width: `st.columns([1] * n)` for equal distribution. For 3-station display on narrow viewports, the metric card layout simplifies to 2 key metrics per station (total count + average) instead of 4.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Selecting 2 comparison stations renders side-by-side metric cards and overlaid timeline chart with 3 distinct colors
- [ ] Deselecting comparison stations returns to single-station full-width layout
- [ ] PR opened with linked issue
- [ ] CI checks green

---

## Exit Criteria

This epic is complete when:

- [ ] `dashboard/data/queries.py` contains 4 station-level query functions (`station_delay_metrics`, `station_trip_metrics`, `station_delay_timeline`, `station_trip_timeline`) with bind-variable parameters for station_key and date range
- [ ] TTC subway station selection renders delay-centric metric cards (total incidents, total minutes, avg delay, top cause) with red border variant
- [ ] Bike Share station selection renders trip-centric metric cards (total trips, avg duration, busiest month, neighborhood) with green border variant
- [ ] TTC station selection renders a monthly delay count line chart sourced from `fct_transit_delays`
- [ ] Bike Share station selection renders a monthly trip count line chart sourced from `fct_bike_trips`
- [ ] Nearby stations table displays 10 nearest stations with distance in km and type-appropriate activity metric, enriched from cached page-level aggregation data
- [ ] Station comparison renders side-by-side metric cards and overlaid timeline charts for up to 3 stations of the same type with distinct palette colors
- [ ] All `fct_bike_trips` queries enforce `date_key BETWEEN` partition pruning — zero unbounded scans of the 21.8M-row table
- [ ] All queries use parameterized execution via `query_filtered()` — zero string interpolation in SQL parameters
- [ ] Empty-state handling displays informative messages for stations with no data in the selected date range
- [ ] Design system applied consistently: TTC red / Bike green border variants, Inter typography, `toronto_mobility` Altair theme, Section 6.1 comparison palette colors
- [ ] No import errors, rendering warnings, or uncaught exceptions during station selection, filter changes, or comparison interaction
