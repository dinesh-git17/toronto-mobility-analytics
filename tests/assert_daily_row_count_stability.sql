-- DESIGN-DOC Section 8.3: Day-over-day activity count must not drop
-- below 50% of the previous day. Detects anomalous data gaps or
-- incomplete loads by comparing consecutive date_key values via LAG().

{{ config(severity='warn') }}

with
    daily_counts as (
        select
            date_key,
            coalesce(total_delay_incidents, 0)
            + coalesce(total_bike_trips, 0) as daily_activity_count
        from {{ ref('fct_daily_mobility') }}
    ),

    with_previous as (
        select
            date_key,
            daily_activity_count,
            lag(daily_activity_count) over (order by date_key) as previous_day_count
        from daily_counts
    )

select
    date_key,
    daily_activity_count,
    previous_day_count
from with_previous
where
    previous_day_count is not null
    and previous_day_count > 0
    and daily_activity_count::float / previous_day_count < 0.5
