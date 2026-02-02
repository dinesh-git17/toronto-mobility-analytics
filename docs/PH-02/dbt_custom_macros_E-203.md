# dbt Custom Macros

| Field        | Value         |
| ------------ | ------------- |
| Epic ID      | E-203         |
| Phase        | PH-02         |
| Owner        | @dinesh-git17 |
| Status       | Draft         |
| Dependencies | E-202         |
| Created      | 2026-02-02    |

## Context

This epic implements the custom dbt macros required for schema routing and date dimension generation in the Toronto Urban Mobility Analytics project. The `generate_schema_name` macro overrides dbt's default schema behavior to route models to the correct Snowflake schemas (STAGING, INTERMEDIATE, MARTS, SEEDS) based on their location in the project hierarchy. The `get_date_spine` macro generates a complete date dimension spanning 2019-01-01 through 2026-12-31, providing the temporal backbone for all time-series analysis. Both macros are foundational utilities referenced throughout the transformation layer and must be implemented before any model development begins.

## Scope

### In Scope

- `generate_schema_name` macro for medallion architecture schema routing
- `get_date_spine` macro for date dimension generation (2019-01-01 to 2026-12-31)
- Macro documentation in YAML format
- Unit tests validating macro behavior
- Integration with dbt_project.yml dispatch configuration

### Out of Scope

- dim_date model implementation (PH-07)
- Other utility macros not specified in DESIGN-DOC.md
- Macro versioning or deprecation patterns

## Technical Approach

### Architecture Decisions

- **Schema routing by folder path**: The `generate_schema_name` macro inspects the model's folder location (staging/, intermediate/, marts/) and returns the corresponding Snowflake schema name (STAGING, INTERMEDIATE, MARTS), overriding dbt's default behavior of prefixing with target schema
- **Date spine using dbt_utils**: The `get_date_spine` macro wraps `dbt_utils.date_spine` with project-specific defaults, ensuring consistent date range across all temporal dimensions
- **Macro dispatch pattern**: Both macros follow dbt's dispatch pattern for potential future adapter-specific overrides

### Integration Points

- dbt_project.yml dispatch configuration
- All model files via implicit schema routing
- dim_date model (PH-07) consumes get_date_spine output
- Seeds schema routing

### Repository Areas

- `macros/generate_schema_name.sql`
- `macros/get_date_spine.sql`
- `macros/_macros.yml` — macro documentation

### Risks

| Risk                                        | Likelihood | Impact | Mitigation                                                      |
| ------------------------------------------- | ---------- | ------ | --------------------------------------------------------------- |
| Schema routing breaks existing dbt behavior | Medium     | High   | Test with sample models in each layer before phase completion   |
| Date spine boundaries incorrect             | Low        | Medium | Validate output row count: 2922 days (2019-01-01 to 2026-12-31) |
| Macro not invoked due to dispatch config    | Low        | High   | Explicitly test macro invocation with `dbt run-operation`       |

## Stories

| ID   | Story                                | Points | Dependencies | Status |
| ---- | ------------------------------------ | ------ | ------------ | ------ |
| S001 | Implement generate_schema_name macro | 5      | None         | Draft  |
| S002 | Implement get_date_spine macro       | 3      | None         | Draft  |
| S003 | Create macro documentation           | 2      | S001, S002   | Draft  |
| S004 | Validate macros with test models     | 3      | S001, S002   | Draft  |

---

### S001: Implement generate_schema_name macro

**Description**: Create the generate_schema_name macro that routes models to their correct Snowflake schemas based on folder location in the medallion architecture.

**Acceptance Criteria**:

- [ ] `macros/generate_schema_name.sql` file created
- [ ] Macro signature: `generate_schema_name(custom_schema_name, node)`
- [ ] Models in `models/staging/` route to schema `STAGING`
- [ ] Models in `models/intermediate/` route to schema `INTERMEDIATE`
- [ ] Models in `models/marts/` route to schema `MARTS`
- [ ] Seeds route to schema `SEEDS`
- [ ] Models with explicit `schema` config respect that override
- [ ] Default fallback returns `custom_schema_name` if no pattern matches
- [ ] Macro handles None/null custom_schema_name gracefully
- [ ] `dbt compile` executes without errors after macro addition

**Technical Notes**: The macro inspects `node.fqn` (fully qualified name) to determine folder location. Use Jinja conditional logic to match path patterns. Reference dbt documentation on custom schema handling: <https://docs.getdbt.com/docs/build/custom-schemas>

```sql
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- set default_schema = target.schema -%}

    {%- if custom_schema_name is not none -%}
        {{ custom_schema_name | trim }}
    {%- elif node.resource_type == 'seed' -%}
        SEEDS
    {%- elif 'staging' in node.fqn -%}
        STAGING
    {%- elif 'intermediate' in node.fqn -%}
        INTERMEDIATE
    {%- elif 'marts' in node.fqn -%}
        MARTS
    {%- else -%}
        {{ default_schema }}
    {%- endif -%}
{%- endmacro %}
```

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Macro compiles without error
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S002: Implement get_date_spine macro

**Description**: Create the get_date_spine macro that generates a complete date series from 2019-01-01 through 2026-12-31 for temporal dimension support.

**Acceptance Criteria**:

- [ ] `macros/get_date_spine.sql` file created
- [ ] Macro wraps `dbt_utils.date_spine` with project defaults
- [ ] Start date is `2019-01-01` (configurable via parameter)
- [ ] End date is `2026-12-31` (configurable via parameter)
- [ ] Date part is `day`
- [ ] Output column named `date_day`
- [ ] Macro can be invoked via `dbt run-operation get_date_spine`
- [ ] Generated spine contains exactly 2922 rows (8 years of daily data)

**Technical Notes**: The macro provides consistent date spine generation across the project. Default dates align with project data range (2019-present) plus future buffer through 2026.

```sql
{% macro get_date_spine(start_date='2019-01-01', end_date='2026-12-31') %}
    {{ dbt_utils.date_spine(
        datepart="day",
        start_date="cast('" ~ start_date ~ "' as date)",
        end_date="cast('" ~ end_date ~ "' as date)"
    ) }}
{% endmacro %}
```

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] Macro compiles without error
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S003: Create macro documentation

**Description**: Document both custom macros in YAML format with descriptions, arguments, and usage examples.

**Acceptance Criteria**:

- [ ] `macros/_macros.yml` file created
- [ ] `generate_schema_name` macro documented with:
  - Description explaining schema routing behavior
  - Arguments: custom_schema_name, node
  - Example usage in model config
- [ ] `get_date_spine` macro documented with:
  - Description explaining date spine generation
  - Arguments: start_date, end_date with defaults
  - Example usage in model SQL
- [ ] Documentation renders correctly in `dbt docs generate`
- [ ] No placeholder text (TODO, TBD) in descriptions

**Technical Notes**: Follow dbt documentation format for macro YAML. Include concrete examples that can be copy-pasted.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] `dbt docs generate` includes macro documentation
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S004: Validate macros with test models

**Description**: Create temporary test models in each layer to verify generate_schema_name routes correctly and get_date_spine produces expected output.

**Acceptance Criteria**:

- [ ] Test model `models/staging/_test_staging_routing.sql` created:
  - Contains `SELECT 1 AS test_column`
  - After `dbt run`, table exists in STAGING schema
  - After validation, file is deleted
- [ ] Test model `models/intermediate/_test_intermediate_routing.sql` created:
  - Contains `SELECT 1 AS test_column`
  - After `dbt run`, model compiles as CTE (ephemeral, no object created)
  - After validation, file is deleted
- [ ] Test model `models/marts/core/_test_marts_routing.sql` created:
  - Contains `SELECT 1 AS test_column`
  - After `dbt run`, table exists in MARTS schema
  - After validation, file is deleted
- [ ] Test model using get_date_spine created:
  - Contains `{{ get_date_spine() }}`
  - After `dbt run`, result contains 2922 rows
  - After validation, file is deleted
- [ ] `SHOW TABLES IN SCHEMA STAGING;` shows test table
- [ ] `SHOW TABLES IN SCHEMA MARTS;` shows test table
- [ ] All test tables cleaned up after validation

**Technical Notes**: These are temporary validation models, not permanent fixtures. Document the validation results in the PR description before deleting test models. Use `dbt run --select _test_staging_routing` syntax to run individual tests.

**Definition of Done**:

- [ ] Schema routing validated for all three layers
- [ ] Date spine row count validated (2922 rows)
- [ ] Test models deleted after validation
- [ ] Validation results documented in PR description
- [ ] PR opened with linked issue
- [ ] CI checks green

## Exit Criteria

This epic is complete when:

- [ ] All stories marked complete
- [ ] All acceptance criteria verified
- [ ] `generate_schema_name` correctly routes staging, intermediate, marts, and seeds
- [ ] `get_date_spine` produces 2922 rows (2019-01-01 to 2026-12-31)
- [ ] Both macros documented in `_macros.yml`
- [ ] `dbt docs generate` includes macro documentation
- [ ] No test models remain in repository after validation
