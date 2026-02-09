-- =============================================================================
-- TORONTO MOBILITY ANALYTICS: INGESTION STAGE & RAW TABLE CREATION
-- =============================================================================
-- Epic: E-303 Snowflake Loading & Pipeline Orchestration (Story S001)
-- Execution Context: SYSADMIN role required for object creation
-- Idempotent: Yes (IF NOT EXISTS / OR REPLACE patterns)
-- =============================================================================

USE ROLE SYSADMIN;
USE DATABASE TORONTO_MOBILITY;
USE SCHEMA RAW;

-- =============================================================================
-- SECTION 1: INTERNAL NAMED STAGE
-- =============================================================================
-- File format embedded in stage definition per E-303 S001:
--   CSV with quoted fields, header skip, NULL handling, UTF-8 encoding
-- =============================================================================

CREATE STAGE IF NOT EXISTS TORONTO_MOBILITY.RAW.INGESTION_STAGE
    FILE_FORMAT = (
        TYPE = 'CSV'
        FIELD_DELIMITER = ','
        RECORD_DELIMITER = '\n'
        FIELD_OPTIONALLY_ENCLOSED_BY = '"'
        SKIP_HEADER = 1
        NULL_IF = ('', 'NULL', 'null')
        COMPRESSION = 'AUTO'
        ENCODING = 'UTF8'
    )
    COMMENT = 'Internal stage for CSV file ingestion into RAW schema tables';

-- =============================================================================
-- SECTION 2: LOADER_ROLE GRANTS ON STAGE
-- =============================================================================

GRANT USAGE ON STAGE TORONTO_MOBILITY.RAW.INGESTION_STAGE TO ROLE LOADER_ROLE;

-- =============================================================================
-- SECTION 3: RAW SCHEMA TABLE DEFINITIONS
-- =============================================================================
-- All columns are VARCHAR to preserve source data integrity.
-- Type casting is deferred to the STAGING layer (dbt views).
-- Column names use UPPER_SNAKE_CASE per Snowflake conventions.
-- =============================================================================

-- TTC Subway Delays (DESIGN-DOC Section 4.3.1)
-- Source CSV columns: Date, Time, Day, Station, Code, Min Delay, Min Gap, Bound, Line
CREATE TABLE IF NOT EXISTS TORONTO_MOBILITY.RAW.TTC_SUBWAY_DELAYS (
    DATE        VARCHAR,
    TIME        VARCHAR,
    DAY         VARCHAR,
    STATION     VARCHAR,
    CODE        VARCHAR,
    MIN_DELAY   VARCHAR,
    MIN_GAP     VARCHAR,
    BOUND       VARCHAR,
    LINE        VARCHAR
)
COMMENT = 'TTC subway delay incidents from Toronto Open Data Portal (2019-present)';

-- TTC Bus Delays (DESIGN-DOC Section 4.3.1)
-- Source CSV columns: Date, Route, Time, Day, Location, Incident, Min Delay, Min Gap, Direction
-- Column INCIDENT renamed to DELAY_CODE for cross-mode consistency
CREATE TABLE IF NOT EXISTS TORONTO_MOBILITY.RAW.TTC_BUS_DELAYS (
    DATE        VARCHAR,
    ROUTE       VARCHAR,
    TIME        VARCHAR,
    DAY         VARCHAR,
    LOCATION    VARCHAR,
    DELAY_CODE  VARCHAR,
    MIN_DELAY   VARCHAR,
    MIN_GAP     VARCHAR,
    DIRECTION   VARCHAR
)
COMMENT = 'TTC bus delay incidents from Toronto Open Data Portal (2020-present)';

-- TTC Streetcar Delays (DESIGN-DOC Section 4.3.1)
-- Source CSV columns: Date, Line, Time, Day, Location, Incident, Min Delay, Min Gap, Bound
-- Columns renamed for cross-mode consistency: Line->ROUTE, Incident->DELAY_CODE, Bound->DIRECTION
CREATE TABLE IF NOT EXISTS TORONTO_MOBILITY.RAW.TTC_STREETCAR_DELAYS (
    DATE        VARCHAR,
    ROUTE       VARCHAR,
    TIME        VARCHAR,
    DAY         VARCHAR,
    LOCATION    VARCHAR,
    DELAY_CODE  VARCHAR,
    MIN_DELAY   VARCHAR,
    MIN_GAP     VARCHAR,
    DIRECTION   VARCHAR
)
COMMENT = 'TTC streetcar delay incidents from Toronto Open Data Portal (2020-present)';

-- Bike Share Trips (DESIGN-DOC Section 4.3.2)
-- Source CSV columns: Trip Id, Trip  Duration, Start Station Id, Start Time,
--   Start Station Name, End Station Id, End Time, End Station Name, Bike Id, User Type
CREATE TABLE IF NOT EXISTS TORONTO_MOBILITY.RAW.BIKE_SHARE_TRIPS (
    TRIP_ID             VARCHAR,
    TRIP_DURATION       VARCHAR,
    START_STATION_ID    VARCHAR,
    START_TIME          VARCHAR,
    START_STATION_NAME  VARCHAR,
    END_STATION_ID      VARCHAR,
    END_TIME            VARCHAR,
    END_STATION_NAME    VARCHAR,
    BIKE_ID             VARCHAR,
    USER_TYPE           VARCHAR
)
COMMENT = 'Bike Share Toronto trip records from Toronto Open Data Portal (2019-present)';

-- Weather Daily (DESIGN-DOC Section 4.3.3)
-- Environment Canada Historical Climate Data, Station ID 51459 (Toronto Pearson)
-- All 31 standard daily weather columns preserved for completeness
CREATE TABLE IF NOT EXISTS TORONTO_MOBILITY.RAW.WEATHER_DAILY (
    LONGITUDE                   VARCHAR,
    LATITUDE                    VARCHAR,
    STATION_NAME                VARCHAR,
    CLIMATE_ID                  VARCHAR,
    DATE_TIME                   VARCHAR,
    YEAR                        VARCHAR,
    MONTH                       VARCHAR,
    DAY                         VARCHAR,
    DATA_QUALITY                VARCHAR,
    MAX_TEMP_C                  VARCHAR,
    MAX_TEMP_FLAG               VARCHAR,
    MIN_TEMP_C                  VARCHAR,
    MIN_TEMP_FLAG               VARCHAR,
    MEAN_TEMP_C                 VARCHAR,
    MEAN_TEMP_FLAG              VARCHAR,
    HEAT_DEG_DAYS_C             VARCHAR,
    HEAT_DEG_DAYS_FLAG          VARCHAR,
    COOL_DEG_DAYS_C             VARCHAR,
    COOL_DEG_DAYS_FLAG          VARCHAR,
    TOTAL_RAIN_MM               VARCHAR,
    TOTAL_RAIN_FLAG             VARCHAR,
    TOTAL_SNOW_CM               VARCHAR,
    TOTAL_SNOW_FLAG             VARCHAR,
    TOTAL_PRECIP_MM             VARCHAR,
    TOTAL_PRECIP_FLAG           VARCHAR,
    SNOW_ON_GRND_CM             VARCHAR,
    SNOW_ON_GRND_FLAG           VARCHAR,
    DIR_OF_MAX_GUST_10S_DEG     VARCHAR,
    DIR_OF_MAX_GUST_FLAG        VARCHAR,
    SPD_OF_MAX_GUST_KMH        VARCHAR,
    SPD_OF_MAX_GUST_FLAG        VARCHAR
)
COMMENT = 'Environment Canada daily weather observations for Toronto Pearson (2019-present)';

-- =============================================================================
-- SECTION 4: VERIFICATION QUERIES
-- =============================================================================
-- Execute as LOADER_ROLE to confirm permissions are correctly configured
-- =============================================================================

USE ROLE LOADER_ROLE;

-- Verify stage access
LIST @TORONTO_MOBILITY.RAW.INGESTION_STAGE;

-- Verify all five RAW tables exist
SELECT TABLE_NAME
FROM TORONTO_MOBILITY.INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA = 'RAW'
    AND TABLE_NAME IN (
        'TTC_SUBWAY_DELAYS',
        'TTC_BUS_DELAYS',
        'TTC_STREETCAR_DELAYS',
        'BIKE_SHARE_TRIPS',
        'WEATHER_DAILY'
    )
ORDER BY TABLE_NAME;

-- Verify PUT access: upload a 1-row test CSV, then remove it
-- Execute the following commands manually to confirm PUT/REMOVE permissions:
--
--   PUT file:///tmp/test_stage_access.csv @TORONTO_MOBILITY.RAW.INGESTION_STAGE/test/;
--   REMOVE @TORONTO_MOBILITY.RAW.INGESTION_STAGE/test/test_stage_access.csv;
--
-- Both commands must succeed without permission errors.
