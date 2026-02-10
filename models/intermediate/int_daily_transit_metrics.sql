select
    delay_date,
    date_key,
    count(*) as total_delay_incidents,
    sum(delay_minutes) as total_delay_minutes,
    round(avg(delay_minutes), 2) as avg_delay_minutes,
    sum(gap_minutes) as total_gap_minutes,
    count_if(transit_mode = 'subway') as subway_delay_incidents,
    count_if(transit_mode = 'bus') as bus_delay_incidents,
    count_if(transit_mode = 'streetcar') as streetcar_delay_incidents,
    sum(
        case when transit_mode = 'subway' then delay_minutes else 0 end
    ) as subway_delay_minutes,
    sum(
        case when transit_mode = 'bus' then delay_minutes else 0 end
    ) as bus_delay_minutes,
    sum(
        case when transit_mode = 'streetcar' then delay_minutes else 0 end
    ) as streetcar_delay_minutes
from {{ ref('int_ttc_delays_enriched') }}
group by delay_date, date_key
