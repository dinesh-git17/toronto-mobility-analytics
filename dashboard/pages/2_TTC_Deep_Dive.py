"""TTC Deep Dive — transit delay analysis by mode, station, and time."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from components.charts import bar_chart, heatmap, line_chart, treemap
from components.filters import date_range_filter, multiselect_filter
from components.maps import scatterplot_map
from components.metrics import render_metric_card
from data.cache import query_filtered, query_reference_data
from data.connection import get_connection
from data.queries import (
    reference_date_bounds,
    ttc_delay_causes,
    ttc_hourly_pattern,
    ttc_monthly_trend,
    ttc_station_delays,
)

_MODES: list[str] = ["subway", "bus", "streetcar"]

_MONTH_ABBR: list[str] = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
]

_DAY_ORDER: list[str] = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


# ---------------------------------------------------------------------------
# Insight computation helpers
# ---------------------------------------------------------------------------


def _bloor_yonge_share(df: pd.DataFrame) -> str:
    """Compute Bloor-Yonge's percentage of total subway delay minutes."""
    if df.empty:
        return "N/A"
    total = float(df["total_delay_minutes"].sum())
    if total <= 0:
        return "0%"
    mask = df["station_name"] == "Bloor-Yonge"
    by_delay = float(df.loc[mask, "total_delay_minutes"].sum())
    return f"{by_delay / total * 100:.1f}%"


def _operations_share(df: pd.DataFrame) -> str:
    """Compute Operations category's percentage of total incidents."""
    if df.empty:
        return "N/A"
    total = int(df["incident_count"].sum())
    if total <= 0:
        return "0%"
    mask = df["delay_category"] == "Operations"
    ops = int(df.loc[mask, "incident_count"].sum())
    return f"{ops / total * 100:.1f}%"


def _peak_window(df: pd.DataFrame) -> str | None:
    """Identify the day + hour with highest delay concentration.

    Returns ``None`` when fewer than 100 total delay records exist
    in the filtered result set.
    """
    if df.empty or int(df["delay_count"].sum()) < 100:
        return None
    peak_idx = df["delay_count"].idxmax()
    peak = df.loc[peak_idx]
    day = str(peak["day_of_week"])[:3]
    hour: int = int(peak["hour_of_day"])  # pyright: ignore[reportArgumentType]
    return f"{day} {hour}-{hour + 1}"


def _yoy_change(df: pd.DataFrame) -> str:
    """Compute year-over-year delay count percentage change."""
    if df.empty:
        return "N/A"
    yearly = df.groupby("year")["delay_count"].sum()
    if len(yearly) < 2:
        total = int(yearly.iloc[0]) if len(yearly) == 1 else 0
        return f"{total:,}"
    first_year = yearly.index.min()
    last_year = yearly.index.max()
    first_total = int(yearly[first_year])
    last_total = int(yearly[last_year])
    if first_total <= 0:
        return f"{last_total:,}"
    pct = (last_total - first_total) / first_total * 100
    arrow = "\u2191" if pct > 0 else "\u2193"
    return f"{arrow} {abs(pct):.0f}% since {first_year}"


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(page_title="TTC Deep Dive | Toronto Mobility", layout="wide")

_css = (Path(__file__).parent.parent / "styles" / "custom.css").read_text()
st.markdown(f"<style>{_css}</style>", unsafe_allow_html=True)

st.title("TTC Deep Dive")

# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------

conn = get_connection()
df_bounds = query_reference_data(reference_date_bounds(), conn)

if df_bounds.empty:
    st.error("Unable to load date range. Check Snowflake connection.")
    st.stop()

min_date = pd.Timestamp(df_bounds.iloc[0]["MIN_DATE"]).date()
max_date = pd.Timestamp(df_bounds.iloc[0]["MAX_DATE"]).date()

start_date, end_date = date_range_filter(min_date, max_date)
selected_modes = multiselect_filter("Transit Mode", _MODES, key="ttc_mode")

if not selected_modes:
    st.warning("Select at least one transit mode.")
    st.stop()

# ---------------------------------------------------------------------------
# Data fetching (10-minute filtered cache)
# ---------------------------------------------------------------------------

start_key = int(start_date.strftime("%Y%m%d"))
end_key = int(end_date.strftime("%Y%m%d"))
params: dict[str, int] = {"start_date": start_key, "end_date": end_key}

df_stations = query_filtered(ttc_station_delays(selected_modes), params, conn)
df_causes = query_filtered(ttc_delay_causes(selected_modes), params, conn)
df_hourly = query_filtered(ttc_hourly_pattern(selected_modes), params, conn)
df_trend = query_filtered(ttc_monthly_trend(selected_modes), params, conn)

for df in [df_stations, df_causes, df_hourly, df_trend]:
    df.columns = [c.lower() for c in df.columns]

# ---------------------------------------------------------------------------
# Section 1: Station map + worst stations bar chart
# ---------------------------------------------------------------------------

st.markdown("---")
col_map, col_bar = st.columns([3, 2])

with col_map:
    st.subheader("Delay Distribution by Station")
    if "subway" not in selected_modes:
        st.info("Station map available for subway mode only.")
    elif df_stations.empty:
        st.info("No data available for the selected filters.")
    else:
        map_data = df_stations.dropna(subset=["latitude", "longitude"])
        if map_data.empty:
            st.info("No station coordinates available.")
        else:
            st.pydeck_chart(
                scatterplot_map(
                    map_data,
                    lat_col="latitude",
                    lon_col="longitude",
                    size_col="total_delay_minutes",
                    tooltip_cols=[
                        "station_name",
                        "delay_count",
                        "total_delay_minutes",
                    ],
                    center_lat=43.6532,
                    center_lon=-79.3832,
                    zoom=11,
                )
            )

with col_bar:
    st.subheader("Top 10 Delay Stations")
    if df_stations.empty:
        st.info("No data available for the selected filters.")
    else:
        st.altair_chart(
            bar_chart(
                df_stations.head(10),
                x="station_name",
                y="total_delay_minutes",
                horizontal=True,
                title="",
            ),
            use_container_width=True,
        )

# ---------------------------------------------------------------------------
# Section 2: Treemap + heatmap
# ---------------------------------------------------------------------------

st.markdown("---")
col_tree, col_heat = st.columns(2)

with col_tree:
    st.subheader("Delay Causes")
    if df_causes.empty:
        st.info("No data available for the selected filters.")
    else:
        st.plotly_chart(
            treemap(
                df_causes,
                path_cols=["delay_category", "delay_description"],
                value_col="incident_count",
                color_col="total_delay_minutes",
            ),
            use_container_width=True,
        )

with col_heat:
    st.subheader("Delay Patterns by Hour and Day")
    if df_hourly.empty:
        st.info("No data available for the selected filters.")
    else:
        hourly = df_hourly.copy()
        hourly["hour_of_day"] = hourly["hour_of_day"].astype(int)
        st.altair_chart(
            heatmap(
                hourly,
                x="hour_of_day",
                y="day_of_week",
                color="delay_count",
                x_sort=[str(h) for h in range(24)],
                y_sort=_DAY_ORDER,
            ),
            use_container_width=True,
        )

# ---------------------------------------------------------------------------
# Section 3: Year-over-year trend
# ---------------------------------------------------------------------------

st.markdown("---")
st.subheader("Year-over-Year Trend")

if df_trend.empty:
    st.info("No data available for the selected filters.")
else:
    trend = df_trend.copy()
    trend["year"] = trend["year"].astype(str)
    trend["month_name"] = trend["month_name"].str[:3]
    trend["month_name"] = pd.Categorical(
        trend["month_name"], categories=_MONTH_ABBR, ordered=True
    )
    st.altair_chart(
        line_chart(
            trend,
            x="month_name",
            y="delay_count",
            color="year",
            title="Monthly Delay Incidents",
        ),
        use_container_width=True,
    )

# ---------------------------------------------------------------------------
# Section 4: Contextual insights
# ---------------------------------------------------------------------------

st.markdown("---")
ins_cols = st.columns(4)

with ins_cols[0]:
    render_metric_card(
        label="Bloor-Yonge Share",
        value=_bloor_yonge_share(df_stations),
        border_variant="ttc",
    )

with ins_cols[1]:
    render_metric_card(
        label="Operations Dominance",
        value=_operations_share(df_causes),
        border_variant="ttc",
    )

with ins_cols[2]:
    peak = _peak_window(df_hourly)
    if peak is not None:
        render_metric_card(
            label="Peak Delay Time",
            value=peak,
            border_variant="ttc",
        )
    else:
        st.empty()

with ins_cols[3]:
    render_metric_card(
        label="Year-over-Year",
        value=_yoy_change(df_trend),
        border_variant="ttc",
    )
