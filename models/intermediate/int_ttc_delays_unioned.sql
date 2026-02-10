with
    subway as (
        select
            delay_sk,
            delay_date,
            delay_time,
            incident_timestamp,
            day_of_week,
            transit_mode,
            line_code,
            cast(null as varchar) as route,
            raw_station_name,
            cast(null as varchar) as location,
            delay_code,
            delay_minutes,
            gap_minutes,
            direction
        from {{ ref('stg_ttc_subway_delays') }}
    ),

    bus as (
        select
            delay_sk,
            delay_date,
            delay_time,
            incident_timestamp,
            day_of_week,
            transit_mode,
            cast(null as varchar) as line_code,
            route,
            cast(null as varchar) as raw_station_name,
            location,
            delay_code,
            delay_minutes,
            gap_minutes,
            direction
        from {{ ref('stg_ttc_bus_delays') }}
    ),

    streetcar as (
        select
            delay_sk,
            delay_date,
            delay_time,
            incident_timestamp,
            day_of_week,
            transit_mode,
            cast(null as varchar) as line_code,
            route,
            cast(null as varchar) as raw_station_name,
            location,
            delay_code,
            delay_minutes,
            gap_minutes,
            direction
        from {{ ref('stg_ttc_streetcar_delays') }}
    )

select
    delay_sk,
    delay_date,
    delay_time,
    incident_timestamp,
    day_of_week,
    transit_mode,
    line_code,
    route,
    raw_station_name,
    location,
    delay_code,
    delay_minutes,
    gap_minutes,
    direction
from subway

union all

select
    delay_sk,
    delay_date,
    delay_time,
    incident_timestamp,
    day_of_week,
    transit_mode,
    line_code,
    route,
    raw_station_name,
    location,
    delay_code,
    delay_minutes,
    gap_minutes,
    direction
from bus

union all

select
    delay_sk,
    delay_date,
    delay_time,
    incident_timestamp,
    day_of_week,
    transit_mode,
    line_code,
    route,
    raw_station_name,
    location,
    delay_code,
    delay_minutes,
    gap_minutes,
    direction
from streetcar
