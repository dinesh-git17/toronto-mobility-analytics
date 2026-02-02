# Snowflake Infrastructure Provisioning

| Field        | Value         |
| ------------ | ------------- |
| Epic ID      | E-201         |
| Phase        | PH-02         |
| Owner        | @dinesh-git17 |
| Status       | Draft         |
| Dependencies | None          |
| Created      | 2026-02-02    |

## Context

This epic establishes the foundational Snowflake infrastructure required for the Toronto Urban Mobility Analytics project. The TORONTO_MOBILITY database serves as the single source of truth for all transit and cycling data transformations. Role-based access control separates ingestion (LOADER_ROLE) from transformation (TRANSFORMER_ROLE) responsibilities per security best practices defined in DESIGN-DOC.md Section 10. The schema hierarchy (RAW, STAGING, INTERMEDIATE, MARTS, SEEDS) implements the medallion architecture that governs all downstream dbt models.

## Scope

### In Scope

- Snowflake Enterprise trial account provisioning
- TORONTO_MOBILITY database creation
- Five schemas: RAW, STAGING, INTERMEDIATE, MARTS, SEEDS
- TRANSFORM_WH warehouse (X-Small, auto-suspend 60s)
- LOADER_ROLE and TRANSFORMER_ROLE custom roles
- Service accounts: LOADER_SVC and TRANSFORMER_SVC
- Complete grant statements for role-schema permissions
- SQL setup scripts in `setup/` directory

### Out of Scope

- Production account configuration
- Multi-region replication
- Network policies or IP whitelisting
- Time Travel configuration beyond defaults
- Data sharing or marketplace listings

## Technical Approach

### Architecture Decisions

- **X-Small warehouse selection**: Per DESIGN-DOC.md Section 10.1, all queries must complete in < 5 seconds on production data (~30M rows); X-Small is sufficient and minimizes credit consumption
- **60-second auto-suspend**: Balances responsiveness with cost efficiency for development workloads
- **Separate roles for load vs. transform**: LOADER_ROLE owns RAW schema exclusively; TRANSFORMER_ROLE has read-only access to RAW and full control of transform schemas; prevents accidental source data corruption

### Integration Points

- GitHub Secrets for credential storage (SNOWFLAKE_ACCOUNT, SNOWFLAKE_PASSWORD, SNOWFLAKE_LOADER_PASSWORD)
- GitHub Actions CI workflows consume service account credentials
- dbt profiles.yml connects using TRANSFORMER_SVC credentials

### Repository Areas

- `setup/snowflake_init.sql` — database, schema, warehouse DDL
- `setup/grants.sql` — role and permission configuration
- `profiles.yml.example` — connection template (no credentials)

### Risks

| Risk                              | Likelihood | Impact | Mitigation                                                               |
| --------------------------------- | ---------- | ------ | ------------------------------------------------------------------------ |
| Trial account expires mid-project | Low        | High   | Complete infrastructure setup within first week; document migration path |
| Incorrect role grants break dbt   | Medium     | Medium | Test grants with `dbt debug` before marking complete                     |
| Credential exposure in repo       | Low        | High   | Never commit profiles.yml; use GitHub Secrets exclusively                |

## Stories

| ID   | Story                                        | Points | Dependencies | Status |
| ---- | -------------------------------------------- | ------ | ------------ | ------ |
| S001 | Provision Snowflake Enterprise trial account | 2      | None         | Draft  |
| S002 | Create TORONTO_MOBILITY database             | 1      | S001         | Draft  |
| S003 | Create schema hierarchy                      | 2      | S002         | Draft  |
| S004 | Configure TRANSFORM_WH warehouse             | 1      | S001         | Draft  |
| S005 | Create custom roles and service accounts     | 3      | S002         | Draft  |
| S006 | Implement role-schema grant statements       | 3      | S003, S005   | Draft  |
| S007 | Validate infrastructure with connection test | 2      | S006         | Draft  |

---

### S001: Provision Snowflake Enterprise trial account

**Description**: Create a new Snowflake Enterprise trial account that provides $400 credits and 30-day access for project development.

**Acceptance Criteria**:

- [ ] Snowflake account created at `https://<account_id>.snowflakecomputing.com`
- [ ] Account edition is Enterprise (verified in ACCOUNTADMIN > Account > Edition)
- [ ] Account region is documented in project notes
- [ ] ACCOUNTADMIN login credentials stored securely outside repository

**Technical Notes**: Use Snowflake free trial signup at <https://signup.snowflake.com/>. Select Enterprise edition and a region geographically close to development location. Document account identifier format (e.g., `xy12345.us-east-1`).

**Definition of Done**:

- [ ] Account accessible via web UI
- [ ] Account identifier documented
- [ ] Trial credit balance confirmed at $400

---

### S002: Create TORONTO_MOBILITY database

**Description**: Execute DDL to create the TORONTO_MOBILITY database that serves as the container for all project schemas and objects.

**Acceptance Criteria**:

- [ ] `CREATE DATABASE TORONTO_MOBILITY;` executes successfully
- [ ] Database visible in Snowflake UI under Databases
- [ ] `SHOW DATABASES LIKE 'TORONTO_MOBILITY';` returns one row
- [ ] DDL script saved to `setup/snowflake_init.sql`

**Technical Notes**: Execute using SYSADMIN role. Database name uses SCREAMING_SNAKE_CASE per Snowflake conventions.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] `setup/snowflake_init.sql` contains database creation DDL
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S003: Create schema hierarchy

**Description**: Create the five schemas (RAW, STAGING, INTERMEDIATE, MARTS, SEEDS) that implement the medallion architecture layers.

**Acceptance Criteria**:

- [ ] `CREATE SCHEMA TORONTO_MOBILITY.RAW;` executes successfully
- [ ] `CREATE SCHEMA TORONTO_MOBILITY.STAGING;` executes successfully
- [ ] `CREATE SCHEMA TORONTO_MOBILITY.INTERMEDIATE;` executes successfully
- [ ] `CREATE SCHEMA TORONTO_MOBILITY.MARTS;` executes successfully
- [ ] `CREATE SCHEMA TORONTO_MOBILITY.SEEDS;` executes successfully
- [ ] `SHOW SCHEMAS IN DATABASE TORONTO_MOBILITY;` returns exactly 5 user schemas plus INFORMATION_SCHEMA and PUBLIC
- [ ] DDL appended to `setup/snowflake_init.sql`

**Technical Notes**: Execute using SYSADMIN role. Schema names use SCREAMING_SNAKE_CASE. INTERMEDIATE schema will contain no persistent objects (ephemeral models compile as CTEs) but must exist for dbt schema routing.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] `setup/snowflake_init.sql` contains all schema DDL
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S004: Configure TRANSFORM_WH warehouse

**Description**: Create the TRANSFORM_WH warehouse with X-Small size and 60-second auto-suspend to balance performance with cost efficiency.

**Acceptance Criteria**:

- [ ] `CREATE WAREHOUSE TRANSFORM_WH WITH WAREHOUSE_SIZE = 'XSMALL' AUTO_SUSPEND = 60 AUTO_RESUME = TRUE INITIALLY_SUSPENDED = TRUE;` executes successfully
- [ ] Warehouse visible in Snowflake UI under Warehouses
- [ ] `SHOW WAREHOUSES LIKE 'TRANSFORM_WH';` returns one row with size XSMALL
- [ ] Auto-suspend value confirmed as 60 seconds
- [ ] DDL appended to `setup/snowflake_init.sql`

**Technical Notes**: INITIALLY_SUSPENDED = TRUE prevents unnecessary credit consumption immediately after creation. AUTO_RESUME = TRUE ensures warehouse activates automatically on first query.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] `setup/snowflake_init.sql` contains warehouse DDL
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S005: Create custom roles and service accounts

**Description**: Create LOADER_ROLE, TRANSFORMER_ROLE, and their corresponding service accounts (LOADER_SVC, TRANSFORMER_SVC) following the security model in DESIGN-DOC.md Section 10.

**Acceptance Criteria**:

- [ ] `CREATE ROLE LOADER_ROLE;` executes successfully under SECURITYADMIN
- [ ] `CREATE ROLE TRANSFORMER_ROLE;` executes successfully under SECURITYADMIN
- [ ] Both roles granted to SYSADMIN for management hierarchy
- [ ] `CREATE USER LOADER_SVC` with DEFAULT_ROLE = LOADER_ROLE
- [ ] `CREATE USER TRANSFORMER_SVC` with DEFAULT_ROLE = TRANSFORMER_ROLE
- [ ] `SHOW ROLES LIKE '%_ROLE';` returns LOADER_ROLE and TRANSFORMER_ROLE
- [ ] `SHOW USERS LIKE '%_SVC';` returns LOADER_SVC and TRANSFORMER_SVC
- [ ] DDL saved to `setup/grants.sql`

**Technical Notes**: Use SECURITYADMIN for role/user creation. Service account passwords should be generated securely (minimum 16 characters, alphanumeric with special characters). Passwords are NOT committed to repository; placeholder `<GENERATED_PASSWORD>` used in script.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] `setup/grants.sql` contains role and user DDL
- [ ] Passwords stored in secure location outside repository
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S006: Implement role-schema grant statements

**Description**: Configure complete grant hierarchy ensuring LOADER_ROLE owns RAW schema and TRANSFORMER_ROLE owns transform schemas with appropriate cross-schema read permissions.

**Acceptance Criteria**:

- [ ] LOADER_ROLE has USAGE on TRANSFORM_WH
- [ ] TRANSFORMER_ROLE has USAGE on TRANSFORM_WH
- [ ] LOADER_ROLE has ALL PRIVILEGES on RAW schema and all current/future tables
- [ ] TRANSFORMER_ROLE has USAGE on RAW schema and SELECT on all current/future tables
- [ ] TRANSFORMER_ROLE has ALL PRIVILEGES on STAGING, INTERMEDIATE, MARTS, SEEDS schemas
- [ ] TRANSFORMER_ROLE has ALL PRIVILEGES on future tables/views in transform schemas
- [ ] Grant statements appended to `setup/grants.sql`
- [ ] Running `setup/grants.sql` is idempotent (can execute multiple times without error)

**Technical Notes**: Use `GRANT ... ON FUTURE TABLES/VIEWS` for forward compatibility. Test grants by connecting as each service account and verifying access. Reference DESIGN-DOC.md Section 10.2 for exact grant statements.

**Definition of Done**:

- [ ] Code committed to feature branch
- [ ] `setup/grants.sql` contains all grant statements
- [ ] Idempotency verified by executing script twice
- [ ] PR opened with linked issue
- [ ] CI checks green

---

### S007: Validate infrastructure with connection test

**Description**: Verify complete infrastructure setup by connecting as TRANSFORMER_SVC and confirming access to all required objects.

**Acceptance Criteria**:

- [ ] SnowSQL or Snowflake UI connection succeeds as TRANSFORMER_SVC
- [ ] `SELECT CURRENT_ROLE();` returns TRANSFORMER_ROLE
- [ ] `SELECT CURRENT_WAREHOUSE();` returns TRANSFORM_WH
- [ ] `USE DATABASE TORONTO_MOBILITY;` executes successfully
- [ ] `USE SCHEMA STAGING;` executes successfully
- [ ] `CREATE TABLE STAGING.TEST_TABLE (id INT);` executes successfully
- [ ] `DROP TABLE STAGING.TEST_TABLE;` executes successfully
- [ ] `USE SCHEMA RAW;` executes successfully
- [ ] `CREATE TABLE RAW.TEST_TABLE (id INT);` fails with insufficient privileges (expected)
- [ ] Validation script created at `setup/validate_infrastructure.sql`

**Technical Notes**: This story validates the complete role-based access control model. TRANSFORMER_ROLE should have full control of transform schemas but only read access to RAW.

**Definition of Done**:

- [ ] Validation script committed to feature branch
- [ ] All acceptance criteria verified manually
- [ ] Results documented in PR description
- [ ] PR opened with linked issue
- [ ] CI checks green

## Exit Criteria

This epic is complete when:

- [ ] All stories marked complete
- [ ] All acceptance criteria verified
- [ ] TRANSFORMER_SVC can connect and access transform schemas
- [ ] TRANSFORMER_SVC cannot modify RAW schema (read-only confirmed)
- [ ] `setup/snowflake_init.sql` and `setup/grants.sql` are committed and idempotent
- [ ] Service account credentials stored in GitHub Secrets
