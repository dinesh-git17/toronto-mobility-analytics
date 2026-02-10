"""Snowflake connection manager targeting the MARTS schema."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pandas as pd
import snowflake.connector
import streamlit as st
from snowflake.connector.errors import DatabaseError, ProgrammingError

if TYPE_CHECKING:
    from snowflake.connector.connection import SnowflakeConnection


@st.cache_resource  # type: ignore[misc]
def get_connection() -> SnowflakeConnection:
    """Establish a cached Snowflake connection targeting the MARTS schema.

    Reads credentials from st.secrets["snowflake"]. Connection is cached
    as a singleton via st.cache_resource and shared across all sessions.
    Sets schema=MARTS to enforce read-only access to the marts layer.
    """
    try:
        secrets = st.secrets["snowflake"]
        return snowflake.connector.connect(
            account=secrets["account"],
            user=secrets["user"],
            password=secrets["password"],
            warehouse=secrets["warehouse"],
            database=secrets["database"],
            role=secrets["role"],
            schema="MARTS",
            login_timeout=30,
            network_timeout=30,
        )
    except DatabaseError:
        st.error(
            "Snowflake connection failed. "
            "Verify credentials in .streamlit/secrets.toml."
        )
        st.stop()
        raise  # Unreachable; st.stop() raises StopException


@st.cache_data(ttl=300)  # type: ignore[misc]
def check_health() -> bool:
    """Validate MARTS schema connectivity via SELECT 1.

    Result is cached for 5 minutes to avoid repeated connectivity probes.
    Returns True on success, False on failure.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
    except (DatabaseError, ProgrammingError):
        return False
    return True


def execute_query(
    query: str,
    conn: SnowflakeConnection,
    params: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """Execute a SQL query with error handling and reconnection retry.

    Catches ProgrammingError (bad SQL) and displays the Snowflake error
    message via st.error. Catches DatabaseError (connection lost), clears
    the cached connection, and retries once before halting the app.

    Args:
        query: SQL query string, optionally containing %(param)s placeholders.
        conn: Active Snowflake connection from get_connection().
        params: Bind-variable parameters for parameterized queries.

    Returns:
        Query results as a pandas DataFrame. Empty DataFrame on
        ProgrammingError.
    """
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        columns = [desc[0] for desc in cursor.description]
        data = cursor.fetchall()
        cursor.close()
        return pd.DataFrame(data, columns=columns)
    except ProgrammingError as exc:
        st.error(f"Query execution failed: {exc}")
        return pd.DataFrame()
    except DatabaseError:
        st.cache_resource.clear()
        try:
            new_conn = get_connection()
            cursor = new_conn.cursor()
            cursor.execute(query, params)
            columns = [desc[0] for desc in cursor.description]
            data = cursor.fetchall()
            cursor.close()
            return pd.DataFrame(data, columns=columns)
        except (DatabaseError, ProgrammingError):
            st.error(
                "Connection lost. "
                "Verify Snowflake credentials in .streamlit/secrets.toml."
            )
            st.stop()
            raise  # Unreachable; st.stop() raises StopException
