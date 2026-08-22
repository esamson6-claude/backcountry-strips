"""Fetch every strip data source with graceful degradation.

If a source's fetch() raises (network error, API change, temporary
outage), that source's previous successful result is reused instead of
failing the whole build, and the source is reported as stale so it's
visible in logs. Each source's last-good result is cached to
data/cache/<source>.json.
"""

import json
import traceback
from pathlib import Path

import import_canada
import import_faa
from scrapers import idaho, montana, shortfield, ubcp

CACHE_DIR = Path(__file__).resolve().parent / "data" / "cache"

SOURCES = [
    ("faa_nasr", import_faa.fetch),
    ("idaho_itd", idaho.fetch),
    ("montana_mdt", montana.fetch),
    ("ubcp", ubcp.fetch),
    ("shortfield", shortfield.fetch),
    ("ourairports_ca", import_canada.fetch),
]


def _cache_path(name):
    return CACHE_DIR / f"{name}.json"


def fetch_all():
    """Return (all_records, stale_sources) -- stale_sources lists any source
    that failed this run and fell back to its cached last-good result."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    all_records = []
    stale_sources = []

    for name, fetch_fn in SOURCES:
        cache_path = _cache_path(name)
        try:
            records = fetch_fn()
            cache_path.write_text(json.dumps(records), encoding="utf-8")
        except Exception:
            print(f"[fetch_all] {name} failed, falling back to cache:")
            traceback.print_exc()
            if cache_path.exists():
                records = json.loads(cache_path.read_text(encoding="utf-8"))
                stale_sources.append(name)
            else:
                print(f"[fetch_all] no cache available for {name}; skipping it entirely")
                records = []
                stale_sources.append(name)

        all_records.append(records)

    return all_records, stale_sources


if __name__ == "__main__":
    lists, stale = fetch_all()
    for (name, _), records in zip(SOURCES, lists):
        flag = " (STALE)" if name in stale else ""
        print(f"{name}: {len(records)} records{flag}")
