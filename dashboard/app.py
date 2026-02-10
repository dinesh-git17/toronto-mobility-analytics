"""Toronto Mobility Dashboard — navigation hub with hero metrics."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from components.metrics import render_metric_row
from data.cache import query_hero_metrics
from data.connection import get_connection

st.set_page_config(
    page_title="Toronto Mobility Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)

_css_path = Path(__file__).parent / "styles" / "custom.css"
st.markdown(f"<style>{_css_path.read_text()}</style>", unsafe_allow_html=True)

st.sidebar.title("Toronto Mobility Dashboard")
st.sidebar.markdown(
    "Operational analytics for Toronto transit delays, Bike Share ridership, "
    "and weather-correlated mobility patterns."
)

# ---------------------------------------------------------------------------
# Hero metrics — 1-hour cache
# ---------------------------------------------------------------------------

conn = get_connection()

df_delay_hours: pd.DataFrame = query_hero_metrics(
    "SELECT COALESCE(SUM(delay_minutes), 0) / 60 AS total_delay_hours"
    " FROM fct_transit_delays",
    conn,
)

df_bike_trips: pd.DataFrame = query_hero_metrics(
    "SELECT COALESCE(SUM(total_bike_trips), 0) AS total_bike_trips"
    " FROM fct_daily_mobility",
    conn,
)

df_fresh: pd.DataFrame = query_hero_metrics(
    "SELECT MAX(d.full_date) AS latest_date"
    " FROM dim_date d"
    " WHERE d.date_key IN (SELECT date_key FROM fct_daily_mobility)",
    conn,
)

delay_hours: int = (
    int(df_delay_hours.iloc[0]["TOTAL_DELAY_HOURS"]) if not df_delay_hours.empty else 0
)

total_trips: int = (
    int(df_bike_trips.iloc[0]["TOTAL_BIKE_TRIPS"]) if not df_bike_trips.empty else 0
)

freshness_fmt: str
if not df_fresh.empty:
    freshness_fmt = pd.Timestamp(df_fresh.iloc[0]["LATEST_DATE"]).strftime("%b %Y")
else:
    freshness_fmt = "N/A"

# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------

st.title("Toronto Mobility Dashboard")
st.caption(
    "Operational analytics across TTC transit delays, "
    "Bike Share ridership, and weather impact"
)

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
            "label": "Data Through",
            "value": freshness_fmt,
        },
    ]
)

st.markdown("---")

# ---------------------------------------------------------------------------
# Page navigation cards
# ---------------------------------------------------------------------------

_NAV_CARDS: list[dict[str, str]] = [
    {
        "title": "Overview",
        "description": "Cross-modal mobility summary with headline KPIs and trends",
        "accent_color": "var(--accent-blue)",
        "page": "pages/1_Overview.py",
    },
    {
        "title": "TTC Deep Dive",
        "description": "Delay patterns by station, cause, and time of day",
        "accent_color": "var(--ttc-red)",
        "page": "pages/2_TTC_Deep_Dive.py",
    },
    {
        "title": "Bike Share",
        "description": "Trip volume, seasonality, and station-level ridership",
        "accent_color": "var(--bike-green)",
        "page": "pages/3_Bike_Share.py",
    },
    {
        "title": "Weather Impact",
        "description": "Temperature and precipitation effects on mobility",
        "accent_color": "var(--warning-amber)",
        "page": "pages/4_Weather_Impact.py",
    },
    {
        "title": "Station Explorer",
        "description": "Geographic drill-down with station comparison",
        "accent_color": "var(--accent-blue)",
        "page": "pages/5_Station_Explorer.py",
    },
]


def _render_nav_card(card: dict[str, str]) -> None:
    """Render a navigation card with accent bar, title, and description.

    Args:
        card: Dictionary with title, description, accent_color, and page keys.
    """
    accent = card["accent_color"]
    title = card["title"]
    desc = card["description"]
    st.markdown(
        f'<div class="nav-card">'
        f'<div class="nav-card__accent"'
        f' style="background:{accent}"></div>'
        f'<div class="nav-card__title">{title}</div>'
        f'<div class="nav-card__description">{desc}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )
    st.page_link(card["page"], label="Open \u2192", use_container_width=True)


st.subheader("Explore the Dashboard")

row1_cols = st.columns(3)
for col, card in zip(row1_cols, _NAV_CARDS[:3], strict=True):
    with col:
        _render_nav_card(card)

row2_cols = st.columns(3)
for col, card in zip(row2_cols[:2], _NAV_CARDS[3:], strict=True):
    with col:
        _render_nav_card(card)
