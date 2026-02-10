-- DESIGN-DOC Section 8.3: No fact table may contain dates beyond the
-- current calendar date. Uses integer date_key comparison in YYYYMMDD
-- format against current_date() to detect forward-dated records.

with
    current_ref as (
        select cast(to_char(current_date(), 'YYYYMMDD') as integer) as current_date_key
    ),

    future_transit_delays as (
        select
            'fct_transit_delays' as source_model,
            date_key
        from {{ ref('fct_transit_delays') }}
        where date_key > (select current_date_key from current_ref)
    ),

    future_bike_trips as (
        select
            'fct_bike_trips' as source_model,
            date_key
        from {{ ref('fct_bike_trips') }}
        where date_key > (select current_date_key from current_ref)
    ),

    future_daily_mobility as (
        select
            'fct_daily_mobility' as source_model,
            date_key
        from {{ ref('fct_daily_mobility') }}
        where date_key > (select current_date_key from current_ref)
    )

select * from future_transit_delays
union all
select * from future_bike_trips
union all
select * from future_daily_mobility
