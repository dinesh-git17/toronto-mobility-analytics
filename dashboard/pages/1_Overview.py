"""Overview landing page — cross-modal mobility summary."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from components.charts import bar_chart, line_chart
from components.metrics import render_metric_row
from data.cache import query_aggregation, query_hero_metrics, query_reference_data
from data.connection import get_connection
from data.queries import reference_date_bounds

st.set_page_config(page_title="Overview | Toronto Mobility", layout="wide")

_css = (Path(__file__).parent.parent / "styles" / "custom.css").read_text()
st.markdown(f"<style>{_css}</style>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

conn = get_connection()

# Hero metrics — 1-hour cache (full-range, no date filter)
df_delay_hours = query_hero_metrics(
    "SELECT COALESCE(SUM(delay_minutes), 0) / 60 AS total_delay_hours"
    " FROM fct_transit_delays",
    conn,
)

df_bike_trips = query_hero_metrics(
    "SELECT COALESCE(SUM(total_bike_trips), 0) AS total_bike_trips"
    " FROM fct_daily_mobility",
    conn,
)

df_worst = query_hero_metrics(
    "SELECT s.station_name, SUM(f.delay_minutes) AS total_delay_minutes"
    " FROM fct_transit_delays f"
    " INNER JOIN dim_station s ON f.station_key = s.station_key"
    " WHERE f.transit_mode = 'subway'"
    " GROUP BY s.station_name"
    " ORDER BY total_delay_minutes DESC"
    " LIMIT 1",
    conn,
)

df_fresh = query_hero_metrics(
    "SELECT MAX(d.full_date) AS latest_date"
    " FROM dim_date d"
    " WHERE d.date_key IN (SELECT date_key FROM fct_daily_mobility)",
    conn,
)

# Chart aggregations — 30-minute cache (full-range)
df_monthly = query_aggregation(
    "SELECT d.year, d.month_num AS month,"
    " SUM(m.total_delay_incidents) AS total_delay_incidents,"
    " SUM(m.total_bike_trips) AS total_bike_trips"
    " FROM fct_daily_mobility m"
    " INNER JOIN dim_date d ON m.date_key = d.date_key"
    " GROUP BY d.year, d.month_num"
    " ORDER BY d.year, d.month_num",
    conn,
)

df_mode = query_aggregation(
    "SELECT transit_mode, COUNT(*) AS delay_count,"
    " SUM(delay_minutes) AS total_delay_minutes"
    " FROM fct_transit_delays"
    " GROUP BY transit_mode",
    conn,
)

# Reference data — 24-hour cache
df_bounds = query_reference_data(reference_date_bounds(), conn)

# ---------------------------------------------------------------------------
# Format
# ---------------------------------------------------------------------------

delay_hours = (
    int(df_delay_hours.iloc[0]["TOTAL_DELAY_HOURS"]) if not df_delay_hours.empty else 0
)

total_trips = (
    int(df_bike_trips.iloc[0]["TOTAL_BIKE_TRIPS"]) if not df_bike_trips.empty else 0
)

worst_station = str(df_worst.iloc[0]["STATION_NAME"]) if not df_worst.empty else "N/A"

if not df_fresh.empty:
    freshness_fmt = pd.Timestamp(df_fresh.iloc[0]["LATEST_DATE"]).strftime("%b %Y")
else:
    freshness_fmt = "N/A"

# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

st.title("Overview")

render_metric_row(
    [
        {
            "label": "Total Delay Hours",
            "value": f"{delay_hours:,}",
            "border_variant": "ttc",
        },
        {
            "label": "Total Bike Trips",
            "value": f"{total_trips / 1_000_000:.1f}M",
            "border_variant": "bike",
        },
        {
            "label": "Worst Station",
            "value": worst_station,
        },
        {
            "label": "Data Freshness",
            "value": freshness_fmt,
        },
    ]
)

st.markdown("---")

# Year-over-Year Trend
st.subheader("Year-over-Year Trend")
if not df_monthly.empty:
    trend = df_monthly.copy()
    trend.columns = [c.lower() for c in trend.columns]
    trend["year"] = trend["year"].astype(str)
    trend = trend.dropna(subset=["total_delay_incidents"])
    st.altair_chart(
        line_chart(
            trend,
            x="month:O",
            y="total_delay_incidents",
            color="year",
            title="Monthly Transit Delay Incidents",
        ),
        use_container_width=True,
    )

st.markdown("---")

# Transit Mode Comparison
st.subheader("Transit Delays by Mode")
if not df_mode.empty:
    mode = df_mode.copy()
    mode.columns = [c.lower() for c in mode.columns]
    st.altair_chart(
        bar_chart(
            mode,
            x="transit_mode",
            y="total_delay_minutes",
            color="transit_mode",
            horizontal=True,
            title="Total Delay Minutes by Mode",
        ),
        use_container_width=True,
    )

# Date range footer
if not df_bounds.empty:
    min_date = df_bounds.iloc[0]["MIN_DATE"]
    max_date = df_bounds.iloc[0]["MAX_DATE"]
    st.caption(f"Data coverage: {min_date} to {max_date}")
