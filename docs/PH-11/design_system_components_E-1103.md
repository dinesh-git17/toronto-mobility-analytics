# Design System & Reusable Component Library

| Field        | Value         |
| ------------ | ------------- |
| Epic ID      | E-1103        |
| Phase        | PH-11         |
| Owner        | @dinesh-git17 |
| Status       | Complete      |
| Dependencies | [E-1101]      |
| Created      | 2026-02-10    |

---

## Context

Without a shared design system, dashboard pages would produce inconsistent styling — mismatched colors, font families, chart aesthetics, and component layouts across 5 pages and 15+ visualizations. Dashboard-design.md Section 6 specifies a precise visual identity: TTC red (`#DA291C`), Bike Share green (`#43B02A`), neutral slate (`#334155`), off-white background (`#FAFAFA`), accent blue (`#2563EB`), Inter/JetBrains Mono typography, and Altair chart theming with labeled axes and transparent view strokes. This epic translates those specifications into production CSS, a registered Altair theme, and three reusable Python component modules — metric cards, chart builders, and sidebar filters — that the Overview page (E-1104) and all PH-12 through PH-14 deep-dive pages consume.

This work belongs in PH-11 because the Overview landing page requires styled metric cards, sparkline charts, and bar chart builders to render its hero metrics and visualizations. Deferring the design system to a later phase would force E-1104 to use unstyled defaults and require a disruptive retrofit when visual standards are applied.

---

## Scope

### In Scope

- `dashboard/styles/custom.css`: Project color palette CSS variables, Inter and JetBrains Mono font imports from Google Fonts CDN, metric card styling (padding, border-radius, shadow, color-coded border), Streamlit layout overrides
- Altair theme registration (`toronto_theme()`) with Inter font family, 12px label / 14px title font sizes, transparent view stroke, and named color scale using the project palette
- `dashboard/components/metrics.py`: Metric card factory function producing styled KPI cards with value formatting, delta indicators, and horizontal row layout via `st.columns`
- `dashboard/components/charts.py`: Chart builder functions for Altair horizontal and vertical bar charts, multi-line time series, and compact sparkline mini-charts — all pre-styled with the registered theme
- `dashboard/components/filters.py`: Sidebar filter components wrapping `st.sidebar.date_input`, `st.sidebar.multiselect`, and `st.sidebar.selectbox` with consistent parameter interfaces and default value handling

### Out of Scope

- `dashboard/components/maps.py` PyDeck map builder functions (PH-12/PH-13 scope — maps are excluded from PH-11 per PHASES.md)
- Plotly chart builders and treemap components (PH-12 scope for delay cause treemaps)
- Mobile-specific CSS media queries and responsive breakpoints
- Dark mode toggle or alternate theme support
- CSS animations, transitions, or loading skeletons
- Icon library integration (Font Awesome, Material Icons)
- Storybook-style component documentation or visual regression testing

---

## Technical Approach

### Architecture Decisions

- **CSS custom properties (variables) for design tokens** — Colors, spacing, and border-radius values defined as CSS variables (`--ttc-red`, `--bike-green`, etc.) in `custom.css`. This enables centralized palette management and consistent references from CSS classes and inline styles. Streamlit loads the CSS via `st.markdown("<style>...</style>", unsafe_allow_html=True)`.
- **Google Fonts CDN for Inter and JetBrains Mono** — Web fonts loaded via `@import` in `custom.css`. Inter covers headers, body, and metric values per dashboard-design.md Section 6.2. JetBrains Mono covers data labels and code-formatted content. CDN loading avoids bundling font files in the repository.
- **Altair theme registration via `alt.themes.register()`** — The `toronto_theme()` function returns a dictionary conforming to Vega-Lite theme specification. Registered once at import time and enabled via `alt.themes.enable("toronto_mobility")`. All chart builder functions inherit the theme automatically — no per-chart styling needed.
- **Component functions return Streamlit-renderable objects** — Chart builders return `alt.Chart` objects (rendered via `st.altair_chart`). Metric card functions call `st.metric()` or `st.markdown()` directly (side-effect rendering). Filter functions return selected values (pure functions). This pattern ensures components are composable in any page layout.
- **Sidebar filter functions wrap Streamlit widgets** — Filter components encapsulate widget creation, default value logic, and type conversion. Pages call `date_range_filter()` instead of raw `st.sidebar.date_input()`, gaining consistent labels, default ranges, and return types across all 5 pages.

### Integration Points

- **Upstream: E-1101** — Requires `dashboard/components/`, `dashboard/styles/` directories and `app.py` entry point (CSS injection point)
- **Downstream: E-1104** — Overview page uses `render_metric_row()` for hero metrics, `line_chart()` or `sparkline()` for YoY trend, `bar_chart()` for mode comparison
- **Downstream: PH-12 through PH-14** — All deep-dive pages reuse chart builders, metric cards, and sidebar filters without reimplementation
- **dashboard-design.md Section 6** — Color palette, typography, chart styling, and map styling specifications

### Repository Areas

- `dashboard/styles/custom.css` (new)
- `dashboard/components/metrics.py` (new)
- `dashboard/components/charts.py` (new)
- `dashboard/components/filters.py` (new)

### Risks

| Risk                                                                                                                                                        | Likelihood | Impact | Mitigation                                                                                                                                                                                                            |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Google Fonts CDN unavailable or blocked in restricted network environments, causing fallback to system fonts with visual inconsistency                      | Low        | Medium | CSS `font-family` declarations include fallback stacks: `'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif` and `'JetBrains Mono', 'Fira Code', 'Consolas', monospace`                               |
| Altair theme registration conflicts with Streamlit's built-in Altair integration, causing charts to render with default styling instead of the custom theme | Medium     | Medium | Verify theme activation via `alt.themes.active` assertion after `enable()` call; test with a minimal chart in S002 acceptance criteria                                                                                |
| `st.markdown` with `unsafe_allow_html=True` for CSS injection is deprecated or restricted in a future Streamlit version, breaking the design system         | Low        | High   | Pin Streamlit version in `requirements.txt` (`>=1.31.0,<2.0.0`); monitor Streamlit changelog for `unsafe_allow_html` deprecation notices; CSS injection is the documented pattern for custom styling in Streamlit 1.x |
| Metric card custom HTML styling conflicts with Streamlit's built-in `st.metric` component CSS, producing doubled borders or misaligned text                 | Medium     | Low    | Scope CSS selectors to custom class names (`.metric-card`, `.metric-row`) to avoid global selector conflicts; test visual output against `st.metric` default rendering                                                |

---

## Stories

| ID   | Story                                                                    | Points | Dependencies | Status |
| ---- | ------------------------------------------------------------------------ | ------ | ------------ | ------ |
| S001 | Create custom CSS with project color palette and typography              | 3      | E-1101.S001  | Complete |
| S002 | Register Altair chart theme with Toronto Mobility design tokens          | 3      | S001         | Complete |
| S003 | Build metric card factory component                                      | 3      | S001         | Complete |
| S004 | Build chart builder functions for standard visualization types           | 5      | S002         | Complete |
| S005 | Build sidebar filter components for date range and categorical selection | 5      | None         | Complete |

---

### S001: Create Custom CSS with Project Color Palette and Typography

**Description**: Create `dashboard/styles/custom.css` with Google Fonts imports for Inter and JetBrains Mono, CSS custom properties for the project color palette, and base styling classes for metric cards and layout utilities.

**Acceptance Criteria**:

- [ ] File `dashboard/styles/custom.css` exists
- [ ] CSS imports Inter font family (weights 400, 600, 700) from Google Fonts CDN via `@import url()`
- [ ] CSS imports JetBrains Mono font family (weight 400) from Google Fonts CDN via `@import url()`
- [ ] CSS defines custom properties on `:root`: `--ttc-red: #DA291C`, `--bike-green: #43B02A`, `--neutral-slate: #334155`, `--bg-offwhite: #FAFAFA`, `--accent-blue: #2563EB`, `--warning-amber: #F59E0B`
- [ ] CSS sets Streamlit main content font family to `'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`
- [ ] CSS sets code and monospace elements to `'JetBrains Mono', 'Fira Code', 'Consolas', monospace`
- [ ] CSS defines `.metric-card` class with: `padding: 1rem 1.5rem`, `border-radius: 0.5rem`, `box-shadow: 0 1px 3px rgba(0,0,0,0.1)`, `border-left: 4px solid var(--accent-blue)`
- [ ] CSS defines `.metric-card--ttc` variant with `border-left-color: var(--ttc-red)` and `.metric-card--bike` variant with `border-left-color: var(--bike-green)`
- [ ] CSS file is loadable in `app.py` via `st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)` without rendering errors
- [ ] No CSS rules override Streamlit's sidebar navigation or widget styling in a way that breaks functionality

**Technical Notes**: Streamlit injects its own CSS at runtime. Custom CSS loaded via `st.markdown` appends to the page stylesheet. Selectors must be specific enough to apply to custom components without bleeding into Streamlit internals. The `.metric-card` class is applied via `st.markdown` in the metric card factory (S003). Google Fonts `@import` statements must appear at the top of the CSS file before any rules.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] CSS renders correctly when injected into a running Streamlit app
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S002: Register Altair Chart Theme with Toronto Mobility Design Tokens

**Description**: Define and register an Altair theme function (`toronto_theme()`) that applies Inter typography, project color scale, transparent view strokes, and consistent axis styling per dashboard-design.md Section 6.3.

**Acceptance Criteria**:

- [ ] Theme function `toronto_theme()` defined in `dashboard/components/charts.py` (or a dedicated `dashboard/styles/theme.py` — colocated with chart builders for import convenience)
- [ ] Theme registered via `alt.themes.register("toronto_mobility", toronto_theme)` at module import time
- [ ] Theme enabled via `alt.themes.enable("toronto_mobility")` at module import time
- [ ] Theme configuration sets `axis.labelFont` and `axis.titleFont` to `"Inter"`
- [ ] Theme configuration sets `legend.labelFont` and `legend.titleFont` to `"Inter"`
- [ ] Theme configuration sets `header.labelFont` and `header.titleFont` to `"Inter"`
- [ ] Theme configuration sets `axis.labelFontSize` to `12` and `axis.titleFontSize` to `14`
- [ ] Theme configuration sets `view.stroke` to `"transparent"` for clean chart backgrounds
- [ ] Theme defines a `range.category` color scale: `["#DA291C", "#43B02A", "#2563EB", "#334155", "#F59E0B"]` (TTC red, Bike Share green, accent blue, slate, amber)
- [ ] A minimal test chart (`alt.Chart(pd.DataFrame({"x": [1], "y": [1]})).mark_point()`) renders without error after theme activation
- [ ] All functions have type hints and docstrings

**Technical Notes**: Altair themes are Vega-Lite config dictionaries returned by a zero-argument function. The theme applies globally after `enable()` — every `alt.Chart` created after this point inherits the styling. The `range.category` color scale determines the default color cycle for nominal/ordinal encodings. Dashboard-design.md Section 6.3 provides the reference theme structure.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] `alt.themes.active` returns `"toronto_mobility"` after import
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S003: Build Metric Card Factory Component

**Description**: Build `dashboard/components/metrics.py` with a metric card factory function that renders styled KPI cards with value formatting, optional delta indicators, and a horizontal row layout using `st.columns`.

**Acceptance Criteria**:

- [ ] File `dashboard/components/metrics.py` exists
- [ ] Function `render_metric_card(label: str, value: str, delta: str | None = None, delta_color: str = "normal", border_variant: str = "default") -> None` renders a single styled metric using `st.metric` or custom HTML via `st.markdown`
- [ ] `delta` parameter supports delta indicators displayed below the primary value (e.g., "↑ 17% vs 2020")
- [ ] `delta_color` parameter accepts `"normal"` (green up / red down), `"inverse"` (red up / green down), or `"off"` (neutral)
- [ ] `border_variant` parameter accepts `"default"` (accent blue), `"ttc"` (TTC red), `"bike"` (Bike Share green) and applies the corresponding `.metric-card--*` CSS class
- [ ] Function `render_metric_row(metrics: list[dict[str, Any]]) -> None` renders a horizontal row of 3-4 metric cards using `st.columns` with equal width distribution
- [ ] Each dict in the `metrics` list contains keys matching `render_metric_card` parameters: `label`, `value`, and optionally `delta`, `delta_color`, `border_variant`
- [ ] Metric values display in large typography (Streamlit's default `st.metric` sizing or equivalent custom HTML)
- [ ] All functions have type hints and docstrings

**Technical Notes**: `st.metric` provides built-in delta formatting and styling. If `st.metric` provides sufficient visual quality, prefer it over custom HTML to reduce CSS maintenance burden. Custom HTML via `st.markdown` with the `.metric-card` CSS class provides more control over border colors and layout but requires `unsafe_allow_html=True`. The choice between these approaches is an implementation-time decision — acceptance criteria are satisfied by either approach.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] `render_metric_row` renders 4 cards in a horizontal row without layout overflow
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S004: Build Chart Builder Functions for Standard Visualization Types

**Description**: Build `dashboard/components/charts.py` with Altair chart factory functions for bar charts (horizontal and vertical), line charts, and sparkline mini-charts — all inheriting the registered `toronto_mobility` Altair theme.

**Acceptance Criteria**:

- [ ] File `dashboard/components/charts.py` exists
- [ ] Function `bar_chart(data: pd.DataFrame, x: str, y: str, color: str | None = None, horizontal: bool = False, title: str = "") -> alt.Chart` returns an Altair `Chart` object
- [ ] `horizontal=True` swaps x/y encoding to produce a horizontal bar chart (Y-axis categorical, X-axis quantitative)
- [ ] Function `line_chart(data: pd.DataFrame, x: str, y: str, color: str | None = None, title: str = "") -> alt.Chart` returns an Altair `Chart` object for multi-line time series
- [ ] `color` parameter encodes a categorical field for multi-series differentiation (e.g., year or transit mode)
- [ ] Function `sparkline(data: pd.DataFrame, x: str, y: str, height: int = 60) -> alt.Chart` returns a compact Altair `Chart` with no axis labels, no legend, no title, and minimal padding — suitable for inline display alongside metrics
- [ ] All chart functions inherit the registered `toronto_mobility` Altair theme (no manual `.configure_*()` calls needed)
- [ ] All chart functions accept a `pd.DataFrame` as the primary data argument
- [ ] Chart dimensions default to container width: `.properties(width="container")` for responsive layout
- [ ] All functions have type hints and docstrings

**Technical Notes**: Altair charts are Vega-Lite specifications rendered by Streamlit via `st.altair_chart(chart, use_container_width=True)`. The `use_container_width=True` parameter in the Streamlit call overrides explicit `width` properties — chart builders should set `width="container"` as a default that works both standalone and within Streamlit columns. The sparkline function strips all chrome via `.configure_axis(disable=True).configure_view(strokeWidth=0)` or equivalent.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] All 3 chart types render with sample data without Altair validation errors
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S005: Build Sidebar Filter Components for Date Range and Categorical Selection

**Description**: Build `dashboard/components/filters.py` with sidebar filter functions wrapping Streamlit widgets for date range selection, categorical multiselect, and single-select dropdown — providing consistent interfaces and default values across all dashboard pages.

**Acceptance Criteria**:

- [ ] File `dashboard/components/filters.py` exists
- [ ] Function `date_range_filter(min_date: date, max_date: date, default_start: date | None = None, default_end: date | None = None, key: str = "date_range") -> tuple[date, date]` returns a `(start_date, end_date)` tuple using `st.sidebar.date_input`
- [ ] `default_start` defaults to `min_date` and `default_end` defaults to `max_date` when `None`
- [ ] Date range filter renders in the sidebar with label "Date Range"
- [ ] Function `multiselect_filter(label: str, options: list[str], default: list[str] | None = None, key: str = "") -> list[str]` returns selected values using `st.sidebar.multiselect`
- [ ] `default` defaults to `options` (all selected) when `None`
- [ ] Function `select_filter(label: str, options: list[str], default: str | None = None, key: str = "") -> str` returns a single selected value using `st.sidebar.selectbox`
- [ ] All filter functions render in the sidebar (use `st.sidebar.*` widgets)
- [ ] `key` parameter enables unique widget identity when the same filter type appears on multiple pages, preventing Streamlit `DuplicateWidgetID` errors
- [ ] All functions have type hints and docstrings
- [ ] Return types are deterministic — no `None` returns for required selections

**Technical Notes**: Streamlit sidebar widgets persist their state within a session. The `key` parameter is critical for multi-page apps where two pages might create a `multiselect` with the same default label. Each page should pass a unique key prefix (e.g., `key="ttc_mode"` vs `key="bike_user_type"`). The `date_range_filter` function must account for `st.date_input` returning a single date (user has selected start but not end) by retaining the previous `end_date` from session state.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] All 3 filter types render in the sidebar and return expected values
- [ ] PR opened with linked issue
- [ ] CI checks green

---

## Exit Criteria

This epic is complete when:

- [ ] `dashboard/styles/custom.css` defines project color variables (`#DA291C`, `#43B02A`, `#334155`, `#FAFAFA`, `#2563EB`, `#F59E0B`), Inter/JetBrains Mono font imports, and metric card CSS classes
- [ ] Altair theme `toronto_mobility` registered and active with Inter typography, transparent view strokes, and project color scale
- [ ] `dashboard/components/metrics.py` renders horizontal rows of 3-4 styled metric cards with delta indicators
- [ ] `dashboard/components/charts.py` produces bar charts, line charts, and sparklines that inherit the project theme
- [ ] `dashboard/components/filters.py` renders date range, multiselect, and single-select filters in the sidebar
- [ ] Design system applied consistently: all components use project colors and typography — no Streamlit defaults visible in custom components
- [ ] All component functions have type hints and docstrings
