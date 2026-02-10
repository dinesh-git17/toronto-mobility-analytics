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


# ---------------------------------------------------------------------------
# TTC Deep Dive queries (E-1202)
# ---------------------------------------------------------------------------

_VALID_MODES: frozenset[str] = frozenset({"subway", "bus", "streetcar"})


def _validate_modes(modes: list[str]) -> str:
    """Validate transit modes and return a SQL IN clause fragment.

    Args:
        modes: Transit mode identifiers to validate.

    Returns:
        SQL-safe IN clause like ``('bus', 'subway')``.

    Raises:
        ValueError: If modes is empty or contains unrecognized values.
    """
    if not modes:
        msg = "At least one transit mode required"
        raise ValueError(msg)
    invalid = set(modes) - _VALID_MODES
    if invalid:
        msg = f"Invalid transit modes: {invalid}"
        raise ValueError(msg)
    quoted = ", ".join(f"'{m}'" for m in sorted(modes))
    return f"({quoted})"


def ttc_station_delays(modes: list[str]) -> str:
    """Station-level delay aggregation with geographic coordinates.

    Joins ``fct_transit_delays`` to ``dim_station`` for latitude/longitude.
    Filters to records with a mapped station (``station_key IS NOT NULL``),
    which effectively scopes results to subway mode.

    Args:
        modes: Transit modes to include (validated against closed set).

    Returns:
        SQL with ``%(start_date)s`` / ``%(end_date)s`` bind variables.
        Columns: station_name, latitude, longitude, delay_count,
        total_delay_minutes.
    """
    in_clause = _validate_modes(modes)
    return f"""
        SELECT
            s.station_name,
            s.latitude,
            s.longitude,
            COUNT(*) AS delay_count,
            SUM(f.delay_minutes) AS total_delay_minutes
        FROM fct_transit_delays f
        INNER JOIN dim_station s
            ON f.station_key = s.station_key
        WHERE f.date_key BETWEEN %(start_date)s AND %(end_date)s
            AND f.transit_mode IN {in_clause}
            AND f.station_key IS NOT NULL
        GROUP BY s.station_name, s.latitude, s.longitude
        ORDER BY total_delay_minutes DESC
    """


def ttc_delay_causes(modes: list[str]) -> str:
    """Delay cause hierarchy: category-to-description breakdown.

    Joins ``fct_transit_delays`` to ``dim_ttc_delay_codes`` for category
    and description labels used in treemap visualization.

    Args:
        modes: Transit modes to include.

    Returns:
        SQL with date range bind variables. Columns: delay_category,
        delay_description, incident_count, total_delay_minutes.
    """
    in_clause = _validate_modes(modes)
    return f"""
        SELECT
            c.delay_category,
            c.delay_description,
            COUNT(*) AS incident_count,
            SUM(f.delay_minutes) AS total_delay_minutes
        FROM fct_transit_delays f
        INNER JOIN dim_ttc_delay_codes c
            ON f.delay_code_key = c.delay_code_key
        WHERE f.date_key BETWEEN %(start_date)s AND %(end_date)s
            AND f.transit_mode IN {in_clause}
            AND f.delay_code_key IS NOT NULL
        GROUP BY c.delay_category, c.delay_description
    """


def ttc_hourly_pattern(modes: list[str]) -> str:
    """Hour-of-day x day-of-week delay count matrix.

    Extracts hour from ``incident_timestamp`` and joins ``dim_date``
    for day-of-week labels and numeric sort keys.

    Args:
        modes: Transit modes to include.

    Returns:
        SQL with date range bind variables. Columns: hour_of_day,
        day_of_week, day_of_week_num, delay_count.
    """
    in_clause = _validate_modes(modes)
    return f"""
        SELECT
            EXTRACT(HOUR FROM f.incident_timestamp) AS hour_of_day,
            d.day_of_week,
            d.day_of_week_num,
            COUNT(*) AS delay_count
        FROM fct_transit_delays f
        INNER JOIN dim_date d
            ON f.date_key = d.date_key
        WHERE f.date_key BETWEEN %(start_date)s AND %(end_date)s
            AND f.transit_mode IN {in_clause}
        GROUP BY hour_of_day, d.day_of_week, d.day_of_week_num
        ORDER BY d.day_of_week_num, hour_of_day
    """


def ttc_monthly_trend(modes: list[str]) -> str:
    """Year x month delay aggregation for trend analysis.

    Joins ``dim_date`` for year, month number, and month name columns
    enabling year-over-year line chart comparison.

    Args:
        modes: Transit modes to include.

    Returns:
        SQL with date range bind variables. Columns: year, month_num,
        month_name, delay_count, total_delay_minutes.
    """
    in_clause = _validate_modes(modes)
    return f"""
        SELECT
            d.year,
            d.month_num,
            d.month_name,
            COUNT(*) AS delay_count,
            SUM(f.delay_minutes) AS total_delay_minutes
        FROM fct_transit_delays f
        INNER JOIN dim_date d
            ON f.date_key = d.date_key
        WHERE f.date_key BETWEEN %(start_date)s AND %(end_date)s
            AND f.transit_mode IN {in_clause}
        GROUP BY d.year, d.month_num, d.month_name
        ORDER BY d.year, d.month_num
    """


# ---------------------------------------------------------------------------
# Bike Share Deep Dive queries (E-1302)
# ---------------------------------------------------------------------------

_VALID_USER_TYPES: frozenset[str] = frozenset({"Annual Member", "Casual Member"})


def _validate_user_types(user_types: list[str]) -> str:
    """Validate user types and return a SQL IN clause fragment.

    Args:
        user_types: User type identifiers to validate.

    Returns:
        SQL-safe IN clause like ``('Annual Member', 'Casual Member')``.

    Raises:
        ValueError: If user_types is empty or contains unrecognized values.
    """
    if not user_types:
        msg = "At least one user type required"
        raise ValueError(msg)
    invalid = set(user_types) - _VALID_USER_TYPES
    if invalid:
        msg = f"Invalid user types: {invalid}"
        raise ValueError(msg)
    quoted = ", ".join(f"'{t}'" for t in sorted(user_types))
    return f"({quoted})"


def bike_station_activity(user_types: list[str]) -> str:
    """Station-level trip count aggregation with geographic coordinates.

    Joins ``fct_bike_trips`` to ``dim_station`` on ``start_station_key``
    for latitude, longitude, and neighborhood. INNER JOIN excludes trips
    with unmatchable stations (91 station_ids not in GBFS snapshot).

    Args:
        user_types: User types to include (validated against closed set).

    Returns:
        SQL with ``%(start_date)s`` / ``%(end_date)s`` bind variables.
        Columns: station_name, latitude, longitude, neighborhood,
        trip_count.
    """
    in_clause = _validate_user_types(user_types)
    return f"""
        SELECT
            s.station_name,
            s.latitude,
            s.longitude,
            s.neighborhood,
            COUNT(*) AS trip_count
        FROM fct_bike_trips f
        INNER JOIN dim_station s
            ON f.start_station_key = s.station_key
        WHERE f.date_key BETWEEN %(start_date)s AND %(end_date)s
            AND f.user_type IN {in_clause}
        GROUP BY s.station_name, s.latitude, s.longitude, s.neighborhood
        ORDER BY trip_count DESC
    """


def bike_yearly_summary() -> str:
    """Annual trip totals with member and casual breakdowns.

    Aggregates ``fct_daily_mobility`` joined to ``dim_date`` for year.
    User type filtering handled in Python from returned columns.

    Returns:
        SQL with ``%(start_date)s`` / ``%(end_date)s`` bind variables.
        Columns: year, total_trips, member_trips, casual_trips,
        total_duration_seconds.
    """
    return """
        SELECT
            d.year,
            SUM(m.total_bike_trips) AS total_trips,
            SUM(m.member_trips) AS member_trips,
            SUM(m.casual_trips) AS casual_trips,
            SUM(m.total_bike_duration_seconds) AS total_duration_seconds
        FROM fct_daily_mobility m
        INNER JOIN dim_date d
            ON m.date_key = d.date_key
        WHERE m.date_key BETWEEN %(start_date)s AND %(end_date)s
            AND m.total_bike_trips IS NOT NULL
        GROUP BY d.year
        ORDER BY d.year
    """


def bike_monthly_seasonality() -> str:
    """Year x month trip totals for seasonality analysis.

    Aggregates ``fct_daily_mobility`` joined to ``dim_date`` for year,
    month number, and month name columns enabling year-over-year
    seasonality overlay.

    Returns:
        SQL with ``%(start_date)s`` / ``%(end_date)s`` bind variables.
        Columns: year, month_num, month_name, total_trips,
        member_trips, casual_trips.
    """
    return """
        SELECT
            d.year,
            d.month_num,
            d.month_name,
            SUM(m.total_bike_trips) AS total_trips,
            SUM(m.member_trips) AS member_trips,
            SUM(m.casual_trips) AS casual_trips
        FROM fct_daily_mobility m
        INNER JOIN dim_date d
            ON m.date_key = d.date_key
        WHERE m.date_key BETWEEN %(start_date)s AND %(end_date)s
            AND m.total_bike_trips IS NOT NULL
        GROUP BY d.year, d.month_num, d.month_name
        ORDER BY d.year, d.month_num
    """


# ---------------------------------------------------------------------------
# Weather Impact queries (E-1303)
# ---------------------------------------------------------------------------


def weather_daily_metrics() -> str:
    """Per-day weather conditions and mobility totals for impact analysis.

    Joins ``fct_daily_mobility`` to ``dim_weather`` on ``date_key`` to
    produce daily rows with weather measurements and trip/delay counts.
    Excludes dates missing temperature observations or mobility data.

    No parameters — queries the full date range for statistical power.

    Returns:
        SQL string. Columns: weather_condition, mean_temp_c,
        total_precip_mm, total_rain_mm, total_snow_cm, total_bike_trips,
        total_delay_incidents, total_delay_minutes, member_trips,
        casual_trips.
    """
    return """
        SELECT
            w.weather_condition,
            w.mean_temp_c::FLOAT AS mean_temp_c,
            COALESCE(w.total_precip_mm, 0)::FLOAT AS total_precip_mm,
            w.total_rain_mm::FLOAT AS total_rain_mm,
            w.total_snow_cm::FLOAT AS total_snow_cm,
            m.total_bike_trips,
            m.total_delay_incidents,
            m.total_delay_minutes,
            m.member_trips,
            m.casual_trips
        FROM fct_daily_mobility m
        INNER JOIN dim_weather w
            ON m.date_key = w.date_key
        WHERE w.mean_temp_c IS NOT NULL
            AND (m.total_bike_trips IS NOT NULL
                 OR m.total_delay_incidents IS NOT NULL)
        ORDER BY m.date_key
    """


# ---------------------------------------------------------------------------
# Station Explorer queries (E-1402)
# ---------------------------------------------------------------------------


def station_delay_metrics() -> str:
    """Aggregate delay statistics for a single TTC subway station.

    Parameters: station_key (str), start_date (int), end_date (int).
    Returns single-row DataFrame with delay_count, total_delay_minutes,
    avg_delay_minutes, top_delay_category from fct_transit_delays joined
    to dim_ttc_delay_codes for category ranking.
    """
    return """
        WITH base AS (
            SELECT
                f.delay_minutes,
                c.delay_category
            FROM fct_transit_delays f
            LEFT JOIN dim_ttc_delay_codes c
                ON f.delay_code_key = c.delay_code_key
            WHERE f.station_key = %(station_key)s
                AND f.date_key BETWEEN %(start_date)s AND %(end_date)s
        ),
        ranked_categories AS (
            SELECT
                delay_category,
                ROW_NUMBER() OVER (ORDER BY COUNT(*) DESC) AS rn
            FROM base
            WHERE delay_category IS NOT NULL
            GROUP BY delay_category
        )
        SELECT
            COUNT(*) AS delay_count,
            COALESCE(SUM(delay_minutes), 0) AS total_delay_minutes,
            ROUND(AVG(delay_minutes), 1) AS avg_delay_minutes,
            (SELECT delay_category FROM ranked_categories WHERE rn = 1)
                AS top_delay_category
        FROM base
    """


def station_trip_metrics() -> str:
    """Aggregate trip statistics for a single Bike Share station.

    Parameters: station_key (str), start_date (int), end_date (int).
    Uses start_station_key (trip origin) consistent with
    bike_station_activity() pattern from E-1302.
    Returns single-row DataFrame with trip_count, avg_duration_minutes,
    top_user_type from fct_bike_trips.
    """
    return """
        WITH base AS (
            SELECT
                duration_seconds,
                user_type
            FROM fct_bike_trips
            WHERE start_station_key = %(station_key)s
                AND date_key BETWEEN %(start_date)s AND %(end_date)s
        ),
        ranked_users AS (
            SELECT
                user_type,
                ROW_NUMBER() OVER (ORDER BY COUNT(*) DESC) AS rn
            FROM base
            WHERE user_type IS NOT NULL
            GROUP BY user_type
        )
        SELECT
            COUNT(*) AS trip_count,
            ROUND(AVG(duration_seconds) / 60, 1) AS avg_duration_minutes,
            (SELECT user_type FROM ranked_users WHERE rn = 1)
                AS top_user_type
        FROM base
    """


def station_delay_timeline() -> str:
    """Monthly delay trend for a single TTC subway station.

    Parameters: station_key (str), start_date (int), end_date (int).
    Returns DataFrame with year, month_num, month_name, delay_count,
    total_delay_minutes from fct_transit_delays joined to dim_date.
    """
    return """
        SELECT
            d.year,
            d.month_num,
            d.month_name,
            COUNT(*) AS delay_count,
            SUM(f.delay_minutes) AS total_delay_minutes
        FROM fct_transit_delays f
        INNER JOIN dim_date d
            ON f.date_key = d.date_key
        WHERE f.station_key = %(station_key)s
            AND f.date_key BETWEEN %(start_date)s AND %(end_date)s
        GROUP BY d.year, d.month_num, d.month_name
        ORDER BY d.year, d.month_num
    """


def station_trip_timeline() -> str:
    """Monthly trip trend for a single Bike Share station.

    Parameters: station_key (str), start_date (int), end_date (int).
    Uses start_station_key (trip origin) consistent with
    bike_station_activity() pattern from E-1302.
    Returns DataFrame with year, month_num, month_name, trip_count,
    avg_duration_minutes from fct_bike_trips joined to dim_date.
    """
    return """
        SELECT
            d.year,
            d.month_num,
            d.month_name,
            COUNT(*) AS trip_count,
            ROUND(AVG(f.duration_seconds) / 60, 1) AS avg_duration_minutes
        FROM fct_bike_trips f
        INNER JOIN dim_date d
            ON f.date_key = d.date_key
        WHERE f.start_station_key = %(station_key)s
            AND f.date_key BETWEEN %(start_date)s AND %(end_date)s
        GROUP BY d.year, d.month_num, d.month_name
        ORDER BY d.year, d.month_num
    """
