with
    delays as (
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
        from {{ ref('int_ttc_delays_unioned') }}
    ),

    enriched as (
        select
            delays.delay_sk,
            delays.delay_date,
            delays.delay_time,
            delays.incident_timestamp,
            delays.day_of_week,
            delays.transit_mode,
            delays.line_code,
            delays.route,
            delays.raw_station_name,
            delays.location,
            delays.delay_code,
            delays.delay_minutes,
            delays.gap_minutes,
            delays.direction,
            sm.canonical_station_name,
            sm.station_key as station_id,
            dc.delay_description,
            dc.delay_category,
            cast(to_char(delays.delay_date, 'YYYYMMDD') as integer) as date_key
        from delays
        left join
            {{ ref('ttc_station_mapping') }} as sm
            on delays.raw_station_name = sm.raw_station_name
        left join
            {{ ref('ttc_delay_codes') }} as dc on delays.delay_code = dc.delay_code
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
    direction,
    canonical_station_name,
    station_id,
    delay_description,
    delay_category,
    date_key
from enriched
