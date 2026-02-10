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
) -> alt.Chart:
    """Build a bar chart with the project theme.

    Args:
        data: Source DataFrame.
        x: Column for the x-axis (categorical when vertical).
        y: Column for the y-axis (quantitative when vertical).
        color: Optional categorical column for color encoding.
        horizontal: Swap axes to produce a horizontal bar chart.
        title: Chart title.

    Returns:
        Altair Chart object ready for ``st.altair_chart``.
    """
    if horizontal:
        x_enc = alt.X(y, type="quantitative")
        y_enc = alt.Y(x, type="nominal", sort="-x")
    else:
        x_enc = alt.X(x, type="nominal")
        y_enc = alt.Y(y, type="quantitative")

    chart = alt.Chart(data).mark_bar().encode(x=x_enc, y=y_enc)

    if color:
        chart = chart.encode(color=alt.Color(color, type="nominal"))

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
