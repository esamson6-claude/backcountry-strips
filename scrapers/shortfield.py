"""Import backcountry airstrip data from Shortfield.com's community listing
directory via its (undocumented) "custom-listing-app" WordPress REST API.

Shortfield has no stated data license (no ToS/About/data-reuse page found).
Its robots.txt is permissive and does not block AI/bot crawlers. Given the
absence of a license, every record from this source carries an explicit
`attribution` crediting Shortfield, per the project's decision to proceed
while attributing clearly.

ID discovery: the `search` endpoint does not appear to honor region/page
filters in practice (it returns a fixed-size default sample regardless of
query params), so there's no reliable way to enumerate every listing ID via
search alone. Instead this module does a breadth-first crawl: start from a
handful of seed IDs (returned by an unfiltered `search` call), and follow
each listing's `related_listing` field to discover more IDs, stopping when
no new IDs turn up. This will not be 100% exhaustive, but surfaces a large,
real set without depending on undocumented/brittle query parameters.
"""

import html
import re

import requests

from schema import blank_record

SEARCH_URL = "https://www.shortfield.com/wp-json/custom-listing-app/search"
DETAIL_URL = "https://www.shortfield.com/wp-json/custom-listing-app/listing_detail/{id}"
ATTRIBUTION_TEXT = "Data courtesy of Shortfield.com"

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

MAX_LISTINGS = 500  # safety cap on the BFS crawl


def _discover_ids(session, max_listings=MAX_LISTINGS):
    resp = session.get(SEARCH_URL, headers=BROWSER_HEADERS, timeout=30)
    resp.raise_for_status()
    seeds = [item["id"] for item in resp.json() if "id" in item]

    seen = set(seeds)
    queue = list(seeds)

    while queue and len(seen) < max_listings:
        listing_id = queue.pop(0)
        try:
            detail = _fetch_detail(session, listing_id)
        except requests.RequestException:
            continue

        for related in detail.get("listing_data", {}).get("related_listing", []) or []:
            related_id = related.get("id")
            if related_id is not None and related_id not in seen:
                seen.add(related_id)
                queue.append(related_id)

        # related_listing is actually a top-level field on some responses;
        # check there too in case listing_data doesn't carry it.
        for related in detail.get("related_listing", []) or []:
            related_id = related.get("id")
            if related_id is not None and related_id not in seen:
                seen.add(related_id)
                queue.append(related_id)

    return seen


def _fetch_detail(session, listing_id):
    resp = session.get(DETAIL_URL.format(id=listing_id), headers=BROWSER_HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _parse_runway_table(html):
    """Parse the `_all-runways` HTML table into (id, length, width, surface) tuples."""
    if not html:
        return []
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL)
    parsed = []
    for row in rows[1:]:  # skip header row
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
        if len(cells) == 4:
            parsed.append(tuple(c.strip() for c in cells))
    return parsed


def fetch():
    session = requests.Session()
    ids = _discover_ids(session)

    records = []
    for listing_id in ids:
        try:
            detail = _fetch_detail(session, listing_id)
        except requests.RequestException:
            continue

        ld = detail.get("listing_data", {})
        runways = _parse_runway_table(ld.get("_all-runways"))
        primary = runways[0] if runways else (None, None, None, None)

        category = None
        for section in (detail.get("footer") or {}).get("sections", []):
            if section.get("first_category"):
                category = section["first_category"]
                break

        record = blank_record()
        record.update(
            {
                "identifier": _clean_identifier(ld.get("_location-id")),
                "name": detail.get("title", {}).get("rendered"),
                "state": ld.get("geolocation_state_short") or None,
                "latitude": _to_float(ld.get("geolocation_lat")),
                "longitude": _to_float(ld.get("geolocation_long")),
                "elevation_ft": _to_float(ld.get("_elevation")),
                "runway_length_ft": _to_float(primary[1]),
                "runway_width_ft": _to_float(primary[2]),
                "runway_surface": primary[3] or None,
                "runway_orientation": primary[0] or None,
                "ctaf_frequency": _to_float(ld.get("_ctaf")),
                "access_notes": category,
                "condition_notes": _clean_description(ld.get("_job_description")),
                "trip_reports_url": detail.get("link"),
                "source": "shortfield",
                "source_url": detail.get("link"),
                "attribution": ATTRIBUTION_TEXT,
                "last_updated": detail.get("modified"),
            }
        )
        records.append(record)

    return records


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clean_description(value):
    if not value:
        return None
    text = re.sub(r"<[^>]+>", " ", value)
    text = html.unescape(text)
    text = text.replace("\r\n", " ").strip()
    return re.sub(r"\s+", " ", text) or None


def _clean_identifier(value):
    """Shortfield stores placeholders like 'No ID 153' when it has no real
    FAA/waypoint identifier -- treat those the same as missing."""
    if not value or re.match(r"(?i)^no\s*id\b", value.strip()):
        return None
    return value


if __name__ == "__main__":
    rows = fetch()
    print(f"{len(rows)} Shortfield airstrip records")
    for r in rows[:3]:
        print(r)
