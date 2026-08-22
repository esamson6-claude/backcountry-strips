"""Merge strip records from multiple sources into one row per strip.

Records are grouped by identifier (FAA LID, when present) since that's the
most reliable join key across sources -- state GIS layers and FAA NASR both
use it. Records without an identifier are grouped by rounded coordinates
instead.

Within a group, official facts (coordinates, elevation, runway length/width/
surface) prefer FAA NASR as the authoritative source, falling back to state
GIS sources when FAA lacks the field. Enrichment fields (hazards, access
notes, condition notes, trip reports) are concatenated across sources so no
source's local knowledge is lost, each tagged with its origin.

Source priority for official facts, highest first:
    faa_nasr > idaho_itd > montana_mdt > (future: ubcp, shortfield)
"""

from schema import FIELDS, blank_record

OFFICIAL_FACT_FIELDS = [
    "name",
    "state",
    "latitude",
    "longitude",
    "elevation_ft",
    "runway_length_ft",
    "runway_width_ft",
    "runway_surface",
    "runway_orientation",
    "ownership",
    "ctaf_frequency",
]

ENRICHMENT_FIELDS = [
    "hazards",
    "access_notes",
    "nearby_amenities",
    "condition_notes",
    "trip_reports_url",
]

SOURCE_PRIORITY = ["faa_nasr", "idaho_itd", "montana_mdt", "ubcp", "shortfield"]


def _source_rank(record):
    source = record.get("source")
    return SOURCE_PRIORITY.index(source) if source in SOURCE_PRIORITY else len(SOURCE_PRIORITY)


def _group_key(record):
    identifier = (record.get("identifier") or "").strip().upper()
    if identifier:
        return ("id", identifier)

    lat, lon = record.get("latitude"), record.get("longitude")
    if lat is not None and lon is not None:
        return ("coord", round(lat, 2), round(lon, 2))

    return ("name", (record.get("name") or "").strip().upper())


def _merge_group(records):
    records = sorted(records, key=_source_rank)
    merged = blank_record()

    for field in OFFICIAL_FACT_FIELDS:
        for record in records:
            if record.get(field) not in (None, ""):
                merged[field] = record[field]
                break

    for field in ENRICHMENT_FIELDS:
        parts = []
        for record in records:
            value = record.get(field)
            if value not in (None, ""):
                parts.append(f"[{record.get('source')}] {value}")
        merged[field] = " | ".join(parts) if parts else None

    merged["identifier"] = next(
        (r["identifier"] for r in records if r.get("identifier")), None
    )
    merged["sources"] = sorted({r.get("source") for r in records if r.get("source")})
    merged["source"] = "+".join(merged["sources"])

    # Prefer a source_url from a record that actually carries an attribution,
    # so the displayed link and credit line refer to the same source.
    attributed_records = [r for r in records if r.get("attribution")]
    url_source = attributed_records[0] if attributed_records else records[0]
    merged["source_url"] = url_source.get("source_url")

    attributions = sorted({r["attribution"] for r in records if r.get("attribution")})
    merged["attribution"] = "; ".join(attributions) if attributions else None

    merged["last_updated"] = max(
        (r["last_updated"] for r in records if r.get("last_updated")),
        default=None,
    )

    return merged


def merge(*record_lists):
    """Merge multiple lists of strip records into one deduped list."""
    groups = {}
    for records in record_lists:
        for record in records:
            key = _group_key(record)
            groups.setdefault(key, []).append(record)

    return [_merge_group(group) for group in groups.values()]


if __name__ == "__main__":
    import import_faa
    from scrapers import idaho, montana, shortfield, ubcp

    merged = merge(
        import_faa.fetch(),
        idaho.fetch(),
        montana.fetch(),
        ubcp.fetch(),
        shortfield.fetch(),
    )
    print(f"{len(merged)} merged strip records")

    multi_source = [r for r in merged if len(r["sources"]) > 1]
    print(f"{len(multi_source)} strips matched across multiple sources")
    for r in multi_source[:5]:
        print(r)
