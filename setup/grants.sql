-- =============================================================================
-- TORONTO MOBILITY ANALYTICS: ROLE-BASED ACCESS CONTROL CONFIGURATION
-- =============================================================================
-- Epic: E-201 Snowflake Infrastructure Provisioning
-- Execution Context: SECURITYADMIN for roles/users, SYSADMIN for grants
-- Idempotent: Yes (IF NOT EXISTS patterns, grants are additive)
-- Prerequisite: snowflake_init.sql must be executed first
-- =============================================================================

-- =============================================================================
-- SECTION 1: ROLE CREATION
-- =============================================================================
-- LOADER_ROLE: Owns RAW schema, performs data ingestion via COPY INTO
-- TRANSFORMER_ROLE: Owns transform schemas, executes dbt builds
-- Both roles granted to SYSADMIN for administrative oversight
-- =============================================================================
USE ROLE SECURITYADMIN;

CREATE ROLE IF NOT EXISTS LOADER_ROLE
    COMMENT = 'Data ingestion role - owns RAW schema objects';

CREATE ROLE IF NOT EXISTS TRANSFORMER_ROLE
    COMMENT = 'Transformation role - owns STAGING/INTERMEDIATE/MARTS/SEEDS objects';

-- Grant roles to SYSADMIN for management hierarchy
-- Enables SYSADMIN to manage objects created by these roles
GRANT ROLE LOADER_ROLE TO ROLE SYSADMIN;
GRANT ROLE TRANSFORMER_ROLE TO ROLE SYSADMIN;

-- =============================================================================
-- SECTION 2: WAREHOUSE GRANTS
-- =============================================================================
-- Both roles require warehouse access for query execution
-- =============================================================================
USE ROLE SYSADMIN;

GRANT USAGE ON WAREHOUSE TRANSFORM_WH TO ROLE LOADER_ROLE;
GRANT USAGE ON WAREHOUSE TRANSFORM_WH TO ROLE TRANSFORMER_ROLE;

-- =============================================================================
-- SECTION 3: DATABASE GRANTS
-- =============================================================================
-- Both roles require database-level USAGE to access schemas
-- =============================================================================
GRANT USAGE ON DATABASE TORONTO_MOBILITY TO ROLE LOADER_ROLE;
GRANT USAGE ON DATABASE TORONTO_MOBILITY TO ROLE TRANSFORMER_ROLE;

-- =============================================================================
-- SECTION 4: LOADER_ROLE SCHEMA GRANTS
-- =============================================================================
-- LOADER_ROLE has full control of RAW schema for data ingestion
-- Includes current and future table privileges for COPY INTO operations
-- =============================================================================
GRANT ALL PRIVILEGES ON SCHEMA TORONTO_MOBILITY.RAW TO ROLE LOADER_ROLE;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA TORONTO_MOBILITY.RAW TO ROLE LOADER_ROLE;
GRANT ALL PRIVILEGES ON FUTURE TABLES IN SCHEMA TORONTO_MOBILITY.RAW TO ROLE LOADER_ROLE;

-- =============================================================================
-- SECTION 5: TRANSFORMER_ROLE SCHEMA GRANTS
-- =============================================================================
-- RAW schema: Read-only access for source data consumption
-- Transform schemas: Full control for dbt model creation
-- =============================================================================

-- RAW schema: Read-only (prevents accidental source data corruption)
GRANT USAGE ON SCHEMA TORONTO_MOBILITY.RAW TO ROLE TRANSFORMER_ROLE;
GRANT SELECT ON ALL TABLES IN SCHEMA TORONTO_MOBILITY.RAW TO ROLE TRANSFORMER_ROLE;
GRANT SELECT ON FUTURE TABLES IN SCHEMA TORONTO_MOBILITY.RAW TO ROLE TRANSFORMER_ROLE;

-- STAGING schema: Full control for view creation
GRANT ALL PRIVILEGES ON SCHEMA TORONTO_MOBILITY.STAGING TO ROLE TRANSFORMER_ROLE;
GRANT ALL PRIVILEGES ON FUTURE TABLES IN SCHEMA TORONTO_MOBILITY.STAGING TO ROLE TRANSFORMER_ROLE;
GRANT ALL PRIVILEGES ON FUTURE VIEWS IN SCHEMA TORONTO_MOBILITY.STAGING TO ROLE TRANSFORMER_ROLE;

-- INTERMEDIATE schema: Full control (ephemeral models compile as CTEs, schema exists for routing)
GRANT ALL PRIVILEGES ON SCHEMA TORONTO_MOBILITY.INTERMEDIATE TO ROLE TRANSFORMER_ROLE;

-- MARTS schema: Full control for fact/dimension table creation
GRANT ALL PRIVILEGES ON SCHEMA TORONTO_MOBILITY.MARTS TO ROLE TRANSFORMER_ROLE;
GRANT ALL PRIVILEGES ON FUTURE TABLES IN SCHEMA TORONTO_MOBILITY.MARTS TO ROLE TRANSFORMER_ROLE;

-- SEEDS schema: Full control for dbt seed operations
GRANT ALL PRIVILEGES ON SCHEMA TORONTO_MOBILITY.SEEDS TO ROLE TRANSFORMER_ROLE;
GRANT ALL PRIVILEGES ON FUTURE TABLES IN SCHEMA TORONTO_MOBILITY.SEEDS TO ROLE TRANSFORMER_ROLE;

-- =============================================================================
-- SECTION 6: SERVICE ACCOUNT CREATION
-- =============================================================================
-- Service accounts for automated pipelines (CI/CD, ingestion scripts)
-- Passwords must be replaced with secure generated values before execution
-- Store actual passwords in GitHub Secrets, never in repository
-- =============================================================================
USE ROLE SECURITYADMIN;

CREATE USER IF NOT EXISTS LOADER_SVC
    PASSWORD = '<GENERATED_PASSWORD>'
    DEFAULT_ROLE = LOADER_ROLE
    DEFAULT_WAREHOUSE = TRANSFORM_WH
    MUST_CHANGE_PASSWORD = FALSE
    COMMENT = 'Service account for data ingestion pipelines';

CREATE USER IF NOT EXISTS TRANSFORMER_SVC
    PASSWORD = '<GENERATED_PASSWORD>'
    DEFAULT_ROLE = TRANSFORMER_ROLE
    DEFAULT_WAREHOUSE = TRANSFORM_WH
    MUST_CHANGE_PASSWORD = FALSE
    COMMENT = 'Service account for dbt transformations and CI/CD';

-- Grant roles to service accounts
GRANT ROLE LOADER_ROLE TO USER LOADER_SVC;
GRANT ROLE TRANSFORMER_ROLE TO USER TRANSFORMER_SVC;

-- =============================================================================
-- VERIFICATION: Confirm role and grant configuration
-- =============================================================================
SHOW ROLES LIKE '%_ROLE';
SHOW USERS LIKE '%_SVC';
SHOW GRANTS TO ROLE LOADER_ROLE;
SHOW GRANTS TO ROLE TRANSFORMER_ROLE;
