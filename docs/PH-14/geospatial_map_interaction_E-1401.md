# Station Explorer Geospatial Map & Interaction Layer

| Field        | Value            |
| ------------ | ---------------- |
| Epic ID      | E-1401           |
| Phase        | PH-14            |
| Owner        | @dinesh-git17    |
| Status       | Complete         |
| Dependencies | [E-1201, E-1301] |
| Created      | 2026-02-10       |

---

## Context

The Station Explorer page demands geospatial capabilities absent from the current component library. PH-12 delivered `scatterplot_map()` for multi-point scatter overlays (E-1201) and PH-13 delivered `heatmap_map()` for density visualization (E-1301) — neither supports the single-station focus pattern required by dashboard-design.md Section 4.2 Page 5: a selected station rendered with a blue highlight ring at street-level zoom, surrounded by nearby stations colored by type (TTC red, Bike Share green) per Section 6.4. This pattern requires a multi-layer PyDeck composition, a geographic proximity computation to identify nearby stations from cached reference data, and a station type visual encoding system that differentiates 75 TTC subway stations from 1,009 Bike Share stations across 1,084 total searchable locations.

This epic extends `dashboard/components/maps.py` with a station focus map builder, introduces `dashboard/utils/geo.py` for Haversine distance computation and nearest-station discovery, and establishes the visual encoding system consumed by E-1402 detail panels and E-1403 page composition. All components are reusable — the proximity utility supports any future distance-based analysis, and the multi-layer map pattern applies to any station-centric visualization beyond the Station Explorer.

---

## Scope

### In Scope

- `dashboard/components/maps.py`: Station focus map builder function (`station_focus_map()`) producing a multi-layer `pydeck.Deck` with a highlighted selected station marker (blue, large radius) and nearby stations overlay (type-colored, smaller radius), centered at zoom 14 on the selected station coordinates with dark basemap
- `dashboard/utils/geo.py`: Haversine distance function computing great-circle distance between two lat/lon coordinate pairs in kilometers, and a nearest-N station discovery function that ranks a station DataFrame by proximity to a reference point, returning a distance-annotated result
- Station type visual encoding configuration: color constants for TTC red (`[218, 41, 28, 180]`), Bike Share green (`[67, 176, 42, 180]`), and selected station blue (`[37, 99, 235, 220]`) per dashboard-design.md Section 6.4; display name mapping; tooltip templates per station type
- Multi-station highlight capability supporting up to 3 simultaneously highlighted stations for the station comparison feature per dashboard-design.md stretch goal specification
- All new functions follow the existing component pattern: accept data parameters, return renderable objects (`pydeck.Deck`), with type hints and docstrings

### Out of Scope

- PyDeck 3D layers, arc layers, trip path visualization, or deck.gl animation
- Custom Mapbox tile providers or API key provisioning (Carto DARK basemap sufficient)
- Interactive click-to-select on map markers (Streamlit PyDeck does not support bidirectional events — station selection occurs via sidebar `st.selectbox`)
- Dynamic marker clustering or aggregation at low zoom levels
- Street-level routing or walking distance computation (Haversine computes straight-line distance only)
- Mobile-specific map viewport adjustments or touch gesture handling
- Query functions for station data (E-1402 scope)
- Page-level composition, sidebar controls, or filter integration (E-1403 scope)

---

## Technical Approach

### Architecture Decisions

- **Multi-layer PyDeck composition in a single function** — `station_focus_map()` creates a `pydeck.Deck` with two `ScatterplotLayer` instances: one for the selected station (large blue marker) and one for nearby stations (smaller, type-colored markers). This follows PyDeck's native layer composability rather than creating separate functions per layer. The function accepts a selected station dict (`lat`, `lon`, `name`, `type`) and a nearby stations DataFrame, returning a complete `pydeck.Deck` consistent with the `scatterplot_map()` and `heatmap_map()` return type contract.
- **Zoom level 14 for street-level station context** — Existing maps use zoom 11-12 for city-wide views. The Station Explorer requires street-level context around a single station. Zoom 14 displays approximately a 1 km radius, sufficient to render the selected station and its 10 nearest neighbors with readable marker spacing. The viewport centers on the selected station's coordinates, not the data centroid.
- **Selected station blue highlight per Section 6.4** — Dashboard-design.md specifies "Selected station: Blue highlight ring" using accent blue (#2563EB). The selected station renders as a large circle (radius 150 meters) with high opacity (0.85) over the dark basemap, creating immediate visual focus. Nearby stations render at 60-80 meter radius, visually subordinate to the selected marker.
- **Haversine distance in pure Python** — Computing distances between lat/lon pairs uses the standard Haversine formula with `math` module functions. A pure Python implementation avoids external dependencies (`geopy`, `scipy`, `shapely`). The computation runs on the cached `reference_stations()` DataFrame (1,084 rows) in under 50ms — no Snowflake round-trip required. Results are deterministic for identical inputs and cacheable alongside reference data at 24-hour TTL.
- **Nearest-N discovery from cached reference data** — `find_nearby_stations()` takes a reference lat/lon and the full stations DataFrame, computes Haversine distance to every station, and returns the top N (default 10) sorted by distance ascending, excluding the selected station. All 1,084 station coordinates come from `reference_stations()` cached at 24-hour TTL per E-1102.
- **`dashboard-design` skill enforcement** — TTC red, Bike Share green, and selected blue derive from Section 6.1/6.4. Dark basemap via `pydeck.map_styles.DARK`. No default PyDeck colors or Mapbox light themes. Tooltip HTML follows the existing `_build_tooltip()` pattern from E-1201 maps.

### Integration Points

- **E-1201** — `maps.py` extended with `station_focus_map()` alongside existing `scatterplot_map()` and `heatmap_map()`; shared utility functions (`_to_records`, `_build_tooltip`) reused; basemap and viewport defaults consistent
- **E-1301** — HeatmapLayer remains for Bike Share page; `station_focus_map()` uses ScatterplotLayer for both marker types (precise point positioning required, not density visualization)
- **E-1102** — `reference_stations()` from `queries.py` provides the station coordinate DataFrame consumed by `find_nearby_stations()`; cached at 24-hour TTL via `query_reference_data()`
- **E-1402** — Detail panels consume `find_nearby_stations()` results for the nearby stations table and station comparison; `STATION_COLORS` and `STATION_TYPE_LABELS` inform conditional metric card rendering
- **E-1403** — Page composition integrates `station_focus_map()` as the primary map section; passes sidebar station selection to the map builder

### Repository Areas

- `dashboard/components/maps.py` (modify — add `station_focus_map()` and station encoding constants)
- `dashboard/utils/geo.py` (create — Haversine distance and nearest-N discovery)
- `dashboard/utils/__init__.py` (create if absent — package init)

### Risks

| Risk                                                                                                                                                                       | Likelihood | Impact | Mitigation                                                                                                                                                                                                                                                                         |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Multi-layer PyDeck rendering with selected station marker and 10 nearby station markers produces overlapping tooltips when stations are within 50 meters in dense downtown | Medium     | Medium | Set `pickable=True` only on the nearby stations layer; selected station info displayed via dedicated metric cards (E-1402) rather than map tooltip; increase selected station marker radius to 150m to visually separate it from the nearby cluster                                |
| Haversine straight-line distance misleads users in areas with geographic barriers (rivers, highways, ravines) — nearby stations may not be practically accessible          | Low        | Low    | Label the nearby stations table distance column as "Straight-line distance"; Haversine is the standard metric for station proximity analysis in transit applications; routing distance computation is out of scope per design doc                                                  |
| `dashboard/utils/geo.py` introduces a new package directory that requires `__init__.py` management and may conflict with future utility module additions                   | Low        | Low    | Create `dashboard/utils/__init__.py` as empty package init following the existing `dashboard/data/__init__.py` pattern; document the module purpose in the file docstring; future utilities colocate naturally in the same package                                                 |
| Multi-station highlight (up to 3 stations) produces visual clutter when selected stations are in the same neighborhood, with overlapping blue markers and nearby clouds    | Medium     | Medium | Multi-station mode auto-adjusts viewport via `pydeck.data_utils.compute_view()` to frame all selected stations; reduce marker radius from 150m to 120m in multi-station mode; deduplicate the union of nearby station sets; cap at 3 stations per dashboard-design.md stretch goal |

---

## Stories

| ID   | Story                                                                       | Points | Dependencies | Status |
| ---- | --------------------------------------------------------------------------- | ------ | ------------ | ------ |
| S001 | Build station focus map builder with selection highlight and nearby overlay | 5      | None         | Complete |
| S002 | Build Haversine geographic proximity computation utility                    | 3      | None         | Complete |
| S003 | Build station type visual encoding and tooltip configuration                | 3      | None         | Complete |
| S004 | Extend station focus map for multi-station comparison highlight             | 5      | S001, S002   | Complete |

---

### S001: Build Station Focus Map Builder with Selection Highlight and Nearby Overlay

**Description**: Add a `station_focus_map()` function to `dashboard/components/maps.py` that produces a multi-layer `pydeck.Deck` centered on a selected station with a blue highlight marker and nearby stations rendered as type-colored smaller markers on a dark basemap.

**Acceptance Criteria**:

- [ ] Function `station_focus_map(selected_station: dict, nearby_stations: pd.DataFrame, lat_col: str = "latitude", lon_col: str = "longitude", type_col: str = "station_type", zoom: int = 14) -> pydeck.Deck` exists in `dashboard/components/maps.py`
- [ ] Selected station renders as a ScatterplotLayer with blue fill color `[37, 99, 235, 220]` (#2563EB) and radius 150 meters, positioned at the station's latitude and longitude
- [ ] Nearby stations render as a second ScatterplotLayer with per-row fill color determined by `type_col` value: `TTC_SUBWAY` in `[218, 41, 28, 180]` (#DA291C), `BIKE_SHARE` in `[67, 176, 42, 180]` (#43B02A)
- [ ] Nearby station marker radius ranges from 60-80 meters — closer stations to the selected station render with slightly larger markers for visual proximity encoding
- [ ] Viewport centers on the selected station's latitude and longitude at the specified zoom level (default 14) providing approximately 1 km of surrounding context
- [ ] Map uses Carto DARK basemap (`pydeck.map_styles.DARK`) consistent with existing map builders per dashboard-design.md Section 6.4
- [ ] Nearby stations layer includes tooltip displaying station name, station type, and distance from selected station via `_build_tooltip()`
- [ ] Selected station layer sets `pickable=False` — station info is displayed via dedicated metric cards (E-1402) rather than tooltip
- [ ] Function returns a `pydeck.Deck` object renderable via `st.pydeck_chart()` consistent with `scatterplot_map()` and `heatmap_map()` return types
- [ ] When `nearby_stations` is an empty DataFrame, the function renders only the selected station marker and returns a valid `pydeck.Deck` object without raising an exception
- [ ] All parameters have type hints; public function has docstring describing parameters and return type
- [ ] Existing `scatterplot_map()` and `heatmap_map()` functions remain functionally unchanged

**Technical Notes**: The function constructs two `pydeck.Layer("ScatterplotLayer", ...)` objects. The selected station layer uses `data=[selected_station]` (single-element list) with fixed `get_radius=150`. The nearby stations layer uses `_to_records(nearby_stations)` with `get_fill_color` mapping derived from the `type_col` column. Color mapping applies via a pre-computed `_color` column added to the DataFrame before serialization: `df['_color'] = df[type_col].map({'TTC_SUBWAY': [218,41,28,180], 'BIKE_SHARE': [67,176,42,180]})`. The `get_fill_color='_color'` parameter references this column. Radius variation uses the `distance_km` column from `find_nearby_stations()`: `radius = 80 - (distance_km / max_distance_km) * 20`, clamped to the 60-80 meter range (closer stations = larger radius).

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] `station_focus_map()` renders a centered map with blue highlight and colored nearby markers from sample data
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S002: Build Haversine Geographic Proximity Computation Utility

**Description**: Create `dashboard/utils/geo.py` with a Haversine distance function for great-circle distance between two lat/lon pairs and a nearest-N station discovery function that ranks a station DataFrame by proximity to a reference point.

**Acceptance Criteria**:

- [ ] Module `dashboard/utils/geo.py` exists with `haversine_distance()` and `find_nearby_stations()` functions
- [ ] `haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float` returns distance in kilometers using the Haversine formula with Earth radius 6,371 km
- [ ] `haversine_distance(43.6532, -79.3832, 43.6629, -79.3957)` returns approximately 1.3 km (Toronto City Hall to Union Station sanity check)
- [ ] `find_nearby_stations(ref_lat: float, ref_lon: float, stations_df: pd.DataFrame, lat_col: str = "latitude", lon_col: str = "longitude", n: int = 10, exclude_key: str | None = None, key_col: str = "station_key") -> pd.DataFrame` returns the N nearest stations sorted by distance ascending
- [ ] `find_nearby_stations()` excludes the station matching `exclude_key` from results when provided (prevents the selected station from appearing in its own nearby list)
- [ ] `find_nearby_stations()` adds a `distance_km` column to the returned DataFrame with Haversine distance rounded to 2 decimal places
- [ ] Computation runs on the full 1,084-station reference DataFrame in under 50ms (pure Python with standard library only)
- [ ] `haversine_distance()` returns 0.0 when both coordinate pairs are identical; `find_nearby_stations()` excludes rows with NaN or None latitude/longitude values from results
- [ ] Module uses only Python standard library (`math` module) — no `geopy`, `scipy`, or `shapely` dependencies
- [ ] All functions have type hints and docstrings describing parameters, return types, and algorithmic approach
- [ ] `dashboard/utils/__init__.py` exists as package init (empty or with package docstring)

**Technical Notes**: The Haversine formula: `a = sin²(Δlat/2) + cos(lat1) · cos(lat2) · sin²(Δlon/2)`, `c = 2 · asin(√a)`, `d = R · c` where R = 6,371 km. Latitude and longitude convert from degrees to radians via `math.radians()`. The `find_nearby_stations()` function applies `haversine_distance()` row-wise via `DataFrame.apply()` across 1,084 rows — execution completes in under 10ms. For the `exclude_key` parameter, pass the selected station's `station_key` surrogate hash to filter it from results before sorting and slicing.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] `haversine_distance()` returns correct distances for known Toronto landmark coordinate pairs
- [ ] `find_nearby_stations()` returns 10 nearest stations from a 1,084-row DataFrame in under 50ms
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S003: Build Station Type Visual Encoding and Tooltip Configuration

**Description**: Establish station type visual encoding constants and tooltip template configuration consumed by the station focus map (S001) and detail panels (E-1402), centralizing color, size, label, and tooltip mappings for TTC subway and Bike Share station types in a single importable location.

**Acceptance Criteria**:

- [ ] Color constants defined in `dashboard/components/maps.py`:
  - `STATION_COLORS: dict[str, list[int]] = {"TTC_SUBWAY": [218, 41, 28, 180], "BIKE_SHARE": [67, 176, 42, 180], "SELECTED": [37, 99, 235, 220]}` matching dashboard-design.md Section 6.4 (TTC red, Bike green, accent blue)
- [ ] Display name mapping: `STATION_TYPE_LABELS: dict[str, str] = {"TTC_SUBWAY": "TTC Subway", "BIKE_SHARE": "Bike Share"}` for user-facing text in tooltips, table columns, and filter labels
- [ ] Hex color mapping for non-PyDeck contexts: `STATION_HEX_COLORS: dict[str, str] = {"TTC_SUBWAY": "#DA291C", "BIKE_SHARE": "#43B02A", "SELECTED": "#2563EB"}` for Altair chart color scales and metric card border variants
- [ ] Nearby station tooltip in `station_focus_map()` displays: station name (bold), station type label, and distance from selected station formatted as "{X} km"
- [ ] All color values derive from dashboard-design.md Section 6.1/6.4 palette — zero ad-hoc color choices outside the defined token system
- [ ] Constants are importable by E-1402 detail panel modules and E-1403 page composition without circular dependencies
- [ ] Type hints on all exported constants and configuration mappings

**Technical Notes**: Centralizing visual encoding in `maps.py` prevents color drift across the map builder, detail panels, and page composition. The RGBA arrays serve PyDeck layers (which require `[R, G, B, A]` lists), while hex strings serve Altair charts and CSS styling. The tooltip HTML uses the `_build_tooltip()` helper with column names matching the nearby stations DataFrame columns from `find_nearby_stations()`.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Constants importable from `dashboard.components.maps` without circular dependencies
- [ ] Color values match dashboard-design.md Section 6.1/6.4 exactly
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S004: Extend Station Focus Map for Multi-Station Comparison Highlight

**Description**: Extend `station_focus_map()` to accept up to 3 selected stations simultaneously, rendering each with a blue highlight marker and auto-adjusting the viewport to frame all selected stations and their nearby contexts.

**Acceptance Criteria**:

- [ ] `station_focus_map()` accepts `selected_station` parameter as either a single dict or a list of up to 3 dicts (backward-compatible with single-station input)
- [ ] When multiple stations are selected, each renders as a blue highlight marker with radius 120 meters (reduced from single-station 150m to prevent visual overlap)
- [ ] When multiple stations are selected, viewport auto-computes using `pydeck.data_utils.compute_view()` to frame all selected stations with padding, rather than centering on a single station's coordinates
- [ ] Nearby stations overlay in multi-station mode displays the union of nearby stations for all selected stations, with duplicates removed by `station_key` (a station near two selected stations appears once)
- [ ] Function raises `ValueError` when `selected_station` list contains more than 3 elements, enforcing the dashboard-design.md comparison limit
- [ ] Single-station input (dict, not list) behavior remains identical to the S001 implementation — full backward compatibility for existing call sites
- [ ] All parameters have type hints; docstring updated to describe both single-station and multi-station behavior
- [ ] Map renders within 2 seconds per dashboard-design.md Section 5.6 map render target for 3 selected stations with up to 30 combined nearby station markers

**Technical Notes**: Multi-station mode creates one ScatterplotLayer with up to 3 blue highlight points and one ScatterplotLayer with the deduplicated union of nearby stations. Deduplication: concatenate the 3 nearby DataFrames, `drop_duplicates(subset='station_key')`. The `pydeck.data_utils.compute_view()` function accepts a list of `[lon, lat]` coordinates and returns a `ViewState` with appropriate zoom and center. For 3 stations spread across Toronto (max ~30 km separation), expect zoom 11-12. For 3 stations in the same neighborhood (within 2 km), expect zoom 13-14. Type checking on input: `if isinstance(selected_station, dict): selected_station = [selected_station]`.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] `station_focus_map()` renders 3 highlighted stations with auto-viewport and deduplicated nearby overlay from sample data
- [ ] Single-station rendering produces identical output to S001 baseline
- [ ] PR opened with linked issue
- [ ] CI checks green

---

## Exit Criteria

This epic is complete when:

- [ ] `dashboard/components/maps.py` contains `station_focus_map()` producing a multi-layer PyDeck Deck with blue highlight on selected station(s) and type-colored nearby stations overlay on dark basemap
- [ ] `dashboard/utils/geo.py` contains `haversine_distance()` and `find_nearby_stations()` computing geographic proximity from cached station reference data without Snowflake round-trip
- [ ] Station type visual encoding constants (`STATION_COLORS`, `STATION_TYPE_LABELS`, `STATION_HEX_COLORS`) are centralized in `maps.py` and importable by downstream epics
- [ ] Single-station mode renders a centered map at zoom 14 with 1 blue highlight marker and up to 10 type-colored nearby markers
- [ ] Multi-station mode renders up to 3 blue highlight markers with auto-computed viewport and deduplicated nearby stations overlay
- [ ] All new functions have type hints and docstrings
- [ ] Existing `scatterplot_map()` and `heatmap_map()` functions remain functionally unchanged
- [ ] All visual encoding derives from dashboard-design.md Section 6.1/6.4 palette — no default PyDeck colors or ad-hoc choices
- [ ] Haversine distance computation runs on 1,084 stations in under 50ms
- [ ] Map renders within 2 seconds per dashboard-design.md Section 5.6 for all supported configurations (single-station and multi-station)
- [ ] No import errors, circular dependencies, or rendering warnings
