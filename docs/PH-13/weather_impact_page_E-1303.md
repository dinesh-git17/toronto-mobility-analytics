# Weather Impact Page

| Field        | Value                            |
| ------------ | -------------------------------- |
| Epic ID      | E-1303                           |
| Phase        | PH-13                            |
| Owner        | @dinesh-git17                    |
| Status       | Complete                         |
| Dependencies | [E-1102, E-1103, E-1104, E-1301] |
| Created      | 2026-02-10                       |

---

## Context

The Weather Impact page is PH-13's second deliverable — it quantifies the relationship between weather conditions and urban mobility, answering "how does weather affect the way Torontonians travel?" Per dashboard-design.md Section 4.2 Page 4, this page surfaces weather-correlated patterns through 4 visualization types and 3 key callout boxes: bike trips by weather condition bar chart, transit delays by weather condition bar chart, temperature vs daily trips scatter plot, precipitation vs daily trips scatter plot, and computed impact comparisons highlighting rain's effect on cycling, snow's effect on transit delays, and the optimal temperature range for peak ridership. All queries source exclusively from `fct_daily_mobility` (1,827 rows) joined to `dim_weather` — no `fct_bike_trips` or `fct_transit_delays` scans required, making this the lightest page in the dashboard from a query performance perspective.

This page completes the dashboard's core analytical coverage by introducing the weather dimension — the only external factor in the dataset that demonstrably influences both transit delays and cycling ridership. It is the third deep-dive page built on the PH-11 foundation and the first to use the scatter plot component from E-1301. The page replaces the stub module created in E-1101 S004.

---

## Scope

### In Scope

- `dashboard/pages/4_Weather_Impact.py`: Complete page implementation replacing the E-1101 stub with 4 chart sections, 3 callout boxes, and a weather condition comparison selector
- Weather Impact query function added to `dashboard/data/queries.py`:
  - Daily weather metrics: per-day weather condition, temperature, precipitation, bike trip counts, and transit delay counts from `fct_daily_mobility` joined to `dim_weather` (single query serving all 4 charts and 3 callouts)
- Sidebar filter per dashboard-design.md Section 4.2 Page 4:
  - Weather condition comparison selector via `select_filter()` from `components/filters.py` (options: Clear, Rain, Snow; default: Rain for maximum impact contrast)
- 4 visualization types:
  1. Bike trips by weather condition horizontal bar chart (Altair, total trips grouped by Clear/Rain/Snow, Bike Share green fill)
  2. Transit delays by weather condition horizontal bar chart (Altair, total delay incidents grouped by Clear/Rain/Snow, TTC red fill)
  3. Temperature vs daily trips scatter plot (Altair, x=`mean_temp_c`, y=`total_bike_trips`, color=`weather_condition`)
  4. Precipitation vs daily trips scatter plot (Altair, x=`total_precip_mm`, y=`total_bike_trips`, color=`weather_condition`)
- 3 contextual callout boxes via `st.info()`:
  - Selected condition's impact on bike trips (percentage change vs clear days)
  - Selected condition's impact on transit delays (percentage change vs clear days)
  - Temperature sweet spot range for peak bike usage
- Cache tier: all queries at 30-minute TTL via `query_aggregation()` (`fct_daily_mobility` is 1,827 rows — filtered-query tier unnecessary)
- Custom CSS injection from `styles/custom.css`

### Out of Scope

- Date range filter on this page (weather analysis uses full date range for maximum statistical power; dashboard-design.md Section 4.2 Page 4 specifies only a weather condition comparison selector)
- Wind speed or wind direction analysis (columns available in `dim_weather` but not included in page specification)
- Weather-based anomaly detection or alerting
- Predictive weather impact modeling or regression analysis
- Bike Share station-level weather impact (requires `fct_bike_trips` scan; beyond page scope)
- Station Explorer page (PH-14)
- Mobile-specific layout adjustments (PH-14)
- Real-time weather data integration
- Precipitation type breakdown (rain vs snow separately on scatter plots)

---

## Technical Approach

### Architecture Decisions

- **All queries source from `fct_daily_mobility` joined to `dim_weather` — zero large fact table scans** — The weather page analyzes daily-level aggregates already pre-computed in `fct_daily_mobility` (1,827 rows). Joining to `dim_weather` (2,922 rows, 1:1 on `date_key`) adds weather measurements. No query touches `fct_bike_trips` (21.8M rows) or `fct_transit_delays` (237K rows). All queries execute in under 200ms on X-Small.
- **Single consolidated daily metrics query serves all 4 charts and 3 callouts** — One query returns per-day rows with `weather_condition`, `mean_temp_c`, `total_precip_mm`, `total_bike_trips`, and `total_delay_incidents`. Bar charts aggregate from this DataFrame in Python (`df.groupby('weather_condition')`). Scatter plots use the raw daily rows directly. Callouts compute comparisons from the same DataFrame. This minimizes Snowflake round-trips to a single query execution per 30-minute cache cycle.
- **Weather condition selector controls callout narrative, not chart filtering** — The bar charts display all 3 conditions for visual comparison. The scatter plots display all daily data points color-coded by condition. The `st.selectbox` controls which condition is compared against "Clear" in the 3 callout boxes (e.g., selecting "Rain" produces "Rain reduces bike trips by 55% compared to clear days"; selecting "Snow" produces "Snow reduces bike trips by X%"). This maximizes the data visible on every chart while providing focused narrative through the selector.
- **Scatter points color-coded by weather condition** — Each daily observation is colored by its `weather_condition`: Clear in `neutral-data` (#737373), Rain in `accent-primary` (#2563EB), Snow in light blue (#93C5FD). This follows the dashboard-design skill's "fewer hues, more shades" principle. The 3-color categorical encoding stays within the maximum 3 semantic accents per page.
- **No date range filter for maximum statistical power** — Weather impact analysis benefits from the full 5-year dataset to establish robust correlations. Restricting to a narrow date range would reduce per-condition sample sizes and introduce year-specific confounds (e.g., COVID-era ridership changes in 2020-2021). The page uses all available data for authoritative statistical comparisons.
- **Page omits KPI row; bar charts serve as the summary tier** — The weather page's analytical question ("how does weather affect mobility?") is comparative, not summary-based. Individual metrics (e.g., "Average Temperature: 8.5°C") do not serve this question. The bar charts provide the summary-level comparison that KPIs would otherwise serve, followed by scatter plots for correlation detail and callouts for narrative insight. This follows the dashboard-design skill's progressive disclosure principle: summary (bars), evidence (scatter), insight (callouts).
- **`dashboard-design` skill enforcement** — Bar charts use `mark_color="#43B02A"` (Bike Share green) for bike trip bars and `mark_color="#DA291C"` (TTC red) for delay bars via the E-1301 `bar_chart(mark_color=...)` extension. Scatter plots use explicit 3-color categorical scale. Callout boxes use `st.info()` for neutral blue styling. All Altair charts inherit the registered `toronto_mobility` theme. Section headings use `st.subheader()`.

### Integration Points

- **E-1101** — Page file `dashboard/pages/4_Weather_Impact.py` replaces the stub created in E-1101 S004
- **E-1102** — Consumes `get_connection()` from `data/connection.py`; `query_aggregation()` (30-minute TTL) from `data/cache.py`
- **E-1103** — Consumes `bar_chart()` from `components/charts.py`; `select_filter()` from `components/filters.py`; `custom.css` from `styles/`
- **E-1104** — Follows the same page composition pattern: CSS injection → filter widget → data fetching → component rendering
- **E-1301** — Consumes `scatter_plot()` from `components/charts.py`; `bar_chart(mark_color=...)` from `components/charts.py`
- **MARTS tables consumed**: `fct_daily_mobility` (1,827 rows), `dim_weather` (2,922 rows)
- **Downstream: PH-14** — Weather Impact page has no downstream page dependencies; it is a terminal analytical page

### Repository Areas

- `dashboard/pages/4_Weather_Impact.py` (replace stub)
- `dashboard/data/queries.py` (modify — add weather query function)

### Risks

| Risk                                                                                                                                                                       | Likelihood | Impact | Mitigation                                                                                                                                                                                                                                                                        |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `dim_weather` contains NULL precipitation or temperature values for some dates, causing gaps in scatter plots and incorrect callout computations                           | Medium     | Medium | Apply `COALESCE(total_precip_mm, 0)` in SQL for NULL-safe precipitation; filter to `mean_temp_c IS NOT NULL` in SQL to exclude dates with missing temperature observations; scatter plots use `dropna()` before rendering; document NULL handling in query docstring              |
| Temperature vs trips scatter shows weak visual correlation because seasonality confounds the relationship (cold months have low trips regardless of daily temperature)     | Medium     | Low    | Color-code scatter points by `weather_condition` to add a second analytical dimension; callout narrative focuses on weather condition impact (clear vs rain vs snow) rather than raw temperature correlation; scatter serves as supporting evidence, not primary insight          |
| Callout computation for snow's impact produces misleading percentage when snow-day sample size is small relative to clear days (potential statistical instability)         | Low        | Medium | Compare average daily values (mean, not sum) between conditions to normalize for different day counts; display day count alongside percentage in callout text (e.g., "based on {N} snow days") for statistical context; flag conditions with fewer than 30 days as low-confidence |
| Bar charts with only 3 categories (Clear, Rain, Snow) look sparse and visually underwhelming compared to TTC and Bike Share deep-dive pages with richer data distributions | Medium     | Low    | Use horizontal bars with distinct project-palette fills (green for bikes, red for delays) for visual impact; add value labels at bar termini showing totals with comma formatting; keep bars wide using `st.columns(2)` for balanced proportions                                  |
| Weather condition selectbox defaulting to "Rain" confuses users who expect all data to be filtered, not just the callout narrative                                         | Low        | Low    | Add explanatory text below the selectbox: "Select a condition to compare against clear weather"; bar charts and scatter plots always show all conditions regardless of selection; callouts dynamically update to reflect the selected comparison                                  |

---

## Stories

| ID   | Story                                                                   | Points | Dependencies      | Status   |
| ---- | ----------------------------------------------------------------------- | ------ | ----------------- | -------- |
| S001 | Add weather impact query function to the data layer                     | 3      | None              | Complete |
| S002 | Build bike trips and transit delays by weather bar charts               | 5      | S001              | Complete |
| S003 | Build temperature and precipitation scatter plots                       | 5      | S001, E-1301.S002 | Complete |
| S004 | Build weather impact callout boxes                                      | 3      | S001              | Complete |
| S005 | Compose Weather Impact page layout with filter and validate performance | 5      | S002, S003, S004  | Complete |

---

### S001: Add Weather Impact Query Function to the Data Layer

**Description**: Add a consolidated weather-daily metrics query function to `dashboard/data/queries.py` returning per-day weather conditions, temperature, precipitation, bike trip counts, and transit delay counts from `fct_daily_mobility` joined to `dim_weather`.

**Acceptance Criteria**:

- [ ] Function `weather_daily_metrics() -> str` in `dashboard/data/queries.py` returns a SQL string that:
  - Selects `w.weather_condition`, `w.mean_temp_c`, `COALESCE(w.total_precip_mm, 0) as total_precip_mm`, `w.total_rain_mm`, `w.total_snow_cm`, `m.total_bike_trips`, `m.total_delay_incidents`, `m.total_delay_minutes`, `m.member_trips`, `m.casual_trips` from `fct_daily_mobility m` inner joined to `dim_weather w` on `m.date_key = w.date_key`
  - Filters to `w.mean_temp_c IS NOT NULL` (excludes dates with missing temperature observations)
  - Filters to `m.total_bike_trips IS NOT NULL OR m.total_delay_incidents IS NOT NULL` (excludes dates with no mobility data)
  - Returns one row per date (no GROUP BY — daily granularity preserved for scatter plots)
  - Orders by `m.date_key` for chronological consistency
- [ ] Function accepts no parameters — queries the full date range for maximum statistical power
- [ ] Function returns SQL with no bind variables (no date range filter on this page)
- [ ] Function has type hints and docstring describing the query purpose and return columns

**Technical Notes**: A single query returning daily rows serves all 4 charts and 3 callouts. Bar charts aggregate in Python via `df.groupby('weather_condition')`. Scatter plots use the raw DataFrame directly. The INNER JOIN between `fct_daily_mobility` and `dim_weather` restricts to dates with weather observations. The `COALESCE` on `total_precip_mm` prevents NULL values from creating scatter plot gaps. Expected result: ~1,500-1,800 rows (dates with both weather data and mobility data).

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Query function returns valid SQL string
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S002: Build Bike Trips and Transit Delays by Weather Bar Charts

**Description**: Implement two horizontal bar charts showing total bike trips and total transit delay incidents grouped by weather condition (Clear, Rain, Snow) for side-by-side weather impact comparison.

**Acceptance Criteria**:

- [ ] Weather Impact page renders a horizontal bar chart showing total bike trips per weather condition using `bar_chart()` from `components/charts.py`
- [ ] Bike trips bar chart data aggregated from `weather_daily_metrics()` DataFrame in Python: `df.groupby('weather_condition')['total_bike_trips'].sum().reset_index()`
- [ ] Bike trips bar chart uses `bar_chart(data, x="total_bike_trips", y="weather_condition", horizontal=True, mark_color="#43B02A")` with Bike Share green fill
- [ ] Bike trips bar chart section includes heading: "Bike Trips by Weather"
- [ ] Weather Impact page renders a horizontal bar chart showing total transit delay incidents per weather condition
- [ ] Delay bar chart data: `df.groupby('weather_condition')['total_delay_incidents'].sum().reset_index()`
- [ ] Delay bar chart uses `bar_chart(..., horizontal=True, mark_color="#DA291C")` with TTC red fill
- [ ] Delay bar chart section includes heading: "Transit Delays by Weather"
- [ ] Both bar charts sort y-axis in fixed order: `['Clear', 'Rain', 'Snow']` via explicit sort parameter or DataFrame ordering
- [ ] Both bar charts display in a 2-column layout using `st.columns(2)`
- [ ] Both bar charts render from a single `weather_daily_metrics()` query result — no duplicate Snowflake queries
- [ ] Both bar charts are independent of the weather condition selectbox — always show all 3 conditions

**Technical Notes**: The `weather_daily_metrics()` DataFrame is fetched once via `query_aggregation()` (30-minute cache) and reused across all chart sections and callout computations. Python aggregation (`groupby`) produces 3 rows per chart. The bar charts use horizontal orientation for readable condition labels. The `mark_color` parameter from E-1301 S004 sets the fill color for all bars in each single-series chart. Numeric formatting for bar value labels can use Altair's `mark_text()` overlay with `alt.Text('value:Q', format=',.0f')` for comma-separated totals.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Bike trips bar chart renders 3 green bars (Clear, Rain, Snow) from live MARTS data
- [ ] Transit delays bar chart renders 3 red bars from live MARTS data
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S003: Build Temperature and Precipitation Scatter Plots

**Description**: Implement two scatter plots showing temperature vs daily bike trips and precipitation vs daily bike trips, with data points color-coded by weather condition for pattern identification.

**Acceptance Criteria**:

- [ ] Weather Impact page renders an Altair scatter plot showing daily mean temperature (x-axis) vs total bike trips (y-axis) using `scatter_plot()` from `components/charts.py`
- [ ] Temperature scatter uses `scatter_plot(data, x="mean_temp_c", y="total_bike_trips", color="weather_condition", x_title="Mean Temperature (°C)", y_title="Daily Bike Trips")`
- [ ] Temperature scatter section includes heading: "Temperature vs Bike Trips"
- [ ] Weather Impact page renders an Altair scatter plot showing daily total precipitation (x-axis) vs total bike trips (y-axis) using `scatter_plot()`
- [ ] Precipitation scatter uses `scatter_plot(data, x="total_precip_mm", y="total_bike_trips", color="weather_condition", x_title="Precipitation (mm)", y_title="Daily Bike Trips")`
- [ ] Precipitation scatter section includes heading: "Precipitation vs Bike Trips"
- [ ] Both scatter plots use explicit color scale for `weather_condition`: Clear=#737373 (`neutral-data`), Rain=#2563EB (`accent-primary`), Snow=#93C5FD (light blue)
- [ ] Both scatter plots render ~1,500-1,800 data points (one per day with valid data) from the `weather_daily_metrics()` DataFrame
- [ ] Both scatter plots include tooltip showing `mean_temp_c` or `total_precip_mm`, `total_bike_trips`, and `weather_condition` on hover
- [ ] Both scatter plots display in a 2-column layout using `st.columns(2)`
- [ ] Both scatter plots are independent of the weather condition selectbox — always show all data points for all conditions
- [ ] Scatter data uses `dropna(subset=['mean_temp_c', 'total_bike_trips'])` for temperature and `dropna(subset=['total_precip_mm', 'total_bike_trips'])` for precipitation to handle any residual NULL values

**Technical Notes**: Both scatter plots use the same `weather_daily_metrics()` DataFrame (no additional queries). The color encoding uses `alt.Color('weather_condition:N', scale=alt.Scale(domain=['Clear', 'Rain', 'Snow'], range=['#737373', '#2563EB', '#93C5FD']))` for explicit project-palette assignment. The 3 colors stay within the dashboard-design skill's maximum 3 semantic accents per page. At 1,827 data points, Altair renders comfortably below its 5,000-row default threshold. The precipitation scatter may show a cluster of points at `total_precip_mm = 0` (clear and dry days) — this is expected and reveals the distribution of non-precipitation days.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Temperature scatter renders daily points with weather condition coloring from live MARTS data
- [ ] Precipitation scatter renders daily points from live MARTS data
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S004: Build Weather Impact Callout Boxes

**Description**: Implement 3 contextual callout boxes using `st.info()` that compute and display weather impact comparisons dynamically based on the selected weather condition from the sidebar selector.

**Acceptance Criteria**:

- [ ] Weather Impact page renders 3 `st.info()` callout boxes in a horizontal row using `st.columns(3)`
- [ ] Callout 1 — Bike trip impact: computes percentage difference in average daily bike trips between the selected condition and Clear days
  - Formula: `avg_trips_selected = df[condition == selected]['total_bike_trips'].mean()`; `avg_trips_clear = df[condition == 'Clear']['total_bike_trips'].mean()`; `pct_change = (avg_trips_selected - avg_trips_clear) / avg_trips_clear * 100`
  - Display: "{Selected} reduces bike trips by {X}%" when negative; "{Selected} increases bike trips by {X}%" when positive
  - When "Clear" is selected: "Clear days average {N:,.0f} bike trips per day"
- [ ] Callout 2 — Transit delay impact: computes percentage difference in average daily delay incidents between the selected condition and Clear days
  - Formula: `avg_delays_selected = df[condition == selected]['total_delay_incidents'].mean()`; `avg_delays_clear = df[condition == 'Clear']['total_delay_incidents'].mean()`; `pct_change = ...`
  - Display: "{Selected} increases TTC delays by {X}%" when positive; "{Selected} reduces TTC delays by {X}%" when negative
  - When "Clear" is selected: "Clear days average {N:.0f} delay incidents per day"
- [ ] Callout 3 — Temperature sweet spot: computes the 5°C temperature bin with the highest average daily bike trips
  - Formula: bin `mean_temp_c` into 5°C intervals via `pd.cut()`; compute mean `total_bike_trips` per bin; identify the peak bin
  - Display: "Peak cycling between {X}°C and {Y}°C" (e.g., "Peak cycling between 20°C and 25°C")
  - This callout is independent of the weather condition selector
- [ ] All callouts dynamically update when the weather condition selector changes (callouts 1 and 2 recompute; callout 3 remains constant)
- [ ] All percentage values rounded to nearest integer (no decimal places)
- [ ] Callout text includes the sample day count for statistical context: "(based on {N} {condition} days)" appended to callouts 1 and 2
- [ ] When any condition has fewer than 30 days in the dataset, the corresponding callout appends "(limited sample)" as a confidence qualifier
- [ ] Callout boxes render below the scatter plot section

**Technical Notes**: All callout computations derive from the same `weather_daily_metrics()` DataFrame — no additional Snowflake queries. The average comparison (mean, not sum) normalizes for different day counts across conditions (Clear days outnumber Rain and Snow days). The temperature binning uses `pd.cut(df['mean_temp_c'], bins=range(-30, 40, 5))` to create 5°C intervals spanning Toronto's temperature range. The peak bin extraction uses `.idxmax()` on the grouped mean. When "Clear" is selected, callouts 1 and 2 display absolute values instead of comparisons (comparing Clear to Clear produces 0% change, which is uninformative).

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] All 3 callout boxes render with computed values from live MARTS data
- [ ] Changing the weather condition selector updates callouts 1 and 2
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S005: Compose Weather Impact Page Layout with Filter and Validate Performance

**Description**: Assemble all Weather Impact sections into the final page layout — sidebar filter, bar charts, scatter plots, callout boxes — with CSS injection, selector propagation, empty-state handling, and end-to-end performance validation.

**Acceptance Criteria**:

- [ ] `dashboard/pages/4_Weather_Impact.py` composes all sections in a structured layout:
  1. `st.set_page_config(page_title="Weather Impact | Toronto Mobility", layout="wide")` as first Streamlit command
  2. CSS injection from `styles/custom.css` via `st.markdown`
  3. `st.title("Weather Impact")`
  4. Sidebar: weather condition comparison selector via `select_filter()` (options: `['Clear', 'Rain', 'Snow']`, default: `'Rain'`)
  5. Sidebar: explanatory text below selector: "Select a condition to compare against clear weather"
  6. Section 1: Bike trips by weather (left) + transit delays by weather (right) in `st.columns(2)`
  7. Section 2: Temperature scatter (left) + precipitation scatter (right) in `st.columns(2)`
  8. Section 3: 3 callout boxes in `st.columns(3)`
- [ ] Weather condition selector value propagates to callout computation (callouts 1 and 2 compare selected condition vs Clear)
- [ ] Bar charts and scatter plots render independently of the selector — always show all conditions
- [ ] All chart sections and callouts derive from a single `weather_daily_metrics()` query execution via `query_aggregation()` (30-minute TTL)
- [ ] Column names normalized to lowercase immediately after query fetch (`df.columns = [c.lower() for c in df.columns]`)
- [ ] Empty-state handling: if query returns 0 rows, display `st.info("No weather-mobility data available.")` and stop rendering
- [ ] `streamlit run dashboard/app.py` renders the Weather Impact page with all 4 chart types and 3 callout boxes from live Snowflake data
- [ ] Changing the weather condition selector updates callout text within 1 second (no Snowflake re-query; Python-only recomputation)
- [ ] All interactions respond within 2 seconds per dashboard-design.md Section 5.6
- [ ] No Python `ImportError`, `ModuleNotFoundError`, or Streamlit rendering warnings in the terminal output
- [ ] All Snowflake queries source exclusively from MARTS tables — zero RAW or STAGING schema access
- [ ] Page layout is visually consistent with dashboard-design.md Section 4.2 Page 4 component hierarchy
- [ ] All chart sections have descriptive headings per dashboard-design skill chart standards
- [ ] No default Streamlit or Altair colors visible — all charts use project palette

**Technical Notes**: This story integrates all E-1303 stories and E-1301 scatter plot component. The `weather_daily_metrics()` query returns ~1,500-1,800 rows from `fct_daily_mobility` joined to `dim_weather` and executes in under 200ms. The 30-minute cache tier is appropriate since the page has no date range filter (same query every time). Changing the weather condition selector triggers a Streamlit rerun but does NOT re-query Snowflake — the cached DataFrame is reused and callouts are recomputed in Python (sub-second). This makes the Weather Impact page the most responsive page in the dashboard.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] `streamlit run dashboard/app.py` → navigate to Weather Impact → all 4 chart types and 3 callouts render with live data
- [ ] Selector changes update callouts within 1 second
- [ ] PR opened with linked issue
- [ ] CI checks green

---

## Exit Criteria

This epic is complete when:

- [ ] `dashboard/pages/4_Weather_Impact.py` replaces the E-1101 stub with a complete interactive page
- [ ] `dashboard/data/queries.py` contains `weather_daily_metrics()` returning per-day weather and mobility data from `fct_daily_mobility` joined to `dim_weather`
- [ ] Weather condition comparison selector in the sidebar controls callout narrative (comparing selected condition vs Clear)
- [ ] Bike trips by weather horizontal bar chart renders 3 bars (Clear, Rain, Snow) with Bike Share green fill via `bar_chart(mark_color="#43B02A")`
- [ ] Transit delays by weather horizontal bar chart renders 3 bars with TTC red fill via `bar_chart(mark_color="#DA291C")`
- [ ] Temperature scatter plot renders ~1,500-1,800 daily data points color-coded by weather condition via `scatter_plot()`
- [ ] Precipitation scatter plot renders daily data points color-coded by weather condition via `scatter_plot()`
- [ ] 3 callout boxes display computed impact comparisons: bike trip change, transit delay change, and temperature sweet spot
- [ ] Callouts 1 and 2 dynamically update when the weather condition selector changes; callout 3 remains constant
- [ ] All callouts include sample day counts for statistical context
- [ ] All queries source exclusively from MARTS tables — zero `fct_bike_trips` or `fct_transit_delays` scans
- [ ] Selector interaction response completes within 1 second (Python-only recomputation, no Snowflake re-query)
- [ ] All chart interactions respond within 2 seconds per dashboard-design.md Section 5.6
- [ ] Empty-state handling displays informative messages when no data is available
- [ ] Design system applied consistently: project colors, Inter typography, `toronto_mobility` Altair theme, no default framework styling visible
- [ ] No import errors, rendering warnings, or uncaught exceptions during page navigation or selector interaction
