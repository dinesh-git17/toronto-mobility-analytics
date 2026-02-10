---
name: dashboard-design
description: Govern dashboard design, layout, color, typography, and visual quality to production-grade standards. Use when designing, reviewing, or critiquing any dashboard, Streamlit app, or data visualization interface. Triggers on dashboard creation, layout planning, chart design, theming, KPI presentation, or any visual quality review. Mandatory for all dashboard output in this repository.
---

# Dashboard Design

Design dashboards that look like shipping products, not prototypes. Every layout decision, color choice, and typographic detail must serve a purpose. The standard is Stripe, Linear, Vercel — not Kaggle notebooks.

## Scope

**In scope:** Layout composition, color systems, typography, chart selection, spacing, visual hierarchy, Streamlit theming, KPI presentation, page flow, and rejection criteria.

**Out of scope:** Data correctness, SQL logic, dbt model design, backend performance, API design, or data pipeline architecture.

## Design Philosophy

### The Three Tests

Every dashboard must pass all three:

1. **The Screenshot Test.** Would this screenshot belong in a product landing page or portfolio? If not, redesign.
2. **The Executive Test.** Can a VP extract the key insight within 5 seconds of looking at the page? If not, restructure.
3. **The Restraint Test.** Can you remove one more element without losing information? If yes, remove it.

### Governing Principles

**Tufte's Data-Ink Ratio.** Maximize the proportion of visual elements that encode data. Remove gridlines, borders, backgrounds, legends, and decorations that do not directly communicate a data value. Every pixel must earn its place.

**Calm over clever.** Dashboards are read under time pressure. Clarity beats novelty. A dashboard that requires explanation has failed.

**Editorial, not encyclopedic.** Curate what matters. A dashboard that shows everything communicates nothing. Decide what story the page tells, then remove everything else.

**Designed, not decorated.** Good design is invisible structure — alignment, rhythm, proportion. Decoration is surface treatment — gradients, shadows, animations. Prefer the former. Reject the latter.

## Color System

### Background and Surface

| Token              | Light Mode | Dark Mode | Usage                |
| ------------------ | ---------- | --------- | -------------------- |
| `background`       | `#FAFAFA`  | `#0A0A0B` | Page background      |
| `surface`          | `#FFFFFF`  | `#141415` | Cards, containers    |
| `surface-elevated` | `#FFFFFF`  | `#1A1A1C` | Modals, popovers     |
| `border`           | `#E5E5E5`  | `#2A2A2D` | Dividers, card edges |
| `border-subtle`    | `#F0F0F0`  | `#1F1F22` | Internal separators  |

### Text Hierarchy

| Token            | Light Mode | Dark Mode | Usage                   |
| ---------------- | ---------- | --------- | ----------------------- |
| `text-primary`   | `#171717`  | `#EDEDED` | Headlines, KPI values   |
| `text-secondary` | `#525252`  | `#A0A0A0` | Descriptions, labels    |
| `text-tertiary`  | `#A3A3A3`  | `#5C5C5C` | Annotations, timestamps |

### Semantic Accents

Limit to three functional accent colors. No decorative color.

| Token            | Value     | Usage                                   |
| ---------------- | --------- | --------------------------------------- |
| `accent-primary` | `#2563EB` | Primary actions, active states, links   |
| `positive`       | `#16A34A` | Upward trends, success, on-time         |
| `negative`       | `#DC2626` | Downward trends, alerts, delays         |
| `neutral-data`   | `#737373` | Baseline data, inactive series, context |

### Chart Color Discipline

Apply the "fewer hues, more shades" principle (per Datawrapper and The Economist style guides):

- **Single-series charts:** One accent color against a neutral background. Never rainbow.
- **Two-series comparisons:** `accent-primary` vs `neutral-data`. Not two bright colors.
- **Multi-series (3-5):** Use sequential shades of one hue (e.g., `#BFDBFE`, `#60A5FA`, `#2563EB`, `#1E40AF`). Never assign arbitrary colors.
- **Categorical (6+):** Reconsider the chart type. Use a table, small multiples, or filter. Six colors is a design failure.

**Gray is the most important color in data visualization.** Use it for context, baselines, inactive series, and secondary data. Reserve saturated color for the single data point demanding attention.

## Typography

### Font Stack

```
font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
```

Inter is purpose-built for interface readability with well-crafted tabular number forms — critical for KPI values and data tables.

### Scale (8px Grid)

| Role           | Size | Weight | Line Height | Usage                              |
| -------------- | ---- | ------ | ----------- | ---------------------------------- |
| Page title     | 24px | 600    | 32px        | One per page, top-left             |
| Section header | 18px | 600    | 28px        | Group-level labels                 |
| KPI value      | 32px | 700    | 40px        | Primary metric numbers             |
| KPI label      | 13px | 500    | 20px        | Metric descriptions                |
| Body text      | 14px | 400    | 22px        | Descriptions, annotations          |
| Caption        | 12px | 400    | 18px        | Axis labels, timestamps, footnotes |

### Typography Rules

- Never use more than two font weights on a single card.
- KPI values use tabular figures (`font-variant-numeric: tabular-nums`) for digit alignment.
- Sentence case everywhere. Title Case only for proper nouns.
- No ALL CAPS except for short status badges (e.g., `DELAYED`, `ACTIVE`).

## Spacing and Layout

### 8px Grid

All spacing values derive from an 8px base unit:

| Token       | Value | Usage                                   |
| ----------- | ----- | --------------------------------------- |
| `space-xs`  | 4px   | Icon-to-text gap, tight inline elements |
| `space-sm`  | 8px   | Intra-component padding                 |
| `space-md`  | 16px  | Card internal padding, form field gaps  |
| `space-lg`  | 24px  | Section gaps, card-to-card margins      |
| `space-xl`  | 32px  | Page-level section separators           |
| `space-2xl` | 48px  | Major page divisions                    |

### Grid System

- Use a **12-column grid** for page layout.
- KPI cards: 3 or 4 per row. Never 5+. Never asymmetric widths.
- Charts: Minimum 6 columns wide. Never compress a time series into 4 columns.
- Tables: Always full-width (12 columns).
- Sidebar navigation: Fixed 240px width or collapsible to 64px.

### Alignment Rules

- Left-align all text by default.
- Right-align numeric columns in tables.
- Center-align only KPI values within their card.
- Vertical rhythm: Maintain consistent spacing between all sibling elements.

## Page Composition

### Information Architecture

Every dashboard page follows a top-down narrative structure:

```
+-------------------------------------------------+
|  Page Title + Date Range / Filters              |  <- Context
+--------+--------+--------+----------------------+
| KPI 1  | KPI 2  | KPI 3  |  KPI 4 (optional)   |  <- Summary
+--------+--------+--------+----------------------+
|  Primary Chart (time series or distribution)     |  <- Trend
+---------------------+---------------------------+
|  Supporting Chart   |  Supporting Chart          |  <- Detail
+---------------------+---------------------------+
|  Data Table (sortable, paginated)                |  <- Evidence
+-------------------------------------------------+
```

### KPI Card Design

- Maximum **4 KPI cards** per row. Three is often better.
- Each KPI card contains exactly: value, label, trend indicator (optional), sparkline (optional).
- No icons inside KPI cards unless they encode data (e.g., up/down arrow for trend).
- Trend indicators: `+12.3%` in `positive` color, `-5.1%` in `negative` color, gray for neutral.
- No background color on KPI cards. Use `surface` background with `border` stroke.

### Progressive Disclosure

- **Level 1 (page load):** KPI summary + primary chart. The story in 5 seconds.
- **Level 2 (scroll):** Supporting charts and breakdowns. The evidence.
- **Level 3 (interaction):** Tooltips, drill-downs, data tables. The detail.

Never front-load all detail. Earn the scroll.

### Page Count Discipline

- One page per analytical question. Never combine unrelated analytical domains on the same page.
- Navigation between pages via sidebar or tab bar. Never pagination dots.
- Maximum 5-7 pages per dashboard application. Beyond that, split into separate applications.

## Chart Standards

### When to Use Charts

| Data Shape                    | Chart Type             | When                                         |
| ----------------------------- | ---------------------- | -------------------------------------------- |
| Single metric over time       | Line chart             | Always for time series with >10 data points  |
| Metric comparison (2-5 items) | Horizontal bar chart   | Comparing named categories                   |
| Part-to-whole                 | Stacked bar or treemap | Showing composition (never pie charts)       |
| Distribution                  | Histogram or box plot  | Understanding spread and outliers            |
| Correlation                   | Scatter plot           | Exploring relationships between two measures |
| Geographic                    | Choropleth or dot map  | Location-dependent metrics                   |

### When NOT to Visualize

- **Single numbers:** Use a KPI card, not a chart.
- **Two values:** Use a comparison card with labels, not a bar chart.
- **Exact values matter more than pattern:** Use a table.
- **More than 6 categories:** Use a table with conditional formatting or sparklines.
- **The chart would be a single bar:** Use a progress indicator or text.

### Chart Formatting

- Remove chart borders and background fills.
- X-axis labels: Rotate only if absolutely necessary. Prefer abbreviation or filtering.
- Y-axis: Start at zero for bar charts. Allow non-zero baselines only for line charts where the range is narrow.
- Gridlines: Horizontal only, using `border-subtle` color. Remove vertical gridlines.
- Legend: Position inline with the data (direct labels) when possible. External legends only for 3+ series.
- Tooltips: Show exact value, formatted with appropriate precision. No redundant tooltip titles.
- No 3D effects. No gradient fills on data marks. No drop shadows on chart elements.

### Annotation Standards

- Use annotations sparingly to mark inflection points, anomalies, or context (e.g., "COVID lockdown", "Holiday weekend").
- Annotations use `text-tertiary` color, 12px, with a thin connector line.
- Maximum 3 annotations per chart. More than that signals the chart needs redesign.

## Streamlit Implementation

### Theme Configuration

Set in `.streamlit/config.toml`:

```toml
[theme]
base = "light"
primaryColor = "#2563EB"
backgroundColor = "#FAFAFA"
secondaryBackgroundColor = "#FFFFFF"
textColor = "#171717"
font = "sans serif"
```

### CSS Override Strategy

Inject via `st.markdown(css, unsafe_allow_html=True)` at the top of each page:

- Override default Streamlit padding (`[data-testid="stAppViewContainer"]`).
- Remove default header decoration (`header[data-testid="stHeader"]`).
- Style metric containers using `.stkey_<key>` class selectors.
- Apply Inter font family to all elements via root-level CSS.
- Set `max-width: 1200px` on the main content area to prevent line lengths exceeding readable limits on wide monitors.

### Layout Patterns

- Use `st.columns([3, 3, 3, 3])` for equal-width KPI rows. Avoid uneven ratios.
- Wrap logical sections in `st.container()` for spacing control.
- Use `st.divider()` between major sections. Never between adjacent KPI cards.
- Place filters in `st.sidebar` or in a collapsible `st.expander` labeled "Filters" — never inline with content.
- Cache data with `@st.cache_data`. Cache UI fragments with `@st.fragment` (Streamlit 1.33+). Never let recomputations cause layout flicker.

### Component Hierarchy

```python
# Page structure pattern
st.set_page_config(page_title="...", layout="wide")
inject_custom_css()

st.title("Page Title")
render_kpi_row(metrics)

st.divider()

col1, col2 = st.columns(2)
with col1:
    render_primary_chart(data)
with col2:
    render_supporting_chart(data)

st.divider()

render_data_table(data)
```

## Anti-Patterns (Reject on Sight)

### Visual Anti-Patterns

- **Rainbow charts.** More than 3 colors in a single chart without sequential logic.
- **Pie charts.** Use horizontal bar charts instead. Angle perception is unreliable.
- **3D effects.** On any chart element, including faux-3D bar charts.
- **Gradient fills** on data-encoding marks (bars, areas). Solid fills only.
- **Shadow boxing.** Drop shadows on cards, charts, or containers that serve no spatial hierarchy purpose.
- **Icon salad.** Decorative icons on KPI cards or section headers.
- **Background color on KPI cards** as a means of differentiation. Use border or accent text instead.

### Layout Anti-Patterns

- **Wall of KPIs.** More than 4 KPI cards in a single row, or more than 8 on a single page.
- **Chart stacking.** Three or more full-width charts in vertical sequence without grouping logic.
- **Filter sprawl.** More than 4 filter controls visible without interaction.
- **Orphan charts.** A chart without a section heading or contextual label explaining what question it answers.
- **Mixed column widths** in the same visual group.

### Interaction Anti-Patterns

- **Autoplay animations.** Loading spinners, chart entrance animations, or number counting effects.
- **Alert fatigue.** Conditional formatting on more than 20% of visible data points.
- **Tooltip novels.** Tooltips with more than 3 lines of information.

## Review Checklist

Before any dashboard ships, verify every item:

### Structure

- [ ] Page answers exactly one analytical question.
- [ ] KPI row appears first, with 3-4 metrics maximum.
- [ ] Primary chart immediately follows KPI row.
- [ ] Content follows top-down narrative: summary, trend, detail, evidence.
- [ ] Filters are contained in sidebar or collapsible section.

### Color

- [ ] Maximum 3 semantic accent colors used across the entire page.
- [ ] Gray (`neutral-data`) used for all secondary data series.
- [ ] No color is used purely for decoration.
- [ ] Positive/negative semantics are consistent across all charts on the page.

### Typography

- [ ] Font hierarchy limited to 2-3 sizes per component.
- [ ] KPI values use the largest type size on the page.
- [ ] No ALL CAPS text except status badges.
- [ ] All numeric values formatted with appropriate precision (no raw floats).

### Charts

- [ ] No pie charts.
- [ ] No 3D effects.
- [ ] No rainbow palettes.
- [ ] Gridlines are horizontal-only and subtle.
- [ ] Y-axis starts at zero for bar charts.
- [ ] Direct labels preferred over external legends.

### Spacing

- [ ] All spacing is a multiple of 8px.
- [ ] Consistent margins between all sibling cards and sections.
- [ ] No cramped elements — minimum 16px internal padding on all containers.

## Rejection Criteria

Reject the dashboard and require redesign if any of the following are true:

- **Looks like a tutorial.** Generic placeholder data, default framework styling, or hobbyist energy.
- **Looks like a demo.** Gratuitous variety of chart types to showcase capability rather than communicate insight.
- **Would embarrass a senior engineer in a design review.** The definitive gut check.
- **Requires explanation.** If the designer must explain what a section means, the section has failed.
- **Uses default Streamlit theme** without custom CSS overrides.
- **Contains a pie chart.** Non-negotiable.
- **Contains more than 4 colors** in a single chart without sequential justification.
- **Page takes more than 5 seconds to deliver its core insight** due to layout density or visual noise.

## Output Contract

When this skill is invoked:

1. **Critique mode (default).** Review a proposed or existing dashboard. Identify every violation of these standards. Propose concrete fixes with specific CSS values, layout changes, or color substitutions.
2. **Design mode (explicit request).** Produce a layout specification: page structure, KPI selection, chart types, color assignments, and spacing. No code unless explicitly requested.
3. **Implementation mode (explicit request).** Generate Streamlit code with full custom CSS, proper layout structure, and chart configuration matching these standards.

Never generate implementation code unless the request explicitly asks for it. Design decisions come first.
