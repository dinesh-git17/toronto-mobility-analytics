"""Bike Share Deep Dive — ridership geography, growth, and composition."""

from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from components.charts import area_chart, bar_chart, line_chart
from components.filters import date_range_filter, multiselect_filter
from components.maps import heatmap_map
from components.metrics import render_metric_card
from data.cache import query_filtered, query_reference_data
from data.connection import get_connection
from data.queries import (
    bike_monthly_seasonality,
    bike_station_activity,
    bike_yearly_summary,
    reference_date_bounds,
)

_USER_TYPES: list[str] = ["Annual Member", "Casual Member"]

_MONTH_ORDER: list[str] = [
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


# ---------------------------------------------------------------------------
# Insight computation helpers
# ---------------------------------------------------------------------------


def _select_trip_column(selected_types: list[str]) -> str:
    """Determine trip count column based on selected user types."""
    if len(selected_types) == 2:
        return "total_trips"
    if "Annual Member" in selected_types:
        return "member_trips"
    return "casual_trips"


def _casual_share(df_yearly: pd.DataFrame) -> str:
    """Compute casual rider share for the most recent year."""
    if df_yearly.empty:
        return "N/A"
    latest = df_yearly.iloc[-1]
    total = int(latest["total_trips"])
    if total <= 0:
        return "N/A"
    casual = int(latest["casual_trips"])
    year = int(latest["year"])
    pct = casual / total * 100
    return f"{pct:.0f}% in {year}"


def _summer_winter_ratio(df_monthly: pd.DataFrame) -> str:
    """Compute summer (Jul+Aug) to winter (Jan+Feb) trip ratio."""
    if df_monthly.empty:
        return "N/A"
    winter = df_monthly.loc[df_monthly["month_num"].isin([1, 2]), "total_trips"]
    summer = df_monthly.loc[df_monthly["month_num"].isin([7, 8]), "total_trips"]
    winter_avg = float(winter.mean()) if not winter.empty else 0.0
    summer_avg = float(summer.mean()) if not summer.empty else 0.0
    if winter_avg <= 0:
        return "N/A"
    ratio = summer_avg / winter_avg
    return f"{ratio:.1f}x"


def _top_station(df_stations: pd.DataFrame) -> str:
    """Extract the station with the highest trip count."""
    if df_stations.empty:
        return "N/A"
    row = df_stations.iloc[0]
    name = str(row["station_name"])
    count = int(row["trip_count"])
    return f"{name}: {count:,}"


def _avg_trip_duration(df_yearly: pd.DataFrame) -> str:
    """Compute average trip duration in minutes from yearly summary."""
    if df_yearly.empty:
        return "N/A"
    total_trips = int(df_yearly["total_trips"].sum())
    if total_trips <= 0:
        return "N/A"
    total_seconds = int(df_yearly["total_duration_seconds"].sum())
    minutes = total_seconds / total_trips / 60
    return f"{minutes:.0f} min"


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Bike Share | Toronto Mobility", layout="wide")

_css = (Path(__file__).parent.parent / "styles" / "custom.css").read_text()
st.markdown(f"<style>{_css}</style>", unsafe_allow_html=True)

st.title("Bike Share Deep Dive")

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

start_date, end_date = date_range_filter(min_date, max_date, key="bike_date_range")
selected_types = multiselect_filter(
    "User Type",
    _USER_TYPES,
    key="bike_user_type",
)

if not selected_types:
    st.warning("Select at least one user type.")
    st.stop()

# ---------------------------------------------------------------------------
# Data fetching (10-minute filtered cache)
# ---------------------------------------------------------------------------

start_key = int(start_date.strftime("%Y%m%d"))
end_key = int(end_date.strftime("%Y%m%d"))
params: dict[str, int] = {"start_date": start_key, "end_date": end_key}

df_stations = query_filtered(
    bike_station_activity(selected_types),
    params,
    conn,
)
df_yearly = query_filtered(bike_yearly_summary(), params, conn)
df_monthly = query_filtered(bike_monthly_seasonality(), params, conn)

for df in [df_stations, df_yearly, df_monthly]:
    df.columns = [c.lower() for c in df.columns]

trip_col = _select_trip_column(selected_types)

# ---------------------------------------------------------------------------
# Section 1: Station heatmap + yearly growth area chart
# ---------------------------------------------------------------------------

st.markdown("---")
col_map, col_growth = st.columns([3, 2])

with col_map:
    st.subheader("Station Activity")
    if df_stations.empty:
        st.info("No data available for the selected filters.")
    else:
        map_data = df_stations.dropna(subset=["latitude", "longitude"])
        if map_data.empty:
            st.info("No station coordinates available.")
        else:
            st.pydeck_chart(
                heatmap_map(
                    map_data,
                    lat_col="latitude",
                    lon_col="longitude",
                    weight_col="trip_count",
                    center_lat=43.6532,
                    center_lon=-79.3832,
                    zoom=12,
                    radius=200,
                ),
            )

with col_growth:
    st.subheader("Ridership Growth")
    if df_yearly.empty:
        st.info("No data available for the selected filters.")
    else:
        yearly_chart = df_yearly.copy()
        yearly_chart["year"] = yearly_chart["year"].astype(str)
        st.altair_chart(
            area_chart(yearly_chart, x="year", y=trip_col, title=""),
            use_container_width=True,
        )

# ---------------------------------------------------------------------------
# Section 2: Stacked bar + seasonality overlay
# ---------------------------------------------------------------------------

st.markdown("---")
col_stack, col_season = st.columns(2)

with col_stack:
    st.subheader("Member vs Casual Riders")
    if df_yearly.empty:
        st.info("No data available for the selected filters.")
    else:
        df_melt = df_yearly.melt(
            id_vars=["year"],
            value_vars=["member_trips", "casual_trips"],
            var_name="user_type",
            value_name="trip_count",
        )
        df_melt["user_type"] = df_melt["user_type"].map(
            {"member_trips": "Annual Member", "casual_trips": "Casual Member"},
        )
        df_melt["year"] = df_melt["year"].astype(str)

        stacked = bar_chart(
            df_melt,
            x="year",
            y="trip_count",
            color="user_type",
            stack=True,
            title="",
        )
        stacked = stacked.encode(
            color=alt.Color(
                "user_type:N",
                scale=alt.Scale(
                    domain=["Annual Member", "Casual Member"],
                    range=["#43B02A", "#334155"],
                ),
            ),
        )
        st.altair_chart(stacked, use_container_width=True)

with col_season:
    st.subheader("Seasonal Ridership Patterns")
    if df_monthly.empty:
        st.info("No data available for the selected filters.")
    else:
        season = df_monthly.copy()
        season["year"] = season["year"].astype(str)
        season["month_name"] = season["month_name"].str[:3]
        season["month_name"] = pd.Categorical(
            season["month_name"],
            categories=_MONTH_ORDER,
            ordered=True,
        )
        st.altair_chart(
            line_chart(
                season,
                x="month_name",
                y=trip_col,
                color="year",
                title="",
            ),
            use_container_width=True,
        )

# ---------------------------------------------------------------------------
# Section 3: Top 20 stations table
# ---------------------------------------------------------------------------

st.markdown("---")
st.subheader("Top 20 Stations")

if df_stations.empty:
    st.info("No data available for the selected filters.")
else:
    top_20 = df_stations.head(20).rename(
        columns={
            "station_name": "Station",
            "neighborhood": "Neighborhood",
            "trip_count": "Trips",
        },
    )[["Station", "Neighborhood", "Trips"]]
    st.dataframe(
        top_20.style.format({"Trips": "{:,}"}),
        use_container_width=True,
        hide_index=True,
    )

# ---------------------------------------------------------------------------
# Section 4: Contextual insights
# ---------------------------------------------------------------------------

st.markdown("---")
ins_cols = st.columns(4)

with ins_cols[0]:
    render_metric_card(
        label="Casual Share",
        value=_casual_share(df_yearly),
        border_variant="bike",
    )

with ins_cols[1]:
    render_metric_card(
        label="Summer vs Winter",
        value=_summer_winter_ratio(df_monthly),
        border_variant="bike",
    )

with ins_cols[2]:
    render_metric_card(
        label="Top Station",
        value=_top_station(df_stations),
        border_variant="bike",
    )

with ins_cols[3]:
    render_metric_card(
        label="Avg Trip Duration",
        value=_avg_trip_duration(df_yearly),
        border_variant="bike",
    )
