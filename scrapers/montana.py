"""Import Montana public-use airport data from MDT Aeronautics' ArcGIS layer.

This layer only has identity/ownership/role fields -- no runway length,
width, or surface data. merge.py fills those in from FAA NASR by
identifier. Useful here mainly to confirm public-use status and surface
Montana airports not present (or misnamed) in other sources.

Public state government data -- no attribution/license restriction found.
"""

import requests

from schema import blank_record

MAP_SERVER_URL = "https://gis.mtmdt.us/server/rest/services/MDTGIS/Airports/MapServer/1/query"


def fetch():
    params = {
        "where": "1=1",
        "outFields": "*",
        "outSR": "4326",
        "f": "json",
    }
    resp = requests.get(MAP_SERVER_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    records = []
    for feature in data.get("features", []):
        attrs = feature.get("attributes", {})

        record = blank_record()
        record.update(
            {
                "identifier": attrs.get("IDENT") or None,
                "name": attrs.get("AIRPORT_NAME"),
                "state": "MT",
                "latitude": attrs.get("LATITUDE"),
                "longitude": attrs.get("LONGITUDE"),
                "ownership": (attrs.get("AIRPORT_OWNERSHIP") or "").lower() or None,
                "access_notes": attrs.get("AIRPORT_ROLE") or None,
                "condition_notes": attrs.get("COMMENT_") or None,
                "source": "montana_mdt",
                "source_url": attrs.get("MAP_LINK") or "https://www.mdt.mt.gov/aviation/",
                "attribution": None,
                "last_updated": None,
            }
        )
        records.append(record)

    return records


if __name__ == "__main__":
    rows = fetch()
    print(f"{len(rows)} Montana airport records")
    for r in rows[:3]:
        print(r)
