"""Station Explorer — interactive station-level geographic drill-down.

Assembles sidebar controls, PyDeck station focus map, conditional
metric cards, timeline charts, nearby stations table, and optional
station comparison panels into the fifth dashboard page.
"""

from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
from utils.geo import find_nearby_stations

from components.charts import line_chart
from components.filters import date_range_filter
from components.maps import STATION_TYPE_LABELS, station_focus_map
from components.metrics import render_metric_card, render_metric_row
from data.cache import query_filtered, query_reference_data
from data.connection import get_connection
from data.queries import (
    bike_station_activity,
    reference_date_bounds,
    reference_stations,
    station_delay_metrics,
    station_delay_timeline,
    station_trip_metrics,
    station_trip_timeline,
    ttc_station_delays,
)

_COMPARISON_COLORS: list[str] = ["#2563EB", "#334155", "#F59E0B"]

_TYPE_MAP: dict[str, str] = {
    "TTC Subway": "TTC_SUBWAY",
    "Bike Share": "BIKE_SHARE",
}


# ---------------------------------------------------------------------------
# S002: Station summary metric cards
# ---------------------------------------------------------------------------


def render_station_metrics(
    station_type: str,
    metrics_df: pd.DataFrame,
    *,
    timeline_df: pd.DataFrame | None = None,
    neighborhood: str = "N/A",
) -> None:
    """Render type-conditional station summary metric cards.

    TTC subway stations display delay-centric metrics with red border.
    Bike Share stations display trip-centric metrics with green border.

    Args:
        station_type: ``TTC_SUBWAY`` or ``BIKE_SHARE``.
        metrics_df: Single-row result from ``station_delay_metrics()``
            or ``station_trip_metrics()``.
        timeline_df: Result from ``station_trip_timeline()`` used to
            derive the busiest month for Bike Share stations.
        neighborhood: Station neighborhood from reference data.
    """
    st.subheader("Station Metrics")

    if station_type == "TTC_SUBWAY":
        _render_ttc_metrics(metrics_df)
    else:
        _render_bike_metrics(metrics_df, timeline_df, neighborhood)


def _render_ttc_metrics(df: pd.DataFrame) -> None:
    """Build 4 TTC delay metric cards from query result."""
    if df.empty:
        values = ("0", "0", "0 min", "N/A")
    else:
        row = df.iloc[0]
        top_cause = (
            str(row["top_delay_category"])
            if pd.notna(row.get("top_delay_category"))
            else "N/A"
        )
        values = (
            f"{int(row['delay_count']):,}",
            f"{int(row['total_delay_minutes']):,}",
            f"{float(row['avg_delay_minutes']):.1f} min",
            top_cause,
        )

    render_metric_row(
        [
            {"label": "Delay Incidents", "value": values[0], "border_variant": "ttc"},
            {
                "label": "Total Delay Minutes",
                "value": values[1],
                "border_variant": "ttc",
            },
            {"label": "Avg Delay", "value": values[2], "border_variant": "ttc"},
            {"label": "Top Cause", "value": values[3], "border_variant": "ttc"},
        ]
    )


def _render_bike_metrics(
    metrics_df: pd.DataFrame,
    timeline_df: pd.DataFrame | None,
    neighborhood: str,
) -> None:
    """Build 4 Bike Share trip metric cards from query result."""
    if metrics_df.empty:
        trip_count = "0"
        avg_duration = "0 min"
    else:
        row = metrics_df.iloc[0]
        trip_count = f"{int(row['trip_count']):,}"
        avg_duration = f"{float(row['avg_duration_minutes']):.1f} min"

    busiest = "N/A"
    if timeline_df is not None and not timeline_df.empty:
        peak_idx = int(timeline_df["trip_count"].idxmax())
        peak = timeline_df.loc[peak_idx]
        busiest = f"{peak['month_name']} {int(peak['year'])}"  # pyright: ignore[reportArgumentType]

    render_metric_row(
        [
            {"label": "Total Trips", "value": trip_count, "border_variant": "bike"},
            {"label": "Avg Duration", "value": avg_duration, "border_variant": "bike"},
            {"label": "Busiest Month", "value": busiest, "border_variant": "bike"},
            {"label": "Neighborhood", "value": neighborhood, "border_variant": "bike"},
        ]
    )


# ---------------------------------------------------------------------------
# S003: Conditional detail timeline charts
# ---------------------------------------------------------------------------


def _build_timeline_period(df: pd.DataFrame) -> pd.DataFrame:
    """Add YYYY-MM period column for chronological ordering."""
    result = df.copy()
    result["period"] = (
        result["year"].astype(str) + "-" + result["month_num"].astype(str).str.zfill(2)
    )
    return result


def render_station_timeline(
    station_type: str,
    timeline_df: pd.DataFrame,
) -> None:
    """Render monthly timeline chart adapted to station type.

    TTC stations display a delay count line chart with 'Delay History'
    heading.  Bike Share stations display a trip count line chart with
    'Trip History' heading.

    Args:
        station_type: ``TTC_SUBWAY`` or ``BIKE_SHARE``.
        timeline_df: Monthly aggregation from ``station_delay_timeline()``
            or ``station_trip_timeline()``.
    """
    if station_type == "TTC_SUBWAY":
        heading = "Delay History"
        y_col = "delay_count"
        y_title = "Delay Incidents"
    else:
        heading = "Trip History"
        y_col = "trip_count"
        y_title = "Trips"

    st.subheader(heading)

    if timeline_df.empty:
        st.info("No data recorded for this station in the selected period.")
        return

    plot_df = _build_timeline_period(timeline_df)
    plot_df = plot_df.rename(columns={"period": "Month", y_col: y_title})

    st.altair_chart(
        line_chart(plot_df, x="Month", y=y_title),
        use_container_width=True,
    )


# ---------------------------------------------------------------------------
# S004: Nearby stations sortable table
# ---------------------------------------------------------------------------


def _enrich_nearby_activity(
    nearby_df: pd.DataFrame,
    ttc_activity_df: pd.DataFrame | None,
    bike_activity_df: pd.DataFrame | None,
) -> pd.DataFrame:
    """Merge activity metrics and format table for display."""
    df = nearby_df.copy()
    df["activity"] = "\u2014"

    if ttc_activity_df is not None and not ttc_activity_df.empty:
        ttc_lookup = ttc_activity_df.drop_duplicates(subset="station_name").set_index(
            "station_name"
        )["delay_count"]
        ttc_mask = df["station_type"] == "TTC_SUBWAY"
        df.loc[ttc_mask, "activity"] = (
            df.loc[ttc_mask, "station_name"]
            .map(ttc_lookup)
            .apply(lambda v: f"{int(v):,} delays" if pd.notna(v) else "\u2014")
        )

    if bike_activity_df is not None and not bike_activity_df.empty:
        bike_lookup = bike_activity_df.drop_duplicates(subset="station_name").set_index(
            "station_name"
        )["trip_count"]
        bike_mask = df["station_type"] == "BIKE_SHARE"
        df.loc[bike_mask, "activity"] = (
            df.loc[bike_mask, "station_name"]
            .map(bike_lookup)
            .apply(lambda v: f"{int(v):,} trips" if pd.notna(v) else "\u2014")
        )

    type_labels = df["station_type"].map(STATION_TYPE_LABELS).fillna("Station")

    return pd.DataFrame(
        {
            "Rank": range(1, len(df) + 1),
            "Station": df["station_name"].values,
            "Type": type_labels.values,
            "Distance (km)": df["distance_km"].values,
            "Activity": df["activity"].values,
        }
    )


def render_nearby_table(
    nearby_df: pd.DataFrame,
    *,
    ttc_activity_df: pd.DataFrame | None = None,
    bike_activity_df: pd.DataFrame | None = None,
) -> None:
    """Render nearby stations table with distance and activity metrics.

    Displays up to 10 nearest stations ranked by proximity. Activity
    metrics are enriched from pre-fetched page-level aggregation
    DataFrames to avoid per-station Snowflake queries.

    Args:
        nearby_df: Result from ``find_nearby_stations()`` with
            ``distance_km`` column.
        ttc_activity_df: Station-level delay counts from
            ``ttc_station_delays()`` for TTC activity enrichment.
        bike_activity_df: Station-level trip counts from
            ``bike_station_activity()`` for Bike Share enrichment.
    """
    st.subheader("Nearby Stations")

    if nearby_df.empty:
        st.info("No nearby stations found.")
        return

    display_df = _enrich_nearby_activity(nearby_df, ttc_activity_df, bike_activity_df)

    st.dataframe(display_df, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# S005: Station comparison panels
# ---------------------------------------------------------------------------


def render_comparison_metrics(
    station_names: list[str],
    metrics_dfs: list[pd.DataFrame],
    station_type: str,
    *,
    timelines: list[pd.DataFrame] | None = None,
    neighborhoods: list[str] | None = None,
) -> None:
    """Render side-by-side metric cards for 2-3 comparison stations.

    Each station renders in its own column with a name heading and
    vertically stacked metric cards appropriate to the station type.

    Args:
        station_names: Display names for each station.
        metrics_dfs: Per-station results from ``station_delay_metrics()``
            or ``station_trip_metrics()``.
        station_type: ``TTC_SUBWAY`` or ``BIKE_SHARE``.
        timelines: Per-station timeline DataFrames for Bike Share
            busiest month derivation.
        neighborhoods: Per-station neighborhood names from reference data.
    """
    cols = st.columns(len(station_names))

    for i, col in enumerate(cols):
        with col:
            st.subheader(station_names[i])
            df = metrics_dfs[i]

            if df.empty:
                st.info("No data for the selected period.")
                continue

            variant = "ttc" if station_type == "TTC_SUBWAY" else "bike"

            if station_type == "TTC_SUBWAY":
                _render_comparison_ttc_card(df, variant)
            else:
                tl = timelines[i] if timelines else None
                nb = neighborhoods[i] if neighborhoods else "N/A"
                _render_comparison_bike_card(df, tl, nb, variant)


def _render_comparison_ttc_card(df: pd.DataFrame, variant: str) -> None:
    """Render TTC metric cards vertically within a comparison column."""
    row = df.iloc[0]
    top_cause = (
        str(row["top_delay_category"])
        if pd.notna(row.get("top_delay_category"))
        else "N/A"
    )
    render_metric_card(
        "Delay Incidents", f"{int(row['delay_count']):,}", border_variant=variant
    )
    render_metric_card(
        "Total Minutes",
        f"{int(row['total_delay_minutes']):,}",
        border_variant=variant,
    )
    render_metric_card(
        "Avg Delay",
        f"{float(row['avg_delay_minutes']):.1f} min",
        border_variant=variant,
    )
    render_metric_card("Top Cause", top_cause, border_variant=variant)


def _render_comparison_bike_card(
    df: pd.DataFrame,
    timeline_df: pd.DataFrame | None,
    neighborhood: str,
    variant: str,
) -> None:
    """Render Bike Share metric cards vertically within a comparison column."""
    row = df.iloc[0]
    busiest = "N/A"
    if timeline_df is not None and not timeline_df.empty:
        peak_idx = int(timeline_df["trip_count"].idxmax())
        peak = timeline_df.loc[peak_idx]
        busiest = f"{peak['month_name']} {int(peak['year'])}"  # pyright: ignore[reportArgumentType]

    render_metric_card(
        "Total Trips", f"{int(row['trip_count']):,}", border_variant=variant
    )
    render_metric_card(
        "Avg Duration",
        f"{float(row['avg_duration_minutes']):.1f} min",
        border_variant=variant,
    )
    render_metric_card("Busiest Month", busiest, border_variant=variant)
    render_metric_card("Neighborhood", neighborhood, border_variant=variant)


def render_comparison_timeline(
    station_names: list[str],
    timelines: list[pd.DataFrame],
    station_type: str,
) -> None:
    """Render overlaid timeline chart for comparison stations.

    Concatenates per-station timelines and plots with explicit color
    assignment: primary blue, neutral slate, warning amber.

    Args:
        station_names: Display names for each station (determines color
            assignment by position).
        timelines: Per-station timeline DataFrames.
        station_type: ``TTC_SUBWAY`` or ``BIKE_SHARE``.
    """
    if station_type == "TTC_SUBWAY":
        y_col = "delay_count"
        y_title = "Delay Incidents"
    else:
        y_col = "trip_count"
        y_title = "Trips"

    parts: list[pd.DataFrame] = []
    for name, tl in zip(station_names, timelines, strict=True):
        if tl.empty:
            continue
        part = _build_timeline_period(tl)
        part = part.assign(station_name=name)
        parts.append(part)

    if not parts:
        st.info("No data recorded for the selected stations in the selected period.")
        return

    combined = pd.concat(parts, ignore_index=True)

    present = set(combined["station_name"].unique())
    domain = [n for n in station_names if n in present]
    palette = [_COMPARISON_COLORS[station_names.index(n)] for n in domain]

    chart = (
        alt.Chart(combined)
        .mark_line(point=True)
        .encode(
            x=alt.X("period:O", axis=alt.Axis(title="Month")),
            y=alt.Y(f"{y_col}:Q", axis=alt.Axis(title=y_title)),
            color=alt.Color(
                "station_name:N",
                scale=alt.Scale(domain=domain, range=palette),
                title="Station",
            ),
        )
        .properties(width="container")
    )

    st.altair_chart(chart, use_container_width=True)


# ---------------------------------------------------------------------------
# Page composition (E-1403)
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Station Explorer | Toronto Mobility", layout="wide")

_css = (Path(__file__).parent.parent / "styles" / "custom.css").read_text()
st.markdown(f"<style>{_css}</style>", unsafe_allow_html=True)

st.title("Station Explorer")

# ---------------------------------------------------------------------------
# Sidebar controls
# ---------------------------------------------------------------------------

conn = get_connection()

df_bounds = query_reference_data(reference_date_bounds(), conn)
if df_bounds.empty:
    st.error("Unable to load date range. Check Snowflake connection.")
    st.stop()

min_date = pd.Timestamp(df_bounds.iloc[0]["MIN_DATE"]).date()
max_date = pd.Timestamp(df_bounds.iloc[0]["MAX_DATE"]).date()

df_all_stations = query_reference_data(reference_stations(), conn)
df_all_stations.columns = [c.lower() for c in df_all_stations.columns]

if df_all_stations.empty:
    st.error("No stations available.")
    st.stop()

type_label: str = st.sidebar.radio(
    "Station Type",
    options=["TTC Subway", "Bike Share"],
    key="station_type",
)
station_type = _TYPE_MAP[type_label]

type_stations = (
    df_all_stations.loc[
        (df_all_stations["station_type"] == station_type)
        & (df_all_stations["station_id"] != "ST_000")
    ]
    .sort_values("station_name")
    .reset_index(drop=True)
)

if type_stations.empty:
    st.error("No stations available for the selected type.")
    st.stop()

station_names: list[str] = type_stations["station_name"].tolist()

selected_name: str = st.sidebar.selectbox(
    "Search Station",
    options=station_names,
    key=f"station_select_{station_type}",
)

start_date, end_date = date_range_filter(min_date, max_date, key="explorer_date_range")

comparison_options = [n for n in station_names if n != selected_name]
comparison_names: list[str] = st.sidebar.multiselect(
    "Compare Stations",
    options=comparison_options,
    max_selections=2,
    key=f"compare_{station_type}",
)

# ---------------------------------------------------------------------------
# Station resolution and data preparation
# ---------------------------------------------------------------------------

selected_row = type_stations.loc[type_stations["station_name"] == selected_name].iloc[0]
station_key = str(selected_row["station_key"])

start_key = int(start_date.strftime("%Y%m%d"))
end_key = int(end_date.strftime("%Y%m%d"))
params: dict[str, int | str] = {
    "station_key": station_key,
    "start_date": start_key,
    "end_date": end_key,
}

nearby_df = find_nearby_stations(
    float(selected_row["latitude"]),
    float(selected_row["longitude"]),
    df_all_stations,
    n=10,
    exclude_key=station_key,
)

selected_dict = {
    "latitude": float(selected_row["latitude"]),
    "longitude": float(selected_row["longitude"]),
    "station_name": selected_name,
    "station_type": station_type,
    "station_key": station_key,
}

map_stations = selected_dict
if comparison_names:
    all_selected = [selected_dict]
    for cname in comparison_names:
        crow = type_stations.loc[type_stations["station_name"] == cname].iloc[0]
        all_selected.append(
            {
                "latitude": float(crow["latitude"]),
                "longitude": float(crow["longitude"]),
                "station_name": cname,
                "station_type": station_type,
                "station_key": str(crow["station_key"]),
            }
        )
    map_stations = all_selected  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Section 1: Station map
# ---------------------------------------------------------------------------

st.markdown("---")
st.subheader("Station Location")
st.pydeck_chart(station_focus_map(map_stations, nearby_df))

# ---------------------------------------------------------------------------
# Section 2: Station metrics
# ---------------------------------------------------------------------------

if station_type == "TTC_SUBWAY":
    df_metrics = query_filtered(station_delay_metrics(), params, conn)
    df_timeline = query_filtered(station_delay_timeline(), params, conn)
else:
    df_metrics = query_filtered(station_trip_metrics(), params, conn)
    df_timeline = query_filtered(station_trip_timeline(), params, conn)

for _df in [df_metrics, df_timeline]:
    _df.columns = [c.lower() for c in _df.columns]

st.markdown("---")
_nb = selected_row["neighborhood"]
neighborhood = str(_nb) if pd.notna(_nb) else "N/A"

render_station_metrics(
    station_type,
    df_metrics,
    timeline_df=df_timeline if station_type == "BIKE_SHARE" else None,
    neighborhood=neighborhood,
)

# ---------------------------------------------------------------------------
# Section 3: Timeline chart
# ---------------------------------------------------------------------------

st.markdown("---")
render_station_timeline(station_type, df_timeline)

# ---------------------------------------------------------------------------
# Section 4: Nearby stations table
# ---------------------------------------------------------------------------

st.markdown("---")

date_params: dict[str, int] = {"start_date": start_key, "end_date": end_key}
ttc_activity: pd.DataFrame | None = None
bike_activity: pd.DataFrame | None = None

if not nearby_df.empty:
    if nearby_df["station_type"].eq("TTC_SUBWAY").any():
        _ttc_df = query_filtered(ttc_station_delays(["subway"]), date_params, conn)
        _ttc_df.columns = [c.lower() for c in _ttc_df.columns]
        ttc_activity = _ttc_df

    if nearby_df["station_type"].eq("BIKE_SHARE").any():
        _bike_df = query_filtered(
            bike_station_activity(["Annual Member", "Casual Member"]),
            date_params,
            conn,
        )
        _bike_df.columns = [c.lower() for c in _bike_df.columns]
        bike_activity = _bike_df

render_nearby_table(
    nearby_df,
    ttc_activity_df=ttc_activity,
    bike_activity_df=bike_activity,
)

# ---------------------------------------------------------------------------
# Section 5: Station comparison (conditional)
# ---------------------------------------------------------------------------

if comparison_names:
    st.markdown("---")
    st.subheader("Station Comparison")

    all_names = [selected_name, *comparison_names]
    all_metrics: list[pd.DataFrame] = [df_metrics]
    all_timelines: list[pd.DataFrame] = [df_timeline]
    all_neighborhoods: list[str] = [neighborhood]

    for cname in comparison_names:
        crow = type_stations.loc[type_stations["station_name"] == cname].iloc[0]
        cparams: dict[str, int | str] = {
            "station_key": str(crow["station_key"]),
            "start_date": start_key,
            "end_date": end_key,
        }

        if station_type == "TTC_SUBWAY":
            _cm = query_filtered(station_delay_metrics(), cparams, conn)
            _ct = query_filtered(station_delay_timeline(), cparams, conn)
        else:
            _cm = query_filtered(station_trip_metrics(), cparams, conn)
            _ct = query_filtered(station_trip_timeline(), cparams, conn)

        _cm.columns = [c.lower() for c in _cm.columns]
        _ct.columns = [c.lower() for c in _ct.columns]

        all_metrics.append(_cm)
        all_timelines.append(_ct)

        _cnb = crow["neighborhood"]
        all_neighborhoods.append(str(_cnb) if pd.notna(_cnb) else "N/A")

    render_comparison_metrics(
        all_names,
        all_metrics,
        station_type,
        timelines=all_timelines if station_type == "BIKE_SHARE" else None,
        neighborhoods=(all_neighborhoods if station_type == "BIKE_SHARE" else None),
    )

    st.markdown("---")
    render_comparison_timeline(all_names, all_timelines, station_type)

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.markdown("---")
st.caption(f"Data coverage: {min_date} to {max_date}")
