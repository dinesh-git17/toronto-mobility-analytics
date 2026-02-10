-- DESIGN-DOC Section 8.3: No negative delay durations in transit delay facts.
-- Returns failing rows where delay_minutes is below zero.

select
    delay_sk,
    delay_minutes,
    transit_mode,
    date_key
from {{ ref('fct_transit_delays') }}
where delay_minutes < 0
