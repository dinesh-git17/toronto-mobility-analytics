with
    trips as (
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
        from {{ ref('stg_bike_trips') }}
    ),

    enriched as (
        select
            trips.trip_sk,
            trips.trip_id,
            trips.trip_duration_seconds,
            trips.start_station_id,
            trips.start_time,
            trips.start_station_name,
            trips.end_station_id,
            trips.end_time,
            trips.end_station_name,
            trips.bike_id,
            trips.user_type,
            start_ref.latitude as start_latitude,
            start_ref.longitude as start_longitude,
            start_ref.neighborhood as start_neighborhood,
            end_ref.latitude as end_latitude,
            end_ref.longitude as end_longitude,
            end_ref.neighborhood as end_neighborhood,
            trips.start_time::date as trip_date,
            to_number(to_char(trips.start_time::date, 'YYYYMMDD')) as date_key,
            case
                when trips.trip_duration_seconds < 300
                then 'Under 5 min'
                when trips.trip_duration_seconds < 900
                then '5-15 min'
                when trips.trip_duration_seconds < 1800
                then '15-30 min'
                when trips.trip_duration_seconds < 3600
                then '30-60 min'
                else 'Over 60 min'
            end as duration_bucket
        from trips
        left join
            {{ ref('bike_station_ref') }} as start_ref
            on trips.start_station_id = start_ref.station_id
        left join
            {{ ref('bike_station_ref') }} as end_ref
            on trips.end_station_id = end_ref.station_id
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
    user_type,
    start_latitude,
    start_longitude,
    start_neighborhood,
    end_latitude,
    end_longitude,
    end_neighborhood,
    trip_date,
    date_key,
    duration_bucket
from enriched
