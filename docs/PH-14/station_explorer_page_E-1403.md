# Station Explorer Page Composition & Performance Validation

| Field        | Value                            |
| ------------ | -------------------------------- |
| Epic ID      | E-1403                           |
| Phase        | PH-14                            |
| Owner        | @dinesh-git17                    |
| Status       | Complete                         |
| Dependencies | [E-1401, E-1402, E-1101, E-1103] |
| Created      | 2026-02-10                       |

---

## Context

The Station Explorer is the fifth and final analytical page in the dashboard, completing the multi-page surface defined in dashboard-design.md. PH-11 created the page stub (`pages/5_Station_Explorer.py` with placeholder text), PH-14 E-1401 delivers the geospatial map components and proximity utilities, and E-1402 delivers the detail panels, query functions, and comparison capability. This epic assembles all components into the production page: a searchable station selector with type toggle in the sidebar, a centered PyDeck map with nearby stations overlay, conditional metric cards and timeline charts, a nearby stations table, and optional station comparison — all bound by date range filtering, state management, empty-state handling, and end-to-end performance validation.

The Station Explorer is the most interactive page in the dashboard — it combines map-centric geographic exploration with station-level analytical drilldown, requiring careful state management across the sidebar type toggle, station selector, date range filter, comparison multiselect, map viewport, and detail panel rendering. Every component responds to station selection changes, and the page must remain responsive within dashboard-design.md Section 5.6 targets: filter interaction under 2 seconds (warm cache), map render under 2 seconds, and cold start under 5 seconds.

---

## Scope

### In Scope

- `dashboard/pages/5_Station_Explorer.py`: Complete page implementation replacing the PH-11 stub with 5 sections (map, metrics, timeline, nearby table, comparison), sidebar controls, and date range filtering
- Sidebar controls per dashboard-design.md Section 4.2 Page 5:
  - Station type toggle: `st.radio` with options "TTC Subway" and "Bike Share" — filters the station selector dropdown
  - Station search/selector: `st.selectbox` with search capability across up to 1,084 stations (75 TTC subway or 1,009 Bike Share), dynamically filtered by type toggle
  - Date range filter: `date_range_filter()` from `components/filters.py` (default: full data range from `reference_date_bounds()`)
  - Station comparison multiselect: `st.multiselect` for up to 2 additional stations of the same type (E-1402 S005)
- Section composition in information hierarchy order:
  1. Station map — centered on selected station via `station_focus_map()` from E-1401
  2. Station summary metrics — 4 conditional cards from E-1402 S002
  3. Detail timeline chart — conditional delay/trip history from E-1402 S003
  4. Nearby stations table — 10 nearest stations from E-1402 S004
  5. Station comparison — optional side-by-side panels from E-1402 S005
- State management: type toggle → station selector → station_key resolution → query parameters → component rendering pipeline
- Cache tier alignment: station-level queries at 10-minute TTL via `query_filtered()`; reference data at 24-hour TTL via `query_reference_data()`; page-level aggregations at 30-minute TTL via `query_aggregation()`
- Empty-state handling for all sections when queries return zero rows
- Custom CSS injection from `styles/custom.css` as first rendering action after `st.set_page_config`

### Out of Scope

- Cross-page deep-link navigation to or from other dashboard pages
- Mobile-specific layout adjustments or responsive breakpoint configuration
- Station editing, data modification, or write-back capabilities
- Animated transitions between station selections or filter changes
- Loading skeleton screens during query execution (`st.spinner` suffices)
- Deployment to Streamlit Community Cloud (subsequent phase scope)
- Demo artifacts (README screenshots, GIF recording)
- URL-based station deep-linking via query parameters

---

## Technical Approach

### Architecture Decisions

- **Station type toggle gates the selector dropdown** — `st.radio("Station Type", ["TTC Subway", "Bike Share"])` filters the `st.selectbox` dropdown to display only stations matching the selected type. This prevents scrolling through 1,084 entries when searching for a specific station type. Changing the type toggle resets the station selector to the first station of the new type via `st.session_state` key management.
- **Station key resolution from cached reference data** — The `st.selectbox` displays station names (user-friendly text). The selected name maps to a `station_key` via lookup in the cached `reference_stations()` DataFrame (24-hour TTL). This avoids a Snowflake round-trip on every selection change. The lookup: `stations_df.loc[stations_df['station_name'] == selected_name, 'station_key'].iloc[0]`.
- **Section ordering follows progressive disclosure** — Map first (geographic context and orientation), then metric cards (summary statistics), then timeline (temporal detail), then nearby table (local context), then comparison (analytical extension). This hierarchy provides immediate geographic grounding before drilling into station-specific analytics.
- **Date range filter integration consistent with existing pages** — `date_range_filter()` returns `(start_date, end_date)` date objects. Conversion to integer `date_key` via `int(date.strftime('%Y%m%d'))` follows the pattern established in E-1202 and E-1302. All station-level queries pass `start_date` and `end_date` as bind parameters through `query_filtered()`.
- **Conditional rendering eliminates empty component sections** — The page checks `station_type` before invoking E-1402 detail panel functions. TTC stations trigger delay queries and delay-centric UI; Bike Share stations trigger trip queries and trip-centric UI. This prevents rendering irrelevant empty sections and avoids unnecessary Snowflake queries for the non-matching station type.
- **`dashboard-design` skill enforcement** — CSS injection as first action after `st.set_page_config`. Section headings via `st.subheader()` with descriptive titles. All component colors from palette tokens. No default Streamlit styling visible. Inter typography inherited from `custom.css`. Metric card variants match station type. Map uses dark basemap per Section 6.4. Page title follows the established pattern: `"Station Explorer | Toronto Mobility"`.

### Integration Points

- **E-1101** — Page file `dashboard/pages/5_Station_Explorer.py` replaces the stub created in E-1101 S004
- **E-1102** — `get_connection()` from `data/connection.py`; `query_filtered()` (10-minute TTL), `query_aggregation()` (30-minute TTL), and `query_reference_data()` (24-hour TTL) from `data/cache.py`; `reference_stations()` and `reference_date_bounds()` from `data/queries.py`
- **E-1103** — `line_chart()` from `components/charts.py`; `date_range_filter()` from `components/filters.py`; `render_metric_card()` and `render_metric_row()` from `components/metrics.py`; `custom.css` from `styles/`
- **E-1401** — `station_focus_map()` from `components/maps.py`; `find_nearby_stations()` and `haversine_distance()` from `utils/geo.py`; `STATION_COLORS`, `STATION_TYPE_LABELS`, and `STATION_HEX_COLORS` from `maps.py`
- **E-1402** — `station_delay_metrics()`, `station_trip_metrics()`, `station_delay_timeline()`, `station_trip_timeline()` from `data/queries.py`; metric card rendering; timeline chart rendering; nearby table rendering; comparison panel rendering
- **MARTS tables consumed** (via E-1402 queries): `fct_transit_delays` (237,446 rows — TTC station queries), `fct_bike_trips` (21,795,223 rows — Bike Share station queries), `dim_station` (1,084 searchable stations), `dim_date` (2,922 rows), `dim_ttc_delay_codes` (334 rows)

### Repository Areas

- `dashboard/pages/5_Station_Explorer.py` (replace stub — full page implementation)

### Risks

| Risk                                                                                                                                                       | Likelihood | Impact | Mitigation                                                                                                                                                                                                                                                                                                    |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `st.selectbox` search with 1,009 Bike Share station names produces sluggish dropdown behavior or slow character-by-character filtering on low-end browsers | Low        | Medium | Streamlit's selectbox uses client-side JavaScript filtering — 1,009 items is well within browser rendering capacity; tested at similar scale in production Streamlit deployments; if slow, pre-sort alphabetically and truncate display names to 40 characters                                                |
| Rapid station type toggling (TTC → Bike Share → TTC) causes stale query results or cache key collisions between station types                              | Low        | High   | Each query function uses `station_key` as a bind parameter — different stations produce different cache keys regardless of type toggle sequence; `st.cache_data` keys include all function arguments preventing cross-type contamination; `st.session_state` reset on type change clears selector state       |
| Page cold start exceeds 5-second target when loading reference data, first station's detail queries, and map render simultaneously on initial page visit   | Medium     | Medium | Reference data is shared across all pages and likely pre-cached from Overview or TTC page visit; station queries execute sequentially after reference data loads; `st.spinner` provides user feedback during initial loading; first-visit cold start of 3-4 seconds is within the 5-second Section 5.6 target |
| Station comparison with 3 stations on a standard 1366px laptop display produces cramped metric card layout with truncated text in the 3-column arrangement | Medium     | Medium | Comparison metric cards use simplified layout for 3 stations: 2 key metrics per station instead of 4; `st.columns([1, 1, 1])` provides equal distribution; timeline chart remains full-width below metric columns; station names as subheadings above each column provide clear identification                |

---

## Stories

| ID   | Story                                                                         | Points | Dependencies                                | Status |
| ---- | ----------------------------------------------------------------------------- | ------ | ------------------------------------------- | ------ |
| S001 | Build station search selector and type toggle sidebar controls                | 5      | None                                        | Complete |
| S002 | Compose map and detail panel sections with station selection state management | 5      | S001, E-1401.S001, E-1402.S002, E-1402.S003 | Complete |
| S003 | Compose nearby stations section and comparison panels                         | 5      | S001, E-1402.S004, E-1402.S005              | Complete |
| S004 | Assemble full page layout with filter propagation and empty-state handling    | 5      | S002, S003                                  | Complete |
| S005 | Validate performance targets and design system compliance                     | 3      | S004                                        | Complete |

---

### S001: Build Station Search Selector and Type Toggle Sidebar Controls

**Description**: Implement the sidebar controls for the Station Explorer page — a station type radio toggle, a searchable station selectbox, a date range filter, and a comparison multiselect — with state management that cascades type changes to the station list and comparison options.

**Acceptance Criteria**:

- [ ] `st.radio("Station Type", ["TTC Subway", "Bike Share"], key="station_type")` renders in the sidebar as the first control
- [ ] Default station type selection is "TTC Subway"
- [ ] `st.selectbox` renders below the type toggle with `label="Search Station"` and displays station names filtered by the selected station type
- [ ] Bike Share type toggle shows 1,009 station names; TTC Subway type toggle shows 75 station names (excluding ST_000 Unknown)
- [ ] Station names sorted alphabetically within each type for predictable search behavior
- [ ] Changing the station type toggle resets the station selectbox to the first station of the new type
- [ ] `date_range_filter()` renders below the station selector with default range from `reference_date_bounds()` (full data coverage)
- [ ] Comparison `st.multiselect("Compare Stations", ...)` renders below the date range filter, populated with stations of the same type as the primary selection, excluding the primary station
- [ ] Comparison multiselect limits selection to 2 additional stations (3 total) — enforced via `max_selections=2` parameter
- [ ] Station list for all controls sourced from cached `reference_stations()` DataFrame (24-hour TTL) — zero Snowflake round-trips on filter interactions
- [ ] Selected station resolves to `station_key` via DataFrame lookup: `stations_df.loc[stations_df['station_name'] == selected, 'station_key'].iloc[0]`
- [ ] Date range converts to integer `date_key` values via `int(date.strftime('%Y%m%d'))` consistent with E-1202 and E-1302 patterns

**Technical Notes**: The type toggle uses `st.session_state` to detect changes. When the type changes, the selectbox key must reset — use a dynamic key incorporating the type value: `key=f"station_select_{station_type}"`. The reference stations DataFrame is filtered by `station_type` column matching the radio selection (map "TTC Subway" → "TTC_SUBWAY", "Bike Share" → "BIKE_SHARE"). The comparison multiselect uses the same filtered DataFrame minus the primary selection's row.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Type toggle switches station list between 75 TTC and 1,009 Bike Share stations
- [ ] Station selectbox search filters stations by typed characters
- [ ] Comparison multiselect shows same-type stations excluding primary selection
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S002: Compose Map and Detail Panel Sections with Station Selection State Management

**Description**: Integrate the station focus map (E-1401) and detail panels (E-1402 metric cards and timeline chart) into the page, wiring the sidebar station selection to map centering, nearby station discovery, and conditional detail panel rendering.

**Acceptance Criteria**:

- [ ] Selected station resolves to a dict with keys `latitude`, `longitude`, `station_name`, `station_type`, `station_key` from the `reference_stations()` DataFrame
- [ ] `station_focus_map()` renders centered on the selected station with up to 10 nearby stations from `find_nearby_stations()` (E-1401)
- [ ] Map section renders via `st.pydeck_chart()` at full page width
- [ ] Map section includes heading: "Station Location"
- [ ] Nearby stations DataFrame computed from `find_nearby_stations(ref_lat, ref_lon, stations_df, n=10, exclude_key=station_key)` — result passed to both the map builder and the nearby table (S003)
- [ ] Station summary metric cards render below the map via `render_metric_row()` with 4 type-conditional cards (E-1402 S002)
- [ ] Detail timeline chart renders below the metric cards showing monthly delay trend (TTC) or trip trend (Bike Share) via `line_chart()` (E-1402 S003)
- [ ] All detail panel data sourced from E-1402 S001 query functions with `station_key` and `date_key` bind parameters
- [ ] Changing the station selection triggers recomputation of nearby stations, re-execution of detail queries, and re-rendering of all sections
- [ ] Changing the date range filter re-executes detail queries with updated date_key parameters; map and nearby table remain unchanged (geographic proximity is date-independent)

**Technical Notes**: The map and detail sections share the `station_key` derived from the sidebar selection. The nearby stations DataFrame is computed once per station change and passed to both `station_focus_map()` (for the overlay layer) and the nearby table component (S003). The detail queries (metrics + timeline) execute via `query_filtered()` with `station_key`, `start_date`, `end_date` parameters. State flow: `sidebar selection → station_key lookup → [map render, nearby computation, detail queries] → component rendering`.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Station selection renders centered map, metric cards, and timeline chart from live MARTS data
- [ ] Changing station updates all sections
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S003: Compose Nearby Stations Section and Comparison Panels

**Description**: Integrate the nearby stations table (E-1402 S004) and station comparison panels (E-1402 S005) into the page, wiring the sidebar comparison multiselect to parallel metric cards and overlaid timeline charts.

**Acceptance Criteria**:

- [ ] Nearby stations table renders below the timeline chart section, displaying 10 stations sorted by distance from the selected station (E-1402 S004)
- [ ] Nearby table enrichment queries (`ttc_station_delays()` or `bike_station_activity()`) execute at 30-minute TTL via `query_aggregation()` — these are the same page-level queries used in other pages, not per-station queries
- [ ] When comparison stations are selected via the sidebar multiselect (S001), the page renders comparison panels below the nearby table:
  - Side-by-side metric cards in `st.columns(n)` where n = total selected stations
  - Overlaid timeline chart with `color` encoding by station name
- [ ] When no comparison stations are selected, the comparison section does not render (single-station default)
- [ ] Comparison map updates via `station_focus_map()` multi-station mode (E-1401 S004) when comparison stations are active — all selected stations highlighted with auto-viewport
- [ ] Transition between single-station and comparison mode is seamless — no page reload or manual state reset required
- [ ] All comparison queries use the same `query_filtered()` cache tier as primary station queries — previously-viewed stations serve from 10-minute cache

**Technical Notes**: The comparison integration point bridges E-1401 (multi-station map), E-1402 (comparison panels), and this page composition. When comparison stations exist, the page: (1) passes all selected stations to `station_focus_map()` as a list, (2) issues parallel queries for each comparison station via `query_filtered()`, (3) renders metric columns and overlaid timeline. The nearby table always shows neighbors of the primary station only — it does not change for comparison selections.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Nearby table renders below timeline with distance-ranked stations
- [ ] Selecting comparison stations activates side-by-side panels and overlaid timeline
- [ ] Deselecting returns to single-station layout
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S004: Assemble Full Page Layout with Filter Propagation and Empty-State Handling

**Description**: Assemble all Station Explorer sections into the final page layout — CSS injection, sidebar controls, map, metrics, timeline, nearby table, comparison — with cross-section filter propagation, comprehensive empty-state handling, and page configuration.

**Acceptance Criteria**:

- [ ] `dashboard/pages/5_Station_Explorer.py` composes all sections in a structured layout:
  1. `st.set_page_config(page_title="Station Explorer | Toronto Mobility", layout="wide")` as first Streamlit command
  2. CSS injection from `styles/custom.css` via `st.markdown(unsafe_allow_html=True)`
  3. `st.title("Station Explorer")`
  4. Sidebar: station type toggle, station search selector, date range filter, comparison multiselect (S001)
  5. Section 1: Station map at full width (S002)
  6. Section 2: Station summary metric cards at full width (S002)
  7. Section 3: Detail timeline chart at full width (S002)
  8. Section 4: Nearby stations table at full width (S003)
  9. Section 5: Comparison panels (conditional — only when comparison stations selected) (S003)
- [ ] Date range filter converts `date` objects to integer `date_key` values and passes as `start_date`/`end_date` to all query functions
- [ ] Station type toggle propagates to the station selector, comparison multiselect, and conditional detail rendering
- [ ] Station selection propagates to map centering, nearby computation, detail queries, and metric card rendering
- [ ] When station detail queries return 0 rows, the corresponding section displays `st.info("No data available for this station in the selected period.")` instead of empty or errored components
- [ ] When the reference stations query returns 0 rows for the selected type (impossible under current data but defensive), display `st.error("No stations available.")` and `st.stop()`
- [ ] `streamlit run dashboard/app.py` renders the Station Explorer page with all 5 sections from live Snowflake data
- [ ] No Python `ImportError`, `ModuleNotFoundError`, or Streamlit rendering warnings in the terminal output
- [ ] All Snowflake queries use parameterized execution via `query_filtered()` or `query_aggregation()` — zero string interpolation in SQL values
- [ ] Page layout is visually consistent with dashboard-design.md Section 4.2 Page 5 component hierarchy
- [ ] All chart sections have descriptive headings per dashboard-design skill chart standards
- [ ] Data coverage footer renders at page bottom: `"Data coverage: {min_date} to {max_date}"` from `reference_date_bounds()`

**Technical Notes**: This story integrates all preceding E-1403 stories and all E-1401/E-1402 components. The page follows the same composition pattern as E-1202 and E-1302: CSS injection first, sidebar filters, then sequential section rendering. The Station Explorer adds map-first rendering and conditional panel logic. The `reference_stations()` call (24-hour cache) is the first data access — it provides the station list for all sidebar controls and the coordinate data for map rendering and proximity computation.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] `streamlit run dashboard/app.py` → navigate to Station Explorer → all 5 sections render with live data
- [ ] Station type toggle, station selection, and date range filter propagate to all sections
- [ ] Empty-state handling displays informative messages for zero-result queries
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S005: Validate Performance Targets and Design System Compliance

**Description**: Execute end-to-end performance benchmarking of the Station Explorer page against dashboard-design.md Section 5.6 targets and verify design system compliance against the `dashboard-design` skill review checklist.

**Acceptance Criteria**:

- [ ] Cold start (first page load after app restart): page renders within 5 seconds including reference data fetch, first station query, and map render
- [ ] Warm page navigation (switching to Station Explorer from another page): page renders within 1 second using cached reference data
- [ ] Filter interaction (changing station selection with warm cache): all sections update within 2 seconds
- [ ] Filter interaction (changing date range with warm cache): detail panels update within 2 seconds
- [ ] Map render: `station_focus_map()` renders selected station + 10 nearby markers within 2 seconds
- [ ] Map render (comparison mode): `station_focus_map()` with 3 stations + up to 30 nearby markers renders within 2 seconds
- [ ] No unbounded fact table scans: all `fct_bike_trips` queries verified to include `date_key BETWEEN` partition pruning via SQL inspection
- [ ] Snowflake cost controls: caching prevents redundant queries — toggling between previously-viewed stations incurs zero Snowflake query executions (verified via Snowflake query history or `st.cache_data` hit metrics)
- [ ] Design system checklist:
  - [ ] Custom CSS applied — no default Streamlit theme visible (page background, card styling, typography)
  - [ ] All chart colors from dashboard-design.md Section 6.1 palette (TTC red, Bike green, accent blue, neutral slate, warning amber)
  - [ ] Map uses dark basemap per Section 6.4
  - [ ] Selected station uses blue highlight per Section 6.4
  - [ ] Metric cards use type-appropriate border variant (red for TTC, green for Bike Share)
  - [ ] Inter typography rendered via custom.css font import
  - [ ] Section headings use `st.subheader()` with descriptive titles
  - [ ] No pie charts, rainbow palettes, 3D effects, or decorative elements
- [ ] Page passes the dashboard-design skill review checklist defined in `.claude/skills/dashboard-design/SKILL.md`
- [ ] Accessibility: all chart sections have descriptive headings; metric card labels use uppercase text per `custom.css`; map tooltip text is readable on dark basemap

**Technical Notes**: Performance validation uses browser-side timing (Streamlit's built-in render timestamps in the terminal log) and Snowflake query history (via `INFORMATION_SCHEMA.QUERY_HISTORY` or the Snowflake web UI) to verify cache behavior. Cold start timing begins from `streamlit run` and measures time to first interactive render. Warm navigation timing measures from page click to full section render. Filter interaction timing measures from widget change to section re-render completion.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] All Section 5.6 performance targets verified and documented in PR description
- [ ] Design system checklist fully satisfied with zero violations
- [ ] PR opened with linked issue
- [ ] CI checks green

---

## Exit Criteria

This epic is complete when:

- [ ] `dashboard/pages/5_Station_Explorer.py` replaces the PH-11 stub with a complete interactive page containing 5 sections: map, metrics, timeline, nearby table, and comparison
- [ ] Sidebar controls: station type toggle filters the station selector between 75 TTC subway and 1,009 Bike Share stations; searchable selectbox enables rapid station discovery; date range filter with full data range default; comparison multiselect for up to 2 additional same-type stations
- [ ] Station selection state propagates correctly to map centering, nearby computation, detail queries, metric cards, and timeline charts
- [ ] Date range filter propagates to all detail queries via `date_key` bind parameters
- [ ] Conditional rendering: TTC stations display delay-centric panels; Bike Share stations display trip-centric panels; no irrelevant empty sections
- [ ] Empty-state handling displays informative `st.info()` messages for stations with zero activity in the selected period
- [ ] Cold start under 5 seconds per dashboard-design.md Section 5.6
- [ ] Warm navigation under 1 second per Section 5.6
- [ ] Filter interaction under 2 seconds on warm cache per Section 5.6
- [ ] Map render under 2 seconds for all configurations (single-station and multi-station) per Section 5.6
- [ ] No unbounded fact table scans — all `fct_bike_trips` queries use `date_key BETWEEN` partition pruning
- [ ] Caching prevents redundant Snowflake queries across station selections and page navigations
- [ ] Design system fully applied: custom CSS, palette colors, dark basemap, type-variant metric cards, Inter typography, descriptive headings
- [ ] Page passes the `dashboard-design` skill review checklist
- [ ] No import errors, rendering warnings, or uncaught exceptions during any interaction
- [ ] `streamlit run dashboard/app.py` → Station Explorer page renders all sections from live Snowflake MARTS data
