"""Altair chart theme registration and chart builder functions.

Registers the ``toronto_mobility`` Altair theme at import time.
All chart builder functions inherit the theme automatically.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import altair as alt

if TYPE_CHECKING:
    import pandas as pd
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

    return cast(alt.Chart, chart.properties(width="container", title=title))


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

    return cast(alt.Chart, chart.properties(width="container", title=title))


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
        alt.Chart,
        alt.Chart(data)
        .mark_area(line={"color": "#2563EB"}, color=gradient)
        .encode(
            x=alt.X(x, axis=None),
            y=alt.Y(y, type="quantitative", axis=None, scale=alt.Scale(zero=False)),
        )
        .properties(width="container", height=height)
        .configure_view(strokeWidth=0),
    )
