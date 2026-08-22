"""Import backcountry-relevant Canadian airport/runway records from
OurAirports' open data (airports.csv + runways.csv).

OurAirports is a global, community-maintained airport database. Its
airports.csv has no runway-surface field, so this joins in runways.csv
(keyed by airport id) and keeps only unpaved-surface runways -- the
same "unpaved implies backcountry-relevant" heuristic import_faa.py
uses for FAA data.

Public domain (explicit statement at ourairports.com/data/) -- no
attribution/license restriction, though OurAirports appreciates a credit.
"""

import csv
import io

import requests

from schema import blank_record

AIRPORTS_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
RUNWAYS_URL = "https://davidmegginson.github.io/ourairports-data/runways.csv"

# Matches import_faa.py's UNPAVED_SURFACE_MARKERS, extended with the messier
# variants OurAirports' community-submitted surface field actually contains
# (mixed case, abbreviations, compound values like "GRAVEL/TURF").
UNPAVED_SURFACE_MARKERS = {
    "TURF", "DIRT", "GRVL", "GRAVEL", "GVL", "GRS", "GRASS", "SAND", "SOD",
    "CRUSHED ROCK", "TREATED GRAVEL",
}


def _is_unpaved(surface):
    if not surface:
        return False
    parts = surface.upper().replace("/", "-").split("-")
    return any(p.strip() in UNPAVED_SURFACE_MARKERS for p in parts)


# OurAirports' `type` field distinguishes facility kind directly -- heliports
# and balloonports aren't backcountry airstrips regardless of surface.
EXCLUDED_AIRPORT_TYPES = {"heliport", "balloonport"}


def fetch():
    airports_resp = requests.get(AIRPORTS_URL, timeout=60)
    airports_resp.raise_for_status()
    runways_resp = requests.get(RUNWAYS_URL, timeout=60)
    runways_resp.raise_for_status()

    airports_by_id = {
        row["id"]: row
        for row in csv.DictReader(io.StringIO(airports_resp.text))
        if row.get("iso_country") == "CA"
    }
    runways = csv.DictReader(io.StringIO(runways_resp.text))

    records = []
    for rwy in runways:
        airport = airports_by_id.get(rwy.get("airport_ref"))
        if airport is None:
            continue
        if not _is_unpaved(rwy.get("surface")):
            continue
        if (airport.get("type") or "").lower() in EXCLUDED_AIRPORT_TYPES:
            continue

        record = blank_record()
        record.update(
            {
                "identifier": airport.get("ident") or None,
                "name": airport.get("name"),
                "state": (airport.get("iso_region") or "").replace("CA-", "") or None,
                "latitude": _to_float(airport.get("latitude_deg")),
                "longitude": _to_float(airport.get("longitude_deg")),
                "elevation_ft": _to_float(airport.get("elevation_ft")),
                "runway_length_ft": _to_float(rwy.get("length_ft")),
                "runway_width_ft": _to_float(rwy.get("width_ft")),
                "runway_surface": rwy.get("surface") or None,
                "runway_orientation": _orientation(rwy),
                "source": "ourairports_ca",
                "source_url": airport.get("home_link") or airport.get("wikipedia_link") or None,
                "attribution": None,  # public domain
                "last_updated": None,
            }
        )
        records.append(record)

    return records


def _orientation(rwy):
    le, he = rwy.get("le_ident"), rwy.get("he_ident")
    if le and he:
        return f"{le}/{he}"
    return le or he or None


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    rows = fetch()
    print(f"{len(rows)} Canadian unpaved-surface runway records")
    for r in rows[:5]:
        print(r)
