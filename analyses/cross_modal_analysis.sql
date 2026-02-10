-- Do bike trips increase on high TTC delay days?
-- Expected rows: 3
-- Reference: DESIGN-DOC Section 15.3, Query #4
select
    case
        when m.total_delay_minutes > 500
        then '3. High Delay (>500 min)'
        when m.total_delay_minutes > 100
        then '2. Medium Delay (100-500 min)'
        else '1. Low Delay (<100 min)'
    end as ttc_delay_category,
    count(*) as days,
    round(avg(m.total_bike_trips), 0) as avg_bike_trips,
    round(avg(m.total_delay_incidents), 1) as avg_delay_incidents
from {{ ref('fct_daily_mobility') }} m
where m.total_bike_trips is not null and m.total_delay_incidents is not null
group by 1
order by 1
