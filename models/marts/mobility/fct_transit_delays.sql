with
    source as (
        select
            delay_sk,
            date_key,
            transit_mode,
            station_id,
            delay_code,
            delay_minutes,
            gap_minutes,
            line_code,
            direction,
            incident_timestamp
        from {{ ref('int_ttc_delays_enriched') }}
    )

select
    {{ dbt_utils.generate_surrogate_key(['transit_mode', 'delay_sk']) }} as delay_sk,
    date_key,
    case
        when transit_mode = 'subway' and station_id is not null
        then {{ dbt_utils.generate_surrogate_key(["'TTC_SUBWAY'", 'station_id']) }}
        else null
    end as station_key,
    case
        when delay_code is not null
        then {{ dbt_utils.generate_surrogate_key(['delay_code']) }}
        else null
    end as delay_code_key,
    delay_minutes,
    gap_minutes,
    transit_mode,
    line_code,
    direction,
    incident_timestamp
from source
