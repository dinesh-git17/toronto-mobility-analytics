with
    source as (
        select delay_code, delay_description, delay_category  -- noqa: LT09
        from {{ ref('ttc_delay_codes') }}
    )

select
    {{ dbt_utils.generate_surrogate_key(['delay_code']) }} as delay_code_key,
    delay_code,
    delay_description,
    delay_category
from source
