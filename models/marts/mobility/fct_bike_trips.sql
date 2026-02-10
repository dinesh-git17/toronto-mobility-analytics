with
    source as (
        select
            trip_sk,
            date_key,
            cast(start_station_id as varchar) as start_station_id,
            cast(end_station_id as varchar) as end_station_id,
            start_latitude,
            end_latitude,
            trip_duration_seconds,
            user_type,
            bike_id,
            start_time,
            end_time
        from {{ ref('int_bike_trips_enriched') }}
    )

select
    trip_sk,
    date_key,
    case
        when start_latitude is not null
        then
            {{ dbt_utils.generate_surrogate_key(["'BIKE_SHARE'", 'start_station_id']) }}
        else null
    end as start_station_key,
    case
        when end_latitude is not null
        then {{ dbt_utils.generate_surrogate_key(["'BIKE_SHARE'", 'end_station_id']) }}
        else null
    end as end_station_key,
    trip_duration_seconds as duration_seconds,
    user_type,
    bike_id,
    start_time,
    end_time
from source
