with
    transit as (
        select
            date_key,
            total_delay_incidents,
            total_delay_minutes,
            avg_delay_minutes,
            total_gap_minutes,
            subway_delay_incidents,
            bus_delay_incidents,
            streetcar_delay_incidents,
            subway_delay_minutes,
            bus_delay_minutes,
            streetcar_delay_minutes
        from {{ ref('int_daily_transit_metrics') }}
    ),

    bike as (
        select
            date_key,
            total_trips,
            total_duration_seconds,
            avg_duration_seconds,
            member_trips,
            casual_trips
        from {{ ref('int_daily_bike_metrics') }}
    )

select  -- noqa: ST06
    coalesce(transit.date_key, bike.date_key) as date_key,
    transit.total_delay_incidents,
    transit.total_delay_minutes,
    transit.avg_delay_minutes,
    transit.total_gap_minutes,
    transit.subway_delay_incidents,
    transit.bus_delay_incidents,
    transit.streetcar_delay_incidents,
    transit.subway_delay_minutes,
    transit.bus_delay_minutes,
    transit.streetcar_delay_minutes,
    bike.total_trips as total_bike_trips,
    bike.total_duration_seconds as total_bike_duration_seconds,
    bike.avg_duration_seconds as avg_bike_duration_seconds,
    bike.member_trips,
    bike.casual_trips
from transit
full outer join bike on transit.date_key = bike.date_key
