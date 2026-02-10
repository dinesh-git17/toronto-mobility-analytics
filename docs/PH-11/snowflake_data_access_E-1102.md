# Snowflake Data Access & Caching Layer

| Field        | Value         |
| ------------ | ------------- |
| Epic ID      | E-1102        |
| Phase        | PH-11         |
| Owner        | @dinesh-git17 |
| Status       | Complete      |
| Dependencies | [E-1101]      |
| Created      | 2026-02-10    |

---

## Context

The dashboard requires read-only access to 7 MARTS tables (4 dimensions, 3 facts) containing 22M+ rows of transit delay, bike share trip, and weather data. Raw SQL execution against Snowflake without connection pooling, parameterization, or caching would produce unacceptable cold-start latency (>5 seconds per dashboard-design.md Section 5.6), redundant warehouse compute on repeated queries, and SQL injection surface area from user-controlled filter parameters. This epic builds the complete data access layer: a `st.cache_resource` connection manager targeting the MARTS schema exclusively, a parameterized SQL query library covering all 7 tables with bind-variable safety, and a tiered caching strategy implementing the 4 TTL tiers specified in dashboard-design.md Section 5.5 (24-hour reference, 1-hour hero, 30-minute standard, 10-minute filtered).

This work belongs in PH-11 because the Overview landing page (E-1104) and all subsequent deep-dive pages require a stable, performant query interface to render any visualization. No page can display live data without this layer.

---

## Scope

### In Scope

- `dashboard/data/connection.py`: Snowflake connection manager using `st.cache_resource` with secrets-based credential retrieval (`account`, `user`, `password`, `warehouse`, `database`, `role`) targeting `schema="MARTS"` exclusively
- `dashboard/data/queries.py`: Parameterized SQL query definitions for all 7 MARTS tables — `fct_transit_delays`, `fct_bike_trips`, `fct_daily_mobility`, `dim_station`, `dim_date`, `dim_weather`, `dim_ttc_delay_codes` — including hero metric queries, monthly aggregation queries, mode comparison queries, and reference data queries
- `dashboard/data/cache.py`: Tiered caching utilities wrapping `st.cache_data` with 4 TTL tiers per dashboard-design.md Section 5.5: reference data (24 hours), hero aggregations (1 hour), standard aggregations (30 minutes), filtered queries (10 minutes)
- Query execution wrapper with Snowflake error handling, connection timeout, and user-facing error display
- Health check function validating MARTS schema connectivity via `SELECT 1`

### Out of Scope

- RAW or STAGING schema access (MARTS-only per DESIGN-DOC.md medallion architecture)
- Write operations of any kind (dashboard is strictly read-only)
- Connection pooling beyond the `st.cache_resource` singleton pattern
- Async or concurrent query execution
- Query result pagination or streaming
- Snowflake query tagging, warehouse auto-scaling, or multi-cluster configuration
- Data transformation or business logic in the query layer (all transformations completed in dbt intermediate/marts layers)

---

## Technical Approach

### Architecture Decisions

- **`st.cache_resource` singleton for connection** — Per dashboard-design.md Section 5.3, the Snowflake connection is cached at the resource level using `@st.cache_resource`. This creates a single connection instance shared across all users and reruns within the Streamlit server process. The connection is not recreated on page navigation or widget interaction — only on server restart or cache eviction.
- **MARTS schema restriction enforced at connection level** — The connection constructor sets `schema="MARTS"` as a fixed parameter. All queries execute against this schema without per-query schema qualification. This prevents accidental reads from RAW or STAGING schemas where data may be unvalidated or contain PII.
- **Bind-variable parameterization for all user-controlled inputs** — All queries accepting filter parameters (date ranges, transit modes, station IDs) use `%(param)s` placeholder syntax with the Snowflake connector's built-in parameter binding. No f-string interpolation, `.format()`, or string concatenation for query construction. This eliminates SQL injection as an attack vector.
- **Date range filtering via `date_key` for partition pruning** — All date-filtered queries use `date_key BETWEEN %(start_date)s AND %(end_date)s` where `date_key` is an integer in YYYYMMDD format. This aligns with the mart models' `date_key` integer column and enables Snowflake micro-partition pruning per DESIGN-DOC.md performance constraints.
- **Tiered caching with `st.cache_data` decorators** — Four distinct TTL tiers match dashboard-design.md Section 5.5. Each tier is implemented as a wrapper function or decorator that applies `@st.cache_data(ttl=N)` with the tier-specific TTL value (86400, 3600, 1800, or 600 seconds). Cache keys automatically incorporate the query text and parameter values, preventing stale cross-query cache hits.

### Integration Points

- **Upstream: E-1101** — Requires `dashboard/data/` directory and `secrets.toml.example` credential template
- **Upstream: PH-07 MARTS layer** — Queries target 7 MARTS tables: `fct_transit_delays` (237,446 rows), `fct_bike_trips` (21,795,223 rows), `fct_daily_mobility` (1,827 rows), `dim_station` (1,085 rows), `dim_date` (2,922 rows), `dim_weather` (~2,200 rows), `dim_ttc_delay_codes` (334 rows)
- **Downstream: E-1104** — Overview page consumes hero metric queries, monthly aggregation queries, and mode comparison queries
- **Downstream: PH-12 through PH-14** — All deep-dive pages consume parameterized queries with date range and categorical filter parameters

### Repository Areas

- `dashboard/data/connection.py` (new)
- `dashboard/data/queries.py` (new)
- `dashboard/data/cache.py` (new)

### Risks

| Risk                                                                                                                                          | Likelihood | Impact | Mitigation                                                                                                                                                                                                                                                         |
| --------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Snowflake connection drops silently during long-running Streamlit sessions (idle timeout), causing `ProgrammingError` on next query execution | Medium     | High   | Implement connection health check (`SELECT 1`) in the query execution wrapper; on failure, clear `st.cache_resource` and reconnect; display `st.error()` with retry instruction                                                                                    |
| `fct_bike_trips` (21.8M rows) full-table aggregation exceeds the 3-second hero metric target on X-Small warehouse without caching             | Medium     | High   | Hero metric queries on `fct_bike_trips` use 1-hour cache TTL; first cold-load may exceed 3 seconds but subsequent requests are instant; pre-aggregated `fct_daily_mobility` (1,827 rows) provides an alternative source for trip counts                            |
| Bind-variable syntax `%(param)s` incompatible with Snowflake connector version or pandas `read_sql` method signature                          | Low        | High   | Validate parameterized query execution against the pinned `snowflake-connector-python>=3.12.0,<4.0.0` during S002 implementation; fall back to `cursor.execute(query, params)` with manual DataFrame construction if `pd.read_sql` does not support bind variables |
| Cache key collisions between queries with identical SQL text but different parameter values cause stale data display                          | Low        | Medium | `st.cache_data` uses all function arguments (including parameters dict) as cache key components by default; verify via explicit testing that changing a date range filter produces a cache miss                                                                    |

---

## Stories

| ID   | Story                                                                 | Points | Dependencies | Status |
| ---- | --------------------------------------------------------------------- | ------ | ------------ | ------ |
| S001 | Implement Snowflake connection manager with secrets-based credentials | 5      | E-1101.S001  | Complete |
| S002 | Build parameterized SQL query definitions for all 7 MARTS tables      | 8      | S001         | Complete |
| S003 | Implement tiered caching strategy with 4 TTL tiers                    | 5      | S001         | Complete |
| S004 | Add query execution wrapper with error handling and health check      | 3      | S001, S003   | Complete |

---

### S001: Implement Snowflake Connection Manager with Secrets-Based Credentials

**Description**: Build `dashboard/data/connection.py` with a `st.cache_resource`-decorated connection factory that reads Snowflake credentials from `st.secrets` and returns a persistent connection targeting the MARTS schema.

**Acceptance Criteria**:

- [ ] File `dashboard/data/connection.py` exists
- [ ] Function `get_connection()` decorated with `@st.cache_resource` returns a `snowflake.connector.SnowflakeConnection` instance
- [ ] Connection reads credentials from `st.secrets["snowflake"]` with keys: `account`, `user`, `password`, `warehouse`, `database`, `role`
- [ ] Connection constructor sets `schema="MARTS"` as a fixed parameter — no RAW or STAGING access
- [ ] Connection constructor sets `login_timeout=30` and `network_timeout=30` to prevent indefinite hangs
- [ ] Function raises `st.error()` with message "Snowflake connection failed. Verify credentials in .streamlit/secrets.toml." and calls `st.stop()` on `snowflake.connector.errors.DatabaseError`
- [ ] No credentials hardcoded, logged, or exposed in error messages
- [ ] All functions have type hints on parameters and return values
- [ ] All public functions have docstrings

**Technical Notes**: `st.cache_resource` creates a single connection instance per Streamlit server process. The connection persists across user sessions and page navigation. Clearing the cache (`st.cache_resource.clear()`) forces reconnection. The `login_timeout` and `network_timeout` parameters prevent the app from hanging if Snowflake is unreachable during cold start.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Connection successfully established to Snowflake MARTS schema with valid credentials
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S002: Build Parameterized SQL Query Definitions for All 7 MARTS Tables

**Description**: Build `dashboard/data/queries.py` with SQL query functions covering all 7 MARTS tables, including hero metric aggregations, monthly time series, mode comparisons, and reference data lookups — all using bind-variable parameterization for user-controlled inputs.

**Acceptance Criteria**:

- [ ] File `dashboard/data/queries.py` exists
- [ ] Hero metric query: total delay hours — `SUM(delay_minutes) / 60` from `fct_transit_delays`, returns single-row DataFrame with `total_delay_hours` column
- [ ] Hero metric query: total bike trips — `COUNT(*)` from `fct_bike_trips`, returns single-row DataFrame with `total_bike_trips` column
- [ ] Hero metric query: worst station — station with highest total delay minutes from `fct_transit_delays` joined to `dim_station` WHERE `transit_mode = 'subway'`, returns single-row DataFrame with `station_name` and `total_delay_minutes` columns
- [ ] Hero metric query: data freshness — `MAX(full_date)` from `dim_date` WHERE `date_key` IN (SELECT `date_key` FROM `fct_daily_mobility`), returns single-row DataFrame with `latest_date` column
- [ ] Monthly aggregation query: year, month, total delay count, total bike trips from `fct_daily_mobility` grouped by year and month, ordered chronologically — returns DataFrame for YoY trend visualization
- [ ] Mode comparison query: `transit_mode`, delay count, total delay minutes from `fct_transit_delays` grouped by `transit_mode` — returns DataFrame for bar chart visualization
- [ ] Reference data queries: all rows from `dim_station`, all rows from `dim_ttc_delay_codes`, MIN/MAX `full_date` from `dim_date` — returns complete DataFrames for filter population and display
- [ ] All queries accepting user-controlled filter parameters (date range, transit mode) use `%(param)s` bind-variable syntax — zero f-string or `.format()` interpolation
- [ ] Date range filtering uses `date_key BETWEEN %(start_date)s AND %(end_date)s` for integer `date_key` partition pruning
- [ ] All query functions have type hints and docstrings describing the query purpose, parameters, and return shape

**Technical Notes**: Query functions return SQL strings (not executed DataFrames) — execution is delegated to the caching layer (S003/S004). This separation allows the same query to be executed with different cache tiers depending on context. The `fct_daily_mobility` table (1,827 rows) is pre-aggregated in the dbt intermediate layer and serves as the primary source for time series and hero metrics that span both transit and bike modalities.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] All query functions return valid SQL strings that execute without error against the MARTS schema
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S003: Implement Tiered Caching Strategy with 4 TTL Tiers

**Description**: Build `dashboard/data/cache.py` with 4 caching tier functions wrapping `st.cache_data`, each enforcing a distinct TTL per dashboard-design.md Section 5.5: reference data (24 hours), hero aggregations (1 hour), standard aggregations (30 minutes), filtered queries (10 minutes).

**Acceptance Criteria**:

- [ ] File `dashboard/data/cache.py` exists
- [ ] Function `query_reference_data(query: str, conn) -> pd.DataFrame` decorated with `@st.cache_data(ttl=86400)` — 24-hour TTL for station lists, delay codes, and date range bounds
- [ ] Function `query_hero_metrics(query: str, conn) -> pd.DataFrame` decorated with `@st.cache_data(ttl=3600)` — 1-hour TTL for hero metric computations
- [ ] Function `query_aggregation(query: str, conn) -> pd.DataFrame` decorated with `@st.cache_data(ttl=1800)` — 30-minute TTL for chart data and monthly rollups
- [ ] Function `query_filtered(query: str, params: dict, conn) -> pd.DataFrame` decorated with `@st.cache_data(ttl=600)` — 10-minute TTL for user-parameterized queries
- [ ] TTL values match dashboard-design.md Section 5.5 exactly: 86400, 3600, 1800, 600 seconds
- [ ] Each function executes the SQL query via the Snowflake connection and returns a `pd.DataFrame`
- [ ] `query_filtered` passes the `params` dict to the Snowflake cursor for bind-variable execution
- [ ] Cache keys incorporate query text and parameter values to prevent stale cross-query hits (verified by `st.cache_data` default behavior using all function arguments as key)
- [ ] Utility function `clear_all_caches()` provided that calls `st.cache_data.clear()` for development and debugging
- [ ] All functions have type hints and docstrings

**Technical Notes**: `st.cache_data` serializes the return value (DataFrame) and caches it keyed on the function name plus all argument values. The `conn` parameter is a Snowflake connection from `get_connection()` — since `st.cache_resource` returns the same object, the connection contributes a stable cache key. The `hash_funcs` parameter may be required to serialize unhashable connection objects: `@st.cache_data(ttl=N, hash_funcs={SnowflakeConnection: id})`.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] All 4 cache tier functions execute queries and return DataFrames
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S004: Add Query Execution Wrapper with Error Handling and Health Check

**Description**: Extend `dashboard/data/connection.py` with a health check function and a query execution wrapper that catches Snowflake errors and displays user-facing messages without exposing credentials or internal state.

**Acceptance Criteria**:

- [ ] Function `check_health() -> bool` in `dashboard/data/connection.py` executes `SELECT 1` against the MARTS schema and returns `True` on success, `False` on failure
- [ ] Health check result cached with `@st.cache_data(ttl=300)` — 5-minute TTL to avoid repeated connectivity probes
- [ ] Query execution catches `snowflake.connector.errors.ProgrammingError` (bad SQL) and displays `st.error()` with the Snowflake error message (safe to display — contains SQL syntax info, not credentials)
- [ ] Query execution catches `snowflake.connector.errors.DatabaseError` (connection lost) and attempts reconnection by clearing `st.cache_resource` and retrying once
- [ ] On persistent connection failure after retry, displays `st.error("Connection lost. Verify Snowflake credentials in .streamlit/secrets.toml.")` and calls `st.stop()`
- [ ] Connection timeout defaults to 30 seconds per the `login_timeout` and `network_timeout` parameters set in S001
- [ ] All functions have type hints and docstrings

**Technical Notes**: Snowflake idle connections may timeout after 4 hours (default session timeout). The health check and retry logic handle this gracefully by detecting the stale connection and re-establishing it. The `st.cache_resource.clear()` call invalidates the cached connection singleton, forcing `get_connection()` to create a fresh connection on the next invocation.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Health check returns `True` with valid credentials and `False` with invalid credentials
- [ ] PR opened with linked issue
- [ ] CI checks green

---

## Exit Criteria

This epic is complete when:

- [ ] `dashboard/data/connection.py` establishes a cached Snowflake connection targeting MARTS schema with secrets-based credentials
- [ ] `dashboard/data/queries.py` contains parameterized SQL query definitions for all 7 MARTS tables: `fct_transit_delays`, `fct_bike_trips`, `fct_daily_mobility`, `dim_station`, `dim_date`, `dim_weather`, `dim_ttc_delay_codes`
- [ ] `dashboard/data/cache.py` implements 4 TTL tiers matching dashboard-design.md Section 5.5: 86400s, 3600s, 1800s, 600s
- [ ] All queries with user-controlled parameters use bind-variable syntax — zero string interpolation
- [ ] Health check function validates MARTS connectivity via `SELECT 1`
- [ ] Connection errors display user-facing messages without exposing credentials
- [ ] Hero metric queries execute and return valid DataFrames when tested against Snowflake MARTS tables
