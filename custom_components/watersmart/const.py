"""Constants for the WaterSmart integration."""

from datetime import timedelta
from enum import StrEnum, auto
from typing import Final

ATTRIBUTION: Final = "Data scraped from WaterSmart"
DOMAIN: Final = "watersmart"
MANUFACTURER: Final = "WaterSmart by VertexOne"
DEFAULT_SCAN_INTERVAL = timedelta(hours=1)

# A leak is reported when the utility flagged hours with leak gallons within
# this window of the newest record, or when usage ran continuously for
# CONTINUOUS_FLOW_HOURS.
LEAK_LOOKBACK: Final = timedelta(hours=24)
CONTINUOUS_FLOW_HOURS: Final = 6


class SensorKey(StrEnum):
    """Converter key enumeration class."""

    GALLONS_FOR_MOST_RECENT_HOUR = auto()
    GALLONS_FOR_MOST_RECENT_FULL_DAY_KEY = auto()
    LEAK_DETECTED = auto()
