select
    trip_date,
    date_key,
    count(*) as total_trips,
    sum(trip_duration_seconds) as total_duration_seconds,
    round(avg(trip_duration_seconds), 2) as avg_duration_seconds,
    count_if(user_type = 'Annual Member') as member_trips,
    count_if(user_type = 'Casual Member') as casual_trips
from {{ ref('int_bike_trips_enriched') }}
group by trip_date, date_key
