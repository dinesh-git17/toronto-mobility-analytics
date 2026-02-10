with
    source as (
        select
            weather_date,
            mean_temp_c,
            max_temp_c,
            min_temp_c,
            total_precip_mm,
            total_rain_mm,
            total_snow_cm,
            snow_on_ground_cm,
            max_wind_gust_kmh,
            max_wind_gust_dir_deg
        from {{ ref('stg_weather_daily') }}
    )

select
    cast(to_char(weather_date, 'YYYYMMDD') as integer) as date_key,
    weather_date,
    mean_temp_c,
    max_temp_c,
    min_temp_c,
    total_precip_mm,
    total_rain_mm,
    total_snow_cm,
    snow_on_ground_cm,
    max_wind_gust_kmh,
    max_wind_gust_dir_deg,
    case
        when total_snow_cm > 0
        then 'Snow'
        when total_rain_mm > 0 and (total_snow_cm = 0 or total_snow_cm is null)
        then 'Rain'
        else 'Clear'
    end as weather_condition
from source
