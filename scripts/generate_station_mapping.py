"""Generate ttc_station_mapping.csv from S001 analysis output.

Reads the collapsed unique station names from the S001 analysis,
applies deterministic matching rules against the canonical TTC
subway station registry, and produces the seed CSV.

Usage:
    python -m scripts.generate_station_mapping
"""

from __future__ import annotations

import csv
import logging
import re
import sys
from pathlib import Path
from typing import Final, NamedTuple

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger: Final = logging.getLogger(__name__)

_INPUT_FILE: Final = Path("data/working/station_name_analysis.csv")
_OUTPUT_FILE: Final = Path("seeds/ttc_station_mapping.csv")

_VALID_LINES: Final[frozenset[str]] = frozenset({"YU", "BD", "SHP", "SRT"})

_OUTPUT_COLUMNS: Final[list[str]] = [
    "raw_station_name",
    "canonical_station_name",
    "station_key",
    "line_code",
]


class StationRef(NamedTuple):
    """Reference entry for a canonical TTC subway station."""

    canonical_name: str
    station_key: str
    default_line: str


# ---------------------------------------------------------------------------
# Canonical station registry — 75 unique physical stations + Unknown
# Keys ordered: YU (ST_001-ST_038), BD (ST_039-ST_066), SHP (ST_067-ST_070),
# SRT (ST_071-ST_075), Unknown (ST_000).
# ---------------------------------------------------------------------------
_REGISTRY: Final[dict[str, StationRef]] = {
    "ST_000": StationRef("Unknown", "ST_000", "YU"),
    # --- Line 1 Yonge-University (YU) ---
    "ST_001": StationRef("Finch", "ST_001", "YU"),
    "ST_002": StationRef("North York Centre", "ST_002", "YU"),
    "ST_003": StationRef("Sheppard-Yonge", "ST_003", "YU"),
    "ST_004": StationRef("York Mills", "ST_004", "YU"),
    "ST_005": StationRef("Lawrence", "ST_005", "YU"),
    "ST_006": StationRef("Eglinton", "ST_006", "YU"),
    "ST_007": StationRef("Davisville", "ST_007", "YU"),
    "ST_008": StationRef("St. Clair", "ST_008", "YU"),
    "ST_009": StationRef("Summerhill", "ST_009", "YU"),
    "ST_010": StationRef("Rosedale", "ST_010", "YU"),
    "ST_011": StationRef("Bloor-Yonge", "ST_011", "YU"),
    "ST_012": StationRef("Wellesley", "ST_012", "YU"),
    "ST_013": StationRef("College", "ST_013", "YU"),
    "ST_014": StationRef("Dundas", "ST_014", "YU"),
    "ST_015": StationRef("Queen", "ST_015", "YU"),
    "ST_016": StationRef("King", "ST_016", "YU"),
    "ST_017": StationRef("Union", "ST_017", "YU"),
    "ST_018": StationRef("St. Andrew", "ST_018", "YU"),
    "ST_019": StationRef("Osgoode", "ST_019", "YU"),
    "ST_020": StationRef("St. Patrick", "ST_020", "YU"),
    "ST_021": StationRef("Queen's Park", "ST_021", "YU"),
    "ST_022": StationRef("Museum", "ST_022", "YU"),
    "ST_023": StationRef("St. George", "ST_023", "YU"),
    "ST_024": StationRef("Spadina", "ST_024", "YU"),
    "ST_025": StationRef("Dupont", "ST_025", "YU"),
    "ST_026": StationRef("St. Clair West", "ST_026", "YU"),
    "ST_027": StationRef("Eglinton West", "ST_027", "YU"),
    "ST_028": StationRef("Glencairn", "ST_028", "YU"),
    "ST_029": StationRef("Lawrence West", "ST_029", "YU"),
    "ST_030": StationRef("Yorkdale", "ST_030", "YU"),
    "ST_031": StationRef("Wilson", "ST_031", "YU"),
    "ST_032": StationRef("Sheppard West", "ST_032", "YU"),
    "ST_033": StationRef("Downsview Park", "ST_033", "YU"),
    "ST_034": StationRef("Finch West", "ST_034", "YU"),
    "ST_035": StationRef("York University", "ST_035", "YU"),
    "ST_036": StationRef("Pioneer Village", "ST_036", "YU"),
    "ST_037": StationRef("Highway 407", "ST_037", "YU"),
    "ST_038": StationRef("Vaughan Metropolitan Centre", "ST_038", "YU"),
    # --- Line 2 Bloor-Danforth (BD) ---
    "ST_039": StationRef("Kipling", "ST_039", "BD"),
    "ST_040": StationRef("Islington", "ST_040", "BD"),
    "ST_041": StationRef("Royal York", "ST_041", "BD"),
    "ST_042": StationRef("Old Mill", "ST_042", "BD"),
    "ST_043": StationRef("Jane", "ST_043", "BD"),
    "ST_044": StationRef("Runnymede", "ST_044", "BD"),
    "ST_045": StationRef("High Park", "ST_045", "BD"),
    "ST_046": StationRef("Keele", "ST_046", "BD"),
    "ST_047": StationRef("Dundas West", "ST_047", "BD"),
    "ST_048": StationRef("Lansdowne", "ST_048", "BD"),
    "ST_049": StationRef("Dufferin", "ST_049", "BD"),
    "ST_050": StationRef("Ossington", "ST_050", "BD"),
    "ST_051": StationRef("Christie", "ST_051", "BD"),
    "ST_052": StationRef("Bathurst", "ST_052", "BD"),
    # Spadina BD → reuse ST_024
    # St. George BD → reuse ST_023
    "ST_053": StationRef("Bay", "ST_053", "BD"),
    # Bloor-Yonge BD → reuse ST_011
    "ST_054": StationRef("Sherbourne", "ST_054", "BD"),
    "ST_055": StationRef("Castle Frank", "ST_055", "BD"),
    "ST_056": StationRef("Broadview", "ST_056", "BD"),
    "ST_057": StationRef("Chester", "ST_057", "BD"),
    "ST_058": StationRef("Pape", "ST_058", "BD"),
    "ST_059": StationRef("Donlands", "ST_059", "BD"),
    "ST_060": StationRef("Greenwood", "ST_060", "BD"),
    "ST_061": StationRef("Coxwell", "ST_061", "BD"),
    "ST_062": StationRef("Woodbine", "ST_062", "BD"),
    "ST_063": StationRef("Main Street", "ST_063", "BD"),
    "ST_064": StationRef("Victoria Park", "ST_064", "BD"),
    "ST_065": StationRef("Warden", "ST_065", "BD"),
    "ST_066": StationRef("Kennedy", "ST_066", "BD"),
    # --- Line 4 Sheppard (SHP) ---
    # Sheppard-Yonge SHP → reuse ST_003
    "ST_067": StationRef("Bayview", "ST_067", "SHP"),
    "ST_068": StationRef("Bessarion", "ST_068", "SHP"),
    "ST_069": StationRef("Leslie", "ST_069", "SHP"),
    "ST_070": StationRef("Don Mills", "ST_070", "SHP"),
    # --- Line 3 Scarborough RT (SRT) ---
    # Kennedy SRT → reuse ST_066
    "ST_071": StationRef("Lawrence East", "ST_071", "SRT"),
    "ST_072": StationRef("Ellesmere", "ST_072", "SRT"),
    "ST_073": StationRef("Midland", "ST_073", "SRT"),
    "ST_074": StationRef("Scarborough Centre", "ST_074", "SRT"),
    "ST_075": StationRef("McCowan", "ST_075", "SRT"),
}


# ---------------------------------------------------------------------------
# Core name lookup: maps normalized station core names to (key, line).
# Handles standard names, known abbreviations, misspellings, and
# truncated values observed in validated data.
# ---------------------------------------------------------------------------
_CORE_LOOKUP: Final[dict[str, tuple[str, str]]] = {
    # --- Line 1 YU stations ---
    "FINCH": ("ST_001", "YU"),
    "FICNH": ("ST_001", "YU"),
    "FICH": ("ST_001", "YU"),
    "FNCH": ("ST_001", "YU"),
    "NORTH YORK CTR": ("ST_002", "YU"),
    "NORTH YORK CENTRE": ("ST_002", "YU"),
    "NORTH YORK CENTER": ("ST_002", "YU"),
    "N YORK CTR": ("ST_002", "YU"),
    "NORTH YORK": ("ST_002", "YU"),
    "NORT YORK CENTRE": ("ST_002", "YU"),
    "SHEPPARD-YONGE": ("ST_003", "SHP"),
    "SHEPPARD YONGE": ("ST_003", "SHP"),
    "SHEPPARD- YONGE": ("ST_003", "SHP"),
    "SHEPPARD -YONGE": ("ST_003", "SHP"),
    "SHEPPARD": ("ST_003", "YU"),
    "SHEPPARD YU": ("ST_003", "YU"),
    "YORK MILLS": ("ST_004", "YU"),
    "YORKMILLS": ("ST_004", "YU"),
    "YORK MILL": ("ST_004", "YU"),
    "LAWRENCE": ("ST_005", "YU"),
    "LAWRNECE": ("ST_005", "YU"),
    "EGLINTON": ("ST_006", "YU"),
    "EGLNTON": ("ST_006", "YU"),
    "EGINTON": ("ST_006", "YU"),
    "EGLINGTON": ("ST_006", "YU"),
    "EGLINTO": ("ST_006", "YU"),
    "EGLINTN": ("ST_006", "YU"),
    "DAVISVILLE": ("ST_007", "YU"),
    "DAVISSVILLE": ("ST_007", "YU"),
    "DAVISVILE": ("ST_007", "YU"),
    "ST CLAIR": ("ST_008", "YU"),
    "ST. CLAIR": ("ST_008", "YU"),
    "SAINT CLAIR": ("ST_008", "YU"),
    "ST CLAIRE": ("ST_008", "YU"),
    "SUMMERHILL": ("ST_009", "YU"),
    "SUMMER HILL": ("ST_009", "YU"),
    "SUMMERILL": ("ST_009", "YU"),
    "ROSEDALE": ("ST_010", "YU"),
    "BLOOR-YONGE": ("ST_011", "YU"),
    "BLOOR YONGE": ("ST_011", "YU"),
    "BLOOR/YONGE": ("ST_011", "YU"),
    "BLOOR - YONGE": ("ST_011", "YU"),
    "BLOOR": ("ST_011", "YU"),
    "BLOOR STN": ("ST_011", "YU"),
    "BLOOR SATION": ("ST_011", "YU"),
    "YONGE BD": ("ST_011", "BD"),
    "YONGE BLOOR": ("ST_011", "BD"),
    "WELLESLEY": ("ST_012", "YU"),
    "WELLSLEY": ("ST_012", "YU"),
    "WELLESLY": ("ST_012", "YU"),
    "WELLESEY": ("ST_012", "YU"),
    "COLLEGE": ("ST_013", "YU"),
    "COLLGE": ("ST_013", "YU"),
    "DUNDAS": ("ST_014", "YU"),
    "TMU": ("ST_014", "YU"),
    "QUEEN": ("ST_015", "YU"),
    "KING": ("ST_016", "YU"),
    "UNION": ("ST_017", "YU"),
    "UNIION": ("ST_017", "YU"),
    "UNON": ("ST_017", "YU"),
    "ST ANDREW": ("ST_018", "YU"),
    "ST. ANDREW": ("ST_018", "YU"),
    "SAINT ANDREW": ("ST_018", "YU"),
    "ST ANREW": ("ST_018", "YU"),
    "OSGOODE": ("ST_019", "YU"),
    "OSGODE": ("ST_019", "YU"),
    "OSSGODE": ("ST_019", "YU"),
    "OSGOOD": ("ST_019", "YU"),
    "ST PATRICK": ("ST_020", "YU"),
    "ST. PATRICK": ("ST_020", "YU"),
    "SAINT PATRICK": ("ST_020", "YU"),
    "QUEEN'S PARK": ("ST_021", "YU"),
    "QUEENS PARK": ("ST_021", "YU"),
    "QUEEN'S PK": ("ST_021", "YU"),
    "MUSEUM": ("ST_022", "YU"),
    "MUSUEM": ("ST_022", "YU"),
    "ST GEORGE": ("ST_023", "YU"),
    "ST. GEORGE": ("ST_023", "YU"),
    "SAINT GEORGE": ("ST_023", "YU"),
    "ST GORGE": ("ST_023", "YU"),
    "ST GEORGE YUS": ("ST_023", "YU"),
    "ST GEORGE BD": ("ST_023", "BD"),
    "SPADINA": ("ST_024", "YU"),
    "SPADINA YUS": ("ST_024", "YU"),
    "SPADINA BD": ("ST_024", "BD"),
    "DUPONT": ("ST_025", "YU"),
    "DUPON": ("ST_025", "YU"),
    "ST CLAIR WEST": ("ST_026", "YU"),
    "ST. CLAIR WEST": ("ST_026", "YU"),
    "ST CLAIR W": ("ST_026", "YU"),
    "SAINT CLAIR WEST": ("ST_026", "YU"),
    "EGLINTON WEST": ("ST_027", "YU"),
    "EGLINTON W": ("ST_027", "YU"),
    "CEDARVALE": ("ST_027", "YU"),
    "CEDARVALE YU": ("ST_027", "YU"),
    "CALENDONIA": ("ST_027", "YU"),
    "CELEDONIA": ("ST_027", "YU"),
    "GLENCAIRN": ("ST_028", "YU"),
    "GLENCARIRN": ("ST_028", "YU"),
    "GLENCARIN": ("ST_028", "YU"),
    "LAWRENCE WEST": ("ST_029", "YU"),
    "LAWRENCE W": ("ST_029", "YU"),
    "YORKDALE": ("ST_030", "YU"),
    "YORK DALE": ("ST_030", "YU"),
    "WILSON": ("ST_031", "YU"),
    "WISLON": ("ST_031", "YU"),
    "WILSN": ("ST_031", "YU"),
    "SHEPPARD WEST": ("ST_032", "YU"),
    "SHEPARD WEST": ("ST_032", "YU"),
    "SHEPPARD W": ("ST_032", "YU"),
    "DOWNSVIEW": ("ST_032", "YU"),
    "DOWNSVIEW PARK": ("ST_033", "YU"),
    "DOWNSVIEW PK": ("ST_033", "YU"),
    "FINCH WEST": ("ST_034", "YU"),
    "FINCH W": ("ST_034", "YU"),
    "YORK UNIVERSITY": ("ST_035", "YU"),
    "YORK UNIVERISTY": ("ST_035", "YU"),
    "YORK UNIVERSIT": ("ST_035", "YU"),
    "PIONEER VILLAGE": ("ST_036", "YU"),
    "PIONEER VILLAG": ("ST_036", "YU"),
    "PIONEER VILLGE": ("ST_036", "YU"),
    "HIGHWAY 407": ("ST_037", "YU"),
    "HWY 407": ("ST_037", "YU"),
    "VAUGHAN METROPOLITAN CENTRE": ("ST_038", "YU"),
    "VAUGHAN MC": ("ST_038", "YU"),
    "VMC": ("ST_038", "YU"),
    "VAUGHAN METROPOLITAN": ("ST_038", "YU"),
    "VAUGHAN": ("ST_038", "YU"),
    # --- Line 2 BD stations ---
    "KIPLING": ("ST_039", "BD"),
    "KIPPLING": ("ST_039", "BD"),
    "ISLINGTON": ("ST_040", "BD"),
    "ISLIGNTON": ("ST_040", "BD"),
    "ROYAL YORK": ("ST_041", "BD"),
    "OLD MILL": ("ST_042", "BD"),
    "OLDMILL": ("ST_042", "BD"),
    "JANE": ("ST_043", "BD"),
    "RUNNYMEDE": ("ST_044", "BD"),
    "RUNNYMED": ("ST_044", "BD"),
    "RUNNYMEAD": ("ST_044", "BD"),
    "RUNNYMDE": ("ST_044", "BD"),
    "HIGH PARK": ("ST_045", "BD"),
    "HIGHPARK": ("ST_045", "BD"),
    "KEELE": ("ST_046", "BD"),
    "DUNDAS WEST": ("ST_047", "BD"),
    "DUNDAS W": ("ST_047", "BD"),
    "LANSDOWNE": ("ST_048", "BD"),
    "LANDSOWNE": ("ST_048", "BD"),
    "LANDDOWNE": ("ST_048", "BD"),
    "LANDSDOWNE": ("ST_048", "BD"),
    "LANSDOWND": ("ST_048", "BD"),
    "DUFFERIN": ("ST_049", "BD"),
    "DUFERIN": ("ST_049", "BD"),
    "OSSINGTON": ("ST_050", "BD"),
    "OSSINTON": ("ST_050", "BD"),
    "OSSIGTON": ("ST_050", "BD"),
    "CHRISTIE": ("ST_051", "BD"),
    "CHRSTIE": ("ST_051", "BD"),
    "CHRISTE": ("ST_051", "BD"),
    "BATHURST": ("ST_052", "BD"),
    "BATHUST": ("ST_052", "BD"),
    "BATHRST": ("ST_052", "BD"),
    "BAY": ("ST_053", "BD"),
    "BAY LOWER": ("ST_053", "BD"),
    "SHERBOURNE": ("ST_054", "BD"),
    "SHERBORNE": ("ST_054", "BD"),
    "SHERBOUNRE": ("ST_054", "BD"),
    "SHERBOUNE": ("ST_054", "BD"),
    "CASTLE FRANK": ("ST_055", "BD"),
    "CASTLEFRANK": ("ST_055", "BD"),
    "CASTLE FANK": ("ST_055", "BD"),
    "BROADVIEW": ("ST_056", "BD"),
    "BRAODVIEW": ("ST_056", "BD"),
    "BROADVIW": ("ST_056", "BD"),
    "CHESTER": ("ST_057", "BD"),
    "CHESER": ("ST_057", "BD"),
    "PAPE": ("ST_058", "BD"),
    "DONLANDS": ("ST_059", "BD"),
    "DONLADS": ("ST_059", "BD"),
    "GREENWOOD": ("ST_060", "BD"),
    "GRENWOOD": ("ST_060", "BD"),
    "COXWELL": ("ST_061", "BD"),
    "COXWLL": ("ST_061", "BD"),
    "WOODBINE": ("ST_062", "BD"),
    "WOOBINE": ("ST_062", "BD"),
    "MAIN STREET": ("ST_063", "BD"),
    "MAIN ST": ("ST_063", "BD"),
    "MAIN STEET": ("ST_063", "BD"),
    "VICTORIA PARK": ("ST_064", "BD"),
    "VICTORIA PK": ("ST_064", "BD"),
    "VIC PARK": ("ST_064", "BD"),
    "WARDEN": ("ST_065", "BD"),
    "WARDN": ("ST_065", "BD"),
    "KENNEDY BD": ("ST_066", "BD"),
    "KENNEDY": ("ST_066", "BD"),
    "KENNDY": ("ST_066", "BD"),
    "KENNEDDY": ("ST_066", "BD"),
    # --- Line 4 SHP stations ---
    "BAYVIEW": ("ST_067", "SHP"),
    "BESSARION": ("ST_068", "SHP"),
    "BESSARIONSTATION": ("ST_068", "SHP"),
    "LESLIE": ("ST_069", "SHP"),
    "DON MILLS": ("ST_070", "SHP"),
    "DONMILLS": ("ST_070", "SHP"),
    # --- Line 3 SRT stations ---
    "KENNEDY SRT": ("ST_066", "SRT"),
    "LAWRENCE EAST": ("ST_071", "SRT"),
    "ELLESMERE": ("ST_072", "SRT"),
    "ELLESEMERE": ("ST_072", "SRT"),
    "MIDLAND": ("ST_073", "SRT"),
    "SCARBOROUGH CTR": ("ST_074", "SRT"),
    "SCARBOROUGH CENTRE": ("ST_074", "SRT"),
    "SCARBOROUGH CENTER": ("ST_074", "SRT"),
    "SCARBOROUGH": ("ST_074", "SRT"),
    "MCCOWAN": ("ST_075", "SRT"),
}

# ---------------------------------------------------------------------------
# Explicit overrides for raw names that cannot be resolved via normalization.
# Maps exact raw_station_name → (station_key, line_code).
# ---------------------------------------------------------------------------
_EXPLICIT: Final[dict[str, tuple[str, str]]] = {
    # Interchange / qualified variants
    "YONGE BD STATION": ("ST_011", "BD"),
    "YONGE STATION": ("ST_011", "BD"),
    "BLOOR STATION - YONGE": ("ST_011", "YU"),
    "BLOOR STATION-DUNDAS S": ("ST_011", "YU"),
    "BLOOR YU / YONGE BD ST": ("ST_011", "BD"),
    "BLOOR YONGE": ("ST_011", "YU"),
    "BLOOR HUB": ("ST_011", "YU"),
    "BLOOR VIADUCT": ("ST_056", "BD"),
    "SPADINA STATION": ("ST_024", "BD"),
    "ST GEORGE STATION": ("ST_023", "YU"),
    "ST. GEORGE STATION": ("ST_023", "YU"),
    "KENNEDY STATION": ("ST_066", "BD"),
    "KENNEDY SRT STATION": ("ST_066", "SRT"),
    "KENNEDY SRT STATION TO": ("ST_066", "SRT"),
    # TMU / Dundas
    "TMU STATION": ("ST_014", "YU"),
    # Line-level / system references → Bloor-Yonge as interchange hub
    "YONGE-UNIVERSITY AND B": ("ST_011", "YU"),
    "YONGE/UNIVERSITY AND B": ("ST_011", "YU"),
    "YONGE UNIVERSITY AND B": ("ST_011", "YU"),
    "YONGE- UNIVERSITY AND": ("ST_011", "YU"),
    "YONGE - UNIVERSITY AND": ("ST_011", "YU"),
    "YONGE-UNIVERSITY/BLOOR": ("ST_011", "YU"),
    "YONGE AND BLOOR": ("ST_011", "YU"),
    "YONGE-UNIVERSITY-SPADI": ("ST_011", "YU"),
    "YONGE UNIVERSITY SPADI": ("ST_011", "YU"),
    "YONGE UNIVESITY LINE": ("ST_011", "YU"),
    "YONGE UNIVERSITY SUBWA": ("ST_011", "YU"),
    "YONGE-UNIVERSITY SUBWA": ("ST_011", "YU"),
    "YONGE UNIVERSITY LINE": ("ST_011", "YU"),
    "YONGE-UNIVERSITY LINE": ("ST_011", "YU"),
    # Yards / facilities → nearest station
    "GREENWOOD YARD": ("ST_060", "BD"),
    "GREENWOOD CARHOUSE": ("ST_060", "BD"),
    "GREENWOOD CAR HOUSE": ("ST_060", "BD"),
    "GREENWOOD SHOPS": ("ST_060", "BD"),
    "GREENWOOD SHOP": ("ST_060", "BD"),
    "GREENWOOD COMPLEX": ("ST_060", "BD"),
    "GREENWOOD WYE": ("ST_060", "BD"),
    "GREENWOOD PORTAL": ("ST_060", "BD"),
    "DAVISVILLE YARD": ("ST_007", "YU"),
    "DAVISVILLE CARHOUSE": ("ST_007", "YU"),
    "DAVISVILLE BUILD UP": ("ST_007", "YU"),
    "DAVISVILLE BUILD-UP": ("ST_007", "YU"),
    "DAVISVILLE BUILDUP": ("ST_007", "YU"),
    "WILSON YARD": ("ST_031", "YU"),
    "WILSON CARHOUSE": ("ST_031", "YU"),
    "WILSON GARAGE": ("ST_031", "YU"),
    "WILSON HOSTLER": ("ST_031", "YU"),
    "WILSON SOUTH HOSTLER": ("ST_031", "YU"),
    "KEELE YARD": ("ST_046", "BD"),
    "MCCOWAN YARD": ("ST_075", "SRT"),
    "DANFORTH DIVISION": ("ST_056", "BD"),
    "DANFORTH DIVSION": ("ST_056", "BD"),
    "DANFORTH": ("ST_056", "BD"),
    "BIRCHMOUNT DIVISION": ("ST_066", "BD"),
    "BIRCHMOUNT EE": ("ST_066", "BD"),
    "BIRCHMOUNT EMERGENCY E": ("ST_066", "BD"),
    # SRT line references
    "SRT LINE": ("ST_066", "SRT"),
    "SCARBOROUGH RAPID TRAN": ("ST_074", "SRT"),
    # Eglinton variants
    "EGLINTON STATION (MIGR": ("ST_006", "YU"),
    "EGLINTON MIGRATION": ("ST_006", "YU"),
    "EGLINTON (MIGRATION)": ("ST_006", "YU"),
    "EGLINTON MIGRATION POI": ("ST_006", "YU"),
    "EGLINTON STATION (APPR": ("ST_006", "YU"),
    # Pioneer Village truncation
    "PIONEER VILLAGE STATIO": ("ST_036", "YU"),
    # York University truncation
    "YORK UNIVERSITY STATIO": ("ST_035", "YU"),
    # Scarborough Centre truncation
    "SCARBOROUGH CTR STATIO": ("ST_074", "SRT"),
    # North York Centre variant
    "NORTH YORK CENTRE STAT": ("ST_002", "YU"),
    # Cedarvale / Eglinton West
    "CEDARVALE YU STATION": ("ST_027", "YU"),
    "CALENDONIA STATION": ("ST_027", "YU"),
    "CELEDONIA STATION": ("ST_027", "YU"),
    # Avenue station (Eglinton Crosstown LRT, not TTC subway)
    "AVENUE STATION": ("ST_000", "YU"),
    "AVENUE ECLRT STATION": ("ST_000", "YU"),
    # Leaside (not a current TTC subway station)
    "LEASIDE STATION": ("ST_000", "BD"),
    # Misspellings caught in Unknown review
    "MC COWAN STATION": ("ST_075", "SRT"),
    "ISLINTON STATION": ("ST_040", "BD"),
    "KENENDY STATION": ("ST_066", "BD"),
    "KILPING STATION TO JAN": ("ST_039", "BD"),
    "SHEBOURNE STATION": ("ST_054", "BD"),
    "WELLSELEY STATION": ("ST_012", "YU"),
    "YORKDLAE STATION": ("ST_030", "YU"),
    "ST GEOGE STATION": ("ST_023", "YU"),
    "DOWNVIEW PARK STATION": ("ST_033", "YU"),
    "DOWNVIEW PARK STN - UN": ("ST_033", "YU"),
    "GREEENWOOD YARD": ("ST_060", "BD"),
    "STR. CLAIR WEST STATIO": ("ST_026", "YU"),
    "ST.GEORGE STATION YU": ("ST_023", "YU"),
    "SHPPARD STATION TO COL": ("ST_003", "YU"),
    "SRT YARD": ("ST_075", "SRT"),
    "STC": ("ST_074", "SRT"),
    "MIGRATION POINT EGLINT": ("ST_006", "YU"),
    # "YOUNG(E)" = misspelling of "YONGE" in line references
    "YOUNG UNIVERSITY LINE": ("ST_011", "YU"),
    "YOUNG UNIVERSITY SPADI": ("ST_011", "YU"),
    "YOUNG-UNIVERSITY-SPADI": ("ST_011", "YU"),
    "YOUNGE UNIVERSITY LINE": ("ST_011", "YU"),
    "YOUNGE UNIVERSITY SPAD": ("ST_011", "YU"),
    "YOUNGE-UNIVERSITY-SPAD": ("ST_011", "YU"),
    "LINE1 - YOUNGE-UNIVERS": ("ST_011", "YU"),
    # Hillcrest Complex → near Davisville
    "HILLCREST COMPLEX": ("ST_007", "YU"),
    "HILLCREST COMPLEX - IN": ("ST_007", "YU"),
    "HILLCREST - GUNN BUILD": ("ST_007", "YU"),
    "HILLCREST - SUBWAY OPE": ("ST_007", "YU"),
    "HILLCREST GATE": ("ST_007", "YU"),
    "HILLCREST POWER CONTRO": ("ST_007", "YU"),
    "GUNN BUILDING": ("ST_007", "YU"),
    "GUNN BUILDING - 2ND FL": ("ST_007", "YU"),
    "GUNN BUILDING - 3RD FL": ("ST_007", "YU"),
    "GUNN BUILDING - ELEVAT": ("ST_007", "YU"),
    "GUNN THEATRE": ("ST_007", "YU"),
    "MCBRIEN BUILDING": ("ST_007", "YU"),
    "MC BRIEN": ("ST_007", "YU"),
    "MCBRIAN BUILDING": ("ST_007", "YU"),
    # Duncan facility → near St. Andrew
    "DUNCAN BUILDING": ("ST_018", "YU"),
    "DUNCAN SUBSTATION": ("ST_018", "YU"),
    "DUNCAN SHOP": ("ST_018", "YU"),
    "DUNCAN SHOPS": ("ST_018", "YU"),
    "DUNCAN SHOPS BRAKE SEC": ("ST_018", "YU"),
    "DUNCAN WAREHOUSE": ("ST_018", "YU"),
    # McBrien Building = 1900 Yonge St, near Davisville (NOT Bloor-Yonge)
    "1900 YONGE MCBRIEN BLD": ("ST_007", "YU"),
    "1900 YONGE ST- MCBRIEN": ("ST_007", "YU"),
    "1900 YONGE STREET": ("ST_007", "YU"),
    "2233 SHEPPARD WEST": ("ST_032", "YU"),
    # VMC variants
    "VMC STATION": ("ST_038", "YU"),
    "VAUGHAN MC STATION": ("ST_038", "YU"),
    # Bay Lower
    "BAY LOWER": ("ST_053", "BD"),
    "BAY LOWER STATION": ("ST_053", "BD"),
    # Queens Park variant
    "QUEENS PARK STATION": ("ST_021", "YU"),
}

# Suffixes stripped during normalization (order matters — longest first)
_STRIP_SUFFIXES: Final[list[str]] = [
    " STATION TO",
    " STATION (LEAVING",
    " STATION (APPROA",
    " STATION (TO KING",
    " STATION (TOWARDS",
    " STATION (LEA",
    " STATIO",
    " STATION",
    " STN",
]

# Facility suffixes that indicate a non-station entry near a station
_FACILITY_SUFFIXES: Final[list[str]] = [
    " YARD",
    " CARHOUSE",
    " CAR HOUSE",
    " GARAGE",
    " SHOPS",
    " SHOP",
    " COMPLEX",
    " DIVISION",
    " DIVSION",
    " WYE",
    " PORTAL",
    " HOSTLER",
    " BUILD UP",
    " BUILD-UP",
    " BUILDUP",
    " CENTRE TRACK",
    " CENTER TRACK",
    " CENTER",
    " CENTRE",
    " SUBSTATION",
    " ESB",
    " EE",
]

# Line qualifier suffixes stripped after station suffix removal
_LINE_SUFFIXES: Final[list[str]] = [
    " BD",
    " YUS",
    " YU",
    " SRT",
    " SHP",
    " SHEP",
]


def _normalize_line_code(raw_line: str) -> str:
    """Normalize a raw line code to a valid enum value.

    Returns the most specific valid line code extractable from the raw
    value, defaulting to YU when no valid code can be determined.
    """
    upper = raw_line.strip().upper()
    if upper in _VALID_LINES:
        return upper
    if "SRT" in upper:
        return "SRT"
    if "SHP" in upper or "SHEP" in upper:
        return "SHP"
    if "BD" in upper and "YU" not in upper:
        return "BD"
    if "YU" in upper and "BD" not in upper:
        return "YU"
    # Mixed references (YU/BD etc.) default to YU as the primary line
    if "YU" in upper:
        return "YU"
    return "YU"


def _strip_suffix(name: str, suffixes: list[str]) -> str:
    """Strip the first matching suffix from name."""
    for suffix in suffixes:
        if name.endswith(suffix):
            return name[: -len(suffix)].rstrip()
    return name


def _resolve_station(
    raw_name: str,
    primary_line: str,
) -> tuple[str, str, str]:
    """Resolve a raw station name to (canonical_name, station_key, line_code).

    Applies matching rules in priority order:
    1. Explicit override dictionary
    2. Core lookup after normalization
    3. Substring matching against canonical station names
    4. Default to Unknown
    """
    # Priority 1: Explicit overrides
    if raw_name in _EXPLICIT:
        key, line = _EXPLICIT[raw_name]
        ref = _REGISTRY[key]
        return (ref.canonical_name, ref.station_key, line)

    # Priority 2: Normalize and look up core name
    core = raw_name

    # Strip station-related suffixes
    for suffix in _STRIP_SUFFIXES:
        if suffix in core:
            idx = core.find(suffix)
            core = core[:idx].rstrip()
            break

    # Strip facility suffixes
    core = _strip_suffix(core, _FACILITY_SUFFIXES)

    # Strip line qualifiers from end
    core = _strip_suffix(core, _LINE_SUFFIXES)

    # Try core lookup
    if core in _CORE_LOOKUP:
        key, line = _CORE_LOOKUP[core]
        ref = _REGISTRY[key]
        return (ref.canonical_name, ref.station_key, line)

    # Priority 3: Handle "X TO Y" patterns — extract first station
    to_match = re.match(r"^(.+?)\s+TO\s+", raw_name)
    if to_match:
        first_part = to_match.group(1).strip()
        first_core = _strip_suffix(first_part, _STRIP_SUFFIXES[:])
        first_core = _strip_suffix(first_core, _LINE_SUFFIXES)
        if first_core in _CORE_LOOKUP:
            key, line = _CORE_LOOKUP[first_core]
            ref = _REGISTRY[key]
            return (ref.canonical_name, ref.station_key, line)

    # Priority 4: Handle "X AND Y" patterns — extract first station
    and_match = re.match(r"^(.+?)\s+AND\s+", raw_name)
    if and_match:
        first_part = and_match.group(1).strip()
        first_core = _strip_suffix(first_part, _LINE_SUFFIXES)
        if first_core in _CORE_LOOKUP:
            key, line = _CORE_LOOKUP[first_core]
            ref = _REGISTRY[key]
            return (ref.canonical_name, ref.station_key, line)

    # Priority 5: Substring match — find longest canonical match in raw name
    best_match: tuple[str, str] | None = None
    best_len = 0
    for core_name, (key, line) in _CORE_LOOKUP.items():
        if len(core_name) > best_len and core_name in raw_name and len(core_name) >= 4:
            best_match = (key, line)
            best_len = len(core_name)

    if best_match is not None:
        key, line = best_match
        ref = _REGISTRY[key]
        return (ref.canonical_name, ref.station_key, line)

    # Priority 6: Handle "(APPROACHING) X" pattern
    approach_match = re.match(r"^\(?APPROACH(?:ING)?\)?\s*(.+)", raw_name)
    if approach_match:
        remainder = approach_match.group(1).strip()
        return _resolve_station(remainder, primary_line)

    # Priority 7: Handle "BETWEEN X AND Y" pattern
    between_match = re.match(r"^BETWEEN\s+(.+?)\s+AND\s+", raw_name)
    if between_match:
        first_part = between_match.group(1).strip()
        first_core = _strip_suffix(first_part, _STRIP_SUFFIXES[:])
        first_core = _strip_suffix(first_core, _LINE_SUFFIXES)
        if first_core in _CORE_LOOKUP:
            key, line = _CORE_LOOKUP[first_core]
            ref = _REGISTRY[key]
            return (ref.canonical_name, ref.station_key, line)

    # Default: Unknown
    valid_line = _normalize_line_code(primary_line)
    return ("Unknown", "ST_000", valid_line)


def _read_unique_names(
    input_path: Path,
) -> list[tuple[str, str, int]]:
    """Read analysis CSV and collapse to unique (name, primary_line, total).

    Returns list sorted alphabetically by raw_station_name.
    """
    from collections import defaultdict

    name_data: dict[str, dict[str, int | dict[str, int]]] = {}

    with input_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row["raw_station_name"]
            line = row["line_code"]
            count = int(row["occurrence_count"])
            if name not in name_data:
                name_data[name] = {"total": 0, "lines": defaultdict(int)}
            stats = name_data[name]
            total = stats["total"]
            assert isinstance(total, int)
            stats["total"] = total + count
            lines = stats["lines"]
            assert isinstance(lines, dict)
            lines[line] = lines.get(line, 0) + count

    result: list[tuple[str, str, int]] = []
    for name in sorted(name_data):
        stats = name_data[name]
        total = stats["total"]
        assert isinstance(total, int)
        lines_raw = stats["lines"]
        assert isinstance(lines_raw, dict)
        lines_dict: dict[str, int] = lines_raw
        primary_line = max(lines_dict, key=lambda k: lines_dict[k])
        result.append((name, primary_line, total))

    return result


def main() -> None:
    """Generate ttc_station_mapping.csv from analysis data."""
    if not _INPUT_FILE.exists():
        logger.error("Input file not found: %s", _INPUT_FILE)
        sys.exit(1)

    names = _read_unique_names(_INPUT_FILE)
    logger.info("Read %d unique raw station names", len(names))

    rows: list[list[str]] = []
    unknown_count = 0
    unknown_occurrences = 0
    total_occurrences = sum(t for _, _, t in names)

    for raw_name, primary_line, occ_count in names:
        canonical, key, line = _resolve_station(raw_name, primary_line)
        rows.append([raw_name, canonical, key, line])
        if key == "ST_000":
            unknown_count += 1
            unknown_occurrences += occ_count

    # Write output
    _OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _OUTPUT_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(_OUTPUT_COLUMNS)
        writer.writerows(rows)

    mapped_occ = total_occurrences - unknown_occurrences
    coverage = mapped_occ / total_occurrences * 100 if total_occurrences else 0

    logger.info("Wrote %d rows to %s", len(rows), _OUTPUT_FILE)
    logger.info(
        "Mapped: %d names (%d occurrences, %.1f%% coverage)",
        len(rows) - unknown_count,
        mapped_occ,
        coverage,
    )
    logger.info(
        "Unknown: %d names (%d occurrences, %.1f%%)",
        unknown_count,
        unknown_occurrences,
        100 - coverage,
    )

    # Verify all canonical stations have at least one mapping
    mapped_keys = {row[2] for row in rows if row[2] != "ST_000"}
    expected_keys = {k for k in _REGISTRY if k != "ST_000"}
    missing = expected_keys - mapped_keys
    if missing:
        logger.warning(
            "Canonical stations with no mapped raw variant: %s",
            sorted(missing),
        )
        for k in sorted(missing):
            ref = _REGISTRY[k]
            logger.warning("  %s: %s (%s)", k, ref.canonical_name, ref.default_line)

    # Verify uniqueness on raw_station_name
    raw_names = [row[0] for row in rows]
    if len(raw_names) != len(set(raw_names)):
        logger.error("DUPLICATE raw_station_name values detected!")
        sys.exit(1)


if __name__ == "__main__":
    main()
