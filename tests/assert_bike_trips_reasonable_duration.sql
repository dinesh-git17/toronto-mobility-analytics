-- DESIGN-DOC Section 8.3: Bike trip durations must not exceed 24 hours
-- (86,400 seconds). Trips at or above this threshold indicate data
-- quality issues or unreturned bikes rather than legitimate rides.

{{ config(severity='warn') }}

select
    trip_sk,
    duration_seconds,
    date_key
from {{ ref('fct_bike_trips') }}
where duration_seconds >= 86400
