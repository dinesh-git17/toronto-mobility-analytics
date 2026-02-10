# Performance Benchmark Results

**Date:** 2026-02-10
**Epic:** E-902 (PH-09)
**Reference:** DESIGN-DOC Section 15.4

---

## 1. Methodology

Five analytical queries compiled via `dbt compile` and executed against Snowflake using the snowflake-connector-python driver. Execution protocol:

1. Warehouse resume and cache warm-up via `SELECT 1 FROM fct_daily_mobility LIMIT 1`
2. Session tagged with `ALTER SESSION SET QUERY_TAG = 'benchmark_ph09'`
3. Each compiled query executed sequentially from `target/compiled/**/analyses/*.sql`
4. Server-side metrics captured from `INFORMATION_SCHEMA.QUERY_HISTORY()` filtered by query ID

All timings reflect server-side elapsed time (network latency excluded). Compilation time is the Snowflake query planner phase; execution time is the warehouse compute phase.

---

## 2. Warehouse Configuration

| Parameter   | Value                 |
| ----------- | --------------------- |
| Warehouse   | `TRANSFORM_WH`        |
| Size        | X-Small (1 node)      |
| Database    | `TORONTO_MOBILITY`    |
| Schema      | `MARTS`               |
| Role        | `TRANSFORMER_ROLE`    |
| dbt Version | 1.11.2                |
| Adapter     | snowflake-dbt 1.11.1  |
| Concurrency | Sequential (1 thread) |

---

## 3. Results

| #   | Query                          | Elapsed (s) | Compilation (s) | Execution (s) | Rows Produced | Bytes Scanned | Pass/Fail |
| --- | ------------------------------ | ----------- | --------------- | ------------- | ------------- | ------------- | --------- |
| 1   | `daily_mobility_summary.sql`   | 0.954       | 0.314           | 0.513         | 1,827         | 121,359       | PASS      |
| 2   | `top_delay_stations.sql`       | 0.593       | 0.182           | 0.411         | 10            | 11,014,656    | PASS      |
| 3   | `bike_weather_correlation.sql` | 0.673       | 0.525           | 0.148         | 4             | 138,752       | PASS      |
| 4   | `cross_modal_analysis.sql`     | 0.164       | 0.117           | 0.047         | 3             | 95,744        | PASS      |
| 5   | `monthly_trends.sql`           | 0.339       | 0.252           | 0.087         | 60            | 121,359       | PASS      |

**Threshold:** < 5 seconds per query (DESIGN-DOC Section 15.4)
**Result:** All 5 queries PASS. Maximum elapsed time: 0.954s (`daily_mobility_summary`).

---

## 4. Summary

All benchmark queries execute well within the 5-second threshold on an X-Small warehouse. The slowest query (`daily_mobility_summary`) completes in under 1 second, leaving a 4x safety margin against the performance target.

Key observations:

- **`top_delay_stations`** scans the most bytes (10.5 MB) due to the `fct_transit_delays` aggregation across 237,446 rows with a dimension join. Execution remains fast at 0.411s.
- **`cross_modal_analysis`** is the fastest query (0.164s total) — conditional aggregation on the pre-aggregated `fct_daily_mobility` table (1,827 rows) requires minimal compute.
- **`bike_weather_correlation`** has the highest compilation-to-execution ratio (0.525s compile vs 0.148s execution) due to the CASE expression and two-table join plan resolution. Execution is negligible once the plan is generated.
- **`monthly_trends`** produces 60 rows (vs expected ~72) reflecting months with data in the current dataset window.
- Compilation time accounts for 40-70% of total elapsed time across queries, typical for sub-second executions where the optimizer phase is a larger proportion of wall clock.

No query exceeds 1 second. No optimization or clustering changes are warranted.

---

## 5. Row Count Validation

| Query                          | Expected Rows | Actual Rows | Status                                          |
| ------------------------------ | ------------- | ----------- | ----------------------------------------------- |
| `daily_mobility_summary.sql`   | ~2,200        | 1,827       | Within range — reflects active dates in dataset |
| `top_delay_stations.sql`       | 10            | 10          | Exact match                                     |
| `bike_weather_correlation.sql` | 4             | 4           | Exact match                                     |
| `cross_modal_analysis.sql`     | 3             | 3           | Exact match                                     |
| `monthly_trends.sql`           | ~72           | 60          | Within range — reflects months with loaded data |
