{{
    config(
        materialized='view'
    )
}}

with
    source as (
        select *
        from {{ source('raw', 'bike_share_trips') }}
        where trip_duration::int >= 60
    ),

    renamed as (
        select
            {{ dbt_utils.generate_surrogate_key([
            'trip_id'
        ]) }} as trip_sk,
            trip_id,
            trip_duration::int as trip_duration_seconds,
            start_station_id::int as start_station_id,
            start_time::timestamp_ntz as start_time,
            start_station_name,
            end_station_id::int as end_station_id,
            end_time::timestamp_ntz as end_time,
            end_station_name,
            bike_id::int as bike_id,
            user_type
        from source
    )

select
    trip_sk,
    trip_id,
    trip_duration_seconds,
    start_station_id,
    start_time,
    start_station_name,
    end_station_id,
    end_time,
    end_station_name,
    bike_id,
    user_type
from renamed
