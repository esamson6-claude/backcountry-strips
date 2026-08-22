# backcountry-strips

A searchable, filterable database of **backcountry / unimproved airstrips**,
aggregated from public sources into one self-contained website — updated
automatically every month.

**Live site:** https://esamson6-claude.github.io/backcountry-strips/

Modeled on [backcountry-aircraft](https://github.com/esamson6-claude/backcountry-aircraft):
a scheduled pipeline fetches data from multiple sources, merges it into a
single deduped dataset, and renders a static page — no backend, no database
server.

## What it tracks

Each strip entry aims to include, where available from its source(s):

- **Basics** — name, identifier, coordinates, elevation, runway length/width,
  surface type, orientation
- **Hazards & access** — access notes (public/private/USFS, permission
  needed), condition reports, hazard/approach notes
- **Flight planning data** — CTAF frequency, links to trip reports and the
  original source page

## Data sources

| Source | Role | Module | License |
|---|---|---|---|
| FAA NASR (28-day AIRAC cycle) | Authoritative base facts — coordinates, elevation, runway length/width/surface — filtered to unpaved (turf/dirt/gravel/etc.) runways nationwide | `import_faa.py` | Public domain (U.S. government work) |
| Idaho ITD Division of Aeronautics | Statewide airfield directory (ArcGIS FeatureServer), incl. runway specs and CTAF | `scrapers/idaho.py` | Public state data |
| Montana MDT Aeronautics | Statewide public-use airport directory (ArcGIS MapServer) | `scrapers/montana.py` | Public state data |
| Utah Back Country Pilots Association (UBCP) | Community-curated Utah airstrip database via their developer API | `scrapers/ubcp.py` | Free/non-commercial use with attribution — **required**, see below |
| Shortfield.com | Community backcountry airstrip directory (undocumented WordPress REST API), covering strips nationwide with rich hazard/condition narratives | `scrapers/shortfield.py` | No stated license; used with clear per-record attribution |

**backcountrypilot.org** was evaluated and dropped: it has no structured
airstrip data of its own (it defers to Shortfield.com) and its `robots.txt`
explicitly blocks AI crawlers.

### Attribution requirement (UBCP)

UBCP's API terms (as of 2026-08-21, from their features page) state:

> The UBCP API cannot be used for commercial purposes. Any data you consume
> from the API must be for personal use only, or made available for free to
> your users with a citation indicating that the UBCP is the origin of this
> data.

This project satisfies that by staying free and non-commercial, and by
attributing every UBCP-sourced record on the site. **Do not put the
generated site behind a paywall or ads without re-checking these terms.**
Shortfield-sourced records are attributed for the same reason, even though
Shortfield has no stated license.

## Pipeline

`generate_html.py` runs, via `fetch_all.py`:

1. **Fetch** every source. Each source's `fetch()` is wrapped so a failure
   (network error, upstream API/schema change) doesn't abort the whole run —
   it falls back to that source's last-good cached result
   (`data/cache/<source>.json`, committed to the repo) and is reported as
   stale in the run log.
2. **Merge** (`merge.py`) — group records by identifier (or rounded
   coordinates as a fallback), preferring FAA NASR for official facts
   (coordinates, elevation, runway specs) and concatenating enrichment
   fields (hazards, access/condition notes, trip report links) across every
   matching source, each tagged with its origin.
3. **Render** (`generate_html.py`) → `docs/index.html`: a single
   self-contained page with a card grid, a Leaflet map view, favorites
   (saved per-browser via `localStorage`), and filters (search, state,
   surface type, runway length, elevation).

The automation lives in `.github/workflows/monthly-refresh.yml` — a cron
job at 14:00 UTC on the 1st of each month, plus a manual "Run workflow"
trigger. It regenerates the
site and commits `docs/` (and refreshed `data/cache/`) if anything changed.
GitHub Pages serves `docs/` as the live site.

## Project layout

```
schema.py              Shared strip record field list
import_faa.py          FAA NASR import (national, unpaved-surface runways)
scrapers/
  idaho.py              Idaho ITD ArcGIS FeatureServer
  montana.py             Montana MDT ArcGIS MapServer
  ubcp.py                 Utah Back Country Pilots Association API
  shortfield.py           Shortfield.com (BFS crawl via related_listing)
fetch_all.py            Fetches every source with graceful degradation/caching
merge.py                Cross-source dedupe/merge
generate_html.py        Render the merged dataset into docs/index.html
.github/workflows/      monthly-refresh.yml — the scheduled pipeline run
data/cache/             Last-good fetch result per source (fallback on outage)
docs/                   Published website (GitHub Pages serves this)
```

## Running it locally

```bash
pip install -r requirements.txt
python generate_html.py   # fetches all sources, merges, writes docs/index.html
```

Or inspect an individual stage:

```bash
python import_faa.py       # FAA NASR only
python -m scrapers.idaho    # Idaho only, etc.
python merge.py             # fetch all sources + merge, print a summary
```

## Status

MVP complete and live: all five sources are wired up, the merge pipeline
dedupes ~9,900 strips nationwide, the site (grid/map/favorites/filters) is
generated and verified working, and the GitHub Actions workflow has
been run successfully end-to-end.

Possible next steps: marker clustering on the map (currently renders one
pin per strip with no clustering, which gets dense at low zoom nationwide),
per-strip detail pages, and broader state coverage beyond Idaho/Montana/Utah.
