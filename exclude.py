"""Filter out strips whose source notes explicitly say not to land without
the owner's permission, or otherwise flag the strip as closed to visitors.

Most private-ownership strips are NOT excluded here -- FAA and other
sources routinely mark small privately-owned airstrips as "private" simply
as an ownership fact, and many of those explicitly welcome visitors in
their notes (e.g. a strip owner who "welcomes visitors who would like to
take a minute and chat"). Only strips whose notes contain an explicit
do-not-land / permission-required / no-trespassing signal are dropped.

This is a blunt regex pass, not a legal read of each strip's actual access
policy -- when in doubt, a strip stays in rather than being silently
dropped. Review PERMISSION_REQUIRED_PATTERNS periodically against new
source text rather than trying to make the pattern list exhaustive upfront.
"""

import re

PERMISSION_REQUIRED_PATTERNS = [
    r"do\s*not\s*land",
    r"don'?t\s*land",
    r"prior\s*permission",
    r"permission\s*required",
    r"permission\s*from\s*the\s*owner",
    r"without\s*(?:the\s*)?(?:owner'?s?\s*)?permission",
    r"no\s*trespassing",
    r"not\s*open\s*to\s*the\s*public",
    r"closed\s*to\s*(?:the\s*)?public",
]

_PATTERN = re.compile("|".join(PERMISSION_REQUIRED_PATTERNS), re.IGNORECASE)


def _permission_required(strip):
    text = " ".join(
        filter(None, [strip.get("condition_notes"), strip.get("access_notes"), strip.get("hazards")])
    )
    return bool(_PATTERN.search(text))


def remove_permission_required(strips):
    """Return (kept, excluded) -- excluded strips are the ones whose notes
    explicitly require permission or forbid landing."""
    kept, excluded = [], []
    for strip in strips:
        (excluded if _permission_required(strip) else kept).append(strip)
    return kept, excluded


# The 50 US states + DC. US territories (PR, VI, GU, MP, AS) are
# deliberately excluded per the project's US(+AK)+Canada scope.
US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS",
    "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK",
    "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV",
    "WI", "WY", "DC",
}

# Canadian provinces/territories, as they appear once import_canada.py
# strips the "CA-" prefix from OurAirports' iso_region field.
CANADA_PROVINCES = {
    "AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT",
}

# Rough bounding box for Canada -- used only as a fallback for records with a
# missing/unrecognized state/province code (e.g. FAA NASR's incidental
# Yukon-area entries, which carry no state field at all), so a real Canadian
# strip isn't dropped just because its source didn't populate that field.
_CANADA_LAT_RANGE = (41.0, 84.0)
_CANADA_LON_RANGE = (-141.0, -52.0)


def _in_scope(strip):
    state = (strip.get("state") or "").strip().upper()
    if state in US_STATES or state in CANADA_PROVINCES:
        return True
    if state:
        return False  # a real, recognized-format code for an out-of-scope place (PR, VI, etc.)

    lat, lon = strip.get("latitude"), strip.get("longitude")
    if lat is None or lon is None:
        return False
    return _CANADA_LAT_RANGE[0] <= lat <= _CANADA_LAT_RANGE[1] and _CANADA_LON_RANGE[0] <= lon <= _CANADA_LON_RANGE[1]


def remove_out_of_scope(strips):
    """Return (kept, excluded) -- keeps only strips in the 50 US states + DC
    or a Canadian province/territory. Drops US territories (Puerto Rico,
    Guam, etc.) and any other foreign strips (e.g. FAA data incidentally
    covers a handful of Pacific island airports)."""
    kept, excluded = [], []
    for strip in strips:
        (kept if _in_scope(strip) else excluded).append(strip)
    return kept, excluded
