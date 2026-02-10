"""Geographic proximity computation utilities.

Provides Haversine great-circle distance calculation and nearest-station
discovery for station reference data.  All computations use the Python
standard library ``math`` module with no external geospatial dependencies.
"""

from __future__ import annotations

import math

import pandas as pd

_EARTH_RADIUS_KM: float = 6_371.0


def haversine_distance(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """Compute great-circle distance between two coordinate pairs.

    Applies the Haversine formula:
    ``a = sin²(dlat/2) + cos(lat1) * cos(lat2) * sin²(dlon/2)``
    ``c = 2 * asin(sqrt(a))``
    ``d = R * c``

    Args:
        lat1: Latitude of the first point in decimal degrees.
        lon1: Longitude of the first point in decimal degrees.
        lat2: Latitude of the second point in decimal degrees.
        lon2: Longitude of the second point in decimal degrees.

    Returns:
        Distance in kilometers.  Returns ``0.0`` for identical coordinates.
    """
    if lat1 == lat2 and lon1 == lon2:
        return 0.0

    rlat1 = math.radians(lat1)
    rlat2 = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))

    return _EARTH_RADIUS_KM * c


def find_nearby_stations(
    ref_lat: float,
    ref_lon: float,
    stations_df: pd.DataFrame,
    *,
    lat_col: str = "latitude",
    lon_col: str = "longitude",
    n: int = 10,
    exclude_key: str | None = None,
    key_col: str = "station_key",
) -> pd.DataFrame:
    """Rank stations by Haversine proximity to a reference point.

    Computes the great-circle distance from ``(ref_lat, ref_lon)`` to
    every station in the DataFrame, excludes rows with missing
    coordinates and the optionally excluded station, then returns the
    N nearest sorted by distance ascending.

    Runs in O(n) over the station DataFrame with constant-factor
    Haversine computation per row.

    Args:
        ref_lat: Reference point latitude in decimal degrees.
        ref_lon: Reference point longitude in decimal degrees.
        stations_df: Station reference DataFrame with coordinate columns.
        lat_col: Column name for latitude values.
        lon_col: Column name for longitude values.
        n: Maximum number of nearby stations to return.
        exclude_key: Station key value to exclude from results.  Pass
            the selected station's key to prevent it from appearing
            in its own nearby list.
        key_col: Column containing station key identifiers.

    Returns:
        DataFrame with the N nearest stations sorted by distance
        ascending, with an appended ``distance_km`` column rounded
        to 2 decimal places.
    """
    df = stations_df.copy()
    df = df.dropna(subset=[lat_col, lon_col])

    if exclude_key is not None and key_col in df.columns:
        df = df.loc[df[key_col] != exclude_key]

    if df.empty:
        result = df.copy()
        result["distance_km"] = pd.Series(dtype="float64")
        return result

    df["distance_km"] = df.apply(
        lambda row: round(
            haversine_distance(
                ref_lat,
                ref_lon,
                float(row[lat_col]),
                float(row[lon_col]),
            ),
            2,
        ),
        axis=1,
    )

    return df.sort_values("distance_km", ascending=True).head(n).reset_index(drop=True)
