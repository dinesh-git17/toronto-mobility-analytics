{{
    config(
        materialized='view'
    )
}}

with
    source as (select * from {{ source('raw', 'weather_daily') }}),

    renamed as (
        select
            {{ dbt_utils.generate_surrogate_key([
            'date_time'
        ]) }} as weather_sk,
            date_time::date as weather_date,
            try_cast(max_temp_c as decimal(10, 1)) as max_temp_c,
            try_cast(min_temp_c as decimal(10, 1)) as min_temp_c,
            try_cast(mean_temp_c as decimal(10, 1)) as mean_temp_c,
            try_cast(heat_deg_days_c as decimal(10, 1)) as heat_degree_days,
            try_cast(cool_deg_days_c as decimal(10, 1)) as cool_degree_days,
            try_cast(total_rain_mm as decimal(10, 1)) as total_rain_mm,
            try_cast(total_snow_cm as decimal(10, 1)) as total_snow_cm,
            try_cast(total_precip_mm as decimal(10, 1)) as total_precip_mm,
            try_cast(snow_on_grnd_cm as decimal(10, 1)) as snow_on_ground_cm,
            try_cast(spd_of_max_gust_kmh as decimal(10, 1)) as max_wind_gust_kmh,
            try_cast(dir_of_max_gust_10s_deg as integer) as max_wind_gust_dir_deg
        from source
    )

select
    weather_sk,
    weather_date,
    max_temp_c,
    min_temp_c,
    mean_temp_c,
    heat_degree_days,
    cool_degree_days,
    total_rain_mm,
    total_snow_cm,
    total_precip_mm,
    snow_on_ground_cm,
    max_wind_gust_kmh,
    max_wind_gust_dir_deg
from renamed
