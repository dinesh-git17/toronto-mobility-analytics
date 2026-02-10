from pathlib import Path

import streamlit as st

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
