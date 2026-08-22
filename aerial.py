"""Fetch a static aerial/satellite snapshot per strip from Esri's free
World Imagery service (no API key, no billing) and cache it to
docs/aerial/<slug>.jpg.

Images are fetched once and reused indefinitely -- a strip's location
doesn't change, so there's no reason to re-download ~10,000 images on
every daily run. Only new slugs (new strips) trigger a fetch; existing
files are left alone. Delete a file manually to force a re-fetch.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

EXPORT_URL = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/export"

# Half-width of the bounding box in degrees longitude/latitude. ~0.003
# frames a single backcountry strip (a few thousand feet) with some
# surrounding context, based on visual inspection against known strips.
BBOX_DELTA = 0.003
IMAGE_SIZE = "480,320"

AERIAL_DIR = Path(__file__).resolve().parent / "docs" / "aerial"


MAX_WORKERS = 16


def ensure_aerial_images(strips_by_slug):
    """Fetch any missing aerial images for the given {slug: strip} records.
    Returns the set of slugs that now have an image on disk (existing or
    freshly fetched) so the caller can link only to real files."""
    AERIAL_DIR.mkdir(parents=True, exist_ok=True)

    have_image = set()
    to_fetch = []

    for slug, strip in strips_by_slug.items():
        lat, lon = strip.get("latitude"), strip.get("longitude")
        if lat is None or lon is None:
            continue

        image_path = AERIAL_DIR / f"{slug}.jpg"
        if image_path.exists():
            have_image.add(slug)
        else:
            to_fetch.append((slug, lat, lon, image_path))

    if not to_fetch:
        return have_image

    fetched = 0
    failed = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {
            pool.submit(_fetch_one, lat, lon, image_path): slug
            for slug, lat, lon, image_path in to_fetch
        }
        for future in as_completed(futures):
            slug = futures[future]
            try:
                future.result()
                have_image.add(slug)
                fetched += 1
            except requests.RequestException:
                failed += 1

    print(f"[aerial] fetched {fetched} new images, {failed} failed")
    return have_image


def _fetch_one(lat, lon, out_path):
    bbox = (
        f"{lon - BBOX_DELTA},{lat - BBOX_DELTA},"
        f"{lon + BBOX_DELTA},{lat + BBOX_DELTA}"
    )
    params = {
        "bbox": bbox,
        "bboxSR": 4326,
        "imageSR": 4326,
        "size": IMAGE_SIZE,
        "format": "jpg",
        "f": "image",
    }
    resp = requests.get(EXPORT_URL, params=params, timeout=30)
    resp.raise_for_status()
    if not resp.headers.get("content-type", "").startswith("image/"):
        raise requests.RequestException(f"unexpected content-type for {lat},{lon}")
    out_path.write_bytes(resp.content)
