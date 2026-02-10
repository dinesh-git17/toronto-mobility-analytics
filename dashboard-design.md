# Toronto Mobility Dashboard

## Technical Design Document

| Field                 | Value                      |
| --------------------- | -------------------------- |
| **Author**            | Dinesh                     |
| **Status**            | Draft                      |
| **Created**           | 2026-02-10                 |
| **Target Completion** | 3-4 days                   |
| **Parent Project**    | toronto-mobility-analytics |

---

## 1. Overview

### 1.1 Executive Summary

The Toronto Mobility Dashboard is a **multi-page Streamlit application** providing interactive visualizations of Toronto's transit reliability and cycling patterns. It serves as the public-facing layer of the toronto-mobility-analytics data pipeline, transforming 4+ years of TTC delay data and 21.8 million Bike Share trips into actionable insights.

The dashboard answers one core question: **"How reliable is Toronto's transportation system, and how are residents adapting?"**

### 1.2 Problem Statement

The toronto-mobility-analytics project has production-grade data infrastructure (dbt + Snowflake) but no visual interface. Portfolio reviewers and potential employers cannot experience the insights without writing SQL. The TTC and City of Toronto publish raw data but provide no consolidated view of system performance over time.

### 1.3 Proposed Solution

Build a Streamlit dashboard with:

- **Live Snowflake connection** — always current, no stale exports
- **5 pages** — Overview, TTC Deep Dive, Bike Share Deep Dive, Weather Impact, Station Explorer
- **High interactivity** — date ranges, filters, drill-downs
- **Map visualizations** — delay heatmaps, station activity maps
- **Mobile-responsive** — works on phone for demo flexibility

### 1.4 Success Criteria

| Criterion           | Target                           |
| ------------------- | -------------------------------- |
| Page load time      | < 3 seconds on initial load      |
| Query response      | < 2 seconds per interaction      |
| Mobile usability    | All charts readable on phone     |
| Uptime              | 99% on Streamlit Community Cloud |
| LinkedIn engagement | 50+ reactions on launch post     |

---

## 2. Goals and Non-Goals

### 2.1 Goals

**G1: Create a portfolio-grade visual artifact**

- Professional design, not generic Streamlit defaults
- Memorable insights that spark conversation
- Shareable screenshots and GIFs for social media

**G2: Demonstrate full-stack data engineering**

- Live connection to Snowflake marts built in PH-01 through PH-10
- Show the pipeline pays off with real insights

**G3: Attract attention from TTC / City of Toronto**

- Neutral, data-driven framing (not inflammatory)
- Actionable insights they could use internally
- Professional enough to share with transit planners

**G4: Serve as foundation for RAG layer**

- Architecture supports adding text-to-SQL interface later
- Clean separation of data access and presentation

### 2.2 Non-Goals

| ID  | Non-Goal              | Rationale                                                             |
| --- | --------------------- | --------------------------------------------------------------------- |
| NG1 | Real-time data        | Source data is monthly batch; real-time adds complexity without value |
| NG2 | User authentication   | Public dashboard; no sensitive data                                   |
| NG3 | Data editing          | Read-only; all writes happen in dbt pipeline                          |
| NG4 | Predictive analytics  | Descriptive focus; ML models are future scope                         |
| NG5 | Embedding in Focus OS | Standalone deployment first; embed later if valuable                  |

---

## 3. Data Foundation

### 3.1 Source Tables (Snowflake MARTS)

| Table                 | Rows       | Primary Use                           |
| --------------------- | ---------- | ------------------------------------- |
| `fct_transit_delays`  | 237,446    | TTC delay incidents                   |
| `fct_bike_trips`      | 21,795,223 | Individual bike trips                 |
| `fct_daily_mobility`  | 1,827      | Pre-aggregated daily metrics          |
| `dim_station`         | 1,085      | TTC + Bike Share stations with coords |
| `dim_date`            | 2,922      | Date dimension                        |
| `dim_weather`         | 2,922      | Daily weather conditions              |
| `dim_ttc_delay_codes` | 334        | Delay cause lookup                    |

### 3.2 Key Metrics

| Metric               | Value               | Derivation                        |
| -------------------- | ------------------- | --------------------------------- |
| Total delay hours    | 77,929              | `sum(delay_minutes) / 60`         |
| Total bike trips     | 21.8M               | `count(*)` from fct_bike_trips    |
| Date range           | Nov 2020 – Dec 2024 | 4+ years                          |
| Worst station        | Bloor-Yonge         | 10,587 delay minutes              |
| YoY delay trend      | +17%                | 18.1 min (2020) → 21.2 min (2024) |
| Bike growth          | +84%                | 2.9M (2020) → 5.3M (2024)         |
| Rain impact on bikes | -55%                | 14.5M clear vs 6.5M rainy         |

### 3.3 Geographic Coverage

| Station Type | Count | Has Coordinates |
| ------------ | ----- | --------------- |
| TTC Subway   | 75    | 74 (99%)        |
| Bike Share   | 1,009 | 1,009 (100%)    |

---

## 4. Information Architecture

### 4.1 Page Structure

```
┌─────────────────────────────────────────────────────────┐
│  Toronto Mobility Dashboard                              │
├─────────────────────────────────────────────────────────┤
│  [Overview] [TTC] [Bike Share] [Weather] [Explorer]     │
└─────────────────────────────────────────────────────────┘
```

### 4.2 Page Specifications

#### Page 1: Overview (Landing)

**Purpose**: First impression; hero stats; "is it getting better?" answer

**Components**:

| Component                   | Type            | Data Source                |
| --------------------------- | --------------- | -------------------------- |
| Hero metrics row            | `st.metric` x 4 | Aggregates                 |
| "9 years of delays" callout | Custom HTML     | Calculated                 |
| YoY trend sparkline         | Line chart      | fct_daily_mobility         |
| Mode comparison             | Bar chart       | fct_transit_delays grouped |
| Date range context          | Text            | dim_date min/max           |

**Hero Metrics**:

1. Total Delay Hours: **77,929** (↑ 17% vs 2020)
2. Total Bike Trips: **21.8M** (↑ 84% vs 2020)
3. Worst Station: **Bloor-Yonge**
4. Data Freshness: **Dec 2024**

**Interactivity**: Minimal — this is a summary page

---

#### Page 2: TTC Deep Dive

**Purpose**: Understand where, when, and why delays happen

**Components**:

| Component                | Type                    | Data Source              |
| ------------------------ | ----------------------- | ------------------------ |
| Date range filter        | `st.date_input`         | Global filter            |
| Transit mode filter      | `st.multiselect`        | subway/bus/streetcar     |
| Worst stations map       | PyDeck ScatterplotLayer | dim_station + aggregates |
| Worst stations bar chart | Altair horizontal bar   | Top 10 by delay minutes  |
| Delay causes treemap     | Plotly treemap          | dim_ttc_delay_codes      |
| Hour × Day heatmap       | Altair heatmap          | fct_transit_delays       |
| Year-over-year trend     | Line chart              | Monthly aggregates       |

**Key Insights to Surface**:

- "Bloor-Yonge accounts for X% of all subway delays"
- "Operations issues cause 47.5% of delays"
- "Friday 3-5 PM is peak delay time"
- "Delays are getting worse: +17% since 2020"

**Interactivity**:

- Date range slider (default: all time)
- Transit mode toggle (default: all)
- Click station on map → filter charts

---

#### Page 3: Bike Share Deep Dive

**Purpose**: Understand ridership patterns and growth

**Components**:

| Component            | Type                | Data Source               |
| -------------------- | ------------------- | ------------------------- |
| Date range filter    | `st.date_input`     | Global filter             |
| User type filter     | `st.multiselect`    | Annual/Casual             |
| Station activity map | PyDeck HeatmapLayer | dim_station + trip counts |
| Growth curve         | Area chart          | Yearly totals             |
| Member vs Casual     | Stacked bar         | fct_bike_trips grouped    |
| Seasonality          | Line chart by month | All years overlaid        |
| Top stations table   | `st.dataframe`      | Top 20 start stations     |

**Key Insights to Surface**:

- "Casual riders now dominate: 89% of trips in 2024"
- "Summer ridership is 5x winter"
- "Waterfront stations lead: Queens Quay dominates"
- "Average trip: 17.5 minutes"

**Interactivity**:

- Date range slider
- User type toggle
- Click station on map → show station details

---

#### Page 4: Weather Impact

**Purpose**: Quantify weather effects on transit choices

**Components**:

| Component                | Type            | Data Source                      |
| ------------------------ | --------------- | -------------------------------- |
| Weather condition filter | `st.selectbox`  | Clear/Rain/Snow                  |
| Bike trips by weather    | Bar chart       | fct_bike_trips + dim_weather     |
| Delays by weather        | Bar chart       | fct_transit_delays + dim_weather |
| Temperature scatter      | Scatter plot    | Daily temp vs trips              |
| Precipitation scatter    | Scatter plot    | Daily precip vs trips            |
| Key callouts             | `st.info` boxes | Calculated comparisons           |

**Key Insights to Surface**:

- "Rain reduces bike trips by 55%"
- "Snow increases TTC delays by only 8%"
- "Sweet spot: 15-25°C sees peak bike usage"

**Interactivity**:

- Weather condition comparison selector
- Hover for daily details on scatter

---

#### Page 5: Station Explorer

**Purpose**: Deep dive into individual stations

**Components**:

| Component           | Type                       | Data Source                 |
| ------------------- | -------------------------- | --------------------------- |
| Station search      | `st.selectbox` with search | dim_station                 |
| Station type toggle | `st.radio`                 | TTC / Bike Share            |
| Station map         | PyDeck centered on station | Single point                |
| Delay history (TTC) | Line chart                 | fct_transit_delays filtered |
| Trip history (Bike) | Line chart                 | fct_bike_trips filtered     |
| Station stats       | `st.metric` cards          | Aggregated                  |
| Nearby stations     | Table                      | Geographic proximity        |

**Interactivity**:

- Search/select any of 1,084 stations
- Compare up to 3 stations (stretch goal)

---

## 5. Technical Architecture

### 5.1 Stack

| Layer    | Technology                               | Rationale                               |
| -------- | ---------------------------------------- | --------------------------------------- |
| Frontend | Streamlit 1.31+                          | Rapid development, Python-native        |
| Charts   | Altair + Plotly                          | Altair for standard, Plotly for complex |
| Maps     | PyDeck                                   | GPU-accelerated, handles 1K+ points     |
| Data     | Snowflake via snowflake-connector-python | Direct connection to marts              |
| Caching  | `st.cache_data`                          | Reduce redundant queries                |
| Hosting  | Streamlit Community Cloud                | Free, GitHub integration                |

### 5.2 Project Structure

```
dashboard/
├── app.py                    # Main entry, page routing
├── pages/
│   ├── 1_Overview.py
│   ├── 2_TTC_Deep_Dive.py
│   ├── 3_Bike_Share.py
│   ├── 4_Weather_Impact.py
│   └── 5_Station_Explorer.py
├── components/
│   ├── metrics.py            # Reusable metric cards
│   ├── charts.py             # Chart factory functions
│   ├── maps.py               # PyDeck map builders
│   └── filters.py            # Sidebar filter components
├── data/
│   ├── connection.py         # Snowflake connection manager
│   ├── queries.py            # SQL query definitions
│   └── cache.py              # Caching utilities
├── styles/
│   └── custom.css            # Custom styling overrides
├── .streamlit/
│   └── config.toml           # Theme configuration
├── requirements.txt
├── README.md
└── secrets.toml.example      # Template for credentials
```

### 5.3 Snowflake Connection

```python
# data/connection.py
import streamlit as st
from snowflake.connector import connect

@st.cache_resource
def get_connection():
    return connect(
        account=st.secrets["snowflake"]["account"],
        user=st.secrets["snowflake"]["user"],
        password=st.secrets["snowflake"]["password"],
        warehouse=st.secrets["snowflake"]["warehouse"],
        database=st.secrets["snowflake"]["database"],
        schema="MARTS",
        role=st.secrets["snowflake"]["role"],
    )

@st.cache_data(ttl=3600)
def run_query(query: str) -> pd.DataFrame:
    conn = get_connection()
    return pd.read_sql(query, conn)
```

### 5.4 Query Patterns

All queries target MARTS layer tables. Examples:

```sql
-- Hero stats (cached for 1 hour)
SELECT
    COUNT(*) as total_delays,
    SUM(delay_minutes) as total_minutes,
    ROUND(SUM(delay_minutes) / 60, 0) as total_hours
FROM fct_transit_delays;

-- Station delays for map (parameterized by date range)
SELECT
    s.station_name,
    s.latitude,
    s.longitude,
    COUNT(*) as delay_count,
    SUM(d.delay_minutes) as total_minutes
FROM fct_transit_delays d
JOIN dim_station s ON d.station_key = s.station_key
WHERE d.date_key BETWEEN %(start_date)s AND %(end_date)s
  AND d.transit_mode = 'subway'
GROUP BY 1, 2, 3;
```

### 5.5 Caching Strategy

| Data Type        | TTL      | Rationale                   |
| ---------------- | -------- | --------------------------- |
| Hero stats       | 1 hour   | Rarely changes              |
| Aggregations     | 30 min   | Balance freshness vs. cost  |
| Filtered queries | 10 min   | User-specific, more dynamic |
| Station list     | 24 hours | Static reference data       |

### 5.6 Performance Targets

| Metric          | Target | Measurement               |
| --------------- | ------ | ------------------------- |
| Cold start      | < 5s   | First page load           |
| Warm navigation | < 1s   | Switching pages           |
| Filter response | < 2s   | Applying date/mode filter |
| Map render      | < 2s   | 1,000+ points             |

---

## 6. Design System

### 6.1 Color Palette

| Element     | Color     | Hex     |
| ----------- | --------- | ------- |
| TTC Primary | Red       | #DA291C |
| Bike Share  | Green     | #43B02A |
| Neutral     | Slate     | #334155 |
| Background  | Off-white | #FAFAFA |
| Accent      | Blue      | #2563EB |
| Warning     | Amber     | #F59E0B |

### 6.2 Typography

- **Headers**: Inter Bold
- **Body**: Inter Regular
- **Metrics**: Inter Semibold, large size
- **Code/Data**: JetBrains Mono

### 6.3 Chart Styling

```python
# Altair theme
def toronto_theme():
    return {
        "config": {
            "view": {"stroke": "transparent"},
            "axis": {
                "labelFont": "Inter",
                "titleFont": "Inter",
                "labelFontSize": 12,
                "titleFontSize": 14,
            },
            "legend": {
                "labelFont": "Inter",
                "titleFont": "Inter",
            },
        }
    }
```

### 6.4 Map Styling

- Dark base map (Mapbox Dark)
- TTC delays: Red gradient (light = few, dark = many)
- Bike stations: Green gradient by trip volume
- Selected station: Blue highlight ring

---

## 7. Implementation Plan

### Phase 1: Foundation (Day 1)

| Task                                    | Hours |
| --------------------------------------- | ----- |
| Project scaffold + Snowflake connection | 2     |
| Config/secrets management               | 1     |
| Base styling + theme                    | 1     |
| Hero metrics component                  | 1     |
| Overview page (static)                  | 2     |

**Deliverable**: Working app with Overview page showing hero stats

### Phase 2: TTC Page (Day 2)

| Task                        | Hours |
| --------------------------- | ----- |
| Date range filter component | 1     |
| Worst stations bar chart    | 1     |
| Delay causes breakdown      | 1     |
| Hour × Day heatmap          | 2     |
| Station map (PyDeck)        | 2     |
| Year-over-year trend        | 1     |

**Deliverable**: Fully interactive TTC page with map

### Phase 3: Bike Share + Weather (Day 3)

| Task                         | Hours |
| ---------------------------- | ----- |
| Bike Share growth chart      | 1     |
| Member vs Casual stacked bar | 1     |
| Seasonality overlay          | 1     |
| Station heatmap              | 2     |
| Weather comparison charts    | 2     |
| Scatter plots (temp, precip) | 1     |

**Deliverable**: Bike Share and Weather pages complete

### Phase 4: Explorer + Polish (Day 4)

| Task                         | Hours |
| ---------------------------- | ----- |
| Station search/select        | 1     |
| Station detail view          | 2     |
| Cross-page navigation polish | 1     |
| Mobile responsiveness fixes  | 1     |
| README + deployment          | 2     |
| Demo GIF recording           | 1     |

**Deliverable**: Production-ready dashboard deployed to Streamlit Cloud

---

## 8. Deployment

### 8.1 Streamlit Community Cloud

1. Push code to `toronto-mobility-analytics` repo (subdirectory or separate repo)
2. Connect Streamlit Cloud to GitHub
3. Configure secrets via Streamlit Cloud UI
4. Set Python version to 3.12
5. Deploy

### 8.2 Secrets Configuration

```toml
# .streamlit/secrets.toml (local) or Streamlit Cloud secrets
[snowflake]
account = "xxx.us-east-1"
user = "DASHBOARD_SVC"
password = "***"
warehouse = "TRANSFORM_WH"
database = "TORONTO_MOBILITY"
role = "TRANSFORMER_ROLE"
```

### 8.3 Service Account

Create a read-only Snowflake user for the dashboard:

```sql
CREATE USER DASHBOARD_SVC
  PASSWORD = '***'
  DEFAULT_WAREHOUSE = TRANSFORM_WH
  DEFAULT_ROLE = TRANSFORMER_ROLE;

GRANT ROLE TRANSFORMER_ROLE TO USER DASHBOARD_SVC;
```

---

## 9. Future Enhancements

### 9.1 RAG Integration (v2)

Add a "Ask a Question" tab:

- Text input for natural language queries
- RAG retrieves relevant schema context from embedded dbt metadata
- LLM generates SQL → executes → returns natural language answer
- Example: "What's the worst station on Line 1?" → "Finch with 7,124 delay minutes"

### 9.2 Embedding in Focus OS (v3)

- Create iframe-friendly version
- Embed as a "project" within Focus OS portfolio site
- Unified portfolio experience

### 9.3 Alerting (v4)

- Weekly email digest of key metrics
- "This week in Toronto transit" summary

---

## 10. Risks and Mitigations

| Risk                                      | Likelihood | Impact   | Mitigation                                                                          |
| ----------------------------------------- | ---------- | -------- | ----------------------------------------------------------------------------------- |
| Snowflake costs from dashboard queries    | Medium     | Medium   | Aggressive caching (1hr TTL on heavy queries); read-only warehouse; monitor credits |
| Streamlit Cloud cold starts slow          | Medium     | Low      | Keep app active with uptime monitor; optimize imports                               |
| fct_bike_trips (21.8M rows) query timeout | Medium     | High     | Pre-aggregate to daily/station level; never scan full table                         |
| PyDeck map doesn't render on mobile       | Low        | Medium   | Fallback to static image on mobile viewport                                         |
| Snowflake credentials exposed             | Low        | Critical | Use Streamlit secrets; never commit credentials; rotate quarterly                   |

---

## 11. Appendix

### 11.1 Sample Queries

See `analyses/` folder in toronto-mobility-analytics repo:

- `daily_mobility_summary.sql`
- `top_delay_stations.sql`
- `bike_weather_correlation.sql`
- `cross_modal_analysis.sql`
- `monthly_trends.sql`

### 11.2 Reference Dashboards

- [TTC Service Alerts](https://www.ttc.ca/service-alerts) — official TTC style
- [Bike Share Toronto Dashboard](https://bikesharetoronto.com/) — official Bike Share style
- [NYC Subway Performance](https://new.mta.info/transparency/metrics) — best-in-class transit dashboard

### 11.3 Data Refresh Cadence

| Source     | Refresh                     | Dashboard Impact                |
| ---------- | --------------------------- | ------------------------------- |
| TTC Delays | Monthly                     | New data appears ~5th of month  |
| Bike Share | Monthly                     | New data appears ~10th of month |
| Weather    | Daily (but we load monthly) | Aligned with transit refresh    |

Dashboard caches auto-expire; no manual refresh needed.
