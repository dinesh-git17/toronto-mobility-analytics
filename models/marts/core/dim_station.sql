with
    ttc_stations as (
        select distinct  -- noqa: LT09
            station_key as station_id, canonical_station_name as station_name
        from {{ ref('ttc_station_mapping') }}
    ),

    ttc_coords as (
        select
            canonical_station_name,
            cast(latitude as decimal(10, 6)) as latitude,
            cast(longitude as decimal(10, 6)) as longitude
        from {{ ref('ttc_station_coords') }}
    ),

    ttc_dim as (
        select
            {{ dbt_utils.generate_surrogate_key(["'TTC_SUBWAY'", 'station_id']) }}
            as station_key,
            ttc_stations.station_id,
            ttc_stations.station_name,
            'TTC_SUBWAY' as station_type,
            ttc_coords.latitude,
            ttc_coords.longitude,
            cast(null as varchar) as neighborhood
        from ttc_stations
        left join
            ttc_coords on ttc_stations.station_name = ttc_coords.canonical_station_name
    ),

    bike_dim as (
        select
            {{ dbt_utils.generate_surrogate_key(["'BIKE_SHARE'", 'station_id']) }}
            as station_key,
            cast(station_id as varchar) as station_id,
            station_name,
            'BIKE_SHARE' as station_type,
            cast(latitude as decimal(10, 6)) as latitude,
            cast(longitude as decimal(10, 6)) as longitude,
            neighborhood
        from {{ ref('bike_station_ref') }}
    )

select
    station_key,
    station_id,
    station_name,
    station_type,
    latitude,
    longitude,
    neighborhood
from ttc_dim

union all

select
    station_key,
    station_id,
    station_name,
    station_type,
    latitude,
    longitude,
    neighborhood
from bike_dim
