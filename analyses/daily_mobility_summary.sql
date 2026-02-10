-- Daily mobility summary: full scan of cross-modal daily metrics
-- Expected rows: ~1,827 (one per active date across transit and bike data)
-- Reference: DESIGN-DOC Section 15.4, Query #1
select
    d.full_date,
    d.day_of_week,
    d.is_weekend,
    d.is_holiday,
    m.total_delay_incidents,
    m.total_delay_minutes,
    m.avg_delay_minutes,
    m.total_gap_minutes,
    m.subway_delay_incidents,
    m.bus_delay_incidents,
    m.streetcar_delay_incidents,
    m.total_bike_trips,
    m.total_bike_duration_seconds,
    m.avg_bike_duration_seconds,
    m.member_trips,
    m.casual_trips
from {{ ref('fct_daily_mobility') }} m
inner join {{ ref('dim_date') }} d on m.date_key = d.date_key
order by d.full_date
