-- Top 10 subway stations by total delay minutes (2019-present)
-- Expected rows: 10
-- Reference: DESIGN-DOC Section 15.3, Query #2
select
    s.station_name,
    s.station_type,
    count(*) as delay_count,
    sum(f.delay_minutes) as total_delay_minutes,
    round(avg(f.delay_minutes), 2) as avg_delay_minutes,
    round(
        sum(f.delay_minutes) * 1.0 / count(distinct f.date_key), 2
    ) as delay_minutes_per_day
from {{ ref('fct_transit_delays') }} f
inner join {{ ref('dim_station') }} s on f.station_key = s.station_key
where f.transit_mode = 'subway'
group by s.station_name, s.station_type
order by total_delay_minutes desc
limit 10
