{{
    config(
        materialized='view'
    )
}}

with
    source as (
        select *
        from {{ source('raw', 'bike_share_trips') }}
        where
            try_cast(trip_duration as int) >= 60
            and try_to_timestamp_ntz(start_time, 'MM/DD/YYYY HH24:MI') is not null
    ),

    renamed as (
        select
            {{ dbt_utils.generate_surrogate_key([
            'trip_id'
        ]) }} as trip_sk,
            trip_id,
            try_cast(trip_duration as int) as trip_duration_seconds,
            try_cast(start_station_id as int) as start_station_id,
            try_to_timestamp_ntz(start_time, 'MM/DD/YYYY HH24:MI') as start_time,
            start_station_name,
            try_cast(end_station_id as int) as end_station_id,
            try_to_timestamp_ntz(end_time, 'MM/DD/YYYY HH24:MI') as end_time,
            end_station_name,
            try_cast(bike_id as int) as bike_id,
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
