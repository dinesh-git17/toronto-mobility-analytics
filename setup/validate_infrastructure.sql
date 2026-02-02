-- =============================================================================
-- TORONTO MOBILITY ANALYTICS: INFRASTRUCTURE VALIDATION SCRIPT
-- =============================================================================
-- Epic: E-201 Snowflake Infrastructure Provisioning (Story S007)
-- Execution Context: Run as TRANSFORMER_SVC to validate RBAC configuration
-- Purpose: Verify complete infrastructure setup and role-based access control
-- =============================================================================

-- =============================================================================
-- SECTION 1: SESSION CONTEXT VALIDATION
-- =============================================================================
-- Confirms the connection is using expected role and warehouse
-- Expected results:
--   CURRENT_ROLE() = 'TRANSFORMER_ROLE'
--   CURRENT_WAREHOUSE() = 'TRANSFORM_WH'
-- =============================================================================

SELECT
    CURRENT_ROLE() AS current_role,
    CURRENT_WAREHOUSE() AS current_warehouse,
    CURRENT_USER() AS current_user,
    CURRENT_DATABASE() AS current_database,
    CASE
        WHEN CURRENT_ROLE() = 'TRANSFORMER_ROLE' THEN 'PASS'
        ELSE 'FAIL: Expected TRANSFORMER_ROLE'
    END AS role_check,
    CASE
        WHEN CURRENT_WAREHOUSE() = 'TRANSFORM_WH' THEN 'PASS'
        ELSE 'FAIL: Expected TRANSFORM_WH'
    END AS warehouse_check;

-- =============================================================================
-- SECTION 2: DATABASE ACCESS VALIDATION
-- =============================================================================
-- Confirms TRANSFORMER_ROLE can access the project database
-- =============================================================================

USE DATABASE TORONTO_MOBILITY;

SELECT 'DATABASE_ACCESS' AS test_name, 'PASS' AS result;

-- =============================================================================
-- SECTION 3: TRANSFORM SCHEMA WRITE ACCESS VALIDATION
-- =============================================================================
-- Confirms TRANSFORMER_ROLE has CREATE TABLE privileges in transform schemas
-- Creates and drops test objects to verify full write access
-- =============================================================================

-- STAGING schema write test
USE SCHEMA STAGING;
CREATE TABLE IF NOT EXISTS STAGING._VALIDATION_TEST (id INT);
DROP TABLE IF EXISTS STAGING._VALIDATION_TEST;
SELECT 'STAGING_WRITE_ACCESS' AS test_name, 'PASS' AS result;

-- INTERMEDIATE schema write test
USE SCHEMA INTERMEDIATE;
CREATE TABLE IF NOT EXISTS INTERMEDIATE._VALIDATION_TEST (id INT);
DROP TABLE IF EXISTS INTERMEDIATE._VALIDATION_TEST;
SELECT 'INTERMEDIATE_WRITE_ACCESS' AS test_name, 'PASS' AS result;

-- MARTS schema write test
USE SCHEMA MARTS;
CREATE TABLE IF NOT EXISTS MARTS._VALIDATION_TEST (id INT);
DROP TABLE IF EXISTS MARTS._VALIDATION_TEST;
SELECT 'MARTS_WRITE_ACCESS' AS test_name, 'PASS' AS result;

-- SEEDS schema write test
USE SCHEMA SEEDS;
CREATE TABLE IF NOT EXISTS SEEDS._VALIDATION_TEST (id INT);
DROP TABLE IF EXISTS SEEDS._VALIDATION_TEST;
SELECT 'SEEDS_WRITE_ACCESS' AS test_name, 'PASS' AS result;

-- =============================================================================
-- SECTION 4: RAW SCHEMA READ ACCESS VALIDATION
-- =============================================================================
-- Confirms TRANSFORMER_ROLE has read access to RAW schema
-- =============================================================================

USE SCHEMA RAW;
SELECT 'RAW_SCHEMA_ACCESS' AS test_name, 'PASS' AS result;

-- =============================================================================
-- SECTION 5: RAW SCHEMA WRITE RESTRICTION VALIDATION
-- =============================================================================
-- CRITICAL: This test MUST FAIL with insufficient privileges
-- TRANSFORMER_ROLE should NOT have write access to RAW schema
-- This enforces separation between ingestion and transformation layers
--
-- MANUAL VERIFICATION REQUIRED:
-- Execute the following command and confirm it returns an error:
--
--     CREATE TABLE RAW._VALIDATION_TEST (id INT);
--
-- Expected error: "Insufficient privileges to operate on schema 'RAW'"
-- If the command succeeds, RBAC configuration is INCORRECT
-- =============================================================================

SELECT
    'RAW_WRITE_RESTRICTION' AS test_name,
    'MANUAL_VERIFICATION_REQUIRED' AS result,
    'Execute: CREATE TABLE RAW._VALIDATION_TEST (id INT); - must fail' AS instruction;

-- =============================================================================
-- SECTION 6: SCHEMA INVENTORY VALIDATION
-- =============================================================================
-- Confirms all required schemas exist in the database
-- =============================================================================

SELECT
    SCHEMA_NAME,
    CASE
        WHEN SCHEMA_NAME IN ('RAW', 'STAGING', 'INTERMEDIATE', 'MARTS', 'SEEDS')
        THEN 'REQUIRED'
        ELSE 'SYSTEM'
    END AS schema_type
FROM TORONTO_MOBILITY.INFORMATION_SCHEMA.SCHEMATA
ORDER BY
    CASE SCHEMA_NAME
        WHEN 'RAW' THEN 1
        WHEN 'STAGING' THEN 2
        WHEN 'INTERMEDIATE' THEN 3
        WHEN 'MARTS' THEN 4
        WHEN 'SEEDS' THEN 5
        ELSE 6
    END;

-- =============================================================================
-- SECTION 7: WAREHOUSE CONFIGURATION VALIDATION
-- =============================================================================
-- Confirms warehouse settings match DESIGN-DOC requirements
-- =============================================================================

SHOW WAREHOUSES LIKE 'TRANSFORM_WH';

SELECT
    'WAREHOUSE_CONFIG' AS test_name,
    'Verify: SIZE=XSMALL, AUTO_SUSPEND=60, AUTO_RESUME=TRUE' AS expected_config;

-- =============================================================================
-- VALIDATION SUMMARY
-- =============================================================================
-- All tests in Sections 1-4, 6-7 should return PASS
-- Section 5 requires manual verification that RAW write fails
-- Infrastructure is validated when:
--   - All automated tests pass
--   - RAW write attempt fails with privilege error
-- =============================================================================
