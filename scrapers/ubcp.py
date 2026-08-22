"""Import Utah backcountry airstrip data from the Utah Back Country Pilots
Association (UBCP) developer API.

UBCP's terms (https://utahbackcountrypilots.org/features, "Developer API"
section, as of 2026-08-21):

    "The UBCP API cannot be used for commercial purposes. Any data you
    consume from the API must be for personal use only, or made available
    for free to your users with a citation indicating that the UBCP is the
    origin of this data."

This project satisfies that by staying free/non-commercial and attributing
every UBCP-sourced record. Do not remove the attribution field for this
source, and do not put the generated site behind a paywall or ads without
re-checking these terms.
"""

import requests

from schema import blank_record

AIRSTRIPS_URL = "https://utahbackcountrypilots.org/api/airstrips"
ATTRIBUTION_TEXT = "Data courtesy of the Utah Back Country Pilots Association (utahbackcountrypilots.org)"

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}


def fetch():
    resp = requests.get(AIRSTRIPS_URL, headers=BROWSER_HEADERS, timeout=30)
    resp.raise_for_status()
    strips = resp.json()

    records = []
    for strip in strips:
        record = blank_record()
        record.update(
            {
                "identifier": strip.get("faa_id") or strip.get("waypoint_id") or None,
                "name": strip.get("title"),
                "state": _clean_state(strip.get("state")),
                "latitude": _to_float(strip.get("latitude")),
                "longitude": _to_float(strip.get("longitude")),
                "elevation_ft": _to_float(strip.get("elevation")),
                "runway_length_ft": _to_float(strip.get("runway_length")),
                "runway_width_ft": _to_float(strip.get("runway_width")),
                "runway_surface": strip.get("runway_surface") or None,
                "runway_orientation": strip.get("runway_direction") or None,
                "ownership": (strip.get("land_ownership") or "").lower() or None,
                "ctaf_frequency": _to_float(strip.get("frequency")),
                "condition_notes": _strip_html(strip.get("description")),
                "trip_reports_url": f"https://utahbackcountrypilots.org/airstrips/{strip['slug']}"
                if strip.get("slug")
                else None,
                "source": "ubcp",
                "source_url": f"https://utahbackcountrypilots.org/airstrips/{strip['slug']}"
                if strip.get("slug")
                else "https://utahbackcountrypilots.org/airstrips",
                "attribution": ATTRIBUTION_TEXT,
                "last_updated": strip.get("modified"),
            }
        )
        records.append(record)

    return records


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clean_state(value):
    """UBCP is scoped to Utah, but its 'state' field is free text and
    sometimes truncated/malformed (e.g. a single 'U' instead of 'UT') --
    treat anything that isn't a real 2-letter code as missing/default."""
    value = (value or "").strip().upper()
    return value if len(value) == 2 else "UT"


def _strip_html(value):
    if not value:
        return None
    import html
    import re

    text = re.sub(r"<[^>]+>", " ", value)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip() or None


if __name__ == "__main__":
    rows = fetch()
    print(f"{len(rows)} Utah airstrip records")
    for r in rows[:3]:
        print(r)
