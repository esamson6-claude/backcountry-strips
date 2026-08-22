# backcountry-strips

A searchable, filterable database of **backcountry / unimproved airstrips**,
aggregated from public sources into one self-contained website — updated
automatically.

**Live site:** https://esamson6-claude.github.io/backcountry-strips/ (once published)

Modeled on [backcountry-aircraft](https://github.com/esamson6-claude/backcountry-aircraft):
a scheduled pipeline scrapes/imports data, merges it into a single dataset, and
renders a static page — no backend, no database server.

## What it tracks

Each strip entry aims to include:

- **Basics** — name/identifier, coordinates, elevation, runway length & width,
  surface type, orientation
- **Hazards & access** — approach/departure hazards, density altitude notes,
  nearby camping/fuel/water, access notes (private/public, permission needed)
- **Flight planning data** — CTAF/frequency, known pilot trip reports,
  condition reports, links to source pages

## Data sources

| Source | Role | Module |
|---|---|---|
| FAA 5010 / NASR airport data | Authoritative base facts (runway, elevation, surface) for public-use strips | `import_faa.py` |
| State DOT/DOA backcountry strip lists (ID, UT, MT, etc.) | State-published unimproved/backcountry strip lists | `scrapers/state_*.py` |
| backcountrypilot.org | Community enrichment — trip reports, hazards, condition notes | `scrapers/backcountrypilot.py` |

Entries are merged by identifier/location; FAA data is treated as the
authoritative source for official facts, with state and community sources
layered in for strips not in FAA data and for hazard/condition enrichment.

## Pipeline

`build.py` runs, in order:

1. **Import** FAA 5010/NASR data → base strip records
2. **Scrape** each state list and backcountrypilot.org
3. **Merge** — dedupe by identifier/location, merge fields, preferring FAA for
   official facts and community sources for hazards/reports
4. **Geocode** any strips missing coordinates
5. **Render** (`generate_html.py`) → `docs/index.html`

## Project layout

```
build.py             Orchestrator: runs the full pipeline
import_faa.py         FAA 5010/NASR import
scrapers/             One module per state list + backcountrypilot.org
merge.py              Cross-source dedupe/merge
geocode.py             Location -> lat/lng (cached)
generate_html.py       Render the dataset into docs/index.html
.github/workflows/     Scheduled pipeline run
data/                  Generated data (strips.csv, caches)
docs/                  Published website (GitHub Pages serves this)
```

## Status

Early scaffold — data sources and schema are being wired up. See issues for
current work.
