# Advanced Visualization Components

| Field        | Value         |
| ------------ | ------------- |
| Epic ID      | E-1201        |
| Phase        | PH-12         |
| Owner        | @dinesh-git17 |
| Status       | Complete      |
| Dependencies | [E-1103]      |
| Created      | 2026-02-10    |

---

## Context

PH-11 established an Altair-based component library (E-1103) with bar charts, line charts, and sparklines sufficient for the Overview landing page. The TTC Deep Dive page requires three visualization types absent from that library: a PyDeck ScatterplotLayer map for geographic station delay analysis (75 subway stations with delay-proportional point sizing), a Plotly treemap for hierarchical delay cause decomposition (8 categories containing ~40-60 descriptions), and an Altair heatmap for temporal delay pattern analysis (24 hours x 7 days-of-week). These components are reusable infrastructure — PH-13 extends `maps.py` with a HeatmapLayer for Bike Share station activity, and PH-14 reuses ScatterplotLayer for the Station Explorer centered map view.

This epic produces three new builder functions and adds two runtime dependencies (`pydeck`, `plotly`) to the dashboard manifest. It extends the existing component architecture without modifying the E-1103 chart builders, filter components, or CSS design system.

---

## Scope

### In Scope

- `dashboard/components/maps.py`: PyDeck ScatterplotLayer builder function with configurable color, size encoding, tooltip columns, viewport centering, and dark basemap per dashboard-design.md Section 6.4
- Extension of `dashboard/components/charts.py`: Plotly treemap builder function for hierarchical category breakdowns with project color scale
- Extension of `dashboard/components/charts.py`: Altair heatmap builder function using `mark_rect()` with ordinal x/y encoding and sequential color scale
- `dashboard/requirements.txt`: Add `pydeck` and `plotly` pinned dependencies
- All new functions follow the existing charts.py signature pattern: accept a `pd.DataFrame`, return a renderable object (`pydeck.Deck`, `plotly.graph_objects.Figure`, or `alt.Chart`)

### Out of Scope

- PyDeck HeatmapLayer builder (PH-13 scope for Bike Share station activity maps)
- Mapbox API key provisioning or custom map tile configuration (PyDeck includes free Carto basemaps)
- Mobile-specific map fallbacks or alternative renderings (PH-14 scope)
- Interactive click-to-filter on map points (page-level integration in E-1202)
- 3D deck.gl layers, animations, view state transitions, or arc layers
- Plotly subplots, sunburst charts, or non-treemap hierarchical visualizations
- Custom Plotly theme registration (inline layout configuration sufficient for single chart type)

---

## Technical Approach

### Architecture Decisions

- **Separate `maps.py` module for PyDeck builders** — Dashboard-design.md Section 5.2 specifies `components/maps.py` as a distinct module. PyDeck has a fundamentally different rendering API from Altair: it produces `pydeck.Deck` objects rendered via `st.pydeck_chart()`, not Vega-Lite specs rendered via `st.altair_chart()`. Isolating map builders in their own module prevents coupling chart and map concerns and enables PH-13/PH-14 to extend the module independently.
- **Plotly treemap colocated in `charts.py`** — Treemaps are charts, not maps. Despite using Plotly instead of Altair for rendering, treemaps belong in the chart builder module for discoverability. The function returns a `plotly.graph_objects.Figure` rendered via `st.plotly_chart(fig, use_container_width=True)`. Mixing Altair and Plotly in one module is acceptable because each function is self-contained with no shared state.
- **Altair heatmap via `mark_rect()` with ordinal encoding** — Altair's `mark_rect` with ordinal x/y axes and quantitative color encoding produces publication-quality heatmaps natively. No third-party heatmap library required. The heatmap function follows the same parameter convention as existing `bar_chart()` and `line_chart()` functions: `(data, x, y, color, title)` with optional sort orders.
- **Carto DARK basemap for PyDeck** — PyDeck includes free Carto basemaps accessible via `pydeck.map_styles.DARK`. No Mapbox API key required for development or Streamlit Community Cloud deployment. Dashboard-design.md Section 6.4 specifies "Dark base map (Mapbox Dark)" — Carto DARK provides equivalent visual treatment with zero credential management.
- **`dashboard-design` skill enforcement** — All color selections, typography, and visual treatments in these components conform to the dashboard-design skill standards. Map point colors use project palette tokens (`#DA291C` for TTC red gradient). Treemap color scales derive from project red (`#FEE2E2` to `#DA291C`). Heatmap inherits the registered `toronto_mobility` Altair theme.

### Integration Points

- **E-1103** — `charts.py` extended with `treemap()` and `heatmap()` functions; existing `bar_chart()`, `line_chart()`, and `sparkline()` remain unchanged. The `toronto_mobility` Altair theme auto-applies to the heatmap. The treemap uses Plotly (no Altair theme inheritance) with explicit Inter font and project colors.
- **E-1202** — TTC Deep Dive page consumes `scatterplot_map()` for station delay map, `treemap()` for delay cause breakdown, and `heatmap()` for temporal patterns
- **PH-13 E-1301+** — Bike Share page extends `maps.py` with `heatmap_map()` for HeatmapLayer over 1,009 Bike Share stations
- **PH-14** — Station Explorer page reuses `scatterplot_map()` for single-station centered view with nearby stations overlay

### Repository Areas

- `dashboard/components/maps.py` (new)
- `dashboard/components/charts.py` (modify — add `treemap()` and `heatmap()`)
- `dashboard/requirements.txt` (modify — add `pydeck` and `plotly`)

### Risks

| Risk                                                                                                                                             | Likelihood | Impact | Mitigation                                                                                                                                                                                                                                        |
| ------------------------------------------------------------------------------------------------------------------------------------------------ | ---------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| PyDeck rendering fails on Streamlit Community Cloud due to WebGL restrictions or missing basemap tiles, producing a blank map viewport           | Low        | High   | Carto basemaps are CDN-hosted and require no API key; test PyDeck rendering on Streamlit Community Cloud during E-1202 integration; fallback option: replace `st.pydeck_chart` with `st.map()` (basic scatter, no sizing) if WebGL is unavailable |
| Plotly treemap CSS conflicts with Streamlit's built-in Plotly integration, producing misaligned tooltips, cropped labels, or scrollbar artifacts | Medium     | Medium | Use `st.plotly_chart(fig, use_container_width=True)` for container-aware sizing; set explicit `margin=dict(t=40, l=10, r=10, b=10)` in Plotly layout to prevent label clipping; test in both full-width and `st.columns` layouts                  |
| Altair heatmap with 168 cells (24 hours x 7 days) and tooltip interactivity renders slowly on low-powered devices or older browsers              | Low        | Low    | 168 rect marks are well within Altair/Vega-Lite performance limits (designed for thousands of marks); set `tooltip` encoding for hover details without interactive selection; chart size remains under Altair's 5,000-row default data threshold  |
| Version conflicts between `pydeck` and `streamlit` dependencies due to shared `pyarrow` or `protobuf` transitive dependency version mismatches   | Medium     | High   | Pin compatible version ranges: `pydeck>=0.9.0,<1.0.0` and `plotly>=5.18.0,<6.0.0`; validate `pip install -r dashboard/requirements.txt` resolves without conflicts in a clean Python 3.12 virtual environment before merge                        |

---

## Stories

| ID   | Story                                                        | Points | Dependencies | Status |
| ---- | ------------------------------------------------------------ | ------ | ------------ | ------ |
| S001 | Add PyDeck and Plotly dependencies to dashboard requirements | 2      | None         | Draft  |
| S002 | Build PyDeck ScatterplotLayer map builder component          | 5      | S001         | Draft  |
| S003 | Build Plotly treemap builder component                       | 5      | S001         | Draft  |
| S004 | Build Altair heatmap builder function                        | 3      | None         | Draft  |

---

### S001: Add PyDeck and Plotly Dependencies to Dashboard Requirements

**Description**: Add `pydeck` and `plotly` runtime dependencies to `dashboard/requirements.txt` with pinned version ranges compatible with the existing Streamlit and pandas dependency surface.

**Acceptance Criteria**:

- [ ] `dashboard/requirements.txt` includes `pydeck>=0.9.0,<1.0.0`
- [ ] `dashboard/requirements.txt` includes `plotly>=5.18.0,<6.0.0`
- [ ] Existing dependencies (`streamlit`, `altair`, `snowflake-connector-python`, `pandas`) remain unchanged
- [ ] `pip install -r dashboard/requirements.txt` completes without dependency resolution errors in a clean Python 3.12 virtual environment
- [ ] `python -c "import pydeck; import plotly; print('OK')"` executes without `ImportError`
- [ ] No version conflicts between `pydeck`, `plotly`, and `streamlit` transitive dependencies (`pyarrow`, `protobuf`, `numpy`)

**Technical Notes**: PyDeck 0.9+ supports Carto basemaps without a Mapbox API key. Plotly 5.18+ includes the `treemap` trace type with `textinfo` formatting. Both libraries are compatible with Streamlit 1.31+ per their respective compatibility matrices. The version ceiling (`<1.0.0`, `<6.0.0`) prevents major-version breaking changes during development.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] `pip install` succeeds in clean environment
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S002: Build PyDeck ScatterplotLayer Map Builder Component

**Description**: Create `dashboard/components/maps.py` with a `scatterplot_map()` function that produces a `pydeck.Deck` object rendering geographic point data with configurable size encoding, color, tooltips, and a dark basemap.

**Acceptance Criteria**:

- [ ] File `dashboard/components/maps.py` exists
- [ ] Function `scatterplot_map(data: pd.DataFrame, lat_col: str, lon_col: str, size_col: str | None = None, color: list[int] | None = None, tooltip_cols: list[str] | None = None, zoom: int = 11, center_lat: float | None = None, center_lon: float | None = None) -> pydeck.Deck` returns a valid `pydeck.Deck` object
- [ ] Default map style is Carto DARK (`pydeck.map_styles.DARK`) per dashboard-design.md Section 6.4
- [ ] `color` parameter defaults to TTC red `[218, 41, 28, 180]` (RGBA with 70% opacity) when `None`
- [ ] `size_col` parameter controls point radius proportional to the column's values; when `None`, all points render at a fixed radius of 100 meters
- [ ] Point radius normalization maps the `size_col` range to a configurable min/max pixel range (default 50-500) for visual differentiation
- [ ] Viewport auto-centers on the mean latitude and longitude of the input data when `center_lat` and `center_lon` are `None`
- [ ] Tooltip displays column values specified in `tooltip_cols` via PyDeck's `pydeck.Tooltip` with `html` template
- [ ] Function renders without error when called with a DataFrame containing 75 rows (subway station count) with `latitude`, `longitude`, and `total_delay_minutes` columns
- [ ] All functions have type hints on parameters and return values
- [ ] All public functions have docstrings describing parameters and return type

**Technical Notes**: PyDeck ScatterplotLayer expects columns named `lat` and `lon` by default. The builder function should rename the DataFrame columns internally to match PyDeck's expectations or use the `get_position` parameter with `[lon_col, lat_col]` syntax. The `pydeck.Deck` object is rendered in Streamlit via `st.pydeck_chart(deck)`. The `initial_view_state` should use `pydeck.ViewState` with the computed or provided center coordinates.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] `scatterplot_map()` renders a map with sample data containing lat/lon/size columns
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S003: Build Plotly Treemap Builder Component

**Description**: Add a `treemap()` function to `dashboard/components/charts.py` that produces a `plotly.graph_objects.Figure` rendering hierarchical data with configurable path levels, value sizing, color encoding, and project-aligned typography.

**Acceptance Criteria**:

- [ ] Function `treemap(data: pd.DataFrame, path_cols: list[str], value_col: str, color_col: str | None = None, title: str = "", color_scale: list[list] | None = None) -> go.Figure` exists in `dashboard/components/charts.py`
- [ ] `path_cols` accepts a list of column names defining the hierarchy levels (e.g., `['delay_category', 'delay_description']`), rendered as nested treemap tiles from outermost to innermost
- [ ] `value_col` determines tile area proportional to the column's numeric values (e.g., `incident_count`)
- [ ] `color_col` determines tile color intensity via a sequential color scale; when `None`, tiles use uniform TTC red `#DA291C`
- [ ] `color_scale` defaults to a project-aligned red sequential palette: `[[0, '#FEE2E2'], [0.5, '#F87171'], [1, '#DA291C']]` (light pink to TTC red)
- [ ] Layout sets `font_family="Inter"` for all text elements (labels, hover, annotations)
- [ ] Layout sets `paper_bgcolor="rgba(0,0,0,0)"` and `plot_bgcolor="rgba(0,0,0,0)"` for transparent backgrounds that blend with the dashboard off-white
- [ ] Layout sets `margin=dict(t=40, l=10, r=10, b=10)` to prevent label clipping in container layouts
- [ ] Treemap displays `textinfo="label+percent parent"` for proportional context within parent tiles
- [ ] Function renders without error when called with a DataFrame containing 50 rows with `delay_category`, `delay_description`, and `incident_count` columns
- [ ] All functions have type hints and docstrings
- [ ] Existing `bar_chart()`, `line_chart()`, and `sparkline()` functions remain unchanged

**Technical Notes**: Plotly treemaps use `px.treemap()` or `go.Treemap()`. The `px.treemap(data, path=path_cols, values=value_col, color=color_col)` API provides the most concise construction. The figure is rendered in Streamlit via `st.plotly_chart(fig, use_container_width=True)`. The `color_continuous_scale` parameter on `px.treemap` accepts the color scale list directly.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] `treemap()` renders with sample hierarchical data without Plotly validation errors
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S004: Build Altair Heatmap Builder Function

**Description**: Add a `heatmap()` function to `dashboard/components/charts.py` that produces an `alt.Chart` rendering a two-dimensional matrix of colored cells using `mark_rect()` with ordinal axes and sequential color encoding.

**Acceptance Criteria**:

- [ ] Function `heatmap(data: pd.DataFrame, x: str, y: str, color: str, title: str = "", x_sort: list[str] | None = None, y_sort: list[str] | None = None) -> alt.Chart` exists in `dashboard/components/charts.py`
- [ ] Uses `mark_rect()` for cell rendering (not `mark_circle` or `mark_square`)
- [ ] `x` and `y` parameters accept column names rendered as ordinal axes
- [ ] `color` parameter accepts a quantitative column name encoded with a sequential color scale (light to dark)
- [ ] `x_sort` accepts an explicit list of category values for x-axis ordering (e.g., `['Mon', 'Tue', ..., 'Sun']`); when `None`, Altair uses default alphabetical sort
- [ ] `y_sort` accepts an explicit list of category values for y-axis ordering (e.g., `['0', '1', ..., '23']` for hours); when `None`, Altair uses default sort
- [ ] Chart includes a tooltip encoding displaying the x value, y value, and color value on hover
- [ ] Chart inherits the registered `toronto_mobility` Altair theme (Inter font, transparent view stroke)
- [ ] Chart uses `width="container"` for responsive layout within Streamlit columns
- [ ] Chart title renders via `.properties(title=title)` when `title` is non-empty
- [ ] Function renders without error when called with a DataFrame containing 168 rows (24 hours x 7 days) with `hour`, `day_of_week`, and `delay_count` columns
- [ ] All functions have type hints and docstrings
- [ ] Existing `bar_chart()`, `line_chart()`, and `sparkline()` functions remain unchanged

**Technical Notes**: Altair ordinal sort is controlled via `alt.X('col:O', sort=sort_list)`. The sequential color scale uses `alt.Color('col:Q', scale=alt.Scale(scheme='reds'))` to align with the project red palette. The `scheme='reds'` Vega scale provides a perceptually uniform light-to-dark red gradient consistent with `--ttc-red`. Cell padding can be added via `.configure_mark(strokeWidth=1, stroke='white')` for visual separation between cells.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] `heatmap()` renders a 7x24 grid with sample data without Altair validation errors
- [ ] PR opened with linked issue
- [ ] CI checks green

---

## Exit Criteria

This epic is complete when:

- [ ] `dashboard/requirements.txt` includes pinned `pydeck` and `plotly` dependencies with zero resolution conflicts
- [ ] `dashboard/components/maps.py` produces PyDeck ScatterplotLayer maps with configurable point sizing, TTC red default color, dark basemap, and auto-centering viewport
- [ ] `dashboard/components/charts.py` contains `treemap()` producing Plotly treemaps with hierarchical path decomposition, sequential red color scale, Inter typography, and transparent backgrounds
- [ ] `dashboard/components/charts.py` contains `heatmap()` producing Altair heatmaps with ordinal axes, sequential color encoding, explicit sort orders, and tooltip interactivity
- [ ] All 3 new builder functions render without error when called with representative sample DataFrames
- [ ] All functions have type hints and docstrings
- [ ] Existing E-1103 components (`bar_chart`, `line_chart`, `sparkline`, `render_metric_row`, filter functions) remain functionally unchanged
- [ ] `pip install -r dashboard/requirements.txt` succeeds in a clean Python 3.12 environment
- [ ] All visual output conforms to dashboard-design skill standards: project color palette, Inter typography, no default framework styling
