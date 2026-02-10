"""Altair chart theme registration and chart builder functions.

Registers the ``toronto_mobility`` Altair theme at import time.
All chart builder functions inherit the theme automatically.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import altair as alt
import plotly.express as px

if TYPE_CHECKING:
    import pandas as pd
    import plotly.graph_objects as go
    from altair.theme import ThemeConfig

# ---------------------------------------------------------------------------
# Altair theme registration (S002)
# ---------------------------------------------------------------------------

_CATEGORY_COLORS: list[str] = [
    "#DA291C",  # TTC red
    "#43B02A",  # Bike Share green
    "#2563EB",  # accent blue
    "#334155",  # neutral slate
    "#F59E0B",  # warning amber
]

_ACCENT_PRIMARY: str = "#2563EB"
_SCATTER_PALETTE: list[str] = ["#2563EB", "#737373", "#F59E0B"]


@alt.theme.register("toronto_mobility", enable=True)
def toronto_theme() -> ThemeConfig:
    """Return a Vega-Lite theme config for Toronto Mobility charts.

    Sets Inter font family on all text elements, transparent view stroke,
    12 px label / 14 px title font sizes, and the project color scale.
    """
    font = "Inter"
    return {
        "config": {
            "axis": {
                "labelFont": font,
                "titleFont": font,
                "labelFontSize": 12,
                "titleFontSize": 14,
            },
            "legend": {
                "labelFont": font,
                "titleFont": font,
            },
            "header": {
                "labelFont": font,
                "titleFont": font,
            },
            "title": {
                "font": font,
                "fontSize": 16,
            },
            "view": {
                "stroke": "transparent",
            },
            "range": {
                "category": _CATEGORY_COLORS,
            },
        }
    }


# ---------------------------------------------------------------------------
# Chart builder functions (S004)
# ---------------------------------------------------------------------------


def bar_chart(
    data: pd.DataFrame,
    x: str,
    y: str,
    color: str | None = None,
    horizontal: bool = False,
    title: str = "",
    stack: bool | None = True,
    mark_color: str | None = None,
) -> alt.Chart:
    """Build a bar chart with the project theme.

    Args:
        data: Source DataFrame.
        x: Column for the x-axis (categorical when vertical).
        y: Column for the y-axis (quantitative when vertical).
        color: Optional categorical column for color encoding.
        horizontal: Swap axes to produce a horizontal bar chart.
        title: Chart title.
        stack: Stacking behavior when ``color`` is provided.  ``True``
            stacks bars, ``False`` groups side-by-side, ``None`` uses
            Altair default.  Has no effect when ``color`` is ``None``.
        mark_color: Explicit fill color for all bars.  Applied only
            when ``color`` is ``None`` (single-series).

    Returns:
        Altair Chart object ready for ``st.altair_chart``.
    """
    apply_stack = color is not None and stack is not None

    if horizontal:
        if apply_stack:
            x_enc = alt.X(y, type="quantitative", stack=stack)
        else:
            x_enc = alt.X(y, type="quantitative")
        y_enc = alt.Y(x, type="nominal", sort="-x")
    else:
        x_enc = alt.X(x, type="nominal")
        if apply_stack:
            y_enc = alt.Y(y, type="quantitative", stack=stack)
        else:
            y_enc = alt.Y(y, type="quantitative")

    if mark_color is not None and color is None:
        chart = alt.Chart(data).mark_bar(color=mark_color).encode(x=x_enc, y=y_enc)
    else:
        chart = alt.Chart(data).mark_bar().encode(x=x_enc, y=y_enc)

    if color:
        chart = chart.encode(color=alt.Color(color, type="nominal"))
        if stack is False:
            if horizontal:
                chart = chart.encode(yOffset=alt.YOffset(f"{color}:N"))
            else:
                chart = chart.encode(xOffset=alt.XOffset(f"{color}:N"))

    return cast("alt.Chart", chart.properties(width="container", title=title))


def line_chart(
    data: pd.DataFrame,
    x: str,
    y: str,
    color: str | None = None,
    title: str = "",
) -> alt.Chart:
    """Build a multi-line time series chart with the project theme.

    Args:
        data: Source DataFrame.
        x: Column for the x-axis (temporal or ordinal).
        y: Column for the y-axis (quantitative).
        color: Optional categorical column for multi-series encoding.
        title: Chart title.

    Returns:
        Altair Chart object ready for ``st.altair_chart``.
    """
    chart = (
        alt.Chart(data)
        .mark_line(point=True)
        .encode(
            x=alt.X(x),
            y=alt.Y(y, type="quantitative"),
        )
    )

    if color:
        chart = chart.encode(color=alt.Color(color, type="nominal"))

    return cast("alt.Chart", chart.properties(width="container", title=title))


def sparkline(
    data: pd.DataFrame,
    x: str,
    y: str,
    height: int = 60,
) -> alt.Chart:
    """Build a compact sparkline mini-chart without axes or labels.

    Suitable for inline display alongside metric cards.

    Args:
        data: Source DataFrame.
        x: Column for the x-axis.
        y: Column for the y-axis.
        height: Chart height in pixels.

    Returns:
        Altair Chart object with all chrome removed.
    """
    gradient = alt.Gradient(  # type: ignore[no-untyped-call]
        gradient="linear",
        stops=[
            alt.GradientStop(color="rgba(37,99,235,0.3)", offset=0),
            alt.GradientStop(color="rgba(37,99,235,0.02)", offset=1),
        ],
        x1=0,
        x2=0,
        y1=0,
        y2=1,
    )
    return cast(
        "alt.Chart",
        alt.Chart(data)
        .mark_area(line={"color": "#2563EB"}, color=gradient)
        .encode(
            x=alt.X(x, axis=None),
            y=alt.Y(y, type="quantitative", axis=None, scale=alt.Scale(zero=False)),
        )
        .properties(width="container", height=height)
        .configure_view(strokeWidth=0),
    )


# ---------------------------------------------------------------------------
# Extended chart builders (E-1201)
# ---------------------------------------------------------------------------

_DEFAULT_TREEMAP_SCALE: list[list[float | str]] = [
    [0, "#FEE2E2"],
    [0.5, "#F87171"],
    [1, "#DA291C"],
]


def treemap(
    data: pd.DataFrame,
    path_cols: list[str],
    value_col: str,
    color_col: str | None = None,
    title: str = "",
    color_scale: list[list[float | str]] | None = None,
) -> go.Figure:
    """Build a Plotly treemap for hierarchical category breakdowns.

    Renders nested tiles sized by ``value_col`` with an optional
    sequential color encoding and project-aligned typography.

    Args:
        data: Source DataFrame with hierarchy and value columns.
        path_cols: Column names defining hierarchy levels from outermost
            to innermost.
        value_col: Numeric column for proportional tile area.
        color_col: Numeric column for color intensity.  When ``None``,
            all tiles render in uniform TTC red.
        title: Chart title.
        color_scale: Plotly color scale as ``[[position, color], ...]``.
            Defaults to a light-pink-to-red sequential palette.

    Returns:
        A ``plotly.graph_objects.Figure`` renderable via
        ``st.plotly_chart``.
    """
    resolved_scale = color_scale if color_scale is not None else _DEFAULT_TREEMAP_SCALE

    if color_col is not None:
        fig = px.treemap(
            data,
            path=path_cols,
            values=value_col,
            color=color_col,
            color_continuous_scale=resolved_scale,
            title=title,
        )
    else:
        fig = px.treemap(
            data.assign(_uniform=1.0),
            path=path_cols,
            values=value_col,
            color="_uniform",
            color_continuous_scale=[[0, "#DA291C"], [1, "#DA291C"]],
            title=title,
        )
        fig.update_coloraxes(showscale=False)

    fig.update_traces(textinfo="label+percent parent")
    fig.update_layout(
        font_family="Inter",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin={"t": 40, "l": 10, "r": 10, "b": 10},
    )
    return fig


def heatmap(
    data: pd.DataFrame,
    x: str,
    y: str,
    color: str,
    title: str = "",
    x_sort: list[str] | None = None,
    y_sort: list[str] | None = None,
) -> alt.Chart:
    """Build a heatmap of colored cells with ordinal axes.

    Uses ``mark_rect()`` to render a two-dimensional matrix with
    sequential red color encoding and hover tooltips.

    Args:
        data: Source DataFrame.
        x: Column for the x-axis (ordinal).
        y: Column for the y-axis (ordinal).
        color: Quantitative column for cell color intensity.
        title: Chart title.
        x_sort: Explicit x-axis category order.  Alphabetical when
            ``None``.
        y_sort: Explicit y-axis category order.  Alphabetical when
            ``None``.

    Returns:
        Altair Chart object ready for ``st.altair_chart``.
    """
    return cast(
        "alt.Chart",
        alt.Chart(data)
        .mark_rect()
        .encode(
            x=alt.X(f"{x}:O", sort=x_sort),
            y=alt.Y(f"{y}:O", sort=y_sort),
            color=alt.Color(f"{color}:Q", scale=alt.Scale(scheme="reds")),
            tooltip=[
                alt.Tooltip(f"{x}:O"),
                alt.Tooltip(f"{y}:O"),
                alt.Tooltip(f"{color}:Q"),
            ],
        )
        .properties(width="container", title=title),
    )


# ---------------------------------------------------------------------------
# Extended chart builders (E-1301)
# ---------------------------------------------------------------------------


def scatter_plot(
    data: pd.DataFrame,
    x: str,
    y: str,
    color: str | None = None,
    size: int = 60,
    opacity: float = 0.6,
    title: str = "",
    x_title: str | None = None,
    y_title: str | None = None,
) -> alt.Chart:
    """Build a scatter plot for two-variable correlation analysis.

    Renders points via ``mark_circle()`` with quantitative axes, optional
    categorical color encoding, and hover tooltips.

    Args:
        data: Source DataFrame.
        x: Column for the x-axis (quantitative).
        y: Column for the y-axis (quantitative).
        color: Optional nominal column for categorical point grouping.
            When ``None``, all points use accent-primary blue.
        size: Point area in square pixels.
        opacity: Point opacity from 0.0 to 1.0.
        title: Chart title.
        x_title: Explicit x-axis label.  Defaults to column name.
        y_title: Explicit y-axis label.  Defaults to column name.

    Returns:
        Altair Chart object ready for ``st.altair_chart``.
    """
    resolved_x_title = x_title if x_title is not None else x
    resolved_y_title = y_title if y_title is not None else y

    tooltips: list[alt.Tooltip] = [
        alt.Tooltip(f"{x}:Q"),
        alt.Tooltip(f"{y}:Q"),
    ]
    if color:
        tooltips.append(alt.Tooltip(f"{color}:N"))

    if color:
        mark = alt.Chart(data).mark_circle(size=size, opacity=opacity)
    else:
        mark = alt.Chart(data).mark_circle(
            size=size,
            opacity=opacity,
            color=_ACCENT_PRIMARY,
        )

    chart = mark.encode(
        x=alt.X(f"{x}:Q", axis=alt.Axis(title=resolved_x_title)),
        y=alt.Y(f"{y}:Q", axis=alt.Axis(title=resolved_y_title)),
        tooltip=tooltips,
    )

    if color:
        unique_vals = data[color].dropna().unique().tolist()
        domain = sorted(str(v) for v in unique_vals)[:3]
        palette = _SCATTER_PALETTE[: len(domain)]
        chart = chart.encode(
            color=alt.Color(
                f"{color}:N",
                scale=alt.Scale(domain=domain, range=palette),
            ),
        )

    return cast("alt.Chart", chart.properties(width="container", title=title))


def area_chart(
    data: pd.DataFrame,
    x: str,
    y: str,
    color: str | None = None,
    title: str = "",
    opacity: float = 0.3,
    x_sort: list[str] | None = None,
) -> alt.Chart:
    """Build an area chart with a line overlay for trend visualization.

    Renders a filled area below a trend line using a layered composition
    of ``mark_area()`` and ``mark_line()``.

    Args:
        data: Source DataFrame.
        x: Column for the x-axis (ordinal).
        y: Column for the y-axis (quantitative).
        color: Optional nominal column for multi-series stacking.
            When ``None``, uses accent-primary blue.
        title: Chart title.
        opacity: Fill opacity for the area from 0.0 to 1.0.
        x_sort: Explicit x-axis category order.

    Returns:
        Altair Chart object ready for ``st.altair_chart``.
    """
    x_enc = alt.X(f"{x}:O", sort=x_sort)
    y_enc = alt.Y(f"{y}:Q")
    tooltip_enc: list[alt.Tooltip] = [
        alt.Tooltip(f"{x}:O"),
        alt.Tooltip(f"{y}:Q"),
    ]

    if color:
        base = alt.Chart(data).encode(
            x=x_enc,
            y=y_enc,
            color=alt.Color(f"{color}:N"),
            tooltip=tooltip_enc,
        )
        area = base.mark_area(opacity=opacity)
        line = base.mark_line()
    else:
        base = alt.Chart(data).encode(
            x=x_enc,
            y=y_enc,
            tooltip=tooltip_enc,
        )
        area = base.mark_area(opacity=opacity, color=_ACCENT_PRIMARY)
        line = base.mark_line(color=_ACCENT_PRIMARY)

    layered = alt.layer(area, line)
    return cast("alt.Chart", layered.properties(width="container", title=title))
