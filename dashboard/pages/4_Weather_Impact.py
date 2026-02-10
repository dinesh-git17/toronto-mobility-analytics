"""Weather Impact — quantifies weather effects on transit and cycling."""

from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from components.charts import bar_chart, scatter_plot
from components.filters import select_filter
from data.cache import query_aggregation
from data.connection import get_connection
from data.queries import weather_daily_metrics

_WEATHER_CONDITIONS: list[str] = ["Clear", "Rain", "Snow"]

# ---------------------------------------------------------------------------
# Insight computation helpers
# ---------------------------------------------------------------------------


def _bike_trip_impact(df: pd.DataFrame, condition: str) -> str:
    """Compute bike trip percentage change for *condition* vs Clear days."""
    clear = df.loc[df["weather_condition"] == "Clear", "total_bike_trips"]
    avg_clear = float(clear.mean()) if not clear.empty else 0.0
    if avg_clear <= 0:
        return "N/A"

    if condition == "Clear":
        return f"Clear days average {avg_clear:,.0f} bike trips per day"

    subset = df.loc[df["weather_condition"] == condition, "total_bike_trips"]
    if subset.empty:
        return "N/A"
    avg_selected = float(subset.mean())
    n_days = len(subset)
    pct = (avg_selected - avg_clear) / avg_clear * 100

    qualifier = " (limited sample)" if n_days < 30 else ""
    if pct < 0:
        return (
            f"{condition} reduces bike trips by {abs(pct):.0f}% "
            f"(based on {n_days} {condition} days){qualifier}"
        )
    return (
        f"{condition} increases bike trips by {pct:.0f}% "
        f"(based on {n_days} {condition} days){qualifier}"
    )


def _delay_impact(df: pd.DataFrame, condition: str) -> str:
    """Compute transit delay percentage change for *condition* vs Clear days."""
    clear = df.loc[df["weather_condition"] == "Clear", "total_delay_incidents"]
    avg_clear = float(clear.mean()) if not clear.empty else 0.0
    if avg_clear <= 0:
        return "N/A"

    if condition == "Clear":
        return f"Clear days average {avg_clear:.0f} delay incidents per day"

    subset = df.loc[df["weather_condition"] == condition, "total_delay_incidents"]
    if subset.empty:
        return "N/A"
    avg_selected = float(subset.mean())
    n_days = len(subset)
    pct = (avg_selected - avg_clear) / avg_clear * 100

    qualifier = " (limited sample)" if n_days < 30 else ""
    if pct > 0:
        return (
            f"{condition} increases TTC delays by {pct:.0f}% "
            f"(based on {n_days} {condition} days){qualifier}"
        )
    return (
        f"{condition} reduces TTC delays by {abs(pct):.0f}% "
        f"(based on {n_days} {condition} days){qualifier}"
    )


def _temperature_sweet_spot(df: pd.DataFrame) -> str:
    """Identify the 5 deg C bin with the highest average daily bike trips."""
    bike_rows = df.dropna(subset=["mean_temp_c", "total_bike_trips"])
    if bike_rows.empty:
        return "N/A"

    bins = list(range(-30, 45, 5))
    bike_rows = bike_rows.copy()
    bike_rows["temp_bin"] = pd.cut(bike_rows["mean_temp_c"], bins=bins)
    grouped = bike_rows.groupby("temp_bin", observed=True)["total_bike_trips"].mean()
    if grouped.empty:
        return "N/A"
    peak = grouped.idxmax()
    left = int(peak.left)  # pyright: ignore[reportAttributeAccessIssue]
    right = int(peak.right)  # pyright: ignore[reportAttributeAccessIssue]
    return f"Peak cycling between {left}\u00b0C and {right}\u00b0C"


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Weather Impact | Toronto Mobility", layout="wide")

_css = (Path(__file__).parent.parent / "styles" / "custom.css").read_text()
st.markdown(f"<style>{_css}</style>", unsafe_allow_html=True)

st.title("Weather Impact")

# ---------------------------------------------------------------------------
# Sidebar filter
# ---------------------------------------------------------------------------

selected_condition = select_filter(
    "Compare Condition",
    _WEATHER_CONDITIONS,
    default="Rain",
    key="weather_condition",
)
st.sidebar.caption("Select a condition to compare against clear weather")

# ---------------------------------------------------------------------------
# Data fetching (30-minute aggregation cache)
# ---------------------------------------------------------------------------

conn = get_connection()
df_weather = query_aggregation(weather_daily_metrics(), conn)

if df_weather.empty:
    st.info("No weather-mobility data available.")
    st.stop()

df_weather.columns = [c.lower() for c in df_weather.columns]

for _col in ("mean_temp_c", "total_precip_mm", "total_rain_mm", "total_snow_cm"):
    df_weather[_col] = pd.to_numeric(df_weather[_col], errors="coerce")

# ---------------------------------------------------------------------------
# Section 1: Bar charts — bike trips & transit delays by weather condition
# ---------------------------------------------------------------------------

st.markdown("---")
col_bike_bar, col_delay_bar = st.columns(2)

with col_bike_bar:
    st.subheader("Bike Trips by Weather")
    bike_by_weather = df_weather.groupby("weather_condition", as_index=False)[
        "total_bike_trips"
    ].mean()
    bike_by_weather = bike_by_weather.rename(  # pyright: ignore[reportCallIssue]
        columns={"total_bike_trips": "avg_daily_trips"},
    )
    bike_by_weather["avg_daily_trips"] = bike_by_weather["avg_daily_trips"].round(0)
    bike_by_weather["weather_condition"] = pd.Categorical(
        bike_by_weather["weather_condition"],
        categories=_WEATHER_CONDITIONS,
        ordered=True,
    )
    bike_by_weather = bike_by_weather.sort_values("weather_condition")
    st.altair_chart(
        bar_chart(
            bike_by_weather,
            x="weather_condition",
            y="avg_daily_trips",
            horizontal=True,
            mark_color="#43B02A",
            title="",
        ),
        use_container_width=True,
    )

with col_delay_bar:
    st.subheader("Transit Delays by Weather")
    delays_by_weather = df_weather.groupby("weather_condition", as_index=False)[
        "total_delay_incidents"
    ].mean()
    delays_by_weather = delays_by_weather.rename(  # pyright: ignore[reportCallIssue]
        columns={"total_delay_incidents": "avg_daily_delays"},
    )
    delays_by_weather["avg_daily_delays"] = delays_by_weather["avg_daily_delays"].round(
        0
    )
    delays_by_weather["weather_condition"] = pd.Categorical(
        delays_by_weather["weather_condition"],
        categories=_WEATHER_CONDITIONS,
        ordered=True,
    )
    delays_by_weather = delays_by_weather.sort_values("weather_condition")
    st.altair_chart(
        bar_chart(
            delays_by_weather,
            x="weather_condition",
            y="avg_daily_delays",
            horizontal=True,
            mark_color="#DA291C",
            title="",
        ),
        use_container_width=True,
    )

# ---------------------------------------------------------------------------
# Section 2: Scatter plots — temperature & precipitation vs bike trips
# ---------------------------------------------------------------------------

st.markdown("---")
col_temp, col_precip = st.columns(2)

scatter_data = df_weather.dropna(subset=["total_bike_trips"]).copy()

_CONDITION_DOMAIN: list[str] = ["Clear", "Rain", "Snow"]
_CONDITION_RANGE: list[str] = ["#737373", "#2563EB", "#93C5FD"]

with col_temp:
    st.subheader("Temperature vs Bike Trips")
    temp_data = scatter_data.dropna(subset=["mean_temp_c"])
    if temp_data.empty:
        st.info("No temperature data available.")
    else:
        temp_chart = scatter_plot(
            temp_data,
            x="mean_temp_c",
            y="total_bike_trips",
            color="weather_condition",
            x_title="Mean Temperature (\u00b0C)",
            y_title="Daily Bike Trips",
            title="",
        )
        temp_chart = temp_chart.encode(
            color=alt.Color(
                "weather_condition:N",
                scale=alt.Scale(
                    domain=_CONDITION_DOMAIN,
                    range=_CONDITION_RANGE,
                ),
            ),
        )
        st.altair_chart(temp_chart, use_container_width=True)

with col_precip:
    st.subheader("Precipitation vs Bike Trips")
    precip_data = scatter_data.dropna(subset=["total_precip_mm"])
    if precip_data.empty:
        st.info("No precipitation data available.")
    else:
        precip_chart = scatter_plot(
            precip_data,
            x="total_precip_mm",
            y="total_bike_trips",
            color="weather_condition",
            x_title="Precipitation (mm)",
            y_title="Daily Bike Trips",
            title="",
        )
        precip_chart = precip_chart.encode(
            color=alt.Color(
                "weather_condition:N",
                scale=alt.Scale(
                    domain=_CONDITION_DOMAIN,
                    range=_CONDITION_RANGE,
                ),
            ),
        )
        st.altair_chart(precip_chart, use_container_width=True)

# ---------------------------------------------------------------------------
# Section 3: Callout boxes
# ---------------------------------------------------------------------------

st.markdown("---")
call_cols = st.columns(3)

with call_cols[0]:
    st.info(_bike_trip_impact(df_weather, selected_condition))

with call_cols[1]:
    st.info(_delay_impact(df_weather, selected_condition))

with call_cols[2]:
    st.info(_temperature_sweet_spot(df_weather))
