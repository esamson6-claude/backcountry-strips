"""Import backcountry-relevant airport/runway records from FAA NASR CSV data.

FAA NASR (National Airspace System Resources) publishes airport data every
28-day AIRAC cycle as a CSV package. This module downloads the current
cycle's APT CSV zip, and extracts runways with unpaved surfaces (turf,
dirt, gravel) plus their parent airport's base facts, since those are the
runways relevant to backcountry flying.

Public domain (U.S. government work) -- no attribution/license restriction.
"""

import csv
import io
import re
import zipfile
from datetime import date

import requests

from schema import blank_record

NASR_INDEX_URL = "https://www.faa.gov/air_traffic/flight_info/aeronav/aero_data/NASR_Subscription/"
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

# Surface codes (APT_RWY.SURFACE_TYPE_CODE) that indicate an unimproved /
# backcountry-relevant runway. Matches if the code contains any of these
# as a hyphen-separated component (e.g. "TURF-GRVL", "ASPH-TURF").
UNPAVED_SURFACE_MARKERS = {"TURF", "DIRT", "GRVL", "GRAVEL", "SAND", "SOD"}


def _current_cycle_csv_url():
    """Find the current NASR cycle's APT CSV zip download URL."""
    resp = requests.get(NASR_INDEX_URL, headers=BROWSER_HEADERS, timeout=30)
    resp.raise_for_status()
    cycles = sorted(set(re.findall(r"NASR_Subscription/(\d{4}-\d{2}-\d{2})", resp.text)))
    if not cycles:
        raise RuntimeError("could not find any NASR cycle dates on the index page")

    today = date.today().isoformat()
    current_cycle = max((c for c in cycles if c <= today), default=cycles[0])

    cycle_url = f"{NASR_INDEX_URL}{current_cycle}/"
    resp = requests.get(cycle_url, headers=BROWSER_HEADERS, timeout=30)
    resp.raise_for_status()
    match = re.search(r'href="(https://nfdc\.faa\.gov/webContent/28DaySub/extra/[^"]*_APT_CSV\.zip)"', resp.text)
    if not match:
        raise RuntimeError(f"could not find APT CSV zip link on {cycle_url}")
    return match.group(1), current_cycle


def _download_apt_csvs():
    """Download the current cycle's APT CSV zip and return parsed CSV dicts."""
    url, cycle = _current_cycle_csv_url()
    resp = requests.get(url, headers=BROWSER_HEADERS, timeout=120)
    resp.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        base_rows = list(csv.DictReader(io.TextIOWrapper(zf.open("APT_BASE.csv"), encoding="utf-8-sig")))
        rwy_rows = list(csv.DictReader(io.TextIOWrapper(zf.open("APT_RWY.csv"), encoding="utf-8-sig")))

    return base_rows, rwy_rows, cycle


def _is_unpaved(surface_code):
    if not surface_code:
        return False
    parts = surface_code.upper().split("-")
    return any(p in UNPAVED_SURFACE_MARKERS for p in parts)


def fetch():
    """Return a list of backcountry-relevant strip records from FAA NASR data."""
    base_rows, rwy_rows, cycle = _download_apt_csvs()
    base_by_site = {row["SITE_NO"]: row for row in base_rows}

    records = []
    for rwy in rwy_rows:
        if not _is_unpaved(rwy.get("SURFACE_TYPE_CODE")):
            continue

        base = base_by_site.get(rwy["SITE_NO"])
        if base is None:
            continue

        record = blank_record()
        record.update(
            {
                "identifier": base.get("ARPT_ID") or None,
                "name": base.get("ARPT_NAME") or None,
                "state": base.get("STATE_CODE") or None,
                "latitude": _to_float(base.get("LAT_DECIMAL")),
                "longitude": _to_float(base.get("LONG_DECIMAL")),
                "elevation_ft": _to_float(base.get("ELEV")),
                "runway_length_ft": _to_float(rwy.get("RWY_LEN")),
                "runway_width_ft": _to_float(rwy.get("RWY_WIDTH")),
                "runway_surface": rwy.get("SURFACE_TYPE_CODE") or None,
                "runway_orientation": rwy.get("RWY_ID") or None,
                "ownership": _ownership(base.get("OWNERSHIP_TYPE_CODE")),
                "source": "faa_nasr",
                "source_url": None,
                "attribution": None,  # public domain, no attribution required
                "last_updated": cycle,
            }
        )
        records.append(record)

    return records


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _ownership(code):
    return {"PU": "public", "PR": "private"}.get((code or "").upper())


if __name__ == "__main__":
    rows = fetch()
    print(f"{len(rows)} unpaved-surface runway records")
    for r in rows[:5]:
        print(r)
