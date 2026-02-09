"""Generate ttc_delay_codes.csv from validated TTC delay data.

Extracts all distinct delay/incident codes from subway, bus, and
streetcar validated CSVs, assigns categories based on the TTC code
prefix taxonomy, and generates human-readable descriptions from
code mnemonics.

Usage:
    python -m scripts.generate_delay_codes
"""

from __future__ import annotations

import csv
import logging
import sys
from collections import defaultdict
from pathlib import Path
from typing import Final

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger: Final = logging.getLogger(__name__)

_SUBWAY_DIR: Final = Path("data/validated/ttc_subway")
_BUS_DIR: Final = Path("data/validated/ttc_bus")
_STREETCAR_DIR: Final = Path("data/validated/ttc_streetcar")
_OUTPUT_FILE: Final = Path("seeds/ttc_delay_codes.csv")

_OUTPUT_COLUMNS: Final[list[str]] = [
    "delay_code",
    "delay_description",
    "delay_category",
]

_VALID_CATEGORIES: Final[frozenset[str]] = frozenset(
    {
        "Mechanical",
        "Signal",
        "Passenger",
        "Infrastructure",
        "Operations",
        "Weather",
        "Security",
        "General",
    }
)

# ---------------------------------------------------------------------------
# Category assignment by code prefix.
# First two characters of alphanumeric codes determine the category.
# ---------------------------------------------------------------------------
_PREFIX_CATEGORY: Final[dict[str, str]] = {
    # Subway (Unit)
    "MU": "Mechanical",
    "PU": "Passenger",
    "SU": "Security",
    "EU": "Infrastructure",
    "TU": "Operations",
    # Scarborough RT (retired Line 3)
    "MR": "Mechanical",
    "PR": "Passenger",
    "SR": "Security",
    "ER": "Infrastructure",
    "TR": "Operations",
    # Bus/surface fleet (2025+)
    "MF": "Mechanical",
    "PF": "Passenger",
    "SF": "Security",
    "EF": "Infrastructure",
    "TF": "Operations",
    # Streetcar/track (2025+)
    "MT": "Mechanical",
    "PT": "Passenger",
    "ST": "Security",
    "ET": "Infrastructure",
    "TT": "Operations",
    # Streetcar general (rare)
    "NT": "General",
}

# Category for full-text incident descriptions (bus/streetcar 2020-2024)
_TEXT_CATEGORY: Final[dict[str, str]] = {
    "Cleaning": "Operations",
    "Cleaning - Disinfection": "Operations",
    "Cleaning - Unsanitary": "Operations",
    "Collision - TTC": "Operations",
    "Collision - TTC Involved": "Operations",
    "Diversion": "Operations",
    "Emergency Services": "Security",
    "General Delay": "General",
    "Held By": "Operations",
    "Investigation": "Security",
    "Late": "Operations",
    "Late Entering Service": "Operations",
    "Late Leaving Garage - Operator": "Operations",
    "Management": "Operations",
    "Mechanical": "Mechanical",
    "Operations": "Operations",
    "Operations - Operator": "Operations",
    "Overhead": "Infrastructure",
    "Rail/Switches": "Infrastructure",
    "Road Blocked - NON-TTC Collision": "Operations",
    "Securitty": "Security",
    "Security": "Security",
    "Utilized Off Route": "Operations",
    "Vision": "Operations",
}

# ---------------------------------------------------------------------------
# Suffix-to-description mapping.
# The suffix is the portion of the code after the 2-character prefix.
# Matched longest-first to handle overlapping suffixes.
# ---------------------------------------------------------------------------
_SUFFIX_DESC: Final[dict[str, str]] = {
    # Mechanical / Equipment suffixes
    "ATC": "Automatic Train Control Fault",
    "CL": "Collision",
    "CP": "Communication Problem",
    "D": "Door Malfunction",
    "DD": "Door Delay",
    "DV": "Diversion",
    "EC": "Emergency Communication",
    "ECD": "Emergency Communication Delay",
    "ESA": "Emergency Services Activity",
    "FM": "Fare Machine",
    "FS": "Fire Suppression",
    "GD": "General Delay",
    "HV": "HVAC Fault",
    "I": "Incident Investigation",
    "IE": "Incident Emergency",
    "IR": "Issue Reported",
    "IS": "In Service Delay",
    "LT": "Light Failure",
    "LV": "Lost Vehicle",
    "ME": "Mechanical Equipment Failure",
    "NCA": "No Car Available",
    "NIP": "No Issue Found on Inspection",
    "NOA": "Operator Not Assigned",
    "O": "Other",
    "ODC": "Operator Door Control",
    "OE": "Operator Error",
    "OI": "Operator Incident",
    "PAA": "Passenger Alarm Activation",
    "PI": "Personnel Incident",
    "PLA": "Platform Alarm Level A",
    "PLB": "Platform Alarm Level B",
    "PLC": "Platform Alarm Level C",
    "POL": "Police Activity",
    "PR1": "Protocol Level 1",
    "R1": "Protocol Level 1",
    "ROB": "Road Obstruction",
    "S": "Short Turn",
    "SA": "Safety Alert",
    "SAN": "Sanitation",
    "SC": "Speed Control Restriction",
    "SH": "Short Turn Delay",
    "SUP": "Supervision Delay",
    "SW": "Switch Failure",
    "TD": "Track Defect",
    "TM": "Timing Equipment",
    "TO": "Turn Out Delay",
    "TP": "Track/Platform Issue",
    "TR": "Track Related",
    "TRD": "Track Restriction/Defect",
    "UR": "Unauthorized Use of Roadway",
    "US": "Unscheduled Stoppage",
    "VA": "Vehicle Assignment Delay",
    "VC": "Vehicle/Car Issue",
    "VE": "Vehicle Equipment",
    "VIS": "Vision Enforcement",
    "WEA": "Weather",
    "WR": "Work/Reconstruction Zone",
    "WS": "Work Zone Safety",
    "YRD": "Yard Delay",
    # Passenger-specific suffixes
    "MEL": "Medical Emergency",
    "MO": "Passenger Medical Other",
    "MST": "Missed Short Turn",
    "OPO": "Operator Passed Station",
    "EO": "Employee/Operator Incident",
    "EWZ": "Emergency Work Zone",
    "SWZ": "Switch Work Zone",
    "TWZ": "Track Work Zone",
    "SCA": "Security Alarm",
    "SCR": "Platform Edge Door",
    "SIO": "Security Incident Other",
    "SIS": "Security Incident Serious",
    "SNT": "Security Not Tracked",
    "SO": "Security Other",
    "SRA": "Security Response Activity",
    "SSW": "Security Switch Alarm",
    "STC": "Short Turn Control",
    "STP": "Security Track/Platform",
    "STS": "Security Threat Serious",
    "TIJ": "Trespasser Injury",
    "TIS": "Trespasser Incident Serious",
    "TOE": "Track Operator Error",
    "TSC": "Train Service Control",
    "TSM": "Train Schedule Management",
    "TTC": "Transit Traffic Control",
    "TTP": "Track/Platform Delay",
    "DN": "System Down",
    "DCS": "Door Control System",
    "CBI": "Cab Issue",
    "CBT": "Cab Trouble",
    "EME": "Emergency",
    "AC": "Air Conditioning",
    "AL": "Alarm",
    "CA": "Communication Alarm",
    "RD": "Route Delay",
    "AX": "Alarm External",
    "AF": "After Schedule",
    "AFR": "After Run",
    "CO": "Control Issue",
    "CM": "Communication",
    "DB": "Door Brake",
    "DS": "Door Sensor",
    "FA": "Fire Alarm",
    "BO": "Breakdown",
    "BK": "Brake Fault",
    "CD": "Communication Delay",
    "CE": "Car Equipment",
    "NT": "Not Tracked",
    "RA": "Route Assignment",
    "SE": "Safety Equipment",
    "AE": "Alarm Escalator",
    "AP": "Alarm Platform",
    "BT": "Bomb Threat",
    "DP": "Disorderly Patron",
    "EAS": "Early Access Shutdown",
    "G": "General",
    "UT": "Unauthorized Track Access",
    "COL": "Collision",
    "OB": "Obstruction",
    "ML": "Main Line Issue",
    "CC": "Crew Change",
    "DOE": "Door Opening Error",
    "MVS": "Missing Vehicle/Service",
    "KEY": "Key Management Issue",
    "PD": "Platform Door",
    "FD": "Fire Department Activity",
    "LD": "Late Departure",
    "LF": "Late Finish",
    "LL": "Late Leaving",
    "PF": "Platform Fault",
    "NO": "Not Operational",
    "NF": "Not Found",
    "SET": "Service Entering Track",
    "ST": "Short Turn",
    "CN": "Communication Network",
    "CAN": "Cancellation",
    "SP": "Speed",
}

# Prefix to descriptive label for the mode/type
_PREFIX_LABEL: Final[dict[str, str]] = {
    "MU": "Mechanical",
    "PU": "Passenger",
    "SU": "Security",
    "EU": "Equipment",
    "TU": "Train Operations",
    "MR": "SRT Mechanical",
    "PR": "SRT Passenger",
    "SR": "SRT Security",
    "ER": "SRT Equipment",
    "TR": "SRT Operations",
    "MF": "Fleet Mechanical",
    "PF": "Fleet Passenger",
    "SF": "Fleet Security",
    "EF": "Fleet Equipment",
    "TF": "Fleet Operations",
    "MT": "Streetcar Mechanical",
    "PT": "Streetcar Passenger",
    "ST": "Streetcar Security",
    "ET": "Streetcar Equipment",
    "TT": "Streetcar Operations",
    "NT": "Streetcar General",
}

# Hardcoded overrides for codes where mnemonic inference is insufficient
_DESC_OVERRIDES: Final[dict[str, str]] = {
    "MUPAA": "Passenger Alarm Activation",
    "PUOPO": "Passenger Overrun Platform",
    "PUMEL": "Passenger Medical Emergency",
    "PUMO": "Passenger Medical Other",
    "PUMST": "Missed Short Turn",
    "SUDP": "Disorderly Patron",
    "SUO": "Security Other",
    "SUG": "Security Guard Activity",
    "SUAE": "Alarm - Escalator",
    "SUAP": "Alarm - Platform",
    "SUBT": "Bomb Threat",
    "SUUT": "Unauthorized Track Access",
    "SUEAS": "Early Access Shutdown",
    "SUPOL": "Police Activity",
    "SUROB": "Road Obstruction",
    "SUSA": "Security Safety Alert",
    "SUSP": "Security Speed",
    "SUCOL": "Collision",
    "EUSC": "Speed Control Restriction",
    "EUDO": "Door Equipment Malfunction",
    "EUBK": "Brake Equipment Fault",
    "EUBO": "Equipment Breakdown",
    "EUCD": "Communication Equipment Delay",
    "EUNT": "Equipment Not Tracked",
    "EUCA": "Communication Alarm",
    "EUAC": "Air Conditioning Equipment",
    "EUAL": "Equipment Alarm",
    "EUATC": "Automatic Train Control Equipment",
    "EUCO": "Equipment Control Issue",
    "EUHV": "HVAC Equipment Fault",
    "EULT": "Light Equipment Failure",
    "EULV": "Lost Vehicle",
    "EUME": "Mechanical Equipment Failure",
    "EUNEA": "Equipment Not Expected Activity",
    "EUOE": "Operator Equipment Error",
    "EUPI": "Personnel Incident - Equipment",
    "EUTAC": "Track Auto Control Equipment",
    "EUTL": "Track Light Equipment",
    "EUTM": "Timing Equipment",
    "EUTR": "Track Related Equipment",
    "EUTRD": "Track Restriction Defect",
    "EUVA": "Vehicle Assignment Delay",
    "EUVE": "Vehicle Equipment Issue",
    "EUYRD": "Yard Departure Delay",
    "EUECD": "Emergency Communication Delay",
    "TUSC": "Speed Control - Train",
    "TUO": "Train Operations - Other",
    "TUMVS": "Missing Vehicle/Service",
    "TUNCA": "No Car Available",
    "TUNOA": "Train Crew Not Assigned",
    "TUCC": "Crew Change Delay",
    "TUKEY": "Key Management Issue",
    "TUML": "Main Line Delay",
    "TUATC": "Automatic Train Control - Train",
    "TUNIP": "No Issue Found on Inspection",
    "TUOS": "Operational Speed Restriction",
    "TUS": "Train Service Delay",
    "TUSUP": "Supervision Delay",
    "TUSET": "Service Entering Track Delay",
    "TUST": "Short Turn - Train",
    "TUDOE": "Door Opening Error - Train",
    "TUUR": "Unauthorized Run",
    "MUSAN": "Sanitation Issue",
    "MUATC": "Automatic Train Control - Mechanical",
    "MUCL": "Collision - Mechanical",
    "MUCP": "Communication Problem",
    "MUD": "Door Malfunction",
    "MUDD": "Door Delay",
    "MUEC": "Emergency Communication",
    "MUESA": "Emergency Services - Mechanical",
    "MUFM": "Fare Machine Malfunction",
    "MUFS": "Fire Suppression System",
    "MUGD": "General Delay - Mechanical",
    "MUI": "Mechanical Incident",
    "MUIE": "Incident Emergency",
    "MUIR": "Issue Reported",
    "MUIRS": "In-Service Issue Reported",
    "MUIS": "In-Service Delay",
    "MUNCA": "No Car Available - Mechanical",
    "MUNOA": "Operator Not Assigned",
    "MUO": "Mechanical Other",
    "MUODC": "Operator Door Control Issue",
    "MUPF": "Platform Fault - Mechanical",
    "MUPLA": "Platform Alarm Level A",
    "MUPLB": "Platform Alarm Level B",
    "MUPLC": "Platform Alarm Level C",
    "MUPR1": "Protocol Level 1 Mechanical",
    "MUSC": "Speed Control - Mechanical",
    "MUTD": "Track Defect - Mechanical",
    "MUTO": "Turn Out Delay",
    "MUWEA": "Weather - Mechanical Impact",
    "MUWR": "Work Zone - Mechanical",
    "PUATC": "Automatic Train Control - Passenger",
    "PUCBI": "Cab Issue - Passenger",
    "PUCSC": "Platform Edge Door - Passenger",
    "PUCSS": "Station Security Screen",
    "PUDCS": "Door Control System - Passenger",
    "PUEME": "Emergency - Passenger",
    "PUEO": "Employee/Operator - Passenger",
    "PUEWZ": "Emergency Work Zone - Passenger",
    "PUSAC": "Security Activity - Passenger",
    "PUSBE": "Switch Blade - Passenger",
    "PUSCA": "Security Alarm - Passenger",
    "PUSCR": "Platform Edge Door Issue",
    "PUSI": "Passenger Incident",
    "PUSIO": "Security Incident - Passenger",
    "PUSIS": "Security Incident Serious - Passenger",
    "PUSNT": "Security Not Tracked",
    "PUSO": "Passenger Security Other",
    "PUSRA": "Security Response - Passenger",
    "PUSSW": "Security Switch - Passenger",
    "PUSTC": "Short Turn Control - Passenger",
    "PUSTP": "Security Platform - Passenger",
    "PUSTS": "Security Threat - Passenger",
    "PUSWZ": "Switch Work Zone - Passenger",
    "PUSZC": "Security Zone - Passenger",
    "PUTCD": "Track Circuit Delay - Passenger",
    "PUTD": "Track Delay - Passenger",
    "PUTDN": "Passenger Hold Down",
    "PUTIJ": "Trespasser Injury",
    "PUTIS": "Trespasser Incident Serious",
    "PUTNT": "Not Tracked - Passenger",
    "PUTO": "Passenger Turn Out Delay",
    "PUTOE": "Track Operator Error - Passenger",
    "PUTR": "Track Related - Passenger",
    "PUTS": "Short Turn - Passenger",
    "PUTSC": "Train Service Control - Passenger",
    "PUTSM": "Train Schedule - Passenger",
    "PUTTC": "Transit Control - Passenger",
    "PUTTP": "Track/Platform - Passenger",
    "PUTWZ": "Track Work Zone - Passenger",
    "XXXXX": "Unknown/Placeholder Code",
    "MFO": "Mechanical Other - Fleet",
    "SRO": "Security Response Other",
    "PREL": "Presto/Fare Equipment",
    # Bus/streetcar 2025 codes
    "MFDV": "Diversion - Fleet",
    "MFESA": "Emergency Services - Fleet",
    "MFFD": "Fire Department Activity - Fleet",
    "MFLD": "Late Departure - Fleet",
    "MFPI": "Personnel Incident - Fleet",
    "MFPR": "Protocol Response - Fleet",
    "MFS": "Short Turn - Fleet",
    "MFSAN": "Sanitation - Fleet",
    "MFSH": "Short Turn/Halt - Fleet",
    "MFTO": "Turn Out Delay - Fleet",
    "MFUI": "Vehicle Incident - Fleet",
    "MFUIR": "Issue Reported - Fleet",
    "MFUS": "Vehicle Stoppage - Fleet",
    "MFVIS": "Vision Enforcement - Fleet",
    "MFWEA": "Weather Delay - Fleet",
    "EFB": "Equipment Breakdown - Fleet",
    "EFCAN": "Cancellation - Fleet",
    "EFD": "Door Equipment - Fleet",
    "EFHVA": "HVAC Equipment - Fleet",
    "EFO": "Equipment Other - Fleet",
    "EFP": "Platform Equipment - Fleet",
    "EFRA": "Route Assignment - Fleet",
    "ETO": "Equipment Other - Streetcar",
    "SFAE": "Alarm Escalator - Fleet",
    "SFAP": "Alarm Platform - Fleet",
    "SFDP": "Disorderly Patron - Fleet",
    "SFO": "Security Other - Fleet",
    "SFPOL": "Police Activity - Fleet",
    "SFSA": "Security Alert - Fleet",
    "SFSP": "Security Speed - Fleet",
    "TFCNO": "Traffic Control No Operator",
    "TFLF": "Late Finish - Fleet",
    "TFLL": "Late Leaving - Fleet",
    "TFO": "Traffic Operations Other - Fleet",
    "TFOI": "Operations Incident - Fleet",
    "TFPD": "Platform Door - Fleet",
    "TFPI": "Personnel Incident - Fleet",
    "PFO": "Passenger Other - Fleet",
    "PFPD": "Platform Door - Passenger Fleet",
    "MTAFR": "After Run Delay",
    "MTCL": "Collision - Streetcar",
    "MTDV": "Diversion - Streetcar",
    "MTEC": "Emergency Communication - Streetcar",
    "MTESA": "Emergency Services - Streetcar",
    "MTGD": "General Delay - Streetcar",
    "MTIE": "Incident Emergency - Streetcar",
    "MTNOA": "Operator Not Assigned - Streetcar",
    "MTO": "Mechanical Other - Streetcar",
    "MTPI": "Personnel Incident - Streetcar",
    "MTPOL": "Police Activity - Streetcar",
    "MTPR": "Protocol Response - Streetcar",
    "MTPU": "Passenger Unit - Streetcar",
    "MTS": "Short Turn - Streetcar",
    "MTSAN": "Sanitation - Streetcar",
    "MTTD": "Track Defect - Streetcar",
    "MTTO": "Turn Out Delay - Streetcar",
    "MTTP": "Track/Platform - Streetcar",
    "MTUI": "Vehicle Incident - Streetcar",
    "MTUIR": "Issue Reported - Streetcar",
    "MTUS": "Vehicle Stoppage - Streetcar",
    "MTVIS": "Vision Enforcement - Streetcar",
    "MTWEA": "Weather Delay - Streetcar",
    "MTWR": "Work Zone - Streetcar",
    "NTGD": "General Delay - Not Tracked",
    "STAE": "Alarm Escalator - Streetcar",
    "STAP": "Alarm Platform - Streetcar",
    "STDP": "Disorderly Patron - Streetcar",
    "STO": "Security Other - Streetcar/Fleet",
    "STSA": "Security Alert - Streetcar",
    "STSP": "Security Speed - Streetcar",
    "ETAC": "Air Conditioning - Streetcar",
    "ETAX": "Alarm External - Streetcar",
    "ETBO": "Breakdown - Streetcar",
    "ETCE": "Car Equipment - Streetcar",
    "ETCM": "Communication - Streetcar",
    "ETCO": "Control Issue - Streetcar",
    "ETDB": "Door Brake - Streetcar",
    "ETDO": "Door Equipment - Streetcar",
    "ETDS": "Door Sensor - Streetcar",
    "ETFA": "Fire Alarm - Streetcar",
    "ETHV": "HVAC - Streetcar",
    "ETLT": "Light Failure - Streetcar",
    "ETLV": "Lost Vehicle - Streetcar",
    "ETNEA": "Not Expected Activity - Streetcar",
    "ETNT": "Not Tracked - Streetcar",
    "ETPI": "Personnel Incident - Streetcar",
    "ETRA": "Route Assignment - Streetcar",
    "ETSA": "Safety Alert - Streetcar",
    "ETSE": "Safety Equipment - Streetcar",
    "ETTB": "Track Brake - Streetcar",
    "ETTM": "Timing Equipment - Streetcar",
    "ETTR": "Track Related - Streetcar",
    "ETVC": "Vehicle/Car Issue - Streetcar",
    "ETVE": "Vehicle Equipment - Streetcar",
    "ETWA": "Weather Alert - Streetcar",
    "ETWS": "Work Zone Safety - Streetcar",
    "PTNTF": "Not Tracked - Fare",
    "PTO": "Passenger Other - Streetcar",
    "PTOV": "Passenger Overshoot - Streetcar",
    "PTPD": "Platform Door - Streetcar",
    "PTSE": "Safety Equipment - Passenger Streetcar",
    "PTSW": "Switch Delay - Passenger Streetcar",
    "PTW": "Weather - Passenger Streetcar",
    "PTNT": "Not Tracked - Passenger Streetcar",
    "TTO": "Traffic Operations - Streetcar",
    "TTOI": "Operations Incident - Streetcar",
    "TTPD": "Platform Door - Streetcar",
    "TTPI": "Personnel Incident - Streetcar",
    "TTLF": "Late Finish - Streetcar",
    "TTLL": "Late Leaving - Streetcar",
    "TTSUP": "Supervision - Streetcar",
    "TTSW": "Switch Delay - Streetcar",
    "TTUS": "Unscheduled Stoppage - Streetcar",
    # SRT codes
    "MRO": "Mechanical Other - SRT",
    "MRPAA": "Passenger Alarm Activation - SRT",
    "MRTO": "Turn Out Delay - SRT",
    "MRUI": "Vehicle Incident - SRT",
    "MRUIR": "Issue Reported - SRT",
    "MRWEA": "Weather - SRT",
    "MRCL": "Collision - SRT",
    "MRD": "Door Malfunction - SRT",
    "MRDD": "Door Delay - SRT",
    "MRFS": "Fire Suppression - SRT",
    "MRIE": "Incident Emergency - SRT",
    "MRNOA": "Operator Not Assigned - SRT",
    "MRPLA": "Platform Alarm Level A - SRT",
    "MRPLB": "Platform Alarm Level B - SRT",
    "MRPLC": "Platform Alarm Level C - SRT",
    "MRSAN": "Sanitation - SRT",
    "MRSTM": "Timing Equipment - SRT",
    "PRO": "Passenger Other - SRT",
    "PRS": "Short Turn - SRT",
    "PRSA": "Safety Alert - SRT",
    "PRSL": "Schedule/Line Delay - SRT",
    "PRSO": "Security Other - SRT",
    "PRSP": "Speed Restriction - SRT",
    "PRST": "Short Turn - SRT",
    "PRSW": "Switch Delay - SRT",
    "PRW": "Weather - SRT Passenger",
    "SRAE": "Alarm Escalator - SRT",
    "SRAP": "Alarm Platform - SRT",
    "SRDP": "Disorderly Patron - SRT",
    "SREAS": "Early Access Shutdown - SRT",
    "SRSA": "Security Alert - SRT",
    "SRUT": "Unauthorized Track Access - SRT",
    "ERAC": "Air Conditioning - SRT",
    "ERBO": "Breakdown - SRT",
    "ERCD": "Communication Delay - SRT",
    "ERCO": "Control Issue - SRT",
    "ERDB": "Door Brake - SRT",
    "ERDO": "Door Equipment - SRT",
    "ERHV": "HVAC - SRT",
    "ERLV": "Lost Vehicle - SRT",
    "ERME": "Mechanical Equipment - SRT",
    "ERNEA": "Not Expected Activity - SRT",
    "ERNT": "Not Tracked - SRT",
    "ERO": "Equipment Other - SRT",
    "ERPR": "Protocol Response - SRT",
    "ERRA": "Route Assignment - SRT",
    "ERTB": "Track Brake - SRT",
    "ERTC": "Track Circuit - SRT",
    "ERTL": "Track Light - SRT",
    "ERTR": "Track Related - SRT",
    "ERWA": "Weather Alert - SRT",
    "ERWS": "Work Zone Safety - SRT",
    "TRNCA": "No Car Available - SRT",
    "TRNIP": "No Issue Found - SRT",
    "TRNOA": "Crew Not Assigned - SRT",
    "TRO": "Operations Other - SRT",
    "TRSET": "Service Entering Track - SRT",
    "TRST": "Short Turn - SRT",
    "TRTC": "Transit Control - SRT",
}


_CODE_CATEGORY_OVERRIDES: Final[dict[str, str]] = {
    "PREL": "Infrastructure",  # Presto fare equipment, not passenger-related
    "PTW": "Weather",  # Passenger streetcar weather
    "PRW": "Weather",  # SRT passenger weather
}


def _extract_codes(
    data_dir: Path,
    column_name: str,
) -> dict[str, int]:
    """Extract distinct values from a column across all CSVs in directory.

    Returns a dictionary mapping code values to occurrence counts.
    """
    counts: dict[str, int] = defaultdict(int)
    csv_files = sorted(data_dir.rglob("*.csv"))

    for csv_path in csv_files:
        with csv_path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                value = row.get(column_name, "").strip()
                if value:
                    counts[value] += 1

    return dict(counts)


def _get_category(code: str) -> str:
    """Determine delay category from code prefix or text mapping.

    Suffix-based overrides take precedence over prefix defaults to
    correctly classify cross-cutting concerns like weather and signaling.
    """
    # Text descriptions (bus/streetcar 2020-2024)
    if code in _TEXT_CATEGORY:
        return _TEXT_CATEGORY[code]

    # Specific code-level overrides
    if code in _CODE_CATEGORY_OVERRIDES:
        return _CODE_CATEGORY_OVERRIDES[code]

    # Suffix-based overrides (cross-cutting concerns)
    if len(code) >= 2:
        suffix = code[2:]
        # Weather-related suffixes → Weather category
        # WEA = Weather, WA = Weather Alert; WS = Work Zone Safety (NOT weather)
        if suffix in ("WEA", "WA"):
            return "Weather"
        # ATC (Automatic Train Control) = signal system
        if suffix in ("ATC",):
            return "Signal"

    # Alphanumeric codes — check prefix
    if len(code) >= 2:
        prefix = code[:2]
        if prefix in _PREFIX_CATEGORY:
            return _PREFIX_CATEGORY[prefix]

    return "General"


def _get_description(code: str) -> str:
    """Generate a human-readable description for a delay code.

    Priority: explicit override > text code (self-describing) > suffix match.
    """
    # Explicit override
    if code in _DESC_OVERRIDES:
        return _DESC_OVERRIDES[code]

    # Text codes are self-describing
    if code in _TEXT_CATEGORY:
        return code

    # Derive from prefix label + suffix
    if len(code) >= 2:
        prefix = code[:2]
        suffix = code[2:]
        prefix_label = _PREFIX_LABEL.get(prefix, "")

        if not suffix:
            return f"{prefix_label} - General" if prefix_label else code

        # Try longest suffix match first
        for length in range(len(suffix), 0, -1):
            candidate = suffix[:length]
            if candidate in _SUFFIX_DESC:
                return _SUFFIX_DESC[candidate]

        if prefix_label:
            return f"{prefix_label} - Code {suffix}"

    return code


def main() -> None:
    """Extract delay codes and generate seed CSV."""
    # Extract codes from all three modes
    logger.info("Extracting subway delay codes (Code column)...")
    subway_codes = _extract_codes(_SUBWAY_DIR, "Code")
    logger.info("  Found %d distinct subway codes", len(subway_codes))

    logger.info("Extracting bus delay codes (Incident column)...")
    bus_codes = _extract_codes(_BUS_DIR, "Incident")
    logger.info("  Found %d distinct bus codes", len(bus_codes))

    logger.info("Extracting streetcar delay codes (Incident column)...")
    streetcar_codes = _extract_codes(_STREETCAR_DIR, "Incident")
    logger.info("  Found %d distinct streetcar codes", len(streetcar_codes))

    # Merge all codes
    all_codes: dict[str, int] = defaultdict(int)
    for codes in (subway_codes, bus_codes, streetcar_codes):
        for code, count in codes.items():
            all_codes[code] += count

    logger.info("Total distinct codes across all modes: %d", len(all_codes))

    # Generate rows
    rows: list[list[str]] = []
    for code in sorted(all_codes):
        category = _get_category(code)
        description = _get_description(code)

        if category not in _VALID_CATEGORIES:
            logger.error("Invalid category '%s' for code '%s'", category, code)
            sys.exit(1)

        rows.append([code, description, category])

    # Write output
    _OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _OUTPUT_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(_OUTPUT_COLUMNS)
        writer.writerows(rows)

    logger.info("Wrote %d rows to %s", len(rows), _OUTPUT_FILE)

    # Category distribution
    cat_counts: dict[str, int] = defaultdict(int)
    for row in rows:
        cat_counts[row[2]] += 1
    for cat in sorted(cat_counts):
        logger.info("  %s: %d codes", cat, cat_counts[cat])


if __name__ == "__main__":
    main()
