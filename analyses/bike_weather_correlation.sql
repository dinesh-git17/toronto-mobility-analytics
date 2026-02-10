-- Bike share ridership by temperature bucket
-- Expected rows: 4
-- Reference: DESIGN-DOC Section 15.3, Query #3
select
    case
        when w.mean_temp_c < 0
        then '1. Below Freezing (<0°C)'
        when w.mean_temp_c < 10
        then '2. Cold (0-10°C)'
        when w.mean_temp_c < 20
        then '3. Mild (10-20°C)'
        else '4. Warm (20°C+)'
    end as temp_bucket,
    count(*) as days_in_bucket,
    round(avg(m.total_bike_trips), 0) as avg_daily_trips,
    round(sum(m.total_bike_trips), 0) as total_trips
from {{ ref('fct_daily_mobility') }} m
inner join {{ ref('dim_weather') }} w on m.date_key = w.date_key
where m.total_bike_trips is not null
group by 1
order by 1
