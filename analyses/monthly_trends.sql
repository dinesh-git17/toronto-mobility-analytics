-- Monthly aggregation of transit and bike metrics with seasonal context
-- Expected rows: ~72 (one per year-month with activity data)
-- Reference: DESIGN-DOC Section 15.4, Query #5
select
    d.year,
    d.month_num,
    d.month_name,
    count(*) as active_days,
    sum(m.total_delay_incidents) as total_delay_incidents,
    round(avg(m.total_delay_minutes), 1) as avg_daily_delay_minutes,
    sum(m.total_bike_trips) as total_bike_trips,
    round(avg(m.total_bike_trips), 0) as avg_daily_bike_trips,
    sum(m.member_trips) as total_member_trips,
    sum(m.casual_trips) as total_casual_trips
from {{ ref('fct_daily_mobility') }} m
inner join {{ ref('dim_date') }} d on m.date_key = d.date_key
group by d.year, d.month_num, d.month_name
order by d.year, d.month_num
