{{
    config(
        materialized='view'
    )
}}

with
    source as (
        select *
        from {{ source('raw', 'ttc_subway_delays') }}
        where try_cast(min_delay as integer) > 0
    ),

    renamed as (
        select
            {{ dbt_utils.generate_surrogate_key([
            'date', 'time', 'station', 'line', 'code', 'min_delay'
        ]) }} as delay_sk,
            date::date as delay_date,
            time::time as delay_time,
            timestamp_from_parts(date::date, time::time) as incident_timestamp,
            day as day_of_week,
            station as raw_station_name,
            code as delay_code,
            try_cast(min_delay as integer) as delay_minutes,
            try_cast(min_gap as integer) as gap_minutes,
            bound as direction,
            line as line_code,
            'subway' as transit_mode,
            row_number() over (
                partition by date, time, station, line, code, min_delay order by date
            ) as _row_num
        from source
    )

select
    delay_sk,
    delay_date,
    delay_time,
    incident_timestamp,
    day_of_week,
    raw_station_name,
    delay_code,
    delay_minutes,
    gap_minutes,
    direction,
    line_code,
    transit_mode
from renamed
where _row_num = 1
