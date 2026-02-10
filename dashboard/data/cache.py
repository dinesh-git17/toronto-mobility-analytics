"""Tiered caching strategy with 4 TTL tiers for MARTS queries.

TTL tiers per dashboard-design.md Section 5.5:
  - Reference data: 86400s (24 hours)
  - Hero metrics:    3600s (1 hour)
  - Aggregations:    1800s (30 minutes)
  - Filtered:         600s (10 minutes)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import streamlit as st

if TYPE_CHECKING:
    import pandas as pd

from data.connection import execute_query


@st.cache_data(ttl=86400)  # type: ignore[misc]
def query_reference_data(query: str, _conn: Any) -> pd.DataFrame:
    """Execute a reference data query with 24-hour TTL cache.

    Used for station lists, delay codes, and date range bounds
    that change infrequently.

    Args:
        query: SQL query string (no bind parameters).
        _conn: Snowflake connection from get_connection().

    Returns:
        Query results as a pandas DataFrame.
    """
    return execute_query(query, _conn)


@st.cache_data(ttl=3600)  # type: ignore[misc]
def query_hero_metrics(query: str, _conn: Any) -> pd.DataFrame:
    """Execute a hero metric query with 1-hour TTL cache.

    Used for headline KPI computations displayed on the
    dashboard overview page.

    Args:
        query: SQL query string (no bind parameters).
        _conn: Snowflake connection from get_connection().

    Returns:
        Query results as a pandas DataFrame.
    """
    return execute_query(query, _conn)


@st.cache_data(ttl=1800)  # type: ignore[misc]
def query_aggregation(query: str, _conn: Any) -> pd.DataFrame:
    """Execute an aggregation query with 30-minute TTL cache.

    Used for chart data, monthly rollups, and mode comparisons.

    Args:
        query: SQL query string (no bind parameters).
        _conn: Snowflake connection from get_connection().

    Returns:
        Query results as a pandas DataFrame.
    """
    return execute_query(query, _conn)


@st.cache_data(ttl=600)  # type: ignore[misc]
def query_filtered(
    query: str,
    params: dict[str, Any],
    _conn: Any,
) -> pd.DataFrame:
    """Execute a user-parameterized query with 10-minute TTL cache.

    Used for queries where filter values (date range, transit mode)
    vary across user sessions. Parameters are passed to the Snowflake
    cursor for bind-variable execution.

    Args:
        query: SQL query string with %(param)s placeholders.
        params: Bind-variable parameters for the query.
        _conn: Snowflake connection from get_connection().

    Returns:
        Query results as a pandas DataFrame.
    """
    return execute_query(query, _conn, params)


def clear_all_caches() -> None:
    """Clear all cached query results for development and debugging."""
    st.cache_data.clear()
