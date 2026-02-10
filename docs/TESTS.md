# Test Strategy

**Last Updated:** 2026-02-10
**Scope:** Full test suite across staging, intermediate, and marts layers
**Regression Baseline:** 135 tests | PASS=130 WARN=5 ERROR=0 | 66s on X-Small warehouse

Maintenance Note: Any epic that adds, removes, or modifies tests must update this document as part of its Definition of Done.

---

## 1. Test Pyramid

Five layers of validation, ordered from foundational to analytical. Each layer builds on the guarantees of the layer below it. Reference: DESIGN-DOC Section 8.1.

```
    ┌─────────────────────────┐
    │  Performance Benchmarks │  5 queries, all < 5s (E-902)
    ├─────────────────────────┤
    │   Data Quality Tests    │  dbt_expectations, Elementary
    ├─────────────────────────┤
    │   Integration Tests     │  relationships, cross-model consistency
    ├─────────────────────────┤
    │      Unit Tests         │  unique, not_null, accepted_values
    ├─────────────────────────┤
    │     Schema Tests        │  Source freshness, column existence
    └─────────────────────────┘
```

| Layer                  | Purpose                                                         | Tools                                   | Coverage                                                      |
| ---------------------- | --------------------------------------------------------------- | --------------------------------------- | ------------------------------------------------------------- |
| Schema Tests           | Source structure validation, freshness monitoring               | dbt source tests                        | All 5 sources                                                 |
| Unit Tests             | Primary key integrity, null constraints, categorical membership | `unique`, `not_null`, `accepted_values` | All PKs (100%), all enums                                     |
| Integration Tests      | Foreign key referential integrity, cross-model consistency      | `relationships`                         | All FKs (100%)                                                |
| Data Quality Tests     | Value range validation, row count bounds, anomaly detection     | dbt_expectations, Elementary            | All mart models                                               |
| Performance Benchmarks | Query execution within 5s on X-Small warehouse                  | Benchmark queries                       | 5 queries, all < 5s ([results](PH-09/performance_results.md)) |

---

## 2. Singular Test Inventory

Five singular SQL tests in `/tests/`. Each returns rows on failure and zero rows on success. Reference: DESIGN-DOC Section 8.3.

| Test Name                               | Target Model                                                 | Assertion                                                           | Severity | Threshold                   | Epic  |
| --------------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------------- | -------- | --------------------------- | ----- |
| `assert_no_negative_delays`             | `fct_transit_delays`                                         | `delay_minutes < 0` returns zero rows                               | error    | 0 rows                      | E-801 |
| `assert_bike_trips_reasonable_duration` | `fct_bike_trips`                                             | `duration_seconds >= 86400` flagged                                 | warn     | 0 rows (warn on violation)  | E-801 |
| `assert_no_future_dates`                | `fct_transit_delays`, `fct_bike_trips`, `fct_daily_mobility` | `date_key > current_date_key` returns zero rows across all facts    | error    | 0 rows                      | E-801 |
| `assert_daily_row_count_stability`      | `fct_daily_mobility`                                         | Day-over-day activity count does not drop below 50% of previous day | warn     | `current / previous >= 0.5` | E-801 |
| `assert_station_mapping_coverage`       | `int_ttc_delays_enriched`                                    | Subway station mapping coverage >= 99%                              | error    | 0.99 coverage ratio         | E-601 |

---

## 3. dbt_expectations Test Inventory

Five dbt_expectations tests defined in `_mobility__models.yml`. Package: `calogica/dbt_expectations` 0.10.4. Reference: DESIGN-DOC Section 7.7.

### Value Range Tests

| Test Macro                           | Target               | Column             | Min Value | Max Value | Severity | Epic  |
| ------------------------------------ | -------------------- | ------------------ | --------- | --------- | -------- | ----- |
| `expect_column_values_to_be_between` | `fct_transit_delays` | `delay_minutes`    | 0         | 1440      | error    | E-802 |
| `expect_column_values_to_be_between` | `fct_bike_trips`     | `duration_seconds` | 60        | 86400     | warn     | E-802 |

`delay_minutes` range 0-1440 represents zero to 24 hours — the maximum plausible single-incident delay. `duration_seconds` range 60-86400 represents 1 minute to 24 hours — the lower bound is enforced by the staging filter (DESIGN-DOC Decision D9). The bike trips test uses `severity: warn` because 4,633 trips (0.02% of 21.8M rows) exceed 24 hours due to unreturned bikes.

### Row Count Bounds

Bounds calibrated 2026-02-09. Lower bounds at ~42-55% of current volumes detect near-empty tables. Upper bounds at ~210-274% detect duplicate-load scenarios.

| Test Macro                             | Target               | Min Value  | Max Value  | Current Rows | Severity | Epic  |
| -------------------------------------- | -------------------- | ---------- | ---------- | ------------ | -------- | ----- |
| `expect_table_row_count_to_be_between` | `fct_transit_delays` | 100,000    | 500,000    | 237,446      | warn     | E-802 |
| `expect_table_row_count_to_be_between` | `fct_bike_trips`     | 10,000,000 | 50,000,000 | 21,795,223   | warn     | E-802 |
| `expect_table_row_count_to_be_between` | `fct_daily_mobility` | 1,000      | 5,000      | 1,827        | warn     | E-802 |

---

## 4. Elementary Configuration

Seventeen Elementary tests across all 7 mart models. Package: `elementary-data/elementary` 0.16.1. Reference: DESIGN-DOC Section 9.5.

Elementary tests compare each run's data profile against a learned historical baseline. The first run establishes the baseline; anomaly detection activates on subsequent runs after sufficient history accumulates (default 14-day training period).

### Core Dimensions (9 tests)

| Model                 | Test Type             | Timestamp Column | Epic  |
| --------------------- | --------------------- | ---------------- | ----- |
| `dim_date`            | `volume_anomalies`    | —                | E-802 |
| `dim_date`            | `schema_changes`      | —                | E-802 |
| `dim_station`         | `volume_anomalies`    | —                | E-802 |
| `dim_station`         | `schema_changes`      | —                | E-802 |
| `dim_weather`         | `volume_anomalies`    | —                | E-802 |
| `dim_weather`         | `freshness_anomalies` | `weather_date`   | E-802 |
| `dim_weather`         | `schema_changes`      | —                | E-802 |
| `dim_ttc_delay_codes` | `volume_anomalies`    | —                | E-802 |
| `dim_ttc_delay_codes` | `schema_changes`      | —                | E-802 |

Freshness anomalies excluded from `dim_date` (static seed), `dim_station` (no timestamp), and `dim_ttc_delay_codes` (no timestamp).

### Mobility Facts (8 tests)

| Model                | Test Type             | Timestamp Column     | Epic  |
| -------------------- | --------------------- | -------------------- | ----- |
| `fct_transit_delays` | `volume_anomalies`    | —                    | E-802 |
| `fct_transit_delays` | `freshness_anomalies` | `incident_timestamp` | E-802 |
| `fct_transit_delays` | `schema_changes`      | —                    | E-802 |
| `fct_bike_trips`     | `volume_anomalies`    | —                    | E-802 |
| `fct_bike_trips`     | `freshness_anomalies` | `start_time`         | E-802 |
| `fct_bike_trips`     | `schema_changes`      | —                    | E-802 |
| `fct_daily_mobility` | `volume_anomalies`    | —                    | E-802 |
| `fct_daily_mobility` | `schema_changes`      | —                    | E-802 |

Freshness anomalies excluded from `fct_daily_mobility` — `date_key` is an integer (YYYYMMDD), not a timestamp column.

---

## 5. Execution Procedures

Four execution contexts per DESIGN-DOC Section 8.4.

### Local Development

```bash
# Test a specific model after changes
dbt test --select <model_name>

# Test all models in a layer
dbt test --select "path:models/marts/"

# Run singular tests only
dbt test --select test_type:singular

# Run all tests on a specific fact table
dbt test --select fct_transit_delays
```

### Pre-commit

```bash
# Build and test modified models and their downstream dependents
dbt build --select state:modified+
```

Requires a production manifest for state comparison. Without a manifest, falls back to full build.

### CI/CD

The CI pipeline (`.github/workflows/ci-dbt.yml`) executes `dbt build --fail-fast` on every push to `main` and on pull requests. `dbt build` includes both model materialization and test execution across all categories — schema, singular, dbt_expectations, and Elementary.

Slim CI on pull requests uses `dbt build --select state:modified+ --defer --state prod_artifacts --fail-fast` when a production manifest is available. This runs only modified models and their downstream dependents, including all associated tests.

No test categories are excluded by `--select` or `--exclude` flags.

### Scheduled

```bash
# Weekly freshness and full test pass (if orchestrated)
dbt source freshness && dbt test
```

### Elementary Report

```bash
# Establish Elementary baseline (required before anomaly detection)
dbt run --select elementary

# Generate HTML observability report
edr report
```

The report is written to `edr_target/elementary_report.html`. Elementary requires a `elementary` profile in `~/.dbt/profiles.yml` pointing to the same Snowflake target.

---

## 6. Severity Classification

Two severity levels per DESIGN-DOC Section 8.3. Severity determines whether a test failure blocks the build (`error`) or surfaces a warning (`warn`).

| Severity          | dbt Behavior                               | CI Impact                    | Use Case                                                             |
| ----------------- | ------------------------------------------ | ---------------------------- | -------------------------------------------------------------------- |
| `error` (default) | Test failure → exit code 1                 | Build fails, PR blocked      | Data corruption, referential integrity violations, impossible values |
| `warn`            | Test failure → warning logged, exit code 0 | Build succeeds with warnings | Data quality deviations, known edge cases, volume fluctuations       |

### Tests Configured as `warn`

| Test                                                    | Rationale                                                                                         |
| ------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| `assert_bike_trips_reasonable_duration`                 | 4,633 trips exceed 24h due to unreturned bikes — legitimate data, not corruption                  |
| `assert_daily_row_count_stability`                      | Day-over-day drops common around holidays, transit service changes, and seasonal ridership shifts |
| `expect_column_values_to_be_between` (duration_seconds) | Same 4,633 long-duration trips flagged; warn-level to avoid blocking builds on known edge case    |
| `expect_table_row_count_to_be_between` (all 3 facts)    | Row counts fluctuate with data loads; bounds detect catastrophic loss, not routine variation      |
| `accepted_values` (stg_ttc_subway_delays.line_code)     | 6 rows with non-standard line codes (YUS, bus routes) in source data — warn rather than reject    |
| `accepted_values` (stg_ttc_subway_delays.direction)     | 1 row with non-standard compass value in source data                                              |

### Tests Configured as `error` (default)

All remaining 129 tests use default `error` severity. This includes:

- All `unique` and `not_null` tests on primary keys
- All `relationships` tests on foreign keys
- All `accepted_values` tests except the 2 staging exceptions above
- `assert_no_negative_delays` — negative delay minutes indicates data corruption
- `assert_no_future_dates` — future-dated records indicate pipeline or source defects
- `assert_station_mapping_coverage` — subway mapping below 99% indicates seed regression
- `expect_column_values_to_be_between` (delay_minutes 0-1440) — all values within bounds
- All Elementary tests — default severity; first-run passes establish baseline

---

## 7. Test Count Summary

### By Category

| Category                                                  | Count   | Layer                               |
| --------------------------------------------------------- | ------- | ----------------------------------- |
| Schema (unique, not_null, accepted_values, relationships) | 108     | Seeds, Staging, Intermediate, Marts |
| Singular                                                  | 5       | Intermediate (1), Marts (4)         |
| dbt_expectations                                          | 5       | Marts Mobility                      |
| Elementary                                                | 17      | Marts Core (9), Marts Mobility (8)  |
| **Total**                                                 | **135** |                                     |

### By Model Layer

| Layer          | Schema  | Singular | dbt_expectations | Elementary | Total   |
| -------------- | ------- | -------- | ---------------- | ---------- | ------- |
| Seeds          | 32      | —        | —                | —          | 32      |
| Staging        | 28      | —        | —                | —          | 28      |
| Intermediate   | 16      | 1        | —                | —          | 17      |
| Marts Core     | 17      | —        | —                | 9          | 26      |
| Marts Mobility | 15      | 4        | 5                | 8          | 32      |
| **Total**      | **108** | **5**    | **5**            | **17**     | **135** |

### By Mart Model

| Model               | unique | not_null | accepted_values | relationships | dbt_expectations | Elementary | Singular | Total  |
| ------------------- | ------ | -------- | --------------- | ------------- | ---------------- | ---------- | -------- | ------ |
| dim_date            | 2      | 2        | 1               | —             | —                | 2          | —        | 7      |
| dim_station         | 1      | 1        | 1               | —             | —                | 2          | —        | 5      |
| dim_weather         | 1      | 1        | 1               | 1             | —                | 3          | —        | 7      |
| dim_ttc_delay_codes | 2      | 2        | 1               | —             | —                | 2          | —        | 7      |
| fct_transit_delays  | 1      | 1        | 1               | 3             | 2                | 3          | 2        | 13     |
| fct_bike_trips      | 1      | 1        | 1               | 3             | 2                | 3          | 1        | 12     |
| fct_daily_mobility  | 1      | 1        | —               | 1             | 1                | 2          | 1        | 7      |
| **Marts Total**     | **9**  | **9**    | **6**           | **8**         | **5**            | **17**     | **4**    | **58** |

### Regression Baseline (2026-02-09)

```
dbt test (no selectors)
PASS=130  WARN=5  ERROR=0  SKIP=0  TOTAL=135
Execution time: 66 seconds (X-Small warehouse, 4 threads)
```
