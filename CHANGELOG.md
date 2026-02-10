# Changelog

All notable changes to the Toronto Urban Mobility Analytics project are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- markdownlint-disable MD036 -->

---

## [1.0.0] - 2026-02-10

Production-ready release of the Toronto Urban Mobility Analytics data platform. Integrates six years of transit delay records, bike share ridership, and weather observations into a star-schema warehouse on Snowflake, built with dbt following medallion architecture.

### PH-01: Repository Governance Foundation

**Added**

- `CLAUDE.md` engineering governance with 17-item Definition of Done checklist
- Claude skills framework: `python-writing`, `dbt-model`, `skill-creator`, `epic-writer`
- Protocol Zero automation script (`tools/protocol-zero.sh`) for forbidden-phrase scanning
- Pre-commit hook infrastructure (`tools/install-hooks.sh`, `.pre-commit-config.yaml`)
- GitHub branch protection on `main`: squash-merge only, linear history, CODEOWNER approval
- 5 required CI status checks: `detect-changes`, `detect-python`, `detect-dbt`, `protocol-zero`, `dependency-audit`
- `CODEOWNERS` file with `@dinesh-git17` as default owner
- Issue templates (bug report, feature request) and PR template with governance checklist

### PH-02: Snowflake & dbt Environment Setup

**Added**

- Snowflake database `TORONTO_MOBILITY` with 5 schemas: RAW, STAGING, INTERMEDIATE, MARTS, SEEDS
- Role-based access control: `LOADER_ROLE` (ingestion), `TRANSFORMER_ROLE` (dbt)
- Warehouse `TRANSFORM_WH` (X-Small, auto-suspend 60s)
- `setup/snowflake_init.sql`, `setup/grants.sql`, `setup/validate_infrastructure.sql`
- dbt project scaffold (`dbt_project.yml`, `packages.yml`, `profiles.yml.example`)
- Pinned dbt packages: dbt_utils 1.3.0, codegen 0.12.1, dbt_expectations 0.10.4, elementary 0.16.1
- Custom macros: `generate_schema_name.sql` (schema routing), `get_date_spine.sql` (date generation)

### PH-03: Data Ingestion Pipeline

**Added**

- Python 3.12 ingestion pipeline: `download.py`, `transform.py`, `validate.py`, `load.py`, `ingest.py`
- Schema contract definitions in `contracts.py` with frozen dataclasses
- Fail-fast validation engine: schema mismatch aborts entire run with non-zero exit code
- XLSX-to-CSV conversion with encoding normalization (UTF-8-BOM, cp1250 handling)
- Snowflake COPY INTO with MERGE idempotency using natural keys
- Atomic transaction semantics: all-or-nothing loading per source
- Row count validation (`validate_load.py`) with 1% tolerance threshold
- 5 RAW tables populated: TTC subway/bus/streetcar delays, bike share trips, weather daily
- 22.25M+ validated rows across 83 source files
- `setup/create_ingestion_stage.sql` for stage and RAW table DDL

### PH-04: Seed Data Layer

**Added**

- `seeds/ttc_station_mapping.csv`: 1,101 raw station name variants mapped to 75 canonical TTC stations
- `seeds/ttc_delay_codes.csv`: 334 delay codes with descriptions and categories
- `seeds/bike_station_ref.csv`: 1,009 Bike Share Toronto stations with coordinates and neighborhoods (GBFS snapshot)
- `seeds/date_spine.csv`: 2,922 calendar rows (2019-01-01 through 2026-12-31) with Ontario statutory holidays
- `seeds/_seeds.yml`: column documentation and schema tests for all 4 seeds
- Generator scripts: `extract_station_names.py`, `generate_station_mapping.py`, `generate_delay_codes.py`, `generate_date_spine.py`, `generate_bike_station_ref.py`

### PH-05: Staging Layer

**Added**

- 5 staging views: `stg_ttc_subway_delays`, `stg_ttc_bus_delays`, `stg_ttc_streetcar_delays`, `stg_bike_trips`, `stg_weather_daily`
- 5 source definitions with freshness checks (warn_after: 45 days, error_after: 90 days)
- Type casting from VARCHAR to native types using `TRY_CAST` / `TRY_TO_TIMESTAMP_NTZ`
- Surrogate key generation via `dbt_utils.generate_surrogate_key()`
- Deduplication via `ROW_NUMBER()` for TTC sources (14 subway, 1,228 bus, 1,014 streetcar duplicates)
- Bike share trip filter: duration >= 60 seconds per industry standard (Decision D9)
- 33 schema tests (PASS=33, WARN=2, ERROR=0)

### PH-06: Intermediate Layer

**Added**

- 5 ephemeral intermediate models compiled as CTEs:
  - `int_ttc_delays_unioned`: UNION ALL of 3 transit modes with mode identifier
  - `int_ttc_delays_enriched`: station name mapping, delay code descriptions, date key generation
  - `int_bike_trips_enriched`: station geography, neighborhood, duration bucket classification
  - `int_daily_transit_metrics`: daily aggregate delay counts and minutes by mode
  - `int_daily_bike_metrics`: daily aggregate trip counts by user type
- `tests/assert_station_mapping_coverage.sql`: 99% subway station mapping threshold
- 19 tests passing (PASS=19, WARN=0, ERROR=0)

### PH-07: Marts Layer

**Added**

- 4 dimension tables:
  - `dim_date`: 2,922 rows — calendar with time intelligence and Ontario holidays
  - `dim_station`: 1,085 rows — unified TTC subway (76) + Bike Share (1,009) stations
  - `dim_weather`: 2,922 rows — daily weather with derived condition classification (Snow/Rain/Clear)
  - `dim_ttc_delay_codes`: 334 rows — code-to-description-to-category lookup
- 3 fact tables:
  - `fct_transit_delays`: 237,446 rows — one per delay incident with FK to dim_date, dim_station, dim_ttc_delay_codes
  - `fct_bike_trips`: 21,795,223 rows — one per trip with FK to dim_date, dim_station (start + end)
  - `fct_daily_mobility`: 1,827 rows — cross-modal daily aggregates via FULL OUTER JOIN
- 41 tests passing (PASS=41, WARN=0, ERROR=0)

### PH-08: Testing & Quality Assurance

**Added**

- 5 singular business rule tests:
  - `assert_no_negative_delays`: zero negative delay_minutes in fct_transit_delays
  - `assert_bike_trips_reasonable_duration`: flag trips >= 24 hours
  - `assert_no_future_dates`: no future date_keys across all 3 fact tables
  - `assert_daily_row_count_stability`: no > 50% day-over-day drop in fct_daily_mobility
  - `assert_station_mapping_coverage`: >= 99% subway station mapping rate
- 5 dbt_expectations tests: value ranges (delay_minutes 0-1440, duration_seconds 60-86400), row count bounds for all 3 fact tables
- 17 Elementary anomaly detection tests across all 7 mart models: volume_anomalies, freshness_anomalies, schema_changes
- Regression baseline: 135 dbt tests | PASS=130 WARN=5 ERROR=0 | 66s on X-Small

### PH-09: Documentation & Observability

**Added**

- Column-level descriptions for all 17 models (staging, intermediate, marts) with `persist_docs` enabled
- `dbt docs generate` producing complete lineage graph with zero missing descriptions
- Performance benchmarks: 5 analytical queries, all < 1s on X-Small warehouse (max 0.954s)
- `analyses/` directory with 5 benchmark queries: daily_mobility_summary, top_delay_stations, bike_weather_correlation, cross_modal_analysis, monthly_trends
- Elementary CI integration via `ci-dbt.yml` workflow
- `docs/TESTS.md`: full test strategy with pyramid, inventory, and regression baseline
- `docs/RUNBOOK.md`: operational procedures for pipeline execution and incident response
- `docs/OBSERVABILITY.md`: Elementary report interpretation, alert thresholds, monitoring procedures

### PH-10: Portfolio Delivery

**Added**

- `README.md`: 647-line portfolio README with executive summary, technology stack, data source inventory
- 3 Mermaid architecture diagrams: system overview (flowchart TD), medallion data flow (flowchart LR), entity-relationship (erDiagram)
- Setup and reproduction instructions: Snowflake provisioning, dbt profile configuration, ingestion pipeline, dbt build
- Sample query documentation with expected output shapes and benchmark results
- Testing pyramid summary, CI/CD workflow table, observability section
- Repository tree, mart model summary, reference data inventory, design decisions table
- `CHANGELOG.md`: complete phase history with quantified deliverables
- `LICENSE`: MIT license
- Governance audit: CLAUDE.md Definition of Done verified across all layers
- v1.0.0 release tag

---

## Summary

| Metric                | Value   |
| --------------------- | ------- |
| Data sources          | 5       |
| RAW tables            | 5       |
| Staging views         | 5       |
| Intermediate models   | 5       |
| Mart tables           | 7       |
| Seed files            | 4       |
| dbt tests             | 135     |
| Singular SQL tests    | 5       |
| Python unit tests     | 202     |
| Validated rows        | 22.25M+ |
| Fact rows (total)     | 22.03M+ |
| CI workflows          | 5       |
| Query benchmark (max) | 0.954s  |
| Snowflake warehouse   | X-Small |
