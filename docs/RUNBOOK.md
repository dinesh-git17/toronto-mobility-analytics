# Pipeline Operations Runbook

**Last Updated:** 2026-02-10
**Scope:** End-to-end operational procedures for the Toronto Urban Mobility Analytics data platform

Maintenance Note: Any phase that modifies pipeline behavior, ingestion logic, or model structure must update this document as part of its Definition of Done.

---

## 1. Environment Setup

### Prerequisites

| Tool                       | Version    | Purpose                                    |
| -------------------------- | ---------- | ------------------------------------------ |
| Python                     | 3.12+      | Ingestion scripts, dbt adapter             |
| dbt-core                   | 1.8+       | Data transformation orchestration          |
| dbt-snowflake              | 1.9+       | Snowflake adapter                          |
| snowflake-connector-python | 3.12+      | Direct Snowflake access (load, validation) |
| uv                         | Latest     | Python dependency management               |
| Snowflake account          | Enterprise | Data warehouse                             |

### Configuration Files

| File                   | Location  | Purpose                           |
| ---------------------- | --------- | --------------------------------- |
| `profiles.yml`         | `~/.dbt/` | Snowflake connection credentials  |
| `dbt_project.yml`      | Repo root | dbt project configuration         |
| `packages.yml`         | Repo root | dbt package dependencies (pinned) |
| `profiles.yml.example` | Repo root | Template for new environments     |

### Initial Setup

```bash
# Clone repository
git clone https://github.com/dinesh-git17/toronto-mobility-analytics.git
cd toronto-mobility-analytics

# Install Python dependencies
uv sync

# Configure dbt profile
cp profiles.yml.example ~/.dbt/profiles.yml
# Edit ~/.dbt/profiles.yml with Snowflake credentials

# Install dbt packages
dbt deps

# Verify Snowflake connectivity
dbt debug
```

Expected output from `dbt debug`: all checks return `OK`.

---

## 2. Data Refresh

Standard procedure for ingesting new source data and propagating through the transformation pipeline.

### Prerequisites

- Snowflake credentials configured in `~/.dbt/profiles.yml`
- `TRANSFORM_WH` warehouse running
- Source data files available from Toronto Open Data Portal

### Steps

```bash
# Step 1: Download and ingest source data
python scripts/ingest.py

# Step 2: Verify RAW table row counts against source files
python scripts/validate_load.py

# Step 3: Build all models (staging → intermediate → marts) and run tests
dbt build --fail-fast

# Step 4: Verify test results
dbt test
```

### Expected Output

- `scripts/ingest.py`: Downloads source files, validates schemas against contracts in `scripts/contracts.py`, transforms XLSX to CSV, loads to Snowflake RAW tables via MERGE
- `scripts/validate_load.py`: Compares source file row counts to RAW table row counts within 1% tolerance
- `dbt build`: Materializes all models and runs 135 tests; exit code 0 on success
- `dbt test`: PASS=130, WARN=5, ERROR=0 (baseline as of 2026-02-09)

### Rollback

If `dbt build` fails after RAW tables are updated:

```bash
# Re-run only failed models and their downstream dependents
dbt build --select result:error+ --fail-fast

# If data corruption is suspected, full refresh from RAW
dbt run --full-refresh
dbt test
```

---

## 3. Full Rebuild

Complete teardown and reconstruction of all dbt-managed objects.

### Prerequisites

- Snowflake credentials configured
- RAW tables populated (run Data Refresh first if empty)

### Steps

```bash
# Step 1: Full refresh all seeds
dbt seed --full-refresh

# Step 2: Full refresh all models
dbt run --full-refresh

# Step 3: Run complete test suite
dbt test

# Step 4: Re-establish Elementary baseline
dbt run --select elementary

# Step 5: Generate dbt documentation
dbt docs generate
```

### Expected Output

- `dbt seed`: 4 seeds loaded (ttc_station_mapping, ttc_delay_codes, bike_station_ref, date_spine)
- `dbt run`: 46 models materialized (5 staging views, 5 intermediate ephemeral, 7 marts tables, plus Elementary internal models)
- `dbt test`: 135 tests, PASS=130, WARN=5, ERROR=0
- Elementary baseline established for anomaly detection

### Rollback

Full rebuild is inherently idempotent. Re-run the same steps if interrupted.

---

## 4. Troubleshooting

### 4.1 Schema Validation Failure (Ingestion Layer)

**Symptom:** `scripts/validate.py` raises `SchemaValidationError` and terminates with exit code 1.

**Root Cause:** Source file schema does not match the contract defined in `scripts/contracts.py`.

**Resolution:**

```bash
# Identify the failing file and mismatched columns
python scripts/validate.py data/raw/<source_file>.csv

# Compare against the expected schema
python -c "from scripts.contracts import CONTRACTS; print(CONTRACTS['<source_key>'])"
```

If the source schema has legitimately changed (Toronto Open Data Portal schema update):

1. Update the contract in `scripts/contracts.py`
2. Update the corresponding staging model SQL and YAML
3. Run `dbt build --select state:modified+`
4. Update this runbook

### 4.2 dbt Test Failure — Schema Tests

**Symptom:** `unique`, `not_null`, or `accepted_values` test fails with `ERROR` severity.

**Root Cause:** Data integrity violation — duplicate primary keys, null values in required columns, or unexpected categorical values.

**Resolution:**

```bash
# Identify failing test and inspect the compiled SQL
dbt test --select <model_name> --store-failures

# Query the failure rows in Snowflake
# Stored in the test schema as <test_name>
```

Common causes:

- Duplicate rows in RAW data → check staging deduplication logic (`ROW_NUMBER()` window function)
- New categorical values in source data → update `accepted_values` list in YAML or set severity to `warn`

### 4.3 dbt Test Failure — Singular Tests

**Symptom:** One of the 5 singular tests in `/tests/` returns rows.

**Root Cause:** Business rule violation detected in mart data.

| Test                                    | Failure Meaning                              | Action                                                           |
| --------------------------------------- | -------------------------------------------- | ---------------------------------------------------------------- |
| `assert_no_negative_delays`             | Negative delay_minutes in fct_transit_delays | Investigate source data; likely data corruption                  |
| `assert_bike_trips_reasonable_duration` | Trips >= 24 hours (warn only)                | Expected for unreturned bikes; no action unless count spikes     |
| `assert_no_future_dates`                | Future-dated records in fact tables          | Check ingestion pipeline for timezone or date parsing errors     |
| `assert_daily_row_count_stability`      | >50% day-over-day drop (warn only)           | Normal around holidays; investigate if persistent                |
| `assert_station_mapping_coverage`       | Subway mapping < 99% coverage only)          | Normal around holidays; investigate if persistent                |
| `assert_station_mapping_coverage`       | Subway mapping < 99% coverage                | Update `seeds/ttc_station_mapping.csv` with new station variants |

### 4.4 Snowflake Warehouse Timeout

**Symptom:** Queries time out or `TRANSFORM_WH` is suspended.

**Resolution:**

```sql
-- Check warehouse state
SHOW WAREHOUSES LIKE 'TRANSFORM_WH';

-- Resume if suspended
ALTER WAREHOUSE TRANSFORM_WH RESUME;

-- Check running queries
SELECT query_id, query_text, execution_status
FROM TABLE(INFORMATION_SCHEMA.QUERY_HISTORY())
WHERE execution_status = 'RUNNING'
ORDER BY start_time DESC;
```

If queries consistently exceed 5 seconds on X-Small, review the query profile in Snowflake's query history UI before considering warehouse sizing changes.

### 4.5 Source Freshness Warnings

**Symptom:** `dbt source freshness` reports `WARN` (>45 days) or `ERROR` (>90 days).

**Root Cause:** Source data has not been refreshed within the configured threshold.

**Resolution:**

```bash
# Check current freshness status
dbt source freshness

# Trigger a data refresh
python scripts/ingest.py

# Rebuild affected models
dbt build --fail-fast
```

Freshness thresholds are configured in source YAML files (`models/staging/*/_*__sources.yml`): warn at 45 days, error at 90 days.

### 4.6 Surrogate Key Collision

**Symptom:** `unique` test fails on a surrogate key column (`delay_sk`, `trip_sk`, `station_key`).

**Root Cause:** Two distinct source records hash to the same surrogate key, or a cross-mode collision in `fct_transit_delays`.

**Resolution:**

```sql
-- Find duplicate keys
SELECT <surrogate_key_column>, COUNT(*)
FROM <table>
GROUP BY 1
HAVING COUNT(*) > 1;
```

Known mitigation: `fct_transit_delays.delay_sk` wraps the staging surrogate with `transit_mode` to prevent bus/streetcar collisions (E-702). If new collisions appear, add additional differentiating columns to the `generate_surrogate_key()` input.

---

## 5. Schema Change Response

Protocol for when Toronto Open Data source schemas change.

### Detection

Schema changes surface as `SchemaValidationError` during ingestion (`scripts/validate.py`) or as `schema_changes` Elementary test failures during `dbt build`.

### Response Protocol

1. **Identify the change**: Compare the new source file headers against the contract in `scripts/contracts.py`
2. **Update ingestion contracts**: Modify `scripts/contracts.py` with the new schema
3. **Update column renaming**: If column names changed, update `scripts/transform.py` rename mappings
4. **Update staging models**: Modify the corresponding `stg_*.sql` model and `_*__models.yml` schema
5. **Test downstream impact**: Run `dbt build --select state:modified+` to propagate changes
6. **Update documentation**: Run `dbt docs generate` to refresh column metadata
7. **Update this runbook** if the change affects operational procedures

### Rollback

If the schema change introduces data quality issues:

```bash
# Revert to previous contract
git checkout HEAD~1 -- scripts/contracts.py scripts/transform.py

# Re-run ingestion with the previous schema
python scripts/ingest.py

# Rebuild models
dbt build --fail-fast
```

---

## 6. References

- Architecture: `DESIGN-DOC.md`
- Test strategy: `docs/TESTS.md`
- Observability: `docs/OBSERVABILITY.md`
- Performance benchmarks: `docs/PH-09/performance_results.md`
- Governance: `CLAUDE.md`
