"""Sidebar filter components for date range and categorical selection."""

from __future__ import annotations

from typing import TYPE_CHECKING

import streamlit as st

if TYPE_CHECKING:
    from datetime import date


def date_range_filter(
    min_date: date,
    max_date: date,
    default_start: date | None = None,
    default_end: date | None = None,
    key: str = "date_range",
) -> tuple[date, date]:
    """Render a date range picker in the sidebar.

    Handles the intermediate state where ``st.date_input`` returns a
    single date (user selected start but not yet end) by retaining the
    previous end date from session state.

    Args:
        min_date: Earliest selectable date.
        max_date: Latest selectable date.
        default_start: Initial start date. Defaults to *min_date*.
        default_end: Initial end date. Defaults to *max_date*.
        key: Unique widget key to prevent ``DuplicateWidgetID`` errors.

    Returns:
        ``(start_date, end_date)`` tuple.
    """
    start = default_start or min_date
    end = default_end or max_date

    result = st.sidebar.date_input(
        "Date Range",
        value=(start, end),
        min_value=min_date,
        max_value=max_date,
        key=key,
    )

    if isinstance(result, tuple) and len(result) == 2:
        return result[0], result[1]

    # User selected start but not end — retain previous end
    session_key = f"_prev_end_{key}"
    if isinstance(result, tuple) and len(result) == 1:
        prev_end = st.session_state.get(session_key, end)
        return result[0], prev_end

    st.session_state[session_key] = end
    return start, end


def multiselect_filter(
    label: str,
    options: list[str],
    default: list[str] | None = None,
    key: str = "",
) -> list[str]:
    """Render a multiselect filter in the sidebar.

    Args:
        label: Widget label text.
        options: Available choices.
        default: Initially selected values. Defaults to all *options*.
        key: Unique widget key to prevent ``DuplicateWidgetID`` errors.

    Returns:
        List of selected values.
    """
    selected: list[str] = st.sidebar.multiselect(
        label,
        options=options,
        default=default if default is not None else options,
        key=key or label,
    )
    return selected


def select_filter(
    label: str,
    options: list[str],
    default: str | None = None,
    key: str = "",
) -> str:
    """Render a single-select dropdown in the sidebar.

    Args:
        label: Widget label text.
        options: Available choices.
        default: Initially selected value. Defaults to first option.
        key: Unique widget key to prevent ``DuplicateWidgetID`` errors.

    Returns:
        Selected value.
    """
    index = 0
    if default and default in options:
        index = options.index(default)

    selected: str = st.sidebar.selectbox(
        label,
        options=options,
        index=index,
        key=key or label,
    )
    return selected
