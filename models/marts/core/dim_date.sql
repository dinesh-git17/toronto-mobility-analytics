with
    source as (
        select
            date_key,
            full_date,
            day_of_week,
            day_of_week_num,
            month_num,
            month_name,
            quarter,
            year,
            is_weekend,
            is_holiday
        from {{ ref('date_spine') }}
    )

select
    cast(date_key as integer) as date_key,
    cast(full_date as date) as full_date,
    day_of_week,
    cast(day_of_week_num as integer) as day_of_week_num,
    cast(month_num as integer) as month_num,
    month_name,
    cast(quarter as integer) as quarter,
    cast(year as integer) as year,
    cast(is_weekend as boolean) as is_weekend,
    cast(is_holiday as boolean) as is_holiday
from source
