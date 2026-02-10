"""Metric card factory for styled KPI display."""

from __future__ import annotations

from typing import Any

import streamlit as st

_VARIANT_CLASS: dict[str, str] = {
    "default": "metric-card",
    "ttc": "metric-card metric-card--ttc",
    "bike": "metric-card metric-card--bike",
}


def render_metric_card(
    label: str,
    value: str,
    delta: str | None = None,
    delta_color: str = "normal",
    border_variant: str = "default",
) -> None:
    """Render a single styled metric card.

    Args:
        label: KPI label displayed above the value.
        value: Formatted metric value (e.g., ``"3,412"``).
        delta: Optional delta indicator text (e.g., ``"↑ 17% vs 2020"``).
        delta_color: Delta coloring mode — ``"normal"`` (green up / red down),
            ``"inverse"`` (red up / green down), or ``"off"`` (neutral).
        border_variant: Card border color — ``"default"`` (accent blue),
            ``"ttc"`` (TTC red), or ``"bike"`` (Bike Share green).
    """
    css_class = _VARIANT_CLASS.get(border_variant, "metric-card")

    delta_html = ""
    if delta:
        if delta_color == "off":
            delta_css = "metric-delta metric-delta--neutral"
        elif delta_color == "inverse":
            is_up = delta.startswith("↑") or delta.startswith("+")
            delta_css = (
                "metric-delta metric-delta--negative"
                if is_up
                else "metric-delta metric-delta--positive"
            )
        else:
            is_up = delta.startswith("↑") or delta.startswith("+")
            delta_css = (
                "metric-delta metric-delta--positive"
                if is_up
                else "metric-delta metric-delta--negative"
            )
        delta_html = f'<div class="{delta_css}">{delta}</div>'

    html = (
        f'<div class="{css_class}">'
        f'<div class="metric-label">{label}</div>'
        f'<div class="metric-value">{value}</div>'
        f"{delta_html}"
        f"</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def render_metric_row(metrics: list[dict[str, Any]]) -> None:
    """Render a horizontal row of metric cards using ``st.columns``.

    Each dict in *metrics* maps to ``render_metric_card`` parameters:
    ``label``, ``value``, and optionally ``delta``, ``delta_color``,
    ``border_variant``.

    Args:
        metrics: List of 1-4 metric definitions.
    """
    cols = st.columns(len(metrics))
    for col, metric in zip(cols, metrics, strict=True):
        with col:
            render_metric_card(
                label=metric["label"],
                value=metric["value"],
                delta=metric.get("delta"),
                delta_color=metric.get("delta_color", "normal"),
                border_variant=metric.get("border_variant", "default"),
            )
