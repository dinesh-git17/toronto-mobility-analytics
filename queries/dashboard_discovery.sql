-- =============================================================================
-- TORONTO MOBILITY DASHBOARD — DISCOVERY QUERIES
-- =============================================================================
-- Run against Snowflake MARTS schema to extract insights for dashboard design.
-- Execute all queries and paste results back for analysis.
-- =============================================================================

USE DATABASE TORONTO_MOBILITY;
USE WAREHOUSE TRANSFORM_WH;

-- =============================================================================
-- TTC DELAYS
-- =============================================================================
-- Q1: Top 10 worst stations by total delay minutes
select
    s.station_name,
    count(*) as delay_count,
    sum(d.delay_minutes) as total_delay_minutes,
    round(avg(d.delay_minutes), 1) as avg_delay_minutes
from marts.fct_transit_delays d
join marts.dim_station s on d.station_key = s.station_key
where d.transit_mode = 'subway'
group by s.station_name
order by total_delay_minutes desc
limit 10
;

-- Q2: Delay categories ranked by frequency
select
    c.delay_category,
    count(*) as incident_count,
    sum(d.delay_minutes) as total_minutes,
    round(100.0 * count(*) / sum(count(*)) over (), 1) as pct_of_total
from marts.fct_transit_delays d
join marts.dim_ttc_delay_codes c on d.delay_code_key = c.delay_code_key
group by c.delay_category
order by incident_count desc
;

-- Q3: Year-over-year delay trend
select
    dt.year,
    count(*) as delay_count,
    sum(d.delay_minutes) as total_delay_minutes,
    round(avg(d.delay_minutes), 1) as avg_delay_minutes
from marts.fct_transit_delays d
join marts.dim_date dt on d.date_key = dt.date_key
group by dt.year
order by dt.year
;

-- Q4: Delays by hour of day
select
    extract(hour from d.incident_timestamp) as hour_of_day,
    count(*) as delay_count,
    sum(d.delay_minutes) as total_minutes
from marts.fct_transit_delays d
group by hour_of_day
order by hour_of_day
;

-- Q5: Delays by day of week
select
    dt.day_of_week,
    dt.day_of_week_num,
    count(*) as delay_count,
    sum(d.delay_minutes) as total_minutes
from marts.fct_transit_delays d
join marts.dim_date dt on d.date_key = dt.date_key
group by dt.day_of_week, dt.day_of_week_num
order by dt.day_of_week_num
;

-- Q6: Transit mode breakdown
select
    transit_mode,
    count(*) as delay_count,
    sum(delay_minutes) as total_minutes,
    round(avg(delay_minutes), 1) as avg_minutes
from marts.fct_transit_delays
group by transit_mode
order by delay_count desc
;

-- =============================================================================
-- BIKE SHARE
-- =============================================================================
-- Q7: Trips by year (growth curve)
select
    dt.year,
    count(*) as total_trips,
    round(avg(b.duration_seconds) / 60.0, 1) as avg_duration_minutes
from marts.fct_bike_trips b
join marts.dim_date dt on b.date_key = dt.date_key
group by dt.year
order by dt.year
;

-- Q8: Member vs casual split by year
select dt.year, b.user_type, count(*) as trips
from marts.fct_bike_trips b
join marts.dim_date dt on b.date_key = dt.date_key
group by dt.year, b.user_type
order by dt.year, b.user_type
;

-- Q9: Top 10 busiest start stations
select s.station_name, count(*) as trip_count
from marts.fct_bike_trips b
join marts.dim_station s on b.start_station_key = s.station_key
group by s.station_name
order by trip_count desc
limit 10
;

-- Q10: Monthly seasonality pattern (all years combined)
select
    dt.month_num,
    dt.month_name,
    count(*) as total_trips,
    round(avg(b.duration_seconds) / 60.0, 1) as avg_duration_minutes
from marts.fct_bike_trips b
join marts.dim_date dt on b.date_key = dt.date_key
group by dt.month_num, dt.month_name
order by dt.month_num
;

-- =============================================================================
-- WEATHER & CROSS-MODAL
-- =============================================================================
-- Q11: Bike trips by weather condition
select
    w.weather_condition,
    count(*) as trip_count,
    round(avg(b.duration_seconds) / 60.0, 1) as avg_duration_minutes
from marts.fct_bike_trips b
join marts.dim_weather w on b.date_key = w.date_key
group by w.weather_condition
order by trip_count desc
;

-- Q12: Delays by weather condition
select
    w.weather_condition,
    count(*) as delay_count,
    sum(d.delay_minutes) as total_minutes,
    round(avg(d.delay_minutes), 1) as avg_minutes
from marts.fct_transit_delays d
join marts.dim_weather w on d.date_key = w.date_key
group by w.weather_condition
order by delay_count desc
;

-- Q13: Daily correlation dataset (sample for scatter plot)
select
    m.date_key,
    m.total_delay_incidents,
    m.total_delay_minutes,
    m.total_bike_trips,
    w.mean_temp_c,
    w.total_precip_mm
from marts.fct_daily_mobility m
join marts.dim_weather w on m.date_key = w.date_key
order by m.date_key
limit 100
;

-- =============================================================================
-- HERO STATS
-- =============================================================================
-- Q14: TTC hero stats
select
    count(*) as total_delay_incidents,
    sum(delay_minutes) as total_delay_minutes,
    round(sum(delay_minutes) / 60.0, 0) as total_delay_hours,
    min(date_key) as min_date,
    max(date_key) as max_date
from marts.fct_transit_delays
;

-- Q15: Bike Share hero stats
select
    count(*) as total_trips,
    round(sum(duration_seconds) / 3600.0, 0) as total_trip_hours,
    round(avg(duration_seconds) / 60.0, 1) as avg_trip_minutes
from marts.fct_bike_trips
;

-- =============================================================================
-- STATION GEOGRAPHY CHECK
-- =============================================================================
-- Q16: Verify lat/long availability for map visualizations
select
    station_type,
    count(*) as station_count,
    sum(
        case when latitude is not null and longitude is not null then 1 else 0 end
    ) as has_coords,
    round(
        100.0 * sum(
            case when latitude is not null and longitude is not null then 1 else 0 end
        )
        / count(*),
        1
    ) as pct_with_coords
from marts.dim_station
group by station_type
;
