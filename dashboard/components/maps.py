"""PyDeck map builder functions for geographic visualizations.

Provides builder functions that return ``pydeck.Deck`` objects
renderable via ``st.pydeck_chart()``.
"""

from __future__ import annotations

import json

import pandas as pd
import pydeck

_TTC_RED_RGBA: list[int] = [218, 41, 28, 180]
_DEFAULT_RADIUS: int = 100
_MIN_RADIUS: int = 50
_MAX_RADIUS: int = 500


def _compute_radius_column(
    data: pd.DataFrame,
    size_col: str | None,
) -> pd.DataFrame:
    """Return a DataFrame copy with a ``_radius`` column for point sizing.

    Maps ``size_col`` values to the ``_MIN_RADIUS``-``_MAX_RADIUS`` range
    when provided.  Falls back to ``_DEFAULT_RADIUS`` for all points
    when ``size_col`` is ``None``.

    Args:
        data: Source DataFrame.
        size_col: Column for proportional sizing, or ``None`` for fixed.

    Returns:
        DataFrame copy with an appended ``_radius`` column.
    """
    plot_data = data.copy()
    if size_col is not None:
        plot_data[size_col] = pd.to_numeric(plot_data[size_col], errors="coerce")
        col_min = float(plot_data[size_col].min())
        col_max = float(plot_data[size_col].max())
        if col_max > col_min:
            normalized = (plot_data[size_col] - col_min) / (col_max - col_min)
            span = _MAX_RADIUS - _MIN_RADIUS
            plot_data["_radius"] = _MIN_RADIUS + normalized * span
        else:
            plot_data["_radius"] = (_MIN_RADIUS + _MAX_RADIUS) / 2
    else:
        plot_data["_radius"] = _DEFAULT_RADIUS
    return plot_data


def _to_records(data: pd.DataFrame) -> list[dict[str, object]]:
    """Convert DataFrame to JSON-safe records for PyDeck serialization.

    PyDeck 0.9.x's JSON encoder does not handle ``Decimal``, numpy
    ``int64``, or numpy ``float64``.  Round-tripping through pandas'
    JSON encoder ensures all values are native Python types.

    Args:
        data: Source DataFrame.

    Returns:
        List of row dicts with native Python values.
    """
    return json.loads(data.to_json(orient="records"))  # type: ignore[no-any-return]


def _build_tooltip(tooltip_cols: list[str] | None) -> dict[str, str] | None:
    """Build a PyDeck HTML tooltip template from column names.

    Args:
        tooltip_cols: Column names to display, or ``None`` to disable.

    Returns:
        Tooltip configuration dict, or ``None`` when disabled.
    """
    if not tooltip_cols:
        return None
    html_parts = [f"<b>{col}</b>: {{{col}}}" for col in tooltip_cols]
    return {"html": "<br/>".join(html_parts)}


def scatterplot_map(
    data: pd.DataFrame,
    lat_col: str,
    lon_col: str,
    size_col: str | None = None,
    color: list[int] | None = None,
    tooltip_cols: list[str] | None = None,
    zoom: int = 11,
    center_lat: float | None = None,
    center_lon: float | None = None,
) -> pydeck.Deck:
    """Build a ScatterplotLayer map for geographic point data.

    Renders points on a Carto DARK basemap with configurable size
    encoding, fill color, and hover tooltips.

    Args:
        data: Source DataFrame with latitude and longitude columns.
        lat_col: Column name containing latitude values.
        lon_col: Column name containing longitude values.
        size_col: Column for proportional point sizing.  When ``None``,
            all points render at a fixed 100-meter radius.
        color: RGBA color as ``[r, g, b, a]``.  Defaults to TTC red
            ``[218, 41, 28, 180]``.
        tooltip_cols: Column names to display in the hover tooltip.
        zoom: Initial map zoom level.
        center_lat: Viewport center latitude.  Auto-computed from data
            mean when ``None``.
        center_lon: Viewport center longitude.  Auto-computed from data
            mean when ``None``.

    Returns:
        A ``pydeck.Deck`` renderable via ``st.pydeck_chart``.
    """
    if color is None:
        color = _TTC_RED_RGBA

    plot_data = _compute_radius_column(data, size_col)
    lat_mean = float(plot_data[lat_col].mean())
    lon_mean = float(plot_data[lon_col].mean())
    view_lat = center_lat if center_lat is not None else lat_mean
    view_lon = center_lon if center_lon is not None else lon_mean

    layer = pydeck.Layer(
        "ScatterplotLayer",
        data=_to_records(plot_data),
        get_position=[lon_col, lat_col],
        get_radius="_radius",
        get_fill_color=color,
        pickable=True,
        radius_min_pixels=2,
    )

    return pydeck.Deck(
        layers=[layer],
        initial_view_state=pydeck.ViewState(
            latitude=view_lat,
            longitude=view_lon,
            zoom=zoom,
            pitch=0,
        ),
        map_style=pydeck.map_styles.DARK,
        tooltip=_build_tooltip(tooltip_cols),
    )
