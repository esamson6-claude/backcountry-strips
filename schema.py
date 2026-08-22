"""Shared strip record schema.

Every importer/scraper module produces a list of dicts with (a subset of)
these fields. merge.py combines records from multiple sources into one row
per strip, preferring authoritative sources for official facts.
"""

FIELDS = [
    "identifier",       # FAA LID or state-assigned identifier, if any
    "name",
    "state",
    "latitude",
    "longitude",
    "elevation_ft",
    "runway_length_ft",
    "runway_width_ft",
    "runway_surface",   # e.g. turf, gravel, dirt, asphalt
    "runway_orientation",  # e.g. "17/35"
    "ownership",        # public, private, or unknown
    "ctaf_frequency",
    "hazards",          # free text: approach/departure hazards, density altitude notes
    "access_notes",     # permission needed, seasonal closures, etc.
    "nearby_amenities", # camping, fuel, water
    "condition_notes",  # free text, most recent known condition
    "trip_reports_url", # link to community discussion/reports, if any
    "source",           # which module produced this record (or "+"-joined after merge)
    "sources",          # list of source module names, populated by merge.py
    "source_url",       # link back to the source's page for this strip, if any
    "attribution",      # required attribution text for this record's source, if any
    "last_updated",     # date this record was last refreshed
]


def blank_record():
    return {field: None for field in FIELDS}
