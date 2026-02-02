-- =============================================================================
-- TORONTO MOBILITY ANALYTICS: SNOWFLAKE INFRASTRUCTURE INITIALIZATION
-- =============================================================================
-- Epic: E-201 Snowflake Infrastructure Provisioning
-- Execution Context: SYSADMIN role required
-- Idempotent: Yes (CREATE OR REPLACE / IF NOT EXISTS patterns)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- PRE-EXECUTION: Set role context for object creation
-- SYSADMIN owns infrastructure objects per Snowflake RBAC best practices
-- -----------------------------------------------------------------------------
USE ROLE SYSADMIN;

-- -----------------------------------------------------------------------------
-- DATABASE: TORONTO_MOBILITY
-- Central container for all project schemas and objects
-- -----------------------------------------------------------------------------
CREATE DATABASE IF NOT EXISTS TORONTO_MOBILITY
    COMMENT = 'Toronto Urban Mobility Analytics - Transit and cycling data warehouse';

-- -----------------------------------------------------------------------------
-- SCHEMAS: Medallion Architecture Implementation
-- RAW: Landing zone for ingested source data (owned by LOADER_ROLE)
-- STAGING: Renamed/typed views over RAW (owned by TRANSFORMER_ROLE)
-- INTERMEDIATE: Ephemeral CTEs - schema exists for dbt routing only
-- MARTS: Analytics-ready fact and dimension tables
-- SEEDS: Reference data loaded via dbt seed
-- -----------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS TORONTO_MOBILITY.RAW
    COMMENT = 'Landing zone for raw ingested data from Open Data Portal sources';

CREATE SCHEMA IF NOT EXISTS TORONTO_MOBILITY.STAGING
    COMMENT = 'Staging views with column renaming, type casting, and basic cleansing';

CREATE SCHEMA IF NOT EXISTS TORONTO_MOBILITY.INTERMEDIATE
    COMMENT = 'Intermediate layer for ephemeral models - no persistent objects';

CREATE SCHEMA IF NOT EXISTS TORONTO_MOBILITY.MARTS
    COMMENT = 'Analytics-ready fact and dimension tables for consumption';

CREATE SCHEMA IF NOT EXISTS TORONTO_MOBILITY.SEEDS
    COMMENT = 'Reference data tables loaded via dbt seed (delay codes, station mappings)';

-- -----------------------------------------------------------------------------
-- WAREHOUSE: TRANSFORM_WH
-- X-Small sizing per DESIGN-DOC Section 10.1 performance requirements
-- 60-second auto-suspend balances cost with responsiveness
-- Initially suspended prevents unnecessary credit consumption at creation
-- -----------------------------------------------------------------------------
CREATE WAREHOUSE IF NOT EXISTS TRANSFORM_WH
    WITH
        WAREHOUSE_SIZE = 'XSMALL'
        AUTO_SUSPEND = 60
        AUTO_RESUME = TRUE
        INITIALLY_SUSPENDED = TRUE
        COMMENT = 'Transformation warehouse for dbt builds and analytics queries';

-- -----------------------------------------------------------------------------
-- VERIFICATION: Confirm object creation
-- Execute these queries to validate successful infrastructure deployment
-- -----------------------------------------------------------------------------
SHOW DATABASES LIKE 'TORONTO_MOBILITY';
SHOW SCHEMAS IN DATABASE TORONTO_MOBILITY;
SHOW WAREHOUSES LIKE 'TRANSFORM_WH';
