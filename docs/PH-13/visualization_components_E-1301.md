# Bike Share & Weather Visualization Components

| Field        | Value            |
| ------------ | ---------------- |
| Epic ID      | E-1301           |
| Phase        | PH-13            |
| Owner        | @dinesh-git17    |
| Status       | Complete         |
| Dependencies | [E-1201, E-1103] |
| Created      | 2026-02-10       |

---

## Context

PH-12 established three advanced visualization components (PyDeck ScatterplotLayer, Plotly treemap, Altair heatmap) in E-1201, sufficient for the TTC Deep Dive page. PH-13 introduces two new pages — Bike Share Deep Dive and Weather Impact — that require four visualization types absent from the current component library: a PyDeck HeatmapLayer for geographic density visualization over 1,009 Bike Share stations, an Altair scatter plot for two-variable correlation analysis (temperature vs. trips, precipitation vs. trips), an Altair area chart for temporal growth curves, and explicit stacking and color control on the existing bar chart function for composition breakdowns. These components are reusable infrastructure — PH-14 may extend the scatter plot for station-level comparisons, and the HeatmapLayer supports any future point-density visualization.

This epic extends `dashboard/components/maps.py` with one new builder function and `dashboard/components/charts.py` with two new builder functions and one parameter extension. No new runtime dependencies are required — PyDeck and Altair are already installed from E-1201 and E-1103 respectively.

---

## Scope

### In Scope

- `dashboard/components/maps.py`: PyDeck HeatmapLayer builder function with configurable weight encoding, color gradient, radius, opacity, viewport centering, and dark basemap per dashboard-design.md Section 6.4
- Extension of `dashboard/components/charts.py`: Altair scatter plot builder function using `mark_circle()` with quantitative x/y encoding, optional color-coded categorical grouping, configurable opacity, and tooltip hover
- Extension of `dashboard/components/charts.py`: Altair area chart builder function using `mark_area()` with temporal or ordinal x-axis, quantitative y-axis, gradient fill, and optional multi-series support
- Extension of `dashboard/components/charts.py`: Add `stack` and `mark_color` parameters to existing `bar_chart()` function for deterministic stacking control and explicit fill color override
- All new functions follow the existing component signature pattern: accept a `pd.DataFrame`, return a renderable object (`pydeck.Deck` or `alt.Chart`)

### Out of Scope

- PyDeck 3D layers, arc layers, or view state animation (beyond PH-13 scope)
- Plotly scatter plots (Altair provides sufficient capability for daily-granularity scatter data)
- Custom map tile providers or Mapbox API key provisioning (Carto basemaps are sufficient)
- Interactive click-to-filter on heatmap regions (standard Streamlit PyDeck does not support bidirectional events)
- Altair `mark_boxplot()` or histogram builders (no PH-13 page requires these)
- Mobile-specific chart fallbacks or responsive breakpoints (PH-14 scope)

---

## Technical Approach

### Architecture Decisions

- **HeatmapLayer in `maps.py` alongside ScatterplotLayer** — Both are geographic PyDeck visualizations sharing the same rendering pipeline (`st.pydeck_chart`), basemap configuration, and viewport management. Colocation in `maps.py` enables shared utility functions (`_compute_radius_column`, `_to_records`, `_build_tooltip`) and consistent viewport defaults. The function returns a `pydeck.Deck` object identical to `scatterplot_map()`.
- **Green color gradient for HeatmapLayer** — Dashboard-design.md Section 6.4 specifies "Bike stations: Green gradient by trip volume." The default `color_range` uses 4 stops from light green (`#ECFCEB`) to Bike Share green (`#43B02A`) to dark green (`#166534`). This contrasts with the TTC red used in ScatterplotLayer, providing immediate visual mode differentiation.
- **Altair scatter plot via `mark_circle()` with `opacity`** — `mark_circle()` with partial opacity handles overlapping points at daily granularity (1,827 data points). Optional `color` parameter enables categorical grouping (e.g., weather_condition) using the project palette. Tooltip encoding shows exact x/y values on hover per dashboard-design skill chart formatting rules.
- **Area chart via `mark_area()` with line overlay** — Altair's `mark_area(opacity=0.3)` combined with `mark_line()` overlay produces a professional area chart with visible trend line and subtle fill. The gradient fill style matches the sparkline component from E-1103. The function follows the same `(data, x, y, color, title)` parameter convention as `line_chart()`.
- **Explicit `stack` and `mark_color` on `bar_chart()`** — Altair stacks bars by default when a `color` encoding is present. Adding `stack: bool | None = True` gives page authors deterministic control. Adding `mark_color: str | None = None` enables single-series fill color overrides (e.g., Bike Share green for bike trip bars, TTC red for delay bars) without requiring a color-encoding column. These additions maintain full backwards compatibility.
- **`dashboard-design` skill enforcement** — All color selections derive from project palette tokens. HeatmapLayer uses Bike Share green gradient. Scatter plots use `accent-primary` (#2563EB) for primary series and `neutral-data` (#737373) for secondary. Area chart uses `accent-primary` fill. All Altair charts inherit the registered `toronto_mobility` theme. No default library colors appear in any new component.

### Integration Points

- **E-1201** — `maps.py` extended with `heatmap_map()` alongside existing `scatterplot_map()`; shared utility functions reused
- **E-1103** — `charts.py` extended with `scatter_plot()` and `area_chart()`; existing `bar_chart()` modified with `stack` and `mark_color` parameters; `toronto_mobility` Altair theme auto-applies to all new chart types
- **E-1302** — Bike Share Deep Dive page consumes `heatmap_map()` for station activity visualization, `area_chart()` for yearly growth, and `bar_chart(stack=True)` for member vs casual composition
- **E-1303** — Weather Impact page consumes `scatter_plot()` for temperature and precipitation correlations, and `bar_chart(mark_color=...)` for per-condition bar coloring
- **PH-14** — Station Explorer page may reuse `scatter_plot()` for station-level metric comparisons

### Repository Areas

- `dashboard/components/maps.py` (modify — add `heatmap_map()`)
- `dashboard/components/charts.py` (modify — add `scatter_plot()`, `area_chart()`, extend `bar_chart()`)

### Risks

| Risk                                                                                                                                                      | Likelihood | Impact | Mitigation                                                                                                                                                                                                                                                  |
| --------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| PyDeck HeatmapLayer WebGL rendering fails on older browsers or Streamlit Community Cloud environments due to GPU shader compilation errors                | Low        | High   | HeatmapLayer uses the same WebGL pipeline as ScatterplotLayer (validated in E-1202); fallback: replace with ScatterplotLayer using small uniform points and green color for visual density approximation                                                    |
| Altair scatter plot with 1,827 daily data points renders slowly or triggers the default 5,000-row data transformer warning on future dataset expansion    | Low        | Low    | 1,827 rows is well under Altair's 5,000-row default limit; scatter circle marks are lightweight; test rendering on a standard laptop before merge                                                                                                           |
| Area chart gradient fill renders differently across browser engines (Safari vs. Chrome), producing inconsistent opacity or clipped fill boundaries        | Low        | Low    | Use solid `opacity=0.3` on `mark_area()` instead of CSS gradients; Altair renders via SVG/Canvas with cross-browser consistency; test in Chrome and Safari                                                                                                  |
| Adding `stack` and `mark_color` parameters to `bar_chart()` changes default behavior for PH-12 TTC mode comparison or Overview charts, causing regression | Medium     | Medium | Default `stack=True` matches Altair's existing default; `mark_color=None` preserves theme default; TTC mode comparison uses single-category x-axis where stacking is irrelevant; verify E-1202 and E-1104 pages render identically after parameter addition |

---

## Stories

| ID   | Story                                                 | Points | Dependencies | Status |
| ---- | ----------------------------------------------------- | ------ | ------------ | ------ |
| S001 | Build PyDeck HeatmapLayer map builder component       | 5      | None         | Complete |
| S002 | Build Altair scatter plot builder function            | 5      | None         | Complete |
| S003 | Build Altair area chart builder function              | 3      | None         | Complete |
| S004 | Extend bar_chart with stack and mark_color parameters | 2      | None         | Complete |

---

### S001: Build PyDeck HeatmapLayer Map Builder Component

**Description**: Add a `heatmap_map()` function to `dashboard/components/maps.py` that produces a `pydeck.Deck` object rendering geographic point-density data with configurable weight encoding, green color gradient, radius, and a dark basemap.

**Acceptance Criteria**:

- [ ] Function `heatmap_map(data: pd.DataFrame, lat_col: str, lon_col: str, weight_col: str | None = None, radius: int = 200, color_range: list[list[int]] | None = None, opacity: float = 0.8, zoom: int = 11, center_lat: float | None = None, center_lon: float | None = None) -> pydeck.Deck` exists in `dashboard/components/maps.py`
- [ ] Default map style is Carto DARK (`pydeck.map_styles.DARK`) consistent with `scatterplot_map()` per dashboard-design.md Section 6.4
- [ ] `color_range` parameter defaults to a Bike Share green gradient: `[[236, 252, 235], [134, 239, 172], [67, 176, 42], [22, 101, 52]]` (light green to dark green)
- [ ] `weight_col` parameter controls the contribution of each point to the heat intensity; when `None`, all points contribute equally (uniform weight of 1)
- [ ] `radius` parameter controls the influence radius of each point in meters (default 200); larger values produce broader, softer heat patches
- [ ] `opacity` parameter controls the overall layer opacity (default 0.8); range 0.0 to 1.0
- [ ] Viewport auto-centers on the mean latitude and longitude of the input data when `center_lat` and `center_lon` are `None`
- [ ] HeatmapLayer uses `aggregation="SUM"` for weight aggregation when points overlap at identical coordinates
- [ ] Function renders without error when called with a DataFrame containing 1,009 rows (Bike Share station count) with `latitude`, `longitude`, and `trip_count` columns
- [ ] Function reuses `_to_records()` utility from `maps.py` for JSON-safe DataFrame serialization
- [ ] All functions have type hints on parameters and return values
- [ ] All public functions have docstrings describing parameters and return type
- [ ] Existing `scatterplot_map()` function remains functionally unchanged

**Technical Notes**: PyDeck HeatmapLayer is accessed via `pydeck.Layer("HeatmapLayer", ...)` with the `data` parameter accepting a list of dictionaries. The `colorRange` parameter accepts the color gradient array. The `getPosition` parameter uses `[lon_col, lat_col]` syntax. The `getWeight` parameter references the weight column name. The layer handles density computation on the GPU — no pre-aggregation required. For Toronto's Bike Share network, `radius=200` meters separates downtown station clusters while maintaining readable density gradients.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] `heatmap_map()` renders a density map with sample data containing 1,009 lat/lon/weight rows
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S002: Build Altair Scatter Plot Builder Function

**Description**: Add a `scatter_plot()` function to `dashboard/components/charts.py` that produces an `alt.Chart` rendering a two-variable correlation using `mark_circle()` with quantitative axes, optional categorical color encoding, and tooltip hover.

**Acceptance Criteria**:

- [ ] Function `scatter_plot(data: pd.DataFrame, x: str, y: str, color: str | None = None, size: int = 60, opacity: float = 0.6, title: str = "", x_title: str | None = None, y_title: str | None = None) -> alt.Chart` exists in `dashboard/components/charts.py`
- [ ] Uses `mark_circle(size=size, opacity=opacity)` for point rendering
- [ ] `x` and `y` parameters accept column names rendered as quantitative axes with explicit axis titles via `x_title` and `y_title` (defaults to column name when `None`)
- [ ] `color` parameter accepts an optional nominal column name for categorical point grouping (e.g., `weather_condition`); when `None`, all points use `accent-primary` (#2563EB)
- [ ] When `color` is provided, the color scale uses explicit project palette values for up to 3 categories per dashboard-design skill chart color discipline
- [ ] Chart includes a tooltip encoding displaying the x value, y value, and color value (if present) on hover
- [ ] Chart inherits the registered `toronto_mobility` Altair theme (Inter font, transparent view stroke)
- [ ] Chart uses `width="container"` for responsive layout within Streamlit columns
- [ ] Chart title renders via `.properties(title=title)` when `title` is non-empty
- [ ] Function renders without error when called with a DataFrame containing 1,827 rows (daily granularity) with `mean_temp_c` and `total_bike_trips` columns
- [ ] All functions have type hints and docstrings
- [ ] Existing chart functions (`bar_chart`, `line_chart`, `sparkline`, `heatmap`, `treemap`) remain unchanged

**Technical Notes**: Altair's `mark_circle` is the standard scatter plot mark. The `size` parameter controls point area in square pixels (60 is moderate for 1,827 points). The `opacity` parameter enables visual detection of overlapping points. For categorical color encoding, use `alt.Color('col:N', scale=alt.Scale(domain=[...], range=[...]))` with explicit palette values. Quantitative axes use `alt.X('col:Q', axis=alt.Axis(title=...))` and `alt.Y('col:Q', axis=alt.Axis(title=...))`.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] `scatter_plot()` renders a correlation plot with sample data containing temperature and trip count columns
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S003: Build Altair Area Chart Builder Function

**Description**: Add an `area_chart()` function to `dashboard/components/charts.py` that produces an `alt.Chart` rendering a filled area below a trend line using `mark_area()` with a line overlay for temporal growth visualization.

**Acceptance Criteria**:

- [ ] Function `area_chart(data: pd.DataFrame, x: str, y: str, color: str | None = None, title: str = "", opacity: float = 0.3, x_sort: list[str] | None = None) -> alt.Chart` exists in `dashboard/components/charts.py`
- [ ] Renders as a layered composition: `mark_area(opacity=opacity)` + `mark_line()` overlay for the visible trend line above the fill
- [ ] `x` parameter accepts a column name rendered as an ordinal axis with optional explicit sort via `x_sort`
- [ ] `y` parameter accepts a quantitative column name for the area height
- [ ] `color` parameter enables multi-series area charts with stacked areas when provided; when `None`, uses `accent-primary` (#2563EB) fill with matching line color
- [ ] Fill uses solid `opacity` (default 0.3) for cross-browser consistency
- [ ] Line overlay uses full opacity (1.0) for clear trend visibility
- [ ] Chart includes a tooltip encoding displaying x and y values on hover
- [ ] Chart inherits the registered `toronto_mobility` Altair theme
- [ ] Chart uses `width="container"` for responsive layout
- [ ] Chart title renders via `.properties(title=title)` when `title` is non-empty
- [ ] Function renders without error when called with a DataFrame containing 5 rows (yearly granularity) with `year` and `total_trips` columns
- [ ] All functions have type hints and docstrings
- [ ] Existing chart functions remain unchanged

**Technical Notes**: The layered composition uses `alt.layer(area, line)` where `area = base.mark_area(opacity=opacity)` and `line = base.mark_line()`. Both layers share the same base encoding to ensure alignment. When `color` is provided for multi-series, Altair's default stacking applies to the area marks. For single-series, the fill color matches `accent-primary` with reduced opacity.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] `area_chart()` renders a filled area chart with sample data containing yearly totals
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S004: Extend bar_chart with Stack and Mark Color Parameters

**Description**: Extend the existing `bar_chart()` function in `dashboard/components/charts.py` with `stack` and `mark_color` parameters for deterministic stacking control and explicit single-series fill color override.

**Acceptance Criteria**:

- [ ] Function signature updated to `bar_chart(data: pd.DataFrame, x: str, y: str, color: str | None = None, horizontal: bool = False, title: str = "", stack: bool | None = True, mark_color: str | None = None) -> alt.Chart`
- [ ] When `stack=True` and `color` is provided, bars are stacked via `alt.Y(stack=True)` or `alt.X(stack=True)` depending on orientation
- [ ] When `stack=False` and `color` is provided, bars render side-by-side (grouped) via `xOffset`/`yOffset` encoding
- [ ] When `stack=None`, Altair default stacking behavior applies
- [ ] When `color` is `None`, the `stack` parameter has no effect
- [ ] `mark_color` parameter: when provided, sets the fill color for all bars via `mark_bar(color=mark_color)`; when `None`, uses Altair theme default
- [ ] `mark_color` is applied only when `color` encoding is `None` (single-series); when `color` encoding is provided, per-series colors take precedence over `mark_color`
- [ ] Existing calls to `bar_chart()` without the new parameters produce identical output (backwards compatible)
- [ ] E-1202 TTC Deep Dive page renders identically after this change
- [ ] E-1104 Overview page renders identically after this change
- [ ] All functions have updated type hints and docstrings

**Technical Notes**: Altair stacking is controlled via the `stack` parameter on the encoding channel. The `True` default matches Altair's existing default when a color encoding is present. For grouped bars with `stack=False`, use `alt.XOffset('color_col:N')` for side-by-side placement. The `mark_color` parameter passes directly to `mark_bar(color=...)`, overriding the theme's default mark color for single-series charts. This enables the Weather Impact page to render Bike Share green bars and TTC red bars without requiring a color-encoding column.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] `bar_chart(stack=True)` produces stacked bars with sample data containing 2 categories
- [ ] `bar_chart(mark_color="#43B02A")` produces green-filled bars
- [ ] Existing pages render unchanged
- [ ] PR opened with linked issue
- [ ] CI checks green

---

## Exit Criteria

This epic is complete when:

- [ ] `dashboard/components/maps.py` contains `heatmap_map()` producing PyDeck HeatmapLayer density maps with configurable weight encoding, green color gradient, and dark basemap
- [ ] `dashboard/components/charts.py` contains `scatter_plot()` producing Altair scatter plots with quantitative axes, optional categorical color encoding, and tooltip hover
- [ ] `dashboard/components/charts.py` contains `area_chart()` producing Altair area charts with filled area, line overlay, gradient opacity, and optional multi-series support
- [ ] `dashboard/components/charts.py` `bar_chart()` accepts `stack` and `mark_color` parameters with full backwards compatibility
- [ ] All 4 new/modified builder functions render without error when called with representative sample DataFrames
- [ ] All functions have type hints and docstrings
- [ ] Existing E-1103 and E-1201 components (`line_chart`, `sparkline`, `heatmap`, `treemap`, `scatterplot_map`, `render_metric_row`, filter functions) remain functionally unchanged
- [ ] E-1202 TTC Deep Dive page and E-1104 Overview page render identically after changes
- [ ] All visual output conforms to dashboard-design skill standards: project color palette, Inter typography, no default framework styling
