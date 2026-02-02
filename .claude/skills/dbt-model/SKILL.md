---
name: dbt-model
description: Create dbt models following medallion architecture (staging/intermediate/marts). Use when adding new models, transforming data, or working with dbt in this project. Triggers on requests for new fact tables, dimension tables, staging views, or intermediate CTEs.
---

# dbt Model Development

Create dbt models following the Toronto Urban Mobility Analytics medallion architecture.

## Architecture Layers

### Staging (Views)

Source-conformed models with minimal transformation.

**Location**: `models/staging/<source>/`
**Materialization**: `view`
**Naming**: `stg_<source>__<entity>.sql`

**Pattern**:

```sql
{{
    config(
        materialized='view'
    )
}}

with source as (
    select * from {{ source('<source>', '<table>') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key(['<natural_key_cols>']) }} as <entity>_sk,
        <column>::<type> as <column_name>,
        -- Type casting and renaming only
    from source
)

select * from renamed
```

### Intermediate (Ephemeral)

Business logic, joins, and enrichment.

**Location**: `models/intermediate/`
**Materialization**: `ephemeral`
**Naming**: `int_<entity>_<action>.sql`

**Pattern**:

```sql
{{
    config(
        materialized='ephemeral'
    )
}}

with <source_cte> as (
    select * from {{ ref('stg_<source>__<entity>') }}
),

<enrichment_cte> as (
    -- Join seeds, apply business logic
),

final as (
    select
        -- Final column selection
    from <enrichment_cte>
)

select * from final
```

### Marts (Tables)

Final presentation layer for analytics.

**Location**: `models/marts/<domain>/`
**Materialization**: `table`
**Naming**: `fct_<entity>.sql` or `dim_<entity>.sql`

**Pattern**:

```sql
{{
    config(
        materialized='table'
    )
}}

with <intermediate_cte> as (
    select * from {{ ref('int_<entity>_<action>') }}
),

final as (
    select
        <surrogate_key> as <entity>_sk,
        <dimension_keys>,
        <measures>,
        <attributes>
    from <intermediate_cte>
)

select * from final
```

## Surrogate Keys

ALWAYS use `dbt_utils.generate_surrogate_key()`:

```sql
{{ dbt_utils.generate_surrogate_key(['date', 'time', 'station', 'line']) }} as delay_sk
```

## Required Documentation

Create `_<domain>__models.yml` alongside models:

```yaml
version: 2

models:
  - name: <model_name>
    description: "<description>"
    columns:
      - name: <column_name>
        description: "<description>"
        tests:
          - unique
          - not_null
```

## Required Tests

**All mart models must have**:

## Required Tests

**All mart models must have**:

- `unique` and `not_null` on primary keys
- `relationships` on all foreign keys
- `accepted_values` on categorical columns

## SQL Standards

- **Dialect**: Snowflake SQL
- **Formatting**: Apply `sqlfmt`
- **Linting**: Pass `SQLFluff` (Snowflake dialect)
- **Tables/Views**: `SNAKE_CASE` (Upper)
- **Columns**: `snake_case` (lower)

## Workflow

See [references/model-checklist.md](references/model-checklist.md) for the full development checklist.
