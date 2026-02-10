"""Parameterized SQL query definitions for all 7 MARTS tables.

All queries targeting user-controlled filter parameters use %(param)s
bind-variable syntax for SQL injection prevention. Date range filtering
uses integer date_key (YYYYMMDD) for Snowflake micro-partition pruning.
"""

from __future__ import annotations


def hero_total_delay_hours() -> str:
    """Total delay hours across all transit modes within a date range.

    Parameters: start_date (int), end_date (int) — YYYYMMDD date keys.
    Returns single-row DataFrame with total_delay_hours column.
    """
    return """
        SELECT
            COALESCE(SUM(delay_minutes), 0) / 60 AS total_delay_hours
        FROM fct_transit_delays
        WHERE date_key BETWEEN %(start_date)s AND %(end_date)s
    """


def hero_total_bike_trips() -> str:
    """Total Bike Share trips within a date range.

    Parameters: start_date (int), end_date (int) — YYYYMMDD date keys.
    Returns single-row DataFrame with total_bike_trips column.
    """
    return """
        SELECT
            COUNT(*) AS total_bike_trips
        FROM fct_bike_trips
        WHERE date_key BETWEEN %(start_date)s AND %(end_date)s
    """


def hero_worst_station() -> str:
    """Subway station with highest total delay minutes within a date range.

    Parameters: start_date (int), end_date (int) — YYYYMMDD date keys.
    Returns single-row DataFrame with station_name and total_delay_minutes.
    Joins fct_transit_delays to dim_station, filtered to subway mode only.
    """
    return """
        SELECT
            s.station_name,
            SUM(f.delay_minutes) AS total_delay_minutes
        FROM fct_transit_delays f
        INNER JOIN dim_station s
            ON f.station_key = s.station_key
        WHERE f.transit_mode = 'subway'
            AND f.date_key BETWEEN %(start_date)s AND %(end_date)s
        GROUP BY s.station_name
        ORDER BY total_delay_minutes DESC
        LIMIT 1
    """


def hero_data_freshness() -> str:
    """Most recent date with mobility data in fct_daily_mobility.

    No parameters required. Returns single-row DataFrame with latest_date.
    """
    return """
        SELECT
            MAX(d.full_date) AS latest_date
        FROM dim_date d
        WHERE d.date_key IN (
            SELECT date_key FROM fct_daily_mobility
        )
    """


def monthly_aggregation() -> str:
    """Monthly totals for delay incidents and bike trips.

    Parameters: start_date (int), end_date (int) — YYYYMMDD date keys.
    Returns DataFrame with year, month, total_delay_incidents,
    total_bike_trips ordered chronologically for YoY trend visualization.
    """
    return """
        SELECT
            d.year,
            d.month_num AS month,
            SUM(m.total_delay_incidents) AS total_delay_incidents,
            SUM(m.total_bike_trips) AS total_bike_trips
        FROM fct_daily_mobility m
        INNER JOIN dim_date d
            ON m.date_key = d.date_key
        WHERE m.date_key BETWEEN %(start_date)s AND %(end_date)s
        GROUP BY d.year, d.month_num
        ORDER BY d.year, d.month_num
    """


def mode_comparison() -> str:
    """Delay count and total delay minutes grouped by transit mode.

    Parameters: start_date (int), end_date (int) — YYYYMMDD date keys.
    Returns DataFrame with transit_mode, delay_count, total_delay_minutes
    for bar chart visualization.
    """
    return """
        SELECT
            transit_mode,
            COUNT(*) AS delay_count,
            SUM(delay_minutes) AS total_delay_minutes
        FROM fct_transit_delays
        WHERE date_key BETWEEN %(start_date)s AND %(end_date)s
        GROUP BY transit_mode
    """


def reference_stations() -> str:
    """All rows from the station dimension.

    No parameters required. Returns complete dim_station DataFrame
    for filter population and map display.
    """
    return """
        SELECT
            station_key,
            station_id,
            station_name,
            station_type,
            latitude,
            longitude,
            neighborhood
        FROM dim_station
    """


def reference_delay_codes() -> str:
    """All rows from the delay code dimension.

    No parameters required. Returns complete dim_ttc_delay_codes DataFrame
    for filter population and code lookup display.
    """
    return """
        SELECT
            delay_code_key,
            delay_code,
            delay_description,
            delay_category
        FROM dim_ttc_delay_codes
    """


def reference_date_bounds() -> str:
    """Minimum and maximum dates from the date dimension.

    No parameters required. Returns single-row DataFrame with min_date
    and max_date for date picker range constraints.
    """
    return """
        SELECT
            MIN(full_date) AS min_date,
            MAX(full_date) AS max_date
        FROM dim_date
    """
