# Observability and Monitoring Procedures

**Last Updated:** 2026-02-10
**Scope:** Monitoring, anomaly detection, and incident response for the Toronto Urban Mobility Analytics data platform
**Reference:** DESIGN-DOC Section 9

Maintenance Note: Any epic that adds, removes, or modifies Elementary tests, source freshness thresholds, or monitoring configuration must update this document as part of its Definition of Done.

---

## 1. Elementary Report Interpretation

### Generating the Report

```bash
# Materialize Elementary artifact tables (required before first report)
dbt run --select elementary

# Generate HTML observability report
edr report
```

Output: `edr_target/elementary_report.html`

In CI, the report is uploaded as the `elementary-report` artifact and downloadable from the GitHub Actions run summary.

### Reading the Report

The Elementary HTML report contains four primary sections:

| Section           | Content                                                                                     |
| ----------------- | ------------------------------------------------------------------------------------------- |
| **Test Results**  | Pass/fail status for all 135 dbt tests with trend lines across runs                        |
| **Model Overview** | Row counts, execution times, and materialization status for all 46 models                  |
| **Lineage**       | Interactive DAG visualization of model dependencies (staging → intermediate → marts)        |
| **Anomalies**     | Flagged deviations from historical baselines for volume, freshness, and schema              |

### What Each Test Type Indicates

| Test Type              | Monitors                                           | Failure Signal                                                        |
| ---------------------- | -------------------------------------------------- | --------------------------------------------------------------------- |
| `volume_anomalies`     | Row count consistency across runs                  | Unexpected row count change — potential data loss, duplicate load, or upstream schema change |
| `freshness_anomalies`  | Timestamp recency of most recent loaded data       | Data staleness — source ingestion may have failed or been delayed     |
| `schema_changes`       | Column names, types, and count in materialized tables | Column added, removed, or type-changed — upstream model modification or source schema drift |

Elementary requires a minimum of 14 days of historical data (default training period) before anomaly detection activates. During the baseline establishment period, all anomaly tests pass by default.

---

## 2. Anomaly Response Matrix

Deterministic action mapping for each Elementary test type and affected model.

### Core Dimensions (9 tests)

| Model                 | Test Type             | Trigger Condition                         | Severity | Corrective Action                                                                                                    |
| --------------------- | --------------------- | ----------------------------------------- | -------- | -------------------------------------------------------------------------------------------------------------------- |
| `dim_date`            | `volume_anomalies`    | Row count deviates from 2,922             | error    | Re-seed: `dbt seed --select date_spine --full-refresh && dbt run --select dim_date --full-refresh`                  |
| `dim_date`            | `schema_changes`      | Column added/removed/type-changed         | error    | Inspect `seeds/_seeds.yml` and `dim_date.sql` for unintended modifications; revert if unauthorized                  |
| `dim_station`         | `volume_anomalies`    | Row count deviates from 1,085             | error    | Check seed files (`ttc_station_mapping.csv`, `bike_station_ref.csv`); re-seed and rebuild if corrupted              |
| `dim_station`         | `schema_changes`      | Column added/removed/type-changed         | error    | Inspect `dim_station.sql` and YAML for unintended modifications                                                     |
| `dim_weather`         | `volume_anomalies`    | Row count deviates from 2,922             | error    | Verify RAW weather table row count; re-run staging and marts build if data loss detected                            |
| `dim_weather`         | `freshness_anomalies` | `weather_date` max value older than expected | error | Trigger data refresh: `python scripts/ingest.py && dbt build --select stg_weather_daily+`                          |
| `dim_weather`         | `schema_changes`      | Column added/removed/type-changed         | error    | Inspect `stg_weather_daily.sql` and `dim_weather.sql` for unintended modifications                                  |
| `dim_ttc_delay_codes` | `volume_anomalies`    | Row count deviates from 334               | error    | Re-seed: `dbt seed --select ttc_delay_codes --full-refresh && dbt run --select dim_ttc_delay_codes --full-refresh`  |
| `dim_ttc_delay_codes` | `schema_changes`      | Column added/removed/type-changed         | error    | Inspect `dim_ttc_delay_codes.sql` and YAML for unintended modifications                                             |

### Mobility Facts (8 tests)

| Model                | Test Type             | Trigger Condition                                  | Severity | Corrective Action                                                                                                  |
| -------------------- | --------------------- | -------------------------------------------------- | -------- | ------------------------------------------------------------------------------------------------------------------ |
| `fct_transit_delays` | `volume_anomalies`    | Row count outside 100,000–500,000 range            | error    | Check RAW TTC tables for data loss or duplicate load; rebuild: `dbt build --select fct_transit_delays --full-refresh` |
| `fct_transit_delays` | `freshness_anomalies` | `incident_timestamp` max value older than expected | error    | Trigger data refresh for TTC sources; rebuild staging through marts                                                |
| `fct_transit_delays` | `schema_changes`      | Column added/removed/type-changed                  | error    | Inspect intermediate and fact model SQL for unintended modifications                                                |
| `fct_bike_trips`     | `volume_anomalies`    | Row count outside 10M–50M range                    | error    | Check RAW bike trip table; rebuild: `dbt build --select fct_bike_trips --full-refresh`                             |
| `fct_bike_trips`     | `freshness_anomalies` | `start_time` max value older than expected         | error    | Trigger data refresh for Bike Share source; rebuild staging through marts                                          |
| `fct_bike_trips`     | `schema_changes`      | Column added/removed/type-changed                  | error    | Inspect staging, intermediate, and fact model SQL for unintended modifications                                      |
| `fct_daily_mobility` | `volume_anomalies`    | Row count outside 1,000–5,000 range                | error    | Rebuild: `dbt build --select fct_daily_mobility --full-refresh`; check upstream daily metric models                |
| `fct_daily_mobility` | `schema_changes`      | Column added/removed/type-changed                  | error    | Inspect `fct_daily_mobility.sql` and upstream intermediate models for unintended modifications                      |

---

## 3. Source Freshness Monitoring

### Configuration

All 5 sources share identical freshness thresholds defined in their respective `_*__sources.yml` files:

| Threshold   | Value    | Meaning                                      |
| ----------- | -------- | -------------------------------------------- |
| `warn_after`  | 45 days  | Source data is aging; schedule a refresh      |
| `error_after` | 90 days  | Source data is critically stale; refresh required |

### Sources Monitored

| Source                  | `loaded_at_field`                             | Table                    |
| ----------------------- | --------------------------------------------- | ------------------------ |
| TTC Subway Delays       | `try_cast(date as timestamp)`                 | `raw.ttc_subway_delays`  |
| TTC Bus Delays          | `try_cast(date as timestamp)`                 | `raw.ttc_bus_delays`     |
| TTC Streetcar Delays    | `try_cast(date as timestamp)`                 | `raw.ttc_streetcar_delays` |
| Bike Share Trips        | `try_cast(start_time as timestamp)`           | `raw.bike_share_trips`   |
| Weather Daily           | `try_cast(date_time as timestamp)`            | `raw.weather_daily`      |

### Checking Freshness

```bash
dbt source freshness
```

Output: per-source freshness status (pass/warn/error) with the timestamp of the most recent record.

### Response Procedure

| Status  | Action                                                                 |
| ------- | ---------------------------------------------------------------------- |
| `pass`  | No action required                                                     |
| `warn`  | Schedule a data refresh within the next maintenance window             |
| `error` | Immediate refresh: `python scripts/ingest.py && dbt build --fail-fast` |

---

## 4. dbt Artifacts

### Artifact Inventory

| Artifact           | Location             | Purpose                                     | Retention                              |
| ------------------ | -------------------- | ------------------------------------------- | -------------------------------------- |
| `manifest.json`    | `target/`            | Model dependencies, compiled SQL, DAG       | CI artifact (30 days); committed to repo on main |
| `run_results.json` | `target/`            | Execution times, row counts, test results   | CI artifact (30 days)                  |
| `catalog.json`     | `target/`            | Column-level metadata from `dbt docs generate` | CI artifact (30 days)                |
| `sources.json`     | `target/`            | Source freshness evaluation results         | CI artifact (30 days)                  |
| `elementary_report.html` | `edr_target/`  | Elementary HTML observability dashboard     | CI artifact (30 days)                  |

Reference: DESIGN-DOC Section 9.1.

### Accessing CI Artifacts

dbt artifacts are uploaded as `dbt-artifacts` on pushes to `main`. The Elementary report is uploaded as `elementary-report` on all CI runs where Snowflake credentials are available.

To download from a specific CI run:

```bash
# List recent workflow runs
gh run list --workflow "CI dbt"

# Download artifacts from a specific run
gh run download <run-id> --name dbt-artifacts --dir ./artifacts
gh run download <run-id> --name elementary-report --dir ./artifacts
```

### Using Artifacts for Diagnostics

**`run_results.json`** — Identify slow models:

```bash
# Parse run times from run_results.json
python -c "
import json
with open('target/run_results.json') as f:
    data = json.load(f)
for r in sorted(data['results'], key=lambda x: x.get('execution_time', 0), reverse=True)[:10]:
    print(f\"{r['unique_id']:60s} {r.get('execution_time', 0):6.2f}s\")
"
```

**`catalog.json`** — Verify documentation completeness:

```bash
# Count models with missing descriptions
python -c "
import json
with open('target/catalog.json') as f:
    data = json.load(f)
missing = [n for n, v in data['nodes'].items() if not v.get('metadata', {}).get('comment')]
print(f'Models with missing descriptions: {len(missing)}')
"
```

---

## 5. Snowflake Native Monitoring

### Query Performance Tracking

```sql
-- Recent query performance (last 24 hours)
SELECT
    query_id,
    query_tag,
    total_elapsed_time / 1000.0 AS elapsed_seconds,
    rows_produced,
    bytes_scanned,
    warehouse_size
FROM TABLE(INFORMATION_SCHEMA.QUERY_HISTORY(
    DATE_RANGE_START => DATEADD('hours', -24, CURRENT_TIMESTAMP()),
    RESULT_LIMIT => 100
))
WHERE warehouse_name = 'TRANSFORM_WH'
ORDER BY start_time DESC;
```

### Performance Thresholds

Reference: DESIGN-DOC Section 9.2.

| Metric           | Warning Threshold | Error Threshold | Action                    |
| ---------------- | ----------------- | --------------- | ------------------------- |
| Model run time   | > 60 seconds      | > 300 seconds   | Investigate query plan    |
| Source freshness  | > 45 days         | > 90 days       | Trigger re-ingestion      |
| Test failures    | Any warning       | Any error       | Block merge, investigate  |

### Warehouse Credit Monitoring

```sql
-- Monthly credit consumption
SELECT
    start_time::date AS usage_date,
    warehouse_name,
    SUM(credits_used) AS total_credits
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
WHERE warehouse_name = 'TRANSFORM_WH'
  AND start_time >= DATEADD('month', -1, CURRENT_TIMESTAMP())
GROUP BY 1, 2
ORDER BY 1;
```

Reference: DESIGN-DOC Section 9.2 — Warning at > $10/month, Error at > $20/month.

### Benchmark Queries

Five benchmark queries in `/analyses/` validate the < 5 second performance target on X-Small warehouse. Results documented in `docs/PH-09/performance_results.md`.

```bash
# Compile benchmark queries
dbt compile

# Compiled SQL available at target/compiled/toronto_mobility/analyses/*.sql
```

Execute compiled queries directly in Snowflake or via the snowflake-connector-python driver. Tag sessions with `ALTER SESSION SET QUERY_TAG = 'benchmark_ph09'` for identification in `QUERY_HISTORY`.

---

## 6. References

- Observability architecture: `DESIGN-DOC.md` Section 9
- Test inventory and thresholds: `docs/TESTS.md`
- Pipeline operations: `docs/RUNBOOK.md`
- Performance benchmarks: `docs/PH-09/performance_results.md`
- Governance: `CLAUDE.md`
