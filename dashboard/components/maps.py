"""PyDeck map builder functions for geographic visualizations.

Provides builder functions that return ``pydeck.Deck`` objects
renderable via ``st.pydeck_chart()``.
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
import pydeck
from pydeck.data_utils import compute_view

_TTC_RED_RGBA: list[int] = [218, 41, 28, 180]
_DEFAULT_RADIUS: int = 100
_MIN_RADIUS: int = 50
_MAX_RADIUS: int = 500

_BIKE_GREEN_GRADIENT: list[list[int]] = [
    [236, 252, 235],
    [134, 239, 172],
    [67, 176, 42],
    [22, 101, 52],
]

STATION_COLORS: dict[str, list[int]] = {
    "TTC_SUBWAY": [218, 41, 28, 180],
    "BIKE_SHARE": [67, 176, 42, 180],
    "SELECTED": [37, 99, 235, 220],
}

STATION_HEX_COLORS: dict[str, str] = {
    "TTC_SUBWAY": "#DA291C",
    "BIKE_SHARE": "#43B02A",
    "SELECTED": "#2563EB",
}

STATION_TYPE_LABELS: dict[str, str] = {
    "TTC_SUBWAY": "TTC Subway",
    "BIKE_SHARE": "Bike Share",
}


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
        tooltip=_build_tooltip(tooltip_cols),  # pyright: ignore[reportArgumentType]
    )


def heatmap_map(
    data: pd.DataFrame,
    lat_col: str,
    lon_col: str,
    weight_col: str | None = None,
    radius: int = 200,
    color_range: list[list[int]] | None = None,
    opacity: float = 0.8,
    zoom: int = 11,
    center_lat: float | None = None,
    center_lon: float | None = None,
) -> pydeck.Deck:
    """Build a HeatmapLayer map for geographic density visualization.

    Renders point-density data on a Carto DARK basemap with configurable
    weight encoding, green color gradient, and influence radius.

    Args:
        data: Source DataFrame with latitude and longitude columns.
        lat_col: Column name containing latitude values.
        lon_col: Column name containing longitude values.
        weight_col: Column for point contribution weight.  When ``None``,
            all points contribute equally with a uniform weight of 1.
        radius: Influence radius of each point in meters.
        color_range: Color gradient as a list of ``[r, g, b]`` stops.
            Defaults to a Bike Share green gradient.
        opacity: Overall layer opacity from 0.0 to 1.0.
        zoom: Initial map zoom level.
        center_lat: Viewport center latitude.  Auto-computed from data
            mean when ``None``.
        center_lon: Viewport center longitude.  Auto-computed from data
            mean when ``None``.

    Returns:
        A ``pydeck.Deck`` renderable via ``st.pydeck_chart``.
    """
    if color_range is None:
        color_range = _BIKE_GREEN_GRADIENT

    plot_data = data.copy()
    if weight_col is None:
        plot_data["_weight"] = 1
        weight_field = "_weight"
    else:
        weight_field = weight_col

    records = _to_records(plot_data)

    lat_mean = float(plot_data[lat_col].mean())
    lon_mean = float(plot_data[lon_col].mean())
    view_lat = center_lat if center_lat is not None else lat_mean
    view_lon = center_lon if center_lon is not None else lon_mean

    layer = pydeck.Layer(
        "HeatmapLayer",
        data=records,
        get_position=[lon_col, lat_col],
        get_weight=weight_field,
        color_range=color_range,
        radius_pixels=radius,
        opacity=opacity,
        aggregation="SUM",
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
    )


def station_focus_map(
    selected_station: dict[str, Any] | list[dict[str, Any]],
    nearby_stations: pd.DataFrame,
    *,
    lat_col: str = "latitude",
    lon_col: str = "longitude",
    type_col: str = "station_type",
    zoom: int = 14,
) -> pydeck.Deck:
    """Build a multi-layer station focus map with selection highlight.

    Renders one to three selected stations as blue highlight markers
    surrounded by type-colored nearby station markers on a dark basemap.

    Single-station mode centers the viewport on the selected station at
    the specified zoom level.  Multi-station mode auto-computes the
    viewport to frame all selected stations.

    Args:
        selected_station: Station dict or list of up to 3 station dicts.
            Each dict must contain keys matching ``lat_col`` and
            ``lon_col``.
        nearby_stations: DataFrame of nearby stations with coordinate,
            type, and ``distance_km`` columns produced by
            ``find_nearby_stations()``.
        lat_col: Column name for latitude values.
        lon_col: Column name for longitude values.
        type_col: Column name for station type values.
        zoom: Initial zoom level for single-station mode.

    Returns:
        A ``pydeck.Deck`` renderable via ``st.pydeck_chart()``.

    Raises:
        ValueError: When more than 3 stations are provided.
    """
    stations: list[dict[str, Any]] = (
        [selected_station]
        if isinstance(selected_station, dict)
        else list(selected_station)
    )
    if len(stations) > 3:
        msg = f"Maximum 3 stations supported, received {len(stations)}"
        raise ValueError(msg)

    multi_mode = len(stations) > 1
    highlight_radius = 120 if multi_mode else 150

    selected_records = _to_records(pd.DataFrame(stations))

    selected_layer = pydeck.Layer(
        "ScatterplotLayer",
        data=selected_records,
        get_position=[lon_col, lat_col],
        get_radius=highlight_radius,
        get_fill_color=STATION_COLORS["SELECTED"],
        pickable=False,
        radius_min_pixels=6,
    )

    layers: list[pydeck.Layer] = [selected_layer]

    if not nearby_stations.empty:
        plot_data = nearby_stations.copy()

        if "station_key" in plot_data.columns:
            plot_data = plot_data.drop_duplicates(subset="station_key")

        color_map: dict[str, list[int]] = {
            "TTC_SUBWAY": STATION_COLORS["TTC_SUBWAY"],
            "BIKE_SHARE": STATION_COLORS["BIKE_SHARE"],
        }
        fallback_color: list[int] = [160, 160, 160, 180]
        plot_data["_color"] = plot_data[type_col].map(color_map)
        plot_data["_color"] = plot_data["_color"].apply(
            lambda c: c if isinstance(c, list) else fallback_color
        )

        max_dist = float(plot_data["distance_km"].max())
        if max_dist > 0:
            plot_data["_radius"] = plot_data["distance_km"].apply(
                lambda d: max(60.0, min(80.0, 80.0 - (float(d) / max_dist) * 20.0))
            )
        else:
            plot_data["_radius"] = 80

        plot_data["_type_label"] = (
            plot_data[type_col].map(STATION_TYPE_LABELS).fillna("Station")
        )

        nearby_layer = pydeck.Layer(
            "ScatterplotLayer",
            data=_to_records(plot_data),
            get_position=[lon_col, lat_col],
            get_radius="_radius",
            get_fill_color="_color",
            pickable=True,
            radius_min_pixels=3,
        )
        layers.append(nearby_layer)

    if multi_mode:
        coords = [[float(s[lon_col]), float(s[lat_col])] for s in stations]
        view_state = compute_view(coords, view_proportion=0.9)  # pyright: ignore[reportArgumentType]
        view_state.pitch = 0
    else:
        view_state = pydeck.ViewState(
            latitude=float(stations[0][lat_col]),
            longitude=float(stations[0][lon_col]),
            zoom=zoom,
            pitch=0,
        )

    tooltip: dict[str, str] | None = None
    if not nearby_stations.empty:
        tooltip = {
            "html": ("<b>{station_name}</b><br/>{_type_label}<br/>{distance_km} km"),
        }

    return pydeck.Deck(
        layers=layers,
        initial_view_state=view_state,
        map_style=pydeck.map_styles.DARK,
        tooltip=tooltip,  # pyright: ignore[reportArgumentType]
    )
