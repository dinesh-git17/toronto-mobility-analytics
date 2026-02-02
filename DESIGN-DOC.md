# Toronto Urban Mobility Analytics

## Technical Design Document

| Field                 | Value                    |
| --------------------- | ------------------------ |
| **Author**            | Dinesh                   |
| **Reviewers**         | —                        |
| **Status**            | Approved                 |
| **Created**           | 2026-01-30               |
| **Last Updated**      | 2026-02-02               |
| **Target Completion** | Flexible (quality-gated) |

---

## Table of Contents

1. [Overview](#1-overview)
2. [Goals and Non-Goals](#2-goals-and-non-goals)
3. [Background](#3-background)
4. [Data Sources](#4-data-sources)
5. [System Architecture](#5-system-architecture)
6. [Data Model](#6-data-model)
7. [Implementation Plan](#7-implementation-plan)
8. [Testing Strategy](#8-testing-strategy)
9. [Observability](#9-observability)
10. [Security](#10-security)
11. [Cost Analysis](#11-cost-analysis)
12. [Risks and Mitigations](#12-risks-and-mitigations)
13. [Future Enhancements](#13-future-enhancements)
14. [Decisions Log](#14-decisions-log)
15. [Appendix](#15-appendix)

---

## 1. Overview

### 1.1 Executive Summary

Toronto Urban Mobility Analytics is a **portfolio project** demonstrating production-grade data engineering practices. It transforms raw transit and cycling data from the City of Toronto Open Data Portal into analytics-ready datasets using modern ELT patterns with dbt and Snowflake.

The project provides insights into how Torontonians navigate the city via TTC transit and Bike Share Toronto, covering **2019–present** data across subway/bus/streetcar delays and bike share trips.

### 1.2 Problem Statement

Toronto's Open Data Portal contains transportation datasets spanning multiple years of transit delays (~300K rows/year across modes) and millions of bike share trips (~5M rows/year). These datasets exist in isolation across dozens of files with inconsistent schemas, making cross-modal analysis impossible without significant data engineering effort.

**Specific pain points:**

- TTC delay data uses inconsistent station naming across years
- Bike Share and TTC use different geographic identifiers
- No unified time dimension for cross-modal correlation
- Weather impact analysis requires manual data integration

### 1.3 Proposed Solution

Build a medallion-architecture data pipeline that:

1. **Ingests** raw data from Toronto Open Data Portal into Snowflake with schema validation
2. **Transforms** data through staging → intermediate → marts layers using dbt
3. **Produces** analytics-ready fact and dimension tables for urban mobility analysis
4. **Validates** data quality with comprehensive testing and observability

### 1.4 Success Criteria

| Metric            | Target                         | Measurement Method                                   |
| ----------------- | ------------------------------ | ---------------------------------------------------- |
| Data freshness    | Monthly refresh capability     | Source freshness tests pass with warn_after: 45 days |
| Test coverage     | 100% of mart models have tests | `dbt test --select tag:marts` returns 0 failures     |
| Documentation     | All models documented          | `dbt docs generate` with no missing descriptions     |
| Query performance | Benchmark queries < 5 seconds  | 5 defined queries on X-Small warehouse (see §15.4)   |
| Data completeness | ≥99% of source rows loaded     | Row count comparison: raw vs. staging                |

---

## 2. Goals and Non-Goals

### 2.1 Goals

**G1: Demonstrate Modern Analytics Engineering**

- Implement medallion architecture (staging/intermediate/marts)
- Use dbt best practices: sources, staging models, intermediate transforms, mart models
- All intermediate models materialized as ephemeral (CTEs)
- Facts and dimensions materialized as tables

**G2: Enable Cross-Modal Transit Analysis**

- Join TTC delay data with Bike Share ridership by date and geography
- Integrate daily weather data to analyze environmental impact on transit patterns
- Produce station-level and time-series aggregations

**G3: Showcase Production-Grade Practices**

- Comprehensive dbt tests (unique, not_null, accepted_values, relationships)
- Schema validation at ingestion with fail-fast behavior
- Full model documentation with column descriptions
- Data lineage via dbt docs
- CI/CD pipeline for dbt runs

**G4: Create Portfolio-Worthy Deliverable**

- Clean, well-documented GitHub repository
- README with architecture diagrams
- Executable sample queries with expected results
- Deployed dbt docs site

### 2.2 Non-Goals

| ID  | Non-Goal                 | Rationale                                                                     |
| --- | ------------------------ | ----------------------------------------------------------------------------- |
| NG1 | Real-time streaming      | Batch processing only; real-time Bike Share station availability out of scope |
| NG2 | Predictive modeling      | No ML models; focus is descriptive analytics and data engineering             |
| NG3 | Frontend dashboard       | No Tableau/Looker/Streamlit; dbt docs and SQL queries are primary interface   |
| NG4 | Production orchestration | No Airflow/Dagster in v1; manual or scheduled Snowflake Task triggers only    |
| NG5 | Multi-region expansion   | Toronto only; no other Canadian cities                                        |
| NG6 | TTC ridership aggregates | Ridership data excluded; delays-only scope (see Decision D1)                  |
| NG7 | Hourly weather           | Daily grain only; hourly adds complexity without proportional value           |

---

## 3. Background

### 3.1 Toronto Transit Commission (TTC)

The TTC is North America's third-largest public transit system, serving approximately 1.7 million daily riders across:

- **4 subway lines** (77 stations): Line 1 Yonge-University (YU), Line 2 Bloor-Danforth (BD), Line 3 Scarborough (SRT - _closed November 2023_), Line 4 Sheppard (SHP)
- **150+ bus routes**
- **10 streetcar routes**

The TTC publishes monthly delay data for each mode, including delay duration, cause codes, location, and timestamps.

> **Note:** Scarborough RT (Line 3/SRT) was permanently closed on November 19, 2023. Historical delay data for SRT is included for completeness but analysis should account for this discontinuity.

### 3.2 Bike Share Toronto

Bike Share Toronto operates 6,850+ bikes across 625+ stations. The system has grown from 665,000 trips in 2015 to 5.7 million trips in 2023. Historical ridership data includes trip start/end times, station IDs, and user type (annual member vs. casual).

**Data scope:** 2019–present (~30 million total trip records)

### 3.3 Prior Art

| Project                                                                                                 | Type              | Differentiation                                                 |
| ------------------------------------------------------------------------------------------------------- | ----------------- | --------------------------------------------------------------- |
| [TTC Delay Report 2022](https://medium.com/@tusharsharma_505/ttc-subway-delay-report-2022-e5e00e79b7c7) | Tableau dashboard | One-time analysis; this project creates reusable infrastructure |
| [Bike Share Growth Analysis](https://schoolofcities.github.io/bike-share-toronto/growth)                | Static analysis   | Academic focus; this project emphasizes engineering practices   |
| [TTC Bus and Subway Delay Analysis](https://github.com/JasonYao3/TTC_transit_delay_proj)                | Python notebook   | Ad-hoc analysis; this project creates tested, documented models |

---

## 4. Data Sources

### 4.1 Primary Sources

| Source            | Dataset              | Format   | Est. Size (2019-present) | Refresh | URL                                                                        |
| ----------------- | -------------------- | -------- | ------------------------ | ------- | -------------------------------------------------------------------------- |
| Toronto Open Data | TTC Subway Delays    | XLSX/CSV | ~300K rows               | Monthly | [Link](https://open.toronto.ca/dataset/ttc-subway-delay-data/)             |
| Toronto Open Data | TTC Bus Delays       | XLSX/CSV | ~1.2M rows               | Monthly | [Link](https://open.toronto.ca/dataset/ttc-bus-delay-data/)                |
| Toronto Open Data | TTC Streetcar Delays | XLSX/CSV | ~300K rows               | Monthly | [Link](https://open.toronto.ca/dataset/ttc-streetcar-delay-data/)          |
| Toronto Open Data | Bike Share Ridership | CSV      | ~30M rows                | Monthly | [Link](https://open.toronto.ca/dataset/bike-share-toronto-ridership-data/) |

### 4.2 Enrichment Sources

| Source             | Dataset                                                 | Purpose                         | Format        | URL                                                                                  |
| ------------------ | ------------------------------------------------------- | ------------------------------- | ------------- | ------------------------------------------------------------------------------------ |
| Environment Canada | Historical Weather (Toronto Pearson, Station ID: 51459) | Weather correlation             | CSV           | [Link](https://climate.weather.gc.ca/climate_data/daily_data_e.html?StationID=51459) |
| Static Seed        | Date Dimension                                          | Time intelligence               | Generated SQL | —                                                                                    |
| Static Seed        | TTC Station Reference                                   | Station metadata + name mapping | CSV           | Manual curation                                                                      |
| Static Seed        | Bike Share Station Reference                            | Station geo + neighborhoods     | CSV           | GBFS snapshot                                                                        |
| Static Seed        | TTC Delay Codes                                         | Code → description mapping      | CSV           | Manual curation                                                                      |

### 4.3 Data Contracts

#### 4.3.1 TTC Subway Delay Schema (Expected)

| Column    | Type    | Description                          | Nullable | Validation                       |
| --------- | ------- | ------------------------------------ | -------- | -------------------------------- |
| Date      | DATE    | Date of delay incident               | No       | Valid date 2019-01-01 to present |
| Time      | TIME    | Time of delay incident               | No       | Valid time HH:MM                 |
| Day       | STRING  | Day of week                          | No       | One of: Monday-Sunday            |
| Station   | STRING  | Station name (raw, requires mapping) | No       | Non-empty string                 |
| Code      | STRING  | Delay cause code                     | Yes      | Matches seed codes or NULL       |
| Min Delay | INTEGER | Delay duration in minutes            | No       | ≥ 0                              |
| Min Gap   | INTEGER | Gap between trains in minutes        | Yes      | ≥ 0 or NULL                      |
| Bound     | STRING  | Direction (N/S/E/W)                  | Yes      | One of: N, S, E, W, or NULL      |
| Line      | STRING  | Subway line code                     | No       | One of: YU, BD, SHP, SRT         |

**Schema Change Policy:** If source schema differs from expected, ingestion **fails immediately** with detailed error message. No partial loads permitted.

#### 4.3.2 Bike Share Trip Schema (Expected)

| Column             | Type      | Description              | Nullable | Validation                           |
| ------------------ | --------- | ------------------------ | -------- | ------------------------------------ |
| Trip Id            | STRING    | Unique trip identifier   | No       | Non-empty, unique per file           |
| Trip Duration      | INTEGER   | Duration in seconds      | No       | ≥ 60 (filter applied)                |
| Start Station Id   | INTEGER   | Origin station ID        | No       | Exists in station reference          |
| Start Time         | TIMESTAMP | Trip start timestamp     | No       | Valid timestamp 2019+                |
| Start Station Name | STRING    | Origin station name      | No       | Non-empty                            |
| End Station Id     | INTEGER   | Destination station ID   | No       | Exists in station reference          |
| End Time           | TIMESTAMP | Trip end timestamp       | No       | Valid timestamp, > Start Time        |
| End Station Name   | STRING    | Destination station name | No       | Non-empty                            |
| Bike Id            | INTEGER   | Bike identifier          | No       | Positive integer                     |
| User Type          | STRING    | Annual Member or Casual  | No       | One of: Annual Member, Casual Member |

#### 4.3.3 Weather Daily Schema (Expected)

| Column                 | Type    | Description            | Nullable |
| ---------------------- | ------- | ---------------------- | -------- |
| Date/Time              | DATE    | Observation date       | No       |
| Mean Temp (°C)         | DECIMAL | Daily mean temperature | Yes      |
| Total Precip (mm)      | DECIMAL | Total precipitation    | Yes      |
| Snow on Grnd (cm)      | DECIMAL | Snow depth             | Yes      |
| Spd of Max Gust (km/h) | DECIMAL | Maximum wind gust      | Yes      |

---

## 5. System Architecture

### 5.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           DATA SOURCES                                   │
├─────────────────┬─────────────────┬─────────────────┬───────────────────┤
│ TTC Subway      │ TTC Bus         │ Bike Share      │ Weather           │
│ Delays (XLSX)   │ Delays (XLSX)   │ Ridership (CSV) │ (CSV)             │
└────────┬────────┴────────┬────────┴────────┬────────┴───────────┬───────┘
         │                 │                 │                    │
         └─────────────────┴────────┬────────┴────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        INGESTION LAYER                                   │
│            Python Scripts (Atomic Transactions, Schema Validation)       │
│                                                                          │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐              │
│   │  download.py │───▶│ validate.py  │───▶│   load.py    │              │
│   │  (fetch)     │    │ (schema chk) │    │ (COPY INTO)  │              │
│   └──────────────┘    └──────────────┘    └──────────────┘              │
│                                                                          │
│   On schema mismatch: FAIL FAST → Alert → No partial load               │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            SNOWFLAKE                                     │
│  Database: TORONTO_MOBILITY                                              │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                         RAW SCHEMA                                  │ │
│  │  ┌────────────────┐ ┌────────────────┐ ┌────────────────┐          │ │
│  │  │TTC_SUBWAY_DELAY│ │TTC_BUS_DELAYS  │ │BIKE_SHARE_TRIPS│          │ │
│  │  └────────────────┘ └────────────────┘ └────────────────┘          │ │
│  │  ┌────────────────┐ ┌────────────────┐                              │ │
│  │  │TTC_STREETCAR_  │ │WEATHER_DAILY   │                              │ │
│  │  │DELAYS          │ │                │                              │ │
│  │  └────────────────┘ └────────────────┘                              │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                    │                                     │
│                                    ▼                                     │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                       dbt TRANSFORMS                                │ │
│  │                                                                      │ │
│  │   STAGING (Views)      INTERMEDIATE (Ephemeral)    MARTS (Tables)   │ │
│  │   ┌──────────────┐     ┌──────────────────┐       ┌──────────────┐  │ │
│  │   │stg_ttc_*     │────▶│int_ttc_delays_   │──────▶│fct_transit_  │  │ │
│  │   │              │     │unioned           │       │delays        │  │ │
│  │   └──────────────┘     │int_ttc_delays_   │       └──────────────┘  │ │
│  │   ┌──────────────┐     │enriched          │       ┌──────────────┐  │ │
│  │   │stg_bike_trips│────▶└──────────────────┘──────▶│fct_bike_trips│  │ │
│  │   └──────────────┘     ┌──────────────────┐       └──────────────┘  │ │
│  │   ┌──────────────┐     │int_daily_*       │       ┌──────────────┐  │ │
│  │   │stg_weather_  │────▶│                  │──────▶│fct_daily_    │  │ │
│  │   │daily         │     └──────────────────┘       │mobility      │  │ │
│  │   └──────────────┘                                └──────────────┘  │ │
│  │                                                   ┌──────────────┐  │ │
│  │                                                   │dim_date      │  │ │
│  │                                                   │dim_station   │  │ │
│  │                                                   │dim_weather   │  │ │
│  │                                                   │dim_delay_code│  │ │
│  │                                                   └──────────────┘  │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Technology Stack

| Layer           | Technology     | Version          | Rationale                                                                          |
| --------------- | -------------- | ---------------- | ---------------------------------------------------------------------------------- |
| Storage         | Snowflake      | Enterprise Trial | Industry-standard cloud DW, free trial (30 days, $400 credits), native dbt support |
| Transform       | dbt Core       | 1.8+             | Open source, SQL-based, excellent documentation; 1.8+ required for latest adapters |
| Ingestion       | Python         | 3.12             | 10-60% performance improvement over 3.11; full Snowflake connector support         |
| Version Control | Git/GitHub     | —                | Standard, enables CI/CD                                                            |
| CI/CD           | GitHub Actions | —                | Free tier (2,000 mins/month), native dbt integration                               |
| Documentation   | dbt docs       | —                | Auto-generated lineage and docs                                                    |
| Linting         | SQLFluff       | 3.3+             | SQL linting with improved Snowflake dialect support                                |
| Formatting      | sqlfmt         | 0.23+            | Opinionated SQL formatter; separates formatting from linting concerns              |
| Observability   | Elementary     | 0.16+            | dbt-native anomaly detection, schema change alerts, artifact analysis              |

### 5.3 Snowflake Object Hierarchy

```
TORONTO_MOBILITY (Database)
├── RAW (Schema)
│   ├── TTC_SUBWAY_DELAYS     [Table, owner: LOADER_ROLE]
│   ├── TTC_BUS_DELAYS        [Table, owner: LOADER_ROLE]
│   ├── TTC_STREETCAR_DELAYS  [Table, owner: LOADER_ROLE]
│   ├── BIKE_SHARE_TRIPS      [Table, owner: LOADER_ROLE]
│   └── WEATHER_DAILY         [Table, owner: LOADER_ROLE]
├── STAGING (Schema)          [Views, owner: TRANSFORMER_ROLE]
├── INTERMEDIATE (Schema)     [Ephemeral - no objects]
├── MARTS (Schema)            [Tables, owner: TRANSFORMER_ROLE]
└── SEEDS (Schema)            [Tables, owner: TRANSFORMER_ROLE]
    ├── TTC_DELAY_CODES
    ├── TTC_STATION_MAPPING   (name variants → canonical key)
    └── BIKE_STATION_REF
```

### 5.4 Data Retention Policy

| Schema  | Retention   | Rationale                                  |
| ------- | ----------- | ------------------------------------------ |
| RAW     | Indefinite  | Source of truth; enables full reprocessing |
| STAGING | N/A (views) | No storage; always computed from RAW       |
| MARTS   | Indefinite  | Query targets; minimal storage (~10GB)     |
| SEEDS   | Indefinite  | Reference data; minimal storage            |

---

## 6. Data Model

### 6.1 Entity Relationship Diagram

```
                         ┌─────────────────┐
                         │    dim_date     │
                         │─────────────────│
                         │ date_key PK     │
                         │ full_date       │
                         │ day_of_week     │
                         │ day_of_week_num │
                         │ month_num       │
                         │ month_name      │
                         │ quarter         │
                         │ year            │
                         │ is_weekend      │
                         │ is_holiday      │
                         └────────┬────────┘
                                  │
            ┌─────────────────────┼─────────────────────┐
            │                     │                     │
            ▼                     ▼                     ▼
┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│ fct_transit_delays  │  │   fct_bike_trips    │  │    dim_weather      │
│─────────────────────│  │─────────────────────│  │─────────────────────│
│ delay_sk PK         │  │ trip_sk PK          │  │ date_key PK/FK      │
│ date_key FK         │  │ date_key FK         │  │ mean_temp_c         │
│ station_key FK      │  │ start_station_key FK│  │ total_precip_mm     │
│ delay_code_key FK   │  │ end_station_key FK  │  │ snow_on_ground_cm   │
│ delay_minutes       │  │ duration_seconds    │  │ max_wind_gust_kmh   │
│ gap_minutes         │  │ user_type           │  │ weather_condition   │
│ transit_mode        │  │ bike_id             │  └─────────────────────┘
│ line_code           │  │ start_time          │
│ direction           │  │ end_time            │
│ incident_timestamp  │  └──────────┬──────────┘
└──────────┬──────────┘             │
           │                        │
           ▼                        ▼
     ┌─────────────────────────────────────┐
     │           dim_station               │
     │─────────────────────────────────────│
     │ station_key PK                      │
     │ station_id (natural key)            │
     │ station_name                        │
     │ station_type (TTC_SUBWAY/TTC_BUS/   │
     │               TTC_STREETCAR/        │
     │               BIKE_SHARE)           │
     │ latitude                            │
     │ longitude                           │
     │ neighborhood                        │
     │ ward                                │
     └─────────────────────────────────────┘

     ┌─────────────────────────────────────┐
     │        dim_ttc_delay_codes          │
     │─────────────────────────────────────│
     │ delay_code_key PK                   │
     │ delay_code (natural key)            │
     │ delay_description                   │
     │ delay_category                      │
     └─────────────────────────────────────┘
```

### 6.2 Dimension Strategy

| Dimension           | SCD Type             | Rationale                                                                       |
| ------------------- | -------------------- | ------------------------------------------------------------------------------- |
| dim_date            | Type 0 (static)      | Generated date spine; never changes                                             |
| dim_station         | Type 1 (overwrite)   | Reflects current state; historical station state is low-value for this analysis |
| dim_weather         | Type 0 (append-only) | Historical weather is immutable                                                 |
| dim_ttc_delay_codes | Type 1 (overwrite)   | Code descriptions may be refined                                                |

### 6.3 Model Specifications

#### Staging Models (Materialized as Views)

| Model                      | Source                   | Grain                      | Key Transformations                                                       |
| -------------------------- | ------------------------ | -------------------------- | ------------------------------------------------------------------------- |
| `stg_ttc_subway_delays`    | raw.ttc_subway_delays    | One row per delay incident | Type casting, column renaming, null handling, surrogate key generation    |
| `stg_ttc_bus_delays`       | raw.ttc_bus_delays       | One row per delay incident | Type casting, column renaming, null handling, surrogate key generation    |
| `stg_ttc_streetcar_delays` | raw.ttc_streetcar_delays | One row per delay incident | Type casting, column renaming, null handling, surrogate key generation    |
| `stg_bike_trips`           | raw.bike_share_trips     | One row per trip           | Type casting, **filter: duration ≥ 60 seconds**, surrogate key generation |
| `stg_weather_daily`        | raw.weather_daily        | One row per day            | Unit standardization, null handling                                       |

#### Intermediate Models (Materialized as Ephemeral)

| Model                       | Sources                        | Purpose                                                            |
| --------------------------- | ------------------------------ | ------------------------------------------------------------------ |
| `int_ttc_delays_unioned`    | All stg*ttc*\* models          | Union all transit modes with mode identifier                       |
| `int_ttc_delays_enriched`   | int_ttc_delays_unioned + seeds | Join delay codes, map station names via `ttc_station_mapping` seed |
| `int_bike_trips_enriched`   | stg_bike_trips + dim_station   | Add station geo, calculate duration buckets                        |
| `int_daily_transit_metrics` | int_ttc_delays_enriched        | Pre-aggregate delays to daily grain                                |
| `int_daily_bike_metrics`    | int_bike_trips_enriched        | Pre-aggregate trips to daily grain                                 |

#### Mart Models (Materialized as Tables)

| Model                 | Grain                                  | Primary Use Case                         | Est. Rows |
| --------------------- | -------------------------------------- | ---------------------------------------- | --------- |
| `fct_transit_delays`  | One row per delay incident             | Delay analysis, root cause investigation | ~1.8M     |
| `fct_bike_trips`      | One row per trip                       | Trip pattern analysis                    | ~30M      |
| `fct_daily_mobility`  | One row per date                       | Cross-modal daily aggregates             | ~2,200    |
| `dim_date`            | One row per calendar date (2019-2026)  | Time intelligence                        | ~2,900    |
| `dim_station`         | One row per station (TTC + Bike Share) | Location dimension                       | ~800      |
| `dim_weather`         | One row per date                       | Weather correlation                      | ~2,200    |
| `dim_ttc_delay_codes` | One row per delay code                 | Code lookup                              | ~50       |

### 6.4 Surrogate Key Strategy

Surrogate keys are generated using `dbt_utils.generate_surrogate_key()` with the following natural key components:

| Model                 | Natural Key Components                                  | Collision Risk Mitigation                                                 |
| --------------------- | ------------------------------------------------------- | ------------------------------------------------------------------------- |
| stg_ttc_subway_delays | `[date, time, station, line, delay_code, min_delay]`    | Added `min_delay` to disambiguate multiple incidents at same station/time |
| stg_ttc_bus_delays    | `[date, time, route, direction, delay_code, min_delay]` | Route + direction + delay included                                        |
| stg_bike_trips        | `[trip_id]`                                             | Source provides unique ID                                                 |
| dim_station           | `[station_type, station_id]`                            | Composite key prevents cross-type collision                               |

### 6.5 Station Name Mapping Strategy

TTC delay data contains raw station names with inconsistent spelling across years. Resolution approach:

1. **Manual seed file** (`seeds/ttc_station_mapping.csv`) maps all known name variants to canonical station_key
2. Seed file structure:
   ```csv
   raw_station_name,canonical_station_name,station_key,line_code
   "BLOOR STN","Bloor-Yonge",ST_001,YU
   "BLOOR STATION","Bloor-Yonge",ST_001,YU
   "BLOOR-YONGE","Bloor-Yonge",ST_001,YU
   ```
3. **Unmatched records** are flagged with `station_key = 'UNKNOWN'` and reported in data quality tests
4. Seed file is curated during Phase 1 by analyzing distinct station names in source data

---

## 7. Implementation Plan

### 7.1 Phase Overview

| Phase | Focus              | Deliverables                                | Dependencies | Exit Criteria                                      |
| ----- | ------------------ | ------------------------------------------- | ------------ | -------------------------------------------------- |
| 0     | Environment Setup  | Snowflake account, dbt project, GitHub repo | None         | `dbt debug` passes                                 |
| 1     | Data Ingestion     | Raw data in Snowflake, station mapping seed | Phase 0      | Row counts validated                               |
| 2     | Staging Layer      | All staging models, source tests            | Phase 1      | `dbt build --select staging` passes                |
| 3     | Intermediate Layer | Union, enrichment, pre-aggregation models   | Phase 2      | `dbt build --select intermediate` passes           |
| 4     | Marts Layer        | Facts, dimensions                           | Phase 3      | `dbt build --select marts` passes                  |
| 5     | Testing & Docs     | Full test suite, documentation              | Phase 4      | `dbt test` 100% pass, `dbt docs generate` succeeds |
| 6     | CI/CD & Polish     | GitHub Actions, README                      | Phase 5      | CI pipeline green, README complete                 |

**Timeline:** Flexible; quality-gated milestones rather than fixed dates. Each phase completes when exit criteria met.

### 7.2 Phase 0: Environment Setup

**Tasks:**

- [ ] Create Snowflake trial account (Enterprise edition)
- [ ] Execute `setup/snowflake_init.sql` to create:
  - Database: `TORONTO_MOBILITY`
  - Schemas: `RAW`, `STAGING`, `INTERMEDIATE`, `MARTS`, `SEEDS`
  - Warehouse: `TRANSFORM_WH` (X-Small, auto-suspend 60s)
  - Roles: `LOADER_ROLE`, `TRANSFORMER_ROLE` (see §10 Security)
- [ ] Initialize dbt project: `dbt init toronto_mobility`
- [ ] Configure `profiles.yml` (local only, not committed)
- [ ] Create GitHub repository with `.gitignore`
- [ ] Add `packages.yml` with dbt-utils, dbt-expectations, elementary
- [ ] Run `dbt deps` and `dbt debug`

**Exit Criteria:** `dbt debug` returns all green checks

### 7.3 Phase 1: Data Ingestion

**Tasks:**

- [ ] Download source files for 2019-present:
  - TTC Subway delays (6 years × 12 months)
  - TTC Bus delays (6 years × 12 months)
  - TTC Streetcar delays (6 years × 12 months)
  - Bike Share ridership (6 years of quarterly files)
  - Weather daily (Toronto Pearson, 2019-present)
- [ ] Create Python ingestion scripts:
  ```
  scripts/
  ├── ingest.py          # Main orchestration (atomic transaction)
  ├── download.py        # Fetch from Open Data Portal
  ├── validate.py        # Schema validation (fail-fast)
  ├── transform.py       # XLSX → CSV conversion
  └── load.py            # Snowflake COPY INTO
  ```
- [ ] Implement schema validation in `validate.py`:
  - Compare actual columns against expected schema (§4.3)
  - On mismatch: log error, raise exception, abort entire run
  - No partial loads permitted
- [ ] Implement idempotent loading:
  - Use `MERGE` statement with natural keys
  - Delete + reinsert pattern within single transaction
- [ ] Create `ttc_station_mapping.csv` seed by analyzing distinct station names
- [ ] Execute initial load
- [ ] Validate: `SELECT COUNT(*) FROM raw.*` matches source file row counts (±1%)

**Exit Criteria:** All raw tables populated, row counts validated, station mapping seed complete

### 7.4 Phase 2: Staging Layer

**Tasks:**

- [ ] Define sources in `models/staging/*/_sources.yml`
- [ ] Create staging models:
  - `stg_ttc_subway_delays.sql`
  - `stg_ttc_bus_delays.sql`
  - `stg_ttc_streetcar_delays.sql`
  - `stg_bike_trips.sql` (with duration ≥ 60s filter)
  - `stg_weather_daily.sql`
- [ ] Add source freshness checks (warn_after: 45 days, error_after: 90 days)
- [ ] Add staging model tests:
  - `not_null` on surrogate keys
  - `unique` on surrogate keys
  - Row count comparison vs raw (dbt_utils.equal_rowcount, allowing for filtered trips)
- [ ] Document all staging models in `_models.yml`

**Staging Model Pattern:**

```sql
-- models/staging/ttc/stg_ttc_subway_delays.sql
{{
    config(
        materialized='view'
    )
}}

with source as (
    select * from {{ source('raw', 'ttc_subway_delays') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            'date', 'time', 'station', 'line', 'code', '"Min Delay"'
        ]) }} as delay_sk,
        date::date as delay_date,
        time::time as delay_time,
        timestamp_from_parts(date::date, time::time) as incident_timestamp,
        station as raw_station_name,
        code as delay_code,
        "Min Delay"::int as delay_minutes,
        "Min Gap"::int as gap_minutes,
        bound as direction,
        line as line_code,
        'subway' as transit_mode
    from source
    where "Min Delay" > 0
)

select * from renamed
```

**Exit Criteria:** `dbt build --select staging` passes, all tests green

### 7.5 Phase 3: Intermediate Layer

**Tasks:**

- [ ] Create seed files:
  - `seeds/ttc_delay_codes.csv` (code, description, category)
  - `seeds/ttc_station_mapping.csv` (raw_name → canonical_name, station_key)
  - `seeds/bike_station_ref.csv` (station_id, name, lat, lon, neighborhood)
- [ ] Create intermediate models (all ephemeral):
  - `int_ttc_delays_unioned.sql`
  - `int_ttc_delays_enriched.sql`
  - `int_bike_trips_enriched.sql`
  - `int_daily_transit_metrics.sql`
  - `int_daily_bike_metrics.sql`
- [ ] Add test for station mapping coverage:
  - Custom test: `assert_station_mapping_coverage` — flag if >1% of records map to UNKNOWN

**Exit Criteria:** `dbt build --select intermediate` passes, station mapping coverage ≥99%

### 7.6 Phase 4: Marts Layer

**Tasks:**

- [ ] Create dimension models:
  - `dim_date.sql` (generate date spine 2019-01-01 to 2026-12-31)
  - `dim_station.sql` (unified TTC + Bike Share)
  - `dim_weather.sql`
  - `dim_ttc_delay_codes.sql`
- [ ] Create fact models:
  - `fct_transit_delays.sql`
  - `fct_bike_trips.sql`
  - `fct_daily_mobility.sql`
- [ ] Add comprehensive tests:
  - `unique` and `not_null` on all primary keys
  - `relationships` on all foreign keys
  - `accepted_values` on categorical columns (transit_mode, user_type, etc.)

**Exit Criteria:** `dbt build --select marts` passes, all tests green

### 7.7 Phase 5: Testing & Documentation

**Tasks:**

- [ ] Add singular tests:
  - `tests/assert_no_negative_delays.sql`
  - `tests/assert_bike_trips_reasonable_duration.sql` (< 24 hours)
  - `tests/assert_no_future_dates.sql`
  - `tests/assert_daily_row_count_stability.sql` (no >50% drop day-over-day)
- [ ] Add data quality tests using `dbt_expectations`:
  - `expect_column_values_to_be_between` for delay_minutes (0, 1440)
  - `expect_table_row_count_to_be_between` for fact tables
- [ ] Write column descriptions for ALL columns in ALL models
- [ ] Generate dbt docs: `dbt docs generate`
- [ ] Review lineage graph for correctness
- [ ] Create `docs/TESTS.md` documenting test strategy

**Exit Criteria:** `dbt test` 100% pass, all models/columns documented, dbt docs site renders correctly

### 7.8 Phase 6: CI/CD & Polish

**Tasks:**

- [ ] Create GitHub Actions workflow (`.github/workflows/dbt-ci.yml`):

  ```yaml
  name: dbt CI

  on:
    pull_request:
      branches: [main]
    push:
      branches: [main]

  env:
    DBT_PROFILES_DIR: ${{ github.workspace }}

  jobs:
    dbt-build:
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v4

        - uses: actions/setup-python@v5
          with:
            python-version: "3.12"

        - name: Install dependencies
          run: |
            pip install "dbt-snowflake>=1.9.0" "sqlfluff>=3.3.0" sqlfmt
            dbt deps

        - name: Create profiles.yml
          run: |
            cat <<EOF > profiles.yml
            toronto_mobility:
              target: ci
              outputs:
                ci:
                  type: snowflake
                  account: ${{ secrets.SNOWFLAKE_ACCOUNT }}
                  user: ${{ secrets.SNOWFLAKE_USER }}
                  password: ${{ secrets.SNOWFLAKE_PASSWORD }}
                  role: TRANSFORMER_ROLE
                  database: TORONTO_MOBILITY
                  warehouse: TRANSFORM_WH
                  schema: MARTS
                  threads: 4
            EOF

        - name: sqlfmt format check
          run: sqlfmt --check models/

        - name: SQLFluff lint
          run: sqlfluff lint models/ --dialect snowflake

        - name: dbt build
          run: dbt build --full-refresh

        - name: dbt docs generate
          run: dbt docs generate

        - name: Elementary report
          run: |
            dbt run --select elementary
            edr report --env ci
  ```

- [ ] Create comprehensive `README.md`
- [ ] Move sample queries to `analyses/` folder (executable, linted)
- [ ] Run performance benchmarks (§15.4) and document results
- [ ] Final code review and cleanup
- [ ] Tag v1.0.0 release

**Exit Criteria:** CI pipeline green on main, README complete, performance targets met

---

## 8. Testing Strategy

### 8.1 Test Pyramid

```
                         ┌─────────────────┐
                         │   Performance   │  ← Benchmark queries (§15.4)
                         │   Benchmarks    │
                         └─────────────────┘
                    ┌─────────────────────────┐
                    │      Data Quality       │  ← dbt_expectations: distributions,
                    │        Tests            │    anomaly detection
                    └─────────────────────────┘
               ┌───────────────────────────────────┐
               │       Integration Tests           │  ← relationships, row counts,
               │                                   │    cross-model consistency
               └───────────────────────────────────┘
          ┌─────────────────────────────────────────────┐
          │            Unit Tests                        │  ← not_null, unique,
          │                                              │    accepted_values per model
          └─────────────────────────────────────────────┘
     ┌───────────────────────────────────────────────────────┐
     │              Schema Tests                              │  ← Source freshness,
     │                                                        │    column existence
     └───────────────────────────────────────────────────────┘
```

### 8.2 Test Categories

| Category               | Tool                   | Examples                                 | Coverage Target |
| ---------------------- | ---------------------- | ---------------------------------------- | --------------- |
| Schema validation      | dbt source tests       | Column types, freshness                  | All sources     |
| Primary key integrity  | dbt generic tests      | `unique`, `not_null`                     | All PKs (100%)  |
| Foreign key integrity  | dbt relationship tests | FK → PK validity                         | All FKs (100%)  |
| Categorical validation | dbt accepted_values    | transit_mode, user_type                  | All enums       |
| Business rules         | dbt singular tests     | No negative delays, reasonable durations | Critical rules  |
| Row count stability    | dbt_utils.recency      | No sudden drops                          | All fact tables |
| Distribution anomalies | dbt_expectations       | Value ranges, null rates                 | Mart columns    |
| Anomaly detection      | Elementary             | Dynamic thresholds, schema changes       | All mart models |

### 8.3 Critical Test Cases

| Test                   | Model              | Assertion                                                    | Severity |
| ---------------------- | ------------------ | ------------------------------------------------------------ | -------- |
| No orphan delays       | fct_transit_delays | All date_keys exist in dim_date                              | Blocker  |
| Valid delay codes      | fct_transit_delays | All delay_code_keys exist in dim_ttc_delay_codes OR are NULL | Blocker  |
| Valid stations         | fct_transit_delays | All station_keys exist in dim_station                        | Blocker  |
| Positive durations     | fct_bike_trips     | duration_seconds ≥ 60                                        | Blocker  |
| Reasonable trip length | fct_bike_trips     | duration_seconds < 86400 (24 hours)                          | Warning  |
| Station uniqueness     | dim_station        | station_key is unique                                        | Blocker  |
| Date spine complete    | dim_date           | No gaps in date sequence 2019-2026                           | Blocker  |
| No future dates        | fct\_\*            | All dates ≤ CURRENT_DATE                                     | Blocker  |
| Row count stability    | fct_daily_mobility | Count ≥ 0.5 × previous run count                             | Warning  |

### 8.4 Test Execution

| Stage             | Command                              | When                     |
| ----------------- | ------------------------------------ | ------------------------ |
| Local development | `dbt test --select <model>`          | After each model change  |
| Pre-commit        | `dbt build --select state:modified+` | Before commit            |
| CI/CD             | `dbt build` (full)                   | On PR and merge to main  |
| Scheduled         | `dbt source freshness && dbt test`   | Weekly (if orchestrated) |

---

## 9. Observability

### 9.1 Artifacts

| Artifact           | Location | Purpose                             | Retention              |
| ------------------ | -------- | ----------------------------------- | ---------------------- |
| `manifest.json`    | target/  | Model dependencies, compiled SQL    | Committed to repo      |
| `run_results.json` | target/  | Execution times, row counts, status | CI artifacts (90 days) |
| `sources.json`     | target/  | Source freshness results            | CI artifacts (90 days) |
| `catalog.json`     | target/  | Column-level metadata               | Committed to repo      |

### 9.2 Key Metrics

| Metric                 | Source                  | Warning Threshold | Error Threshold | Action                   |
| ---------------------- | ----------------------- | ----------------- | --------------- | ------------------------ |
| Model run time         | run_results.json        | > 60 seconds      | > 300 seconds   | Investigate query plan   |
| Test failures          | run_results.json        | Any warning       | Any error       | Block merge, investigate |
| Source freshness       | sources.json            | > 45 days         | > 90 days       | Trigger re-ingestion     |
| Warehouse credit usage | Snowflake ACCOUNT_USAGE | > $10/month       | > $20/month     | Review query efficiency  |

### 9.3 Alerting (Portfolio Project Scope)

| Event                  | Alert Channel                       | Recipient        |
| ---------------------- | ----------------------------------- | ---------------- |
| CI build failure       | GitHub email notification           | Repository owner |
| Source freshness error | dbt Cloud (if used) or manual check | Repository owner |
| Test failure on main   | GitHub Actions failure notification | Repository owner |

> **Note:** For production systems, integrate with PagerDuty/Slack/email. For portfolio scope, GitHub notifications are sufficient.

### 9.4 Logging

- dbt logs: `logs/dbt.log` (gitignored)
- Snowflake query history: `SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY` (retain 365 days by default)
- GitHub Actions logs: retained 90 days
- Ingestion script logs: stdout/stderr captured by CI

### 9.5 Elementary Observability

Elementary provides production-grade dbt observability beyond basic logging:

| Feature                    | Description                                                                                | Configuration                                                   |
| -------------------------- | ------------------------------------------------------------------------------------------ | --------------------------------------------------------------- |
| **Anomaly Detection**      | Compares new data against historical baselines to detect volume/freshness/schema anomalies | `elementary.volume_anomalies`, `elementary.freshness_anomalies` |
| **Schema Monitoring**      | Alerts on column additions, removals, or type changes                                      | `elementary.schema_changes`                                     |
| **Test Results Dashboard** | HTML report of all dbt test results with trends                                            | `edr report` CLI command                                        |
| **dbt Artifacts Analysis** | Tracks model run times, test coverage, lineage changes                                     | Automatic via Elementary models                                 |

**Setup:**

```bash
# After dbt deps
dbt run --select elementary       # Create Elementary tables
pip install elementary-data       # Install CLI
edr report                        # Generate HTML report
```

**Integration with CI:**

```yaml
# In GitHub Actions workflow
- name: Elementary report
  run: |
    dbt run --select elementary
    edr report --env ci
```

---

## 10. Security

### 10.1 Role Hierarchy

```
ACCOUNTADMIN (system)
      │
      ├── SYSADMIN (system)
      │       │
      │       ├── LOADER_ROLE (custom)
      │       │   └── Owns: RAW schema objects
      │       │   └── Can: COPY INTO raw tables
      │       │
      │       └── TRANSFORMER_ROLE (custom)
      │           └── Owns: STAGING, INTERMEDIATE, MARTS, SEEDS schema objects
      │           └── Can: SELECT from RAW, CREATE in owned schemas
      │
      └── SECURITYADMIN (system)
              └── Manages role grants
```

### 10.2 Grant Statements

```sql
-- setup/grants.sql

-- Create custom roles
USE ROLE SECURITYADMIN;
CREATE ROLE IF NOT EXISTS LOADER_ROLE;
CREATE ROLE IF NOT EXISTS TRANSFORMER_ROLE;

-- Grant roles to SYSADMIN for management
GRANT ROLE LOADER_ROLE TO ROLE SYSADMIN;
GRANT ROLE TRANSFORMER_ROLE TO ROLE SYSADMIN;

-- Warehouse access
USE ROLE SYSADMIN;
GRANT USAGE ON WAREHOUSE TRANSFORM_WH TO ROLE LOADER_ROLE;
GRANT USAGE ON WAREHOUSE TRANSFORM_WH TO ROLE TRANSFORMER_ROLE;

-- Database access
GRANT USAGE ON DATABASE TORONTO_MOBILITY TO ROLE LOADER_ROLE;
GRANT USAGE ON DATABASE TORONTO_MOBILITY TO ROLE TRANSFORMER_ROLE;

-- LOADER_ROLE: RAW schema (full control)
GRANT ALL PRIVILEGES ON SCHEMA TORONTO_MOBILITY.RAW TO ROLE LOADER_ROLE;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA TORONTO_MOBILITY.RAW TO ROLE LOADER_ROLE;
GRANT ALL PRIVILEGES ON FUTURE TABLES IN SCHEMA TORONTO_MOBILITY.RAW TO ROLE LOADER_ROLE;

-- TRANSFORMER_ROLE: Read RAW, manage transform schemas
GRANT USAGE ON SCHEMA TORONTO_MOBILITY.RAW TO ROLE TRANSFORMER_ROLE;
GRANT SELECT ON ALL TABLES IN SCHEMA TORONTO_MOBILITY.RAW TO ROLE TRANSFORMER_ROLE;
GRANT SELECT ON FUTURE TABLES IN SCHEMA TORONTO_MOBILITY.RAW TO ROLE TRANSFORMER_ROLE;

GRANT ALL PRIVILEGES ON SCHEMA TORONTO_MOBILITY.STAGING TO ROLE TRANSFORMER_ROLE;
GRANT ALL PRIVILEGES ON SCHEMA TORONTO_MOBILITY.INTERMEDIATE TO ROLE TRANSFORMER_ROLE;
GRANT ALL PRIVILEGES ON SCHEMA TORONTO_MOBILITY.MARTS TO ROLE TRANSFORMER_ROLE;
GRANT ALL PRIVILEGES ON SCHEMA TORONTO_MOBILITY.SEEDS TO ROLE TRANSFORMER_ROLE;

-- Future object privileges in transform schemas
GRANT ALL PRIVILEGES ON FUTURE TABLES IN SCHEMA TORONTO_MOBILITY.STAGING TO ROLE TRANSFORMER_ROLE;
GRANT ALL PRIVILEGES ON FUTURE VIEWS IN SCHEMA TORONTO_MOBILITY.STAGING TO ROLE TRANSFORMER_ROLE;
GRANT ALL PRIVILEGES ON FUTURE TABLES IN SCHEMA TORONTO_MOBILITY.MARTS TO ROLE TRANSFORMER_ROLE;
GRANT ALL PRIVILEGES ON FUTURE TABLES IN SCHEMA TORONTO_MOBILITY.SEEDS TO ROLE TRANSFORMER_ROLE;

-- Create service users
USE ROLE SECURITYADMIN;
CREATE USER IF NOT EXISTS LOADER_SVC
    PASSWORD = '<GENERATED_PASSWORD>'
    DEFAULT_ROLE = LOADER_ROLE
    DEFAULT_WAREHOUSE = TRANSFORM_WH
    MUST_CHANGE_PASSWORD = FALSE;

CREATE USER IF NOT EXISTS TRANSFORMER_SVC
    PASSWORD = '<GENERATED_PASSWORD>'
    DEFAULT_ROLE = TRANSFORMER_ROLE
    DEFAULT_WAREHOUSE = TRANSFORM_WH
    MUST_CHANGE_PASSWORD = FALSE;

GRANT ROLE LOADER_ROLE TO USER LOADER_SVC;
GRANT ROLE TRANSFORMER_ROLE TO USER TRANSFORMER_SVC;
```

### 10.3 Credential Management

| Credential               | Storage                                      | Access                  |
| ------------------------ | -------------------------------------------- | ----------------------- |
| LOADER_SVC password      | GitHub Secrets (`SNOWFLAKE_LOADER_PASSWORD`) | Ingestion workflow only |
| TRANSFORMER_SVC password | GitHub Secrets (`SNOWFLAKE_PASSWORD`)        | dbt CI workflow         |
| Snowflake account ID     | GitHub Secrets (`SNOWFLAKE_ACCOUNT`)         | All workflows           |

**Security Rules:**

- NEVER commit `profiles.yml` with credentials
- NEVER use ACCOUNTADMIN for automated scripts
- NEVER share credentials between humans and service accounts
- USE environment variables in CI
- ROTATE service account passwords quarterly
- AUDIT `QUERY_HISTORY` for anomalous access patterns

---

## 11. Cost Analysis

### 11.1 Snowflake Costs (Estimated)

| Activity                  | Warehouse Size | Est. Runtime/Month | Credits/Hour | Monthly Credits | Monthly Cost |
| ------------------------- | -------------- | ------------------ | ------------ | --------------- | ------------ |
| Initial ingestion         | X-Small        | 2 hours (one-time) | 1            | 2               | $4           |
| Monthly ingestion         | X-Small        | 0.5 hours          | 1            | 0.5             | $1           |
| dbt build (full)          | X-Small        | 0.25 hours         | 1            | 0.25            | $0.50        |
| dbt build (CI, ~10/month) | X-Small        | 0.1 hours × 10     | 1            | 1               | $2           |
| Ad-hoc queries            | X-Small        | 1 hour             | 1            | 1               | $2           |
| **Monthly Total**         |                |                    |              | ~3-4            | **~$6-8**    |

**Storage:**

- Estimated total data: ~10 GB
- Storage cost: ~$0.023/GB/month = ~$0.25/month

**Trial Budget:**

- Snowflake trial: $400 credits
- Estimated monthly burn: ~$8
- Runway: ~50 months (well beyond project scope)

### 11.2 Other Costs

| Service                                | Cost    |
| -------------------------------------- | ------- |
| GitHub (public repo)                   | $0      |
| GitHub Actions (2,000 mins/month free) | $0      |
| dbt Core (open source)                 | $0      |
| **Total Monthly**                      | **~$8** |

---

## 12. Risks and Mitigations

| ID  | Risk                                    | Likelihood | Impact | Mitigation                                                                                                       | Owner  |
| --- | --------------------------------------- | ---------- | ------ | ---------------------------------------------------------------------------------------------------------------- | ------ |
| R1  | **Source schema change**                | Medium     | High   | Schema validation at ingestion with fail-fast; pin expected schemas in code; monitor Toronto Open Data changelog | Dinesh |
| R2  | **Snowflake trial expiration**          | Low        | High   | Complete core functionality within 30 days; document migration path to free tier or alternative                  | Dinesh |
| R3  | **Large data volumes exceed warehouse** | Low        | Medium | X-Small warehouse sufficient for 30M rows; partition by year if needed; use incremental models in v2             | Dinesh |
| R4  | **Station name mapping incomplete**     | High       | Medium | Manual seed file; iterate on mapping during Phase 1; accept ≤1% UNKNOWN rate                                     | Dinesh |
| R5  | **API rate limits on data download**    | Low        | Low    | Download files once, cache locally; batch requests with delays                                                   | Dinesh |
| R6  | **Scope creep**                         | Medium     | Medium | Strict adherence to non-goals; time-box research; prioritize quality over features                               | Dinesh |
| R7  | **CI/CD secrets exposure**              | Low        | High   | Use GitHub encrypted secrets; never log credentials; restrict secret access to required workflows                | Dinesh |

---

## 13. Future Enhancements

### 13.1 Version 2.0 Candidates

| Enhancement                               | Complexity | Value  | Prerequisite                    |
| ----------------------------------------- | ---------- | ------ | ------------------------------- |
| Incremental loading for fct_bike_trips    | Medium     | High   | Baseline performance benchmarks |
| Airflow/Dagster orchestration             | Medium     | Medium | v1 stable                       |
| dbt metrics layer                         | Low        | Medium | dbt 1.6+ semantic layer         |
| Streamlit dashboard                       | Medium     | High   | Mart models stable              |
| Real-time Bike Share station availability | High       | Medium | Streaming infrastructure        |
| 311 Service Request integration           | Low        | Medium | Additional seed mappings        |

### 13.2 Explicitly Not Planned

| Item                      | Reason                                                  |
| ------------------------- | ------------------------------------------------------- |
| ML-based delay prediction | Out of scope (NG2); different skill demonstration       |
| Multi-city expansion      | Out of scope (NG5); Toronto-specific seeds and mappings |
| Real-time streaming       | Out of scope (NG1); batch is sufficient for portfolio   |
| Mobile application        | Out of scope (NG3); no frontend deliverable             |
| TTC ridership aggregates  | Decided out of scope (D1); limited join potential       |

---

## 14. Decisions Log

| ID  | Decision                                                         | Rationale                                                                                                                                                                        | Date       | Status   |
| --- | ---------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | -------- |
| D1  | Exclude TTC ridership data                                       | Ridership is aggregate-only (daily/monthly totals); cannot join to individual delays; keeps scope tight                                                                          | 2026-02-02 | Approved |
| D2  | Date range: 2019-present                                         | 6 years provides sufficient history; aligns with Bike Share growth period; manageable data volume                                                                                | 2026-02-02 | Approved |
| D3  | Station matching via manual seed                                 | Higher accuracy than fuzzy matching; acceptable upfront effort for portfolio project                                                                                             | 2026-02-02 | Approved |
| D4  | Daily weather grain                                              | Simpler implementation; sufficient for correlation analysis; matches fact table grain                                                                                            | 2026-02-02 | Approved |
| D5  | SCD Type 1 for dim_station                                       | Station metadata changes rarely; historical state is low-value; simplifies implementation                                                                                        | 2026-02-02 | Approved |
| D6  | Fail-fast on schema changes                                      | Prevents silent data corruption; acceptable for batch system; manual intervention preferred                                                                                      | 2026-02-02 | Approved |
| D7  | Flexible timeline                                                | Quality over speed; prevents technical debt accumulation; appropriate for portfolio project                                                                                      | 2026-02-02 | Approved |
| D8  | Atomic ingestion transactions                                    | All-or-nothing ensures consistency; simpler error handling; re-run from clean state                                                                                              | 2026-02-02 | Approved |
| D9  | Trip duration filter ≥ 60 seconds                                | Industry standard for dock-based systems; excludes accidental undocks; aligns with Bike Share Toronto guidance                                                                   | 2026-02-02 | Approved |
| D10 | Ephemeral materialization for intermediate                       | No direct querying of intermediate models; reduces Snowflake object count; sufficient for data volume                                                                            | 2026-02-02 | Approved |
| D11 | Technology stack versions (Python 3.12, dbt 1.8+, SQLFluff 3.3+) | Python 3.12 offers 10-60% performance gain over 3.11 with solid library support; dbt 1.8+ required for latest adapter compatibility; SQLFluff 3.x has improved Snowflake dialect | 2026-02-02 | Approved |
| D12 | Add Elementary for observability                                 | Elementary provides dynamic anomaly detection vs. dbt_expectations' static thresholds; schema change monitoring; superior for production monitoring                              | 2026-02-02 | Approved |
| D13 | Pin dbt package versions                                         | Broad version ranges create reproducibility risk; pinned versions ensure consistent CI builds and test behavior                                                                  | 2026-02-02 | Approved |
| D14 | Add sqlfmt for SQL formatting                                    | Separates formatting (sqlfmt) from linting (SQLFluff); opinionated formatter eliminates style debates; aligns with dbt Cloud IDE default                                         | 2026-02-02 | Approved |

---

## 15. Appendix

### 15.1 Project Structure

```
toronto-mobility-analytics/
├── .github/
│   └── workflows/
│       └── dbt-ci.yml
├── analyses/
│   ├── top_delay_stations.sql
│   ├── bike_weather_correlation.sql
│   ├── cross_modal_analysis.sql
│   ├── monthly_trends.sql
│   └── daily_mobility_summary.sql
├── data/
│   └── raw/                         # Downloaded source files (gitignored)
├── docs/
│   └── TESTS.md
├── macros/
│   ├── generate_schema_name.sql
│   └── get_date_spine.sql
├── models/
│   ├── staging/
│   │   ├── ttc/
│   │   │   ├── _ttc__sources.yml
│   │   │   ├── _ttc__models.yml
│   │   │   ├── stg_ttc_subway_delays.sql
│   │   │   ├── stg_ttc_bus_delays.sql
│   │   │   └── stg_ttc_streetcar_delays.sql
│   │   ├── bike_share/
│   │   │   ├── _bike_share__sources.yml
│   │   │   ├── _bike_share__models.yml
│   │   │   └── stg_bike_trips.sql
│   │   └── weather/
│   │       ├── _weather__sources.yml
│   │       ├── _weather__models.yml
│   │       └── stg_weather_daily.sql
├── intermediate/
│   │   ├── _int__models.yml
│   │   ├── int_ttc_delays_unioned.sql
│   │   ├── int_ttc_delays_enriched.sql
│   │   ├── int_bike_trips_enriched.sql
│   │   ├── int_daily_transit_metrics.sql
│   │   └── int_daily_bike_metrics.sql
│   └── marts/
│       ├── core/
│       │   ├── _core__models.yml
│       │   ├── dim_date.sql
│       │   ├── dim_station.sql
│       │   ├── dim_weather.sql
│       │   └── dim_ttc_delay_codes.sql
│       └── mobility/
│           ├── _mobility__models.yml
│           ├── fct_transit_delays.sql
│           ├── fct_bike_trips.sql
│           └── fct_daily_mobility.sql
├── scripts/
│   ├── ingest.py
│   ├── download.py
│   ├── validate.py
│   ├── transform.py
│   └── load.py
├── seeds/
│   ├── _seeds.yml
│   ├── ttc_delay_codes.csv
│   ├── ttc_station_mapping.csv
│   └── bike_station_ref.csv
├── setup/
│   ├── snowflake_init.sql
│   └── grants.sql
├── tests/
│   ├── assert_no_negative_delays.sql
│   ├── assert_bike_trips_reasonable_duration.sql
│   ├── assert_no_future_dates.sql
│   └── assert_station_mapping_coverage.sql
├── .gitignore
├── .sqlfluff
├── dbt_project.yml
├── packages.yml
├── profiles.yml.example
├── README.md
├── DESIGN-DOC.md
└── CHANGELOG.md
```

### 15.2 dbt Packages

```yaml
# packages.yml
# Pin versions for reproducible builds (evaluated 2026-02-02)
packages:
  - package: dbt-labs/dbt_utils
    version: "1.3.0"
  - package: dbt-labs/codegen
    version: "0.12.1"
  - package: calogica/dbt_expectations
    version: "0.10.4"
  - package: elementary-data/elementary
    version: "0.16.1"
```

**Package Rationale:**

| Package          | Purpose                                                     | Why Pinned                                             |
| ---------------- | ----------------------------------------------------------- | ------------------------------------------------------ |
| dbt_utils        | Core utility macros (surrogate keys, date spine, etc.)      | Foundation package; broad ranges risk breaking changes |
| codegen          | Model/YAML scaffolding during development                   | Dev-time only; pin for consistency                     |
| dbt_expectations | Static data quality tests (value ranges, distributions)     | Hundreds of test types; pin for test stability         |
| elementary       | Dynamic anomaly detection, schema monitoring, dbt artifacts | Production observability; pin for alert consistency    |

### 15.3 Sample Queries

All queries are in `analyses/` folder and executable via `dbt run-operation run_query --args '{sql: "..."}'` or directly in Snowflake.

**analyses/top_delay_stations.sql:**

```sql
-- Top 10 subway stations by total delay minutes (2019-present)
select
    s.station_name,
    s.station_type,
    count(*) as delay_count,
    sum(f.delay_minutes) as total_delay_minutes,
    round(avg(f.delay_minutes), 2) as avg_delay_minutes,
    round(sum(f.delay_minutes) * 1.0 / count(distinct f.date_key), 2) as delay_minutes_per_day
from {{ ref('fct_transit_delays') }} f
inner join {{ ref('dim_station') }} s
    on f.station_key = s.station_key
where f.transit_mode = 'subway'
group by s.station_name, s.station_type
order by total_delay_minutes desc
limit 10
```

**analyses/bike_weather_correlation.sql:**

```sql
-- Bike share ridership by temperature bucket
select
    case
        when w.mean_temp_c < 0 then '1. Below Freezing (<0°C)'
        when w.mean_temp_c < 10 then '2. Cold (0-10°C)'
        when w.mean_temp_c < 20 then '3. Mild (10-20°C)'
        else '4. Warm (20°C+)'
    end as temp_bucket,
    count(*) as days_in_bucket,
    round(avg(m.total_bike_trips), 0) as avg_daily_trips,
    round(sum(m.total_bike_trips), 0) as total_trips
from {{ ref('fct_daily_mobility') }} m
inner join {{ ref('dim_weather') }} w
    on m.date_key = w.date_key
where m.total_bike_trips is not null
group by 1
order by 1
```

**analyses/cross_modal_analysis.sql:**

```sql
-- Do bike trips increase on high TTC delay days?
select
    case
        when m.total_delay_minutes > 500 then '3. High Delay (>500 min)'
        when m.total_delay_minutes > 100 then '2. Medium Delay (100-500 min)'
        else '1. Low Delay (<100 min)'
    end as ttc_delay_category,
    count(*) as days,
    round(avg(m.total_bike_trips), 0) as avg_bike_trips,
    round(avg(m.total_delay_incidents), 1) as avg_delay_incidents
from {{ ref('fct_daily_mobility') }} m
where m.total_bike_trips is not null
  and m.total_delay_incidents is not null
group by 1
order by 1
```

### 15.4 Performance Benchmark Queries

These 5 queries define the "<5 second" performance target. All must execute in under 5 seconds on X-Small warehouse with production data volume.

| #   | Query                                   | Description                                          | Expected Rows |
| --- | --------------------------------------- | ---------------------------------------------------- | ------------- |
| 1   | `analyses/daily_mobility_summary.sql`   | Full scan of fct_daily_mobility                      | ~2,200        |
| 2   | `analyses/top_delay_stations.sql`       | Aggregation on fct_transit_delays + dim_station join | 10            |
| 3   | `analyses/bike_weather_correlation.sql` | Join fct_daily_mobility + dim_weather with grouping  | 4             |
| 4   | `analyses/cross_modal_analysis.sql`     | Conditional aggregation on fct_daily_mobility        | 3             |
| 5   | `analyses/monthly_trends.sql`           | Time-series aggregation by month                     | ~72           |

**Benchmark execution:**

```bash
# Run benchmarks and capture timing
snowsql -q "ALTER SESSION SET QUERY_TAG = 'benchmark';"
for f in analyses/*.sql; do
    snowsql -f "$f" --timing
done
```

### 15.5 Glossary

| Term              | Definition                                                                                                                  |
| ----------------- | --------------------------------------------------------------------------------------------------------------------------- |
| **Delay**         | Time difference between scheduled and actual arrival/departure                                                              |
| **Gap**           | Time between consecutive vehicles at a station                                                                              |
| **Line Code**     | TTC subway route identifier: YU (Yonge-University), BD (Bloor-Danforth), SHP (Sheppard), SRT (Scarborough RT - closed 2023) |
| **Bound**         | Direction of travel (N/S/E/W)                                                                                               |
| **Casual User**   | Bike Share user paying per-trip without annual membership                                                                   |
| **Annual Member** | Bike Share user with annual subscription                                                                                    |
| **GBFS**          | General Bikeshare Feed Specification (industry standard for bike share data)                                                |
| **Surrogate Key** | System-generated unique identifier (vs. natural key from source)                                                            |
| **SCD**           | Slowly Changing Dimension - strategy for handling dimension changes over time                                               |
| **Ephemeral**     | dbt materialization that compiles model as CTE into downstream models                                                       |

### 15.6 References

- [Toronto Open Data Portal](https://open.toronto.ca/)
- [dbt Best Practices - How We Structure Our dbt Projects](https://docs.getdbt.com/best-practices/how-we-structure/1-guide-overview)
- [Snowflake Access Control Best Practices](https://docs.snowflake.com/en/user-guide/security-access-control-considerations)
- [Environment Canada Historical Climate Data](https://climate.weather.gc.ca/)
- [TTC Open Data Datasets](https://open.toronto.ca/dataset/?search=ttc)
- [Bike Share Toronto](https://bikesharetoronto.com/)
- [dbt_expectations Package](https://github.com/calogica/dbt-expectations)

---

## Document History

| Version | Date       | Author | Changes                                                                                                                                                                                                                                                                                 |
| ------- | ---------- | ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 0.1     | 2026-01-30 | Dinesh | Initial draft                                                                                                                                                                                                                                                                           |
| 1.0     | 2026-02-02 | Dinesh | Architectural review and gap closure: resolved all open questions, added security section, defined data contracts with validation rules, specified SCD strategy, added performance benchmarks, documented all decisions, added schema change policy, clarified materialization strategy |
| 1.1     | 2026-02-02 | Dinesh | Technology evaluation: updated Python to 3.12, dbt Core to 1.8+, SQLFluff to 3.3+; added sqlfmt for formatting and Elementary for observability; pinned all dbt package versions for reproducibility                                                                                    |
