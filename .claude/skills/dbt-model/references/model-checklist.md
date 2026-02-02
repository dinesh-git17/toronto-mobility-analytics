# dbt Model Development Checklist

## Pre-Development

- [ ] Identify source table(s) in RAW schema
- [ ] Determine target layer (staging/intermediate/marts)
- [ ] Review existing models for patterns

## Staging Model

- [ ] Create in `models/staging/<source>/`
- [ ] Name as `stg_<source>__<entity>.sql`
- [ ] Set `materialized='view'`
- [ ] Generate surrogate key with `dbt_utils.generate_surrogate_key()`
- [ ] Cast all columns explicitly
- [ ] Rename columns to snake_case
- [ ] Add to `_<source>__sources.yml`
- [ ] Add to `_<source>__models.yml`

## Intermediate Model

- [ ] Create in `models/intermediate/`
- [ ] Name as `int_<entity>_<action>.sql`
- [ ] Set `materialized='ephemeral'`
- [ ] Reference staging models with `{{ ref() }}`
- [ ] Join with seeds or other staging models
- [ ] Apply business logic
- [ ] Add to `_int__models.yml`

## Mart Model

- [ ] Create in `models/marts/<domain>/`
- [ ] Name as `fct_<entity>.sql` or `dim_<entity>.sql`
- [ ] Set `materialized='table'`
- [ ] Reference intermediate models
- [ ] Include all required columns
- [ ] Add to `_<domain>__models.yml`

## Documentation

- [ ] Write model description
- [ ] Document all columns
- [ ] Add column-level tests

## Testing

- [ ] `unique` test on primary key
- [ ] `not_null` test on primary key
- [ ] `relationships` tests on foreign keys
- [ ] `accepted_values` on enums
- [ ] Custom singular tests for business rules

## Validation

```bash
# Format SQL
sqlfmt models/<path>/<model>.sql

# Lint SQL
sqlfluff lint models/<path>/<model>.sql --dialect snowflake

# Build and test
dbt build --select <model_name>

# Generate docs
dbt docs generate
```

## Definition of Done

- [ ] Model follows medallion architecture
- [ ] SQL formatted via sqlfmt
- [ ] SQL passes SQLFluff linting
- [ ] All columns documented
- [ ] All tests pass
- [ ] `dbt build` succeeds
