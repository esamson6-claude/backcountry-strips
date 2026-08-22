"""Import Idaho airfield data from ITD Division of Aeronautics' ArcGIS layer.

This is the statewide "ITD Airport Facilities" directory (not filtered to
backcountry-only) -- it includes municipal, USFS, and private airfields.
merge.py cross-references against FAA NASR surface/identifier data; here we
just normalize the raw ArcGIS fields into strip records.

Public state government data -- no attribution/license restriction found.
"""

import re

import requests

from schema import blank_record

FEATURE_SERVER_URL = (
    "https://services1.arcgis.com/Qqv4dYPC8Vv8e3c3/arcgis/rest/services/"
    "ITD_Airport_Facilities/FeatureServer/0/query"
)


def fetch():
    params = {
        "where": "1=1",
        "outFields": "*",
        "outSR": "4326",
        "f": "json",
    }
    resp = requests.get(FEATURE_SERVER_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    records = []
    for feature in data.get("features", []):
        attrs = feature.get("attributes", {})
        geom = feature.get("geometry") or {}

        record = blank_record()
        record.update(
            {
                "identifier": attrs.get("FAA") or None,
                "name": attrs.get("AirfieldName") or attrs.get("Airfield_Name_PDF"),
                "state": "ID",
                "latitude": geom.get("y"),
                "longitude": geom.get("x"),
                "elevation_ft": attrs.get("AirportElevation"),
                "runway_length_ft": _first_number(attrs.get("RunwayLengthList")),
                "runway_width_ft": _first_number(attrs.get("RunwayWidthList")),
                "runway_surface": attrs.get("RunwaySurfaceTypeComb") or None,
                "runway_orientation": attrs.get("RunwayDesignatorList") or None,
                "ctaf_frequency": attrs.get("Frequency"),
                "access_notes": attrs.get("Airfield_Type") or None,
                "source": "idaho_itd",
                "source_url": "https://itd.idaho.gov/aero/backcountry-airports/",
                "attribution": None,
                "last_updated": None,
            }
        )
        records.append(record)

    return records


def _first_number(value):
    """RunwayLengthList/WidthList can be multi-runway strings like '3800,2200'."""
    if not value:
        return None
    match = re.search(r"\d+", str(value))
    return float(match.group()) if match else None


if __name__ == "__main__":
    rows = fetch()
    print(f"{len(rows)} Idaho airfield records")
    for r in rows[:3]:
        print(r)
