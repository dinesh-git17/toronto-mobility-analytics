-- Validates that at least 99% of subway delay records resolve to a
-- canonical station mapping. Returns rows (failing) when coverage
-- drops below the 0.99 threshold.

with
    subway_delays as (
        select
            canonical_station_name
        from {{ ref('int_ttc_delays_enriched') }}
        where transit_mode = 'subway'
    ),

    coverage as (
        select
            count(*) as total_rows,
            count(canonical_station_name) as mapped_rows
        from subway_delays
    )

select
    total_rows,
    mapped_rows,
    mapped_rows::float / nullif(total_rows, 0) as coverage_ratio
from coverage
where mapped_rows::float / nullif(total_rows, 0) < 0.99
