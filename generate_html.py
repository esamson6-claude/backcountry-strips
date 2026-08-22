"""Render merged strip records as a single self-contained HTML page with
grid/map views and sort/filter UI. Pattern mirrors the sibling project
backcountry-aircraft's generate_html.py.
"""

import hashlib
import html
import re
from datetime import date
from pathlib import Path

import merge
from aerial import ensure_aerial_images
from exclude import remove_helipads_and_balloonports, remove_out_of_scope, remove_permission_required
from fetch_all import fetch_all

PROJECT_ROOT = Path(__file__).resolve().parent
DOCS_DIR = PROJECT_ROOT / "docs"
DOCS_DIR.mkdir(exist_ok=True)
STRIP_DIR = DOCS_DIR / "strip"
STRIP_DIR.mkdir(exist_ok=True)
DOCS_HTML_PATH = DOCS_DIR / "index.html"

SOURCE_LABELS = {
    "faa_nasr": "FAA",
    "idaho_itd": "Idaho ITD",
    "montana_mdt": "Montana MDT",
    "ubcp": "UBCP",
    "shortfield": "Shortfield",
    "ourairports_ca": "OurAirports",
}

# Broad surface categories for the filter chips -- individual sources use
# dozens of raw surface strings (e.g. "DIRT/GRASS", "GRVL", "SOFT SAND");
# without normalizing, the filter row balloons to 30+ chips.
SURFACE_CATEGORIES = [
    ("PAVED", ["ASPH", "ASPHALT", "CONC", "PEM", "ROOF-TOP"]),
    ("TURF", ["TURF", "SOD", "GRASS"]),
    ("GRAVEL", ["GRVL", "GRAVEL", "ROADMIX", "HARDPAN"]),
    ("DIRT", ["DIRT", "SOIL"]),
    ("SAND", ["SAND"]),
    ("WATER", ["WATER", "WATERWAY"]),
]


def _surface_category(raw_surface):
    if not raw_surface:
        return ""
    tokens = [t.strip().upper() for t in raw_surface.replace(",", "-").replace("/", "-").split("-")]
    for category, markers in SURFACE_CATEGORIES:
        if any(t in markers for t in tokens):
            return category
    return "OTHER"


# Broad ownership categories for the filter chips -- FAA's field is a clean
# public/private binary, but UBCP's is free text with government land
# agencies (BLM/USFS/NPS/tribal/state) and mixed-boundary strips like
# "BLM/private" or "SITLA (NW) / BLM (SE)".
GOVERNMENT_LAND_MARKERS = [
    "BLM", "TRIBAL", "SITLA", "NPS", "USFS", "USFWS", "STATE",
]


def _ownership_category(raw_ownership):
    if not raw_ownership:
        return ""
    value = raw_ownership.strip().upper()
    if value == "PUBLIC" or value == "PUBLIC AIRPORT":
        return "PUBLIC"
    if value == "PRIVATE":
        return "PRIVATE"
    if "/" in value or "(" in value:
        return "MIXED"
    if any(marker in value for marker in GOVERNMENT_LAND_MARKERS):
        return "GOVERNMENT LAND"
    return "MIXED"


def _source_label(source_key):
    parts = [SOURCE_LABELS.get(p, p) for p in source_key.split("+")]
    return " + ".join(parts)


def _slug_for(strip):
    """Stable filename slug per strip: identifier when present, else a
    short hash of name+coordinates (both are near-always present, unlike
    identifier, which many Shortfield/UBCP records lack)."""
    identifier = (strip.get("identifier") or "").strip()
    if identifier:
        slug = re.sub(r"[^A-Za-z0-9]+", "-", identifier).strip("-").lower()
        # Windows reserves these device names -- unusable as filenames even
        # with an extension (e.g. FAA identifier "NUL" for Nulato, AK).
        if slug.upper() not in _RESERVED_WINDOWS_NAMES:
            return slug

    basis = f"{strip.get('name') or ''}|{strip.get('latitude')}|{strip.get('longitude')}"
    return "s-" + hashlib.md5(basis.encode("utf-8")).hexdigest()[:10]


_RESERVED_WINDOWS_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *{f"COM{i}" for i in range(1, 10)},
    *{f"LPT{i}" for i in range(1, 10)},
}


def _fmt_number(value, suffix=""):
    if value is None:
        return ""
    try:
        return f"{int(value):,}{suffix}"
    except (TypeError, ValueError):
        return str(value)


def _detail_html(strip, name, subtitle, spec_rows, notes_full, source_label, source_url, attribution, aerial_url):
    notes_block = (
        f'<div class="description"><h2>Notes</h2><div class="description-text">{notes_full}</div></div>'
        if notes_full
        else ""
    )
    attribution_block = f'<p class="attribution">{attribution}</p>' if attribution else ""
    aerial_block = (
        f'<img class="aerial" src="{aerial_url}" alt="Aerial view of {name}" loading="lazy">'
        if aerial_url
        else ""
    )
    aerial_credit = (
        '<p class="aerial-credit">Aerial imagery source: Esri, Vantor, Earthstar Geographics, '
        'and the GIS User Community</p>'
        if aerial_url
        else ""
    )
    lat, lon = strip.get("latitude"), strip.get("longitude")
    sectional_cta = ""
    if lat is not None and lon is not None:
        sectional_cta = (
            f'<a class="cta cta-secondary" href="../?sectional={lat},{lon}">View on VFR sectional →</a>'
            f' <a class="cta cta-secondary" href="../?maplink={lat},{lon}">View on map →</a>'
        )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{name}</title>
<style>
  :root {{ color-scheme: light dark; --bg:#f5f5f7; --card:#fff; --fg:#222; --muted:#666;
           --border:#e2e2e6; --accent:#0366d6; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg:#1a1a1c; --card:#26262a; --fg:#eee; --muted:#aaa; --border:#3a3a40;
             --accent:#58a6ff; }}
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font: 14px/1.4 -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
          background:var(--bg); color:var(--fg); }}
  header {{ padding:14px 20px; border-bottom:1px solid var(--border); background:var(--card); }}
  .back {{ color:var(--accent); text-decoration:none; font-size:13px; }}
  main {{ max-width: 720px; margin: 0 auto; padding: 20px; }}
  h1 {{ margin:0 0 4px 0; font-size:24px; font-weight:600; }}
  .subtitle {{ color:var(--muted); font-size:14px; margin-bottom:16px; }}
  .cta-row {{ display:flex; gap:10px; flex-wrap:wrap; margin-bottom:20px; }}
  .cta {{ display:inline-block; background:var(--accent); color:#fff !important; padding:10px 20px;
          border-radius:8px; font-weight:600; text-decoration:none; margin-bottom:0; }}
  .cta:hover {{ opacity:0.9; }}
  .cta-secondary {{ background:transparent; color:var(--accent) !important; border:1px solid var(--border);
                    padding:9px 20px; }}
  table.specs {{ width:100%; border-collapse:collapse; background:var(--card);
                 border:1px solid var(--border); border-radius:8px; overflow:hidden; }}
  table.specs th, table.specs td {{ padding:8px 12px; text-align:left;
                                    border-bottom:1px solid var(--border); font-size:13px; }}
  table.specs tr:last-child th, table.specs tr:last-child td {{ border-bottom:0; }}
  table.specs th {{ width:140px; color:var(--muted); font-weight:500; text-transform:uppercase;
                    letter-spacing:0.4px; font-size:11px; vertical-align:top; }}
  .description {{ margin-top:24px; padding:18px; background:var(--card);
                  border:1px solid var(--border); border-radius:8px; }}
  .description h2 {{ margin:0 0 10px 0; font-size:15px; color:var(--muted);
                     text-transform:uppercase; letter-spacing:0.5px; font-weight:600; }}
  .description-text {{ font-size:14px; line-height:1.55; color:var(--fg); white-space:pre-wrap; }}
  footer {{ margin-top:30px; padding-top:12px; border-top:1px solid var(--border);
            font-size:12px; color:var(--muted); }}
  .attribution {{ font-style:italic; }}
  .aerial {{ width:100%; aspect-ratio: 3/2; object-fit:cover; border-radius:10px;
             border:1px solid var(--border); margin: 14px 0; background:#0001; }}
  .aerial-credit {{ font-size:11px; color:var(--muted); margin:-8px 0 20px 0; }}
</style>
</head>
<body>
<header>
  <a class="back" href="../" id="back-link">← Back</a>
</header>
<main>
  <h1>{name}</h1>
  <div class="subtitle">{subtitle}</div>
  {aerial_block}
  {aerial_credit}
  <div class="cta-row">
    <a class="cta" href="{source_url}" target="_blank" rel="noopener">
      View original source ({source_label}) →
    </a>
    {sectional_cta}
  </div>
  <table class="specs">{spec_rows}</table>
  {notes_block}
  <footer>
    Aggregated from {source_label}. {attribution_block}
  </footer>
</main>
<script>
  // Prefer returning to whatever page/state the user actually came from
  // (search results, a filtered view, a specific map position) over always
  // landing on the plain unfiltered grid -- but only when we got here via
  // in-site navigation (history.length > 1 alone isn't reliable: a page
  // opened in a new tab or reloaded directly still has history entries).
  document.getElementById('back-link').addEventListener('click', (e) => {{
    if (document.referrer && new URL(document.referrer).origin === location.origin) {{
      e.preventDefault();
      history.back();
    }}
  }});
</script>
</body>
</html>
"""


def _build_cards(strips, have_aerial):
    cards_html = []
    states = set()
    surfaces = set()
    ownerships = set()
    keep_slugs = set()

    for strip in strips:
        name = html.escape(strip.get("name") or "Unnamed strip")
        identifier = html.escape(strip.get("identifier") or "")
        state = html.escape(strip.get("state") or "")
        surface = html.escape((strip.get("runway_surface") or "").strip())
        surface_key = _surface_category(strip.get("runway_surface"))
        ownership_key = _ownership_category(strip.get("ownership"))
        source_key = strip.get("source") or ""
        source_label = html.escape(_source_label(source_key))
        source_url = html.escape(strip.get("source_url") or "#", quote=True)
        attribution = html.escape(strip.get("attribution") or "")

        elevation = strip.get("elevation_ft")
        length = strip.get("runway_length_ft")
        width = strip.get("runway_width_ft")
        lat, lon = strip.get("latitude"), strip.get("longitude")

        if state:
            states.add(strip["state"])
        if surface_key:
            surfaces.add(surface_key)
        if ownership_key:
            ownerships.add(ownership_key)

        length_n = int(length) if length else 0
        elevation_n = int(elevation) if elevation else 0

        subtitle_bits = [b for b in [identifier, state] if b]
        subtitle = " · ".join(subtitle_bits)

        spec_rows = []
        if length:
            spec_rows.append(f'<div class="spec"><span>Length</span><span>{_fmt_number(length, " ft")}</span></div>')
        if width:
            spec_rows.append(f'<div class="spec"><span>Width</span><span>{_fmt_number(width, " ft")}</span></div>')
        if surface:
            spec_rows.append(f'<div class="spec"><span>Surface</span><span>{surface}</span></div>')
        if elevation:
            spec_rows.append(f'<div class="spec"><span>Elevation</span><span>{_fmt_number(elevation, " ft")}</span></div>')
        if strip.get("runway_orientation"):
            spec_rows.append(f'<div class="spec"><span>Runway</span><span>{html.escape(strip["runway_orientation"])}</span></div>')
        if strip.get("ctaf_frequency"):
            spec_rows.append(f'<div class="spec"><span>CTAF</span><span>{strip["ctaf_frequency"]}</span></div>')
        if ownership_key:
            spec_rows.append(f'<div class="spec"><span>Ownership</span><span>{ownership_key.title()}</span></div>')

        notes = " ".join(
            filter(None, [strip.get("access_notes"), strip.get("condition_notes"), strip.get("hazards")])
        )
        notes_preview = html.escape(notes[:220] + ("…" if len(notes) > 220 else "")) if notes else ""
        notes_full = html.escape(notes) if notes else ""

        slug = _slug_for(strip)
        keep_slugs.add(slug)
        detail_url = f"strip/{slug}.html"

        detail_spec_pairs = [
            ("Identifier", strip.get("identifier")),
            ("State", strip.get("state")),
            ("Runway length", _fmt_number(length, " ft") if length else None),
            ("Runway width", _fmt_number(width, " ft") if width else None),
            ("Surface", strip.get("runway_surface")),
            ("Runway", strip.get("runway_orientation")),
            ("Elevation", _fmt_number(elevation, " ft") if elevation else None),
            ("Ownership", strip.get("ownership")),
            ("CTAF", strip.get("ctaf_frequency")),
            ("Coordinates", f"{lat}, {lon}" if lat is not None and lon is not None else None),
        ]
        detail_spec_rows = "".join(
            f"<tr><th>{html.escape(k)}</th><td>{html.escape(str(v))}</td></tr>"
            for k, v in detail_spec_pairs
            if v
        )

        aerial_url = f"../aerial/{slug}.jpg" if slug in have_aerial else None

        (STRIP_DIR / f"{slug}.html").write_text(
            _detail_html(
                strip,
                name,
                subtitle,
                detail_spec_rows,
                notes_full,
                source_label,
                source_url,
                attribution,
                aerial_url,
            ),
            encoding="utf-8",
        )

        search_blob = html.escape(
            " ".join(
                filter(
                    None,
                    [
                        strip.get("name"),
                        strip.get("identifier"),
                        strip.get("state"),
                        surface,
                        strip.get("access_notes"),
                        strip.get("condition_notes"),
                    ],
                )
            ).lower(),
            quote=True,
        )

        lat_attr = f' data-lat="{lat}"' if lat is not None else ""
        lon_attr = f' data-lng="{lon}"' if lon is not None else ""

        map_links = (
            f'<span class="sectional-link" role="button" tabindex="0" '
            f'data-lat="{lat}" data-lng="{lon}" data-name="{name}">View on VFR sectional →</span>'
            f' <span class="map-link" role="button" tabindex="0" '
            f'data-lat="{lat}" data-lng="{lon}" data-name="{name}">View on map →</span>'
            if lat is not None and lon is not None
            else ""
        )

        cards_html.append(
            f"""<a class="card" href="{detail_url}"
   data-state="{state}" data-surface="{surface_key}" data-ownership="{html.escape(ownership_key, quote=True)}"
   data-source="{html.escape(source_key)}"
   data-length="{length_n}" data-elevation="{elevation_n}"
   data-search="{search_blob}"{lat_attr}{lon_attr}
   data-name="{name}" data-subtitle="{html.escape(subtitle)}">
  <div class="body">
    <div class="title-row">
      <div class="title">{name}</div>
      <span class="fav-btn" role="button" tabindex="0" aria-pressed="false" aria-label="Save to favorites" title="Save to favorites">&#9829;</span>
    </div>
    <div class="subtitle">{subtitle}</div>
    <div class="specs">{''.join(spec_rows)}</div>
    {'<div class="notes">' + notes_preview + '</div>' if notes_preview else ''}
    {map_links}
    <div class="footer">
      <span class="source">{source_label}</span>
      {'<span class="attribution">' + attribution + '</span>' if attribution else ''}
    </div>
  </div>
</a>"""
        )

    # Prune stale detail pages from strips no longer in the dataset.
    for path in STRIP_DIR.glob("*.html"):
        if path.stem not in keep_slugs:
            path.unlink(missing_ok=True)

    return cards_html, sorted(states), sorted(surfaces), sorted(ownerships)


def render():
    record_lists, stale_sources = fetch_all()
    if stale_sources:
        print(f"Using cached data for: {', '.join(stale_sources)}")
    strips = merge.merge(*record_lists)
    strips, out_of_scope = remove_out_of_scope(strips)
    if out_of_scope:
        print(f"Excluded {len(out_of_scope)} strips outside the US(+territories excluded)/Canada scope")
    strips, excluded = remove_permission_required(strips)
    if excluded:
        print(f"Excluded {len(excluded)} strips flagged permission-required/no-trespassing")
    strips, heli_balloon = remove_helipads_and_balloonports(strips)
    if heli_balloon:
        print(f"Excluded {len(heli_balloon)} heliports/balloonports")
    strips.sort(key=lambda s: s.get("name") or "")

    strips_by_slug = {_slug_for(s): s for s in strips}
    have_aerial = ensure_aerial_images(strips_by_slug)

    cards_html, states, surfaces, ownerships = _build_cards(strips, have_aerial)

    state_buttons = "".join(
        f'<button class="chip state-chip" data-state="{html.escape(s, quote=True)}">{html.escape(s)}</button>'
        for s in states
    )
    surface_buttons = "".join(
        f'<button class="chip surface-chip" data-surface="{html.escape(s, quote=True)}">{html.escape(s)}</button>'
        for s in surfaces
    )
    ownership_buttons = "".join(
        f'<button class="chip ownership-chip" data-ownership="{html.escape(o, quote=True)}">{html.escape(o.title())}</button>'
        for o in ownerships
    )

    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Backcountry strips — {date.today().isoformat()}</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
      integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin="">
<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css"
      integrity="sha256-YU3qCpj/P06tdPBJGPax0bm6Q1wltfwjsho5TR4+TYc=" crossorigin="">
<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css"
      integrity="sha256-YSWCMtmNZNwqex4CEw1nQhvFub2lmU7vcCKP+XVwwXA=" crossorigin="">
<style>
  :root {{ color-scheme: light dark; --bg:#f5f5f7; --card:#fff; --fg:#222; --muted:#666;
           --border:#e2e2e6; --accent:#0366d6; --chip-bg:transparent; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg:#1a1a1c; --card:#26262a; --fg:#eee; --muted:#aaa; --border:#3a3a40;
             --accent:#58a6ff; }}
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font: 14px/1.4 -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
          background:var(--bg); color:var(--fg); }}
  header {{ padding:14px 20px; border-bottom:1px solid var(--border); background:var(--card);
            position:sticky; top:0; z-index:30; }}
  h1 {{ margin:0 0 4px 0; font-size:18px; font-weight:600; }}
  .subhead {{ color:var(--muted); font-size:12px; margin-bottom:10px; }}
  @media (max-width: 759px) {{
    header {{ position:static; padding:10px 14px; }}
  }}
  .controls {{ display:grid; gap:10px; grid-template-columns: 1fr; }}
  @media (min-width: 760px) {{
    .controls {{ grid-template-columns: 2fr 1fr 1fr; align-items:end; }}
  }}
  .control-group {{ display:flex; flex-direction:column; gap:4px; }}
  .control-group label {{ font-size:11px; color:var(--muted); text-transform:uppercase;
                          letter-spacing:0.5px; }}
  .control-group input, .control-group select {{
    padding:6px 10px; border:1px solid var(--border); border-radius:6px;
    background:var(--bg); color:var(--fg); font:inherit; }}
  .range-row {{ display:flex; gap:6px; }}
  .range-row input {{ width:0; flex:1; min-width:0; }}
  .chips {{ display:flex; gap:6px; flex-wrap:wrap; margin-top:10px; }}
  .chip {{ padding:5px 12px; border-radius:999px; border:1px solid var(--border);
           background:var(--chip-bg); color:var(--fg); font:inherit; font-size:12px; cursor:pointer; }}
  .chip:hover {{ border-color:var(--accent); }}
  .chip.active {{ background:var(--accent); color:#fff; border-color:var(--accent); }}
  .chip-row-label {{ font-size:11px; color:var(--muted); text-transform:uppercase;
                     letter-spacing:0.5px; align-self:center; margin-right:4px; }}
  #count {{ font-weight:600; }}
  main {{ padding:20px; display:grid; gap:16px;
          grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); }}
  .card {{ display:flex; flex-direction:column; background:var(--card); border:1px solid var(--border);
           border-radius:10px; overflow:hidden; text-decoration:none; color:inherit;
           transition: transform .1s, box-shadow .15s; }}
  .card:hover {{ transform: translateY(-2px); box-shadow: 0 8px 20px rgba(0,0,0,0.08); }}
  .card.hidden {{ display:none; }}
  .body {{ padding:14px 16px; display:flex; flex-direction:column; gap:6px; position:relative; }}
  .title-row {{ display:flex; justify-content:space-between; align-items:flex-start; gap:8px; }}
  .title {{ font-weight:600; font-size:15px; }}
  .subtitle {{ color:var(--muted); font-size:12px; }}
  .specs {{ display:grid; grid-template-columns: auto 1fr; gap:2px 10px; font-size:12px;
            color:var(--muted); margin-top:4px; }}
  .spec {{ display:contents; }}
  .spec > span:first-child {{ text-transform:uppercase; letter-spacing:0.4px; font-size:10px;
                              opacity:0.7; align-self:center; }}
  .spec > span:last-child {{ color:var(--fg); font-size:12.5px; }}
  .notes {{ font-size:12px; color:var(--muted); margin-top:4px; }}
  .footer {{ display:flex; justify-content:space-between; gap:8px; font-size:11px; color:var(--muted);
             margin-top:auto; padding-top:6px; border-top:1px solid var(--border); }}
  .source {{ text-transform:uppercase; letter-spacing:0.5px; }}
  .attribution {{ font-style:italic; text-align:right; }}
  #empty {{ padding:40px 20px; text-align:center; color:var(--muted); display:none; }}
  .view-toggle {{ display:flex; gap:4px; background:var(--bg); padding:3px; border-radius:8px;
                  border:1px solid var(--border); }}
  .view-toggle button {{ padding:5px 14px; border:0; background:transparent; color:var(--fg);
                         font:inherit; cursor:pointer; border-radius:5px; }}
  .view-toggle button.active {{ background:var(--accent); color:#fff; }}
  #fav-badge {{ display:none; min-width:16px; height:16px; padding:0 4px; margin-left:5px;
                border-radius:999px; background:#ff4d6d; color:#fff; font-size:10px; font-weight:700;
                line-height:16px; text-align:center; vertical-align:middle; }}
  .fav-btn {{ cursor:pointer; color:var(--muted); font-size:17px; line-height:1; user-select:none;
              transition: transform .1s, color .15s; }}
  .fav-btn:hover {{ transform:scale(1.15); }}
  .fav-btn.faved {{ color:#ff4d6d; }}
  #map {{ height: 70vh; min-height: 500px; margin:20px; margin-top:0;
          border-radius: 10px; border:1px solid var(--border); display:none; }}
  body.map-view #grid, body.map-view #empty {{ display:none; }}
  body.map-view #map {{ display:block; }}
  .leaflet-popup-content {{ margin:8px 10px; }}
  .leaflet-popup-content .popup-title {{ font-weight:600; font-size:13px; margin-bottom:2px; }}
  .leaflet-popup-content .popup-sub {{ font-size:11px; color:#666; margin-bottom:4px; }}
  .leaflet-popup-content a {{ color:#0366d6; text-decoration:none; font-size:11px; }}
  .sectional-notice {{ background:rgba(20,20,22,0.85); color:#fff; padding:8px 14px;
                       border-radius:6px; font-size:12px; max-width:280px; margin:0 0 10px 10px;
                       box-shadow:0 2px 8px rgba(0,0,0,0.3); }}
  .sectional-link, .map-link {{ font-size:11px; color:var(--accent); text-decoration:none; cursor:pointer; }}
  .sectional-link:hover, .map-link:hover {{ text-decoration:underline; }}
</style>
</head>
<body>
<header>
  <div style="display:flex; justify-content:space-between; align-items:center; gap:12px; flex-wrap:wrap;">
    <div>
      <h1>Backcountry strips — <span id="count">{len(cards_html)}</span> shown</h1>
      <div class="subhead">Updated {date.today().isoformat()} · click any card to open the source page</div>
    </div>
    <div style="display:flex; gap:8px; align-items:center;">
      <div class="view-toggle">
        <button id="view-grid" class="active">Grid</button>
        <button id="view-favorites">♥ Favorites<span id="fav-badge">0</span></button>
        <button id="view-map">Map</button>
      </div>
    </div>
  </div>
  <div id="filter-panel">
  <div class="controls">
    <div class="control-group">
      <label for="search">Search</label>
      <input id="search" type="search" placeholder="Name, identifier, state, notes…">
    </div>
    <div class="control-group">
      <label>Runway length (ft)</label>
      <div class="range-row">
        <input id="length-min" type="number" placeholder="Min" min="0">
        <input id="length-max" type="number" placeholder="Max" min="0">
      </div>
    </div>
    <div class="control-group">
      <label>Elevation (ft)</label>
      <div class="range-row">
        <input id="elevation-min" type="number" placeholder="Min" min="0">
        <input id="elevation-max" type="number" placeholder="Max" min="0">
      </div>
    </div>
  </div>
  <div class="chips">
    <span class="chip-row-label">State:</span>
    <button class="chip state-chip active" data-state="__all__">All</button>
    {state_buttons}
  </div>
  <div class="chips">
    <span class="chip-row-label">Surface:</span>
    <button class="chip surface-chip active" data-surface="__all__">All</button>
    {surface_buttons}
  </div>
  <div class="chips">
    <span class="chip-row-label">Ownership:</span>
    <button class="chip ownership-chip active" data-ownership="__all__">All</button>
    {ownership_buttons}
  </div>
  </div><!-- /#filter-panel -->
</header>
<main id="grid">
  {''.join(cards_html)}
</main>
<div id="empty">No strips match the current filters.</div>
<div id="map"></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
        integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
<script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"
        integrity="sha256-Hk4dIpcqOSb0hZjgyvFOP+cEmDXUKKNE/tT542ZbNQg=" crossorigin=""></script>
<script>
  const grid = document.getElementById('grid');
  const cards = Array.from(grid.querySelectorAll('.card'));
  const countEl = document.getElementById('count');
  const emptyEl = document.getElementById('empty');

  // ---- Favorites (persisted per-browser in localStorage, keyed by source URL) ----
  const FAV_KEY = 'backcountry-strips-favorites';
  const favBadge = document.getElementById('fav-badge');
  function loadFavs() {{
    try {{ return new Set(JSON.parse(localStorage.getItem(FAV_KEY) || '[]')); }}
    catch (e) {{ return new Set(); }}
  }}
  let favs = loadFavs();
  function saveFavs() {{ localStorage.setItem(FAV_KEY, JSON.stringify([...favs])); }}
  function updateFavBadge() {{
    favBadge.textContent = favs.size;
    favBadge.style.display = favs.size ? 'inline-block' : 'none';
  }}
  function favKey(card) {{ return card.dataset.name + '|' + card.dataset.subtitle; }}
  function markCardFav(card) {{
    const btn = card.querySelector('.fav-btn');
    const on = favs.has(favKey(card));
    if (btn) {{ btn.classList.toggle('faved', on); btn.setAttribute('aria-pressed', String(on)); }}
  }}
  function toggleFav(card) {{
    const key = favKey(card);
    if (favs.has(key)) favs.delete(key); else favs.add(key);
    saveFavs();
    markCardFav(card);
    updateFavBadge();
    if (document.body.classList.contains('fav-view')) apply();
  }}
  for (const c of cards) markCardFav(c);
  updateFavBadge();
  function heartHandler(e) {{
    const btn = e.target.closest('.fav-btn');
    if (!btn) return;
    if (e.type === 'keydown' && e.key !== 'Enter' && e.key !== ' ') return;
    e.preventDefault();
    e.stopPropagation();
    const card = btn.closest('.card');
    if (card) toggleFav(card);
  }}
  document.addEventListener('click', heartHandler);
  document.addEventListener('keydown', heartHandler);

  function mapLinkHandler(e) {{
    const link = e.target.closest('.sectional-link, .map-link');
    if (!link) return;
    if (e.type === 'keydown' && e.key !== 'Enter' && e.key !== ' ') return;
    e.preventDefault();
    e.stopPropagation();
    const lat = parseFloat(link.dataset.lat);
    const lng = parseFloat(link.dataset.lng);
    const name = link.dataset.name || null;
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;
    if (link.classList.contains('sectional-link')) {{
      showOnSectional(lat, lng, name);
    }} else {{
      showOnStreetMap(lat, lng, name);
    }}
  }}
  document.addEventListener('click', mapLinkHandler);
  document.addEventListener('keydown', mapLinkHandler);

  const searchEl = document.getElementById('search');
  const lengthMinEl = document.getElementById('length-min');
  const lengthMaxEl = document.getElementById('length-max');
  const elevationMinEl = document.getElementById('elevation-min');
  const elevationMaxEl = document.getElementById('elevation-max');

  function activeChips(selector) {{
    return new Set(
      Array.from(document.querySelectorAll(selector + '.active'))
        .map(c => c.dataset.state || c.dataset.surface || c.dataset.ownership)
        .filter(v => v && v !== '__all__')
    );
  }}

  // Filters live only as DOM state (.active classes, input values), which a
  // fresh page load can't see -- so clicking Back after filtering used to
  // land back on an unfiltered grid even though the URL/history entry was
  // otherwise correct. Mirroring the filter state into the URL query string
  // (via replaceState, so every keystroke doesn't spam browser history) lets
  // a reload/back-navigation restore the exact same filtered view.
  function syncFiltersToUrl() {{
    const params = new URLSearchParams();
    if (searchEl.value.trim()) params.set('q', searchEl.value.trim());
    if (lengthMinEl.value) params.set('lmin', lengthMinEl.value);
    if (lengthMaxEl.value) params.set('lmax', lengthMaxEl.value);
    if (elevationMinEl.value) params.set('emin', elevationMinEl.value);
    if (elevationMaxEl.value) params.set('emax', elevationMaxEl.value);
    const states = [...activeChips('.state-chip')];
    if (states.length) params.set('state', states.join(','));
    const surfaces = [...activeChips('.surface-chip')];
    if (surfaces.length) params.set('surface', surfaces.join(','));
    const ownerships = [...activeChips('.ownership-chip')];
    if (ownerships.length) params.set('ownership', ownerships.join(','));
    if (document.body.classList.contains('fav-view')) params.set('view', 'favorites');
    else if (document.body.classList.contains('map-view')) params.set('view', 'map');

    const qs = params.toString();
    const newUrl = location.pathname + (qs ? '?' + qs : '');
    if (newUrl !== location.pathname + location.search) {{
      history.replaceState(null, '', newUrl);
    }}
  }}

  function restoreFiltersFromUrl() {{
    const params = new URLSearchParams(location.search);
    if (params.has('q')) searchEl.value = params.get('q');
    if (params.has('lmin')) lengthMinEl.value = params.get('lmin');
    if (params.has('lmax')) lengthMaxEl.value = params.get('lmax');
    if (params.has('emin')) elevationMinEl.value = params.get('emin');
    if (params.has('emax')) elevationMaxEl.value = params.get('emax');

    function activateChips(rowSelector, key) {{
      const values = params.get(key);
      if (!values) return;
      const wanted = new Set(values.split(','));
      const chips = document.querySelectorAll(rowSelector);
      let any = false;
      chips.forEach(c => {{
        const v = c.dataset.state || c.dataset.surface || c.dataset.ownership;
        if (wanted.has(v)) {{ c.classList.add('active'); any = true; }}
      }});
      if (any) {{
        const allChip = Array.from(chips).find(c =>
          (c.dataset.state || c.dataset.surface || c.dataset.ownership) === '__all__'
        );
        if (allChip) allChip.classList.remove('active');
      }}
    }}
    activateChips('.state-chip', 'state');
    activateChips('.surface-chip', 'surface');
    activateChips('.ownership-chip', 'ownership');

    return params.get('view');  // 'map' | 'favorites' | null, applied by caller
  }}

  function num(v) {{ const n = parseInt(v, 10); return Number.isFinite(n) ? n : null; }}

  // Whether any real filter narrows the result set -- used to decide whether
  // Map view should fit-to-results (filtered) or just show the default
  // continental-US view (unfiltered; fitting ~9,900 strips spanning Guam to
  // Puerto Rico zooms out to a near-useless world view).
  function isFilteredNow() {{
    return !!(searchEl.value.trim() || lengthMinEl.value || lengthMaxEl.value
      || elevationMinEl.value || elevationMaxEl.value
      || activeChips('.state-chip').size > 0 || activeChips('.surface-chip').size > 0
      || activeChips('.ownership-chip').size > 0
      || document.body.classList.contains('fav-view'));
  }}

  function apply() {{
    const q = searchEl.value.trim().toLowerCase();
    const lMin = num(lengthMinEl.value), lMax = num(lengthMaxEl.value);
    const eMin = num(elevationMinEl.value), eMax = num(elevationMaxEl.value);
    const activeStates = activeChips('.state-chip');
    const activeSurfaces = activeChips('.surface-chip');
    const activeOwnerships = activeChips('.ownership-chip');
    const favView = document.body.classList.contains('fav-view');

    let visible = [];
    for (const c of cards) {{
      const state = c.dataset.state;
      const surface = c.dataset.surface;
      const ownership = c.dataset.ownership;
      const length = parseInt(c.dataset.length, 10) || 0;
      const elevation = parseInt(c.dataset.elevation, 10) || 0;
      const search = c.dataset.search;

      let show = true;
      if (activeStates.size > 0 && !activeStates.has(state)) show = false;
      if (activeSurfaces.size > 0 && !activeSurfaces.has(surface)) show = false;
      if (activeOwnerships.size > 0 && !activeOwnerships.has(ownership)) show = false;
      if (q && !search.includes(q)) show = false;
      if (lMin !== null && (length === 0 || length < lMin)) show = false;
      if (lMax !== null && length > lMax) show = false;
      if (eMin !== null && (elevation === 0 || elevation < eMin)) show = false;
      if (eMax !== null && elevation > eMax) show = false;
      if (favView && !favs.has(favKey(c))) show = false;

      c.classList.toggle('hidden', !show);
      if (show) visible.push(c);
    }}

    countEl.textContent = visible.length;
    if (visible.length === 0) {{
      emptyEl.textContent = (favView && favs.size === 0)
        ? 'No favorites yet — tap the ♥ on any strip to save it here.'
        : 'No strips match the current filters.';
      emptyEl.style.display = 'block';
    }} else {{
      emptyEl.style.display = 'none';
    }}
    if (document.body.classList.contains('map-view') && !suppressMapRefresh) renderMarkers(isFilteredNow());
    syncFiltersToUrl();
  }}

  function wireChipRow(rowSelector) {{
    const chips = document.querySelectorAll(rowSelector);
    const chipKey = c => c.dataset.state || c.dataset.surface || c.dataset.ownership;
    const allChip = Array.from(chips).find(c => chipKey(c) === '__all__');
    chips.forEach(b => b.addEventListener('click', () => {{
      const key = chipKey(b);
      if (key === '__all__') {{
        chips.forEach(x => x.classList.remove('active'));
        b.classList.add('active');
      }} else {{
        b.classList.toggle('active');
        const others = Array.from(chips).filter(c =>
          chipKey(c) !== '__all__' && c.classList.contains('active')
        );
        if (allChip) allChip.classList.toggle('active', others.length === 0);
      }}
      apply();
    }}));
  }}
  wireChipRow('.state-chip');
  wireChipRow('.surface-chip');
  wireChipRow('.ownership-chip');
  for (const el of [searchEl, lengthMinEl, lengthMaxEl, elevationMinEl, elevationMaxEl]) {{
    el.addEventListener('input', apply);
    el.addEventListener('change', apply);
  }}

  // ---- Map view (Leaflet) ----
  const SECTIONAL_HARD_MIN_ZOOM = 8;   // floor the FAA tile service accepts at all
  const SECTIONAL_READABLE_ZOOM = 10;  // below this, chart detail is too small to read
  const SECTIONAL_MAX_ZOOM = 12;
  const SECTIONAL_DEFAULT_ZOOM = 11;   // readable single-strip zoom when auto-jumping in
  // Fallback center when the sectional is toggled on from the default
  // whole-country view: the geometric center of the US ([39.8, -98.5]) sits
  // in a coverage gap between sectional chart tiles at usable zoom levels,
  // so jump to a real backcountry hub (McCall, ID) with confirmed coverage
  // instead of leaving the user staring at blank grey tiles.
  const SECTIONAL_FALLBACK_CENTER = [45.0, -115.0];
  const DEFAULT_MAP_CENTER = [39.8, -98.5];
  const DEFAULT_MAP_ZOOM = 4;

  let map = null;
  let markerLayer = null;
  let streetLayer = null;
  let sectionalLayer = null;
  let sectionalNotice = null;
  let focusMarker = null;

  // Distinct single-strip pin, shown whenever the map jumps to focus on one
  // strip (from a card/detail-page link) -- separate from the clustered
  // markerLayer so the target strip is unmistakable even on the street map,
  // where it might otherwise sit inside a cluster bubble.
  function setFocusMarker(lat, lng, name) {{
    if (focusMarker) map.removeLayer(focusMarker);
    focusMarker = L.marker([lat, lng], {{ zIndexOffset: 1000 }});
    if (name) focusMarker.bindPopup('<div class="popup-title">' + name + '</div>').openPopup();
    focusMarker.addTo(map);
  }}

  function updateSectionalNoticeRef() {{
    if (!sectionalNotice) return;
    const showingSectional = map.hasLayer(sectionalLayer);
    const el = sectionalNotice.getContainer();
    el.style.display = (showingSectional && map.getZoom() < SECTIONAL_READABLE_ZOOM) ? 'block' : 'none';
  }}

  // Leaflet has a quirk where setView(latlng, zoom) to a zoom above the
  // map's zoom just before/during a base layer swap can silently settle
  // back to the new layer's minZoom once its own 'zoomend' fires, even
  // though getZoom() briefly reports the requested zoom right after the
  // call. Reasserting the zoom once that settle-zoomend fires corrects it.
  function forceView(latlng, zoom) {{
    map.setView(latlng, zoom, {{ animate: false }});
    map.once('zoomend', () => {{
      const target = L.latLng(latlng);
      const driftedZoom = map.getZoom() !== zoom;
      const driftedCenter = map.getCenter().distanceTo(target) > 1000;
      if (driftedZoom || driftedCenter) map.setView(target, zoom, {{ animate: false }});
    }});
  }}

  function initMap() {{
    if (map) return;
    map = L.map('map', {{ scrollWheelZoom: true }}).setView(DEFAULT_MAP_CENTER, DEFAULT_MAP_ZOOM);

    streetLayer = L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 18,
    }});
    // FAA's official VFR sectional tile cache only renders zoom 8-12.
    sectionalLayer = L.tileLayer(
      'https://tiles.arcgis.com/tiles/ssFJjBXIUyZDrSYZ/arcgis/rest/services/VFR_Sectional/MapServer/tile/{{z}}/{{y}}/{{x}}',
      {{
        attribution: 'FAA Aeronautical Information Services (VFR Sectional)',
        minZoom: SECTIONAL_HARD_MIN_ZOOM,
        maxZoom: SECTIONAL_MAX_ZOOM,
        maxNativeZoom: SECTIONAL_MAX_ZOOM,
      }}
    );

    streetLayer.addTo(map);
    L.control.layers(
      {{ 'Street map': streetLayer, 'VFR sectional': sectionalLayer }},
      null,
      {{ position: 'topright' }}
    ).addTo(map);

    sectionalNotice = L.control({{ position: 'bottomleft' }});
    sectionalNotice.onAdd = function() {{
      const div = L.DomUtil.create('div', 'sectional-notice');
      div.textContent = 'VFR sectional charts only render when zoomed in — zoom in to see chart detail.';
      div.style.display = 'none';
      return div;
    }};
    sectionalNotice.addTo(map);

    // Auto-zoom to a readable level the moment the sectional layer is turned
    // on, instead of leaving the user looking at a blank/grey map and
    // guessing they need to zoom in themselves.
    map.on('baselayerchange', (e) => {{
      if (e.layer !== sectionalLayer) {{ updateSectionalNoticeRef(); return; }}
      if (map.getZoom() < SECTIONAL_READABLE_ZOOM) {{
        // Starting from the default whole-country view has no meaningful
        // "current location" to zoom in on -- recenter on a spot with known
        // sectional coverage instead of the geometric center of the US,
        // which can land on a gap between chart tiles.
        const atDefaultView = map.getCenter().distanceTo(L.latLng(DEFAULT_MAP_CENTER)) < 50000;
        forceView(atDefaultView ? SECTIONAL_FALLBACK_CENTER : map.getCenter(), SECTIONAL_DEFAULT_ZOOM);
      }}
      updateSectionalNoticeRef();
    }});
    map.on('zoomend', updateSectionalNoticeRef);

    markerLayer = L.markerClusterGroup({{ maxClusterRadius: 50 }}).addTo(map);
  }}

  // Switch to Map view showing the VFR sectional, zoomed in on one strip.
  // Used by each card/detail page's "View on sectional" control.
  function showOnSectional(lat, lng, name) {{
    setView('map', /* focusStrip */ true);
    initMap();
    // setView('map', true) already scheduled its own invalidateSize() +
    // renderMarkers(false) in a setTimeout -- run this centering after that
    // same delay so it isn't racing (and losing to) that callback.
    setTimeout(() => {{
      map.invalidateSize();
      if (!map.hasLayer(sectionalLayer)) {{
        map.removeLayer(streetLayer);
        sectionalLayer.addTo(map);
      }}
      forceView([lat, lng], SECTIONAL_DEFAULT_ZOOM);
      setFocusMarker(lat, lng, name);
      updateSectionalNoticeRef();
    }}, 60);
  }}

  // Switch to Map view on the street layer, zoomed/pinned on one strip.
  // Used by each card's "View on map" control -- unlike showOnSectional,
  // this doesn't force the sectional layer, so a strip you're inspecting
  // stays visible as a distinct pin instead of just being wherever it falls
  // inside a cluster bubble.
  function showOnStreetMap(lat, lng, name) {{
    setView('map', /* focusStrip */ true);
    initMap();
    setTimeout(() => {{
      map.invalidateSize();
      if (map.hasLayer(sectionalLayer)) {{
        map.removeLayer(sectionalLayer);
        streetLayer.addTo(map);
      }}
      forceView([lat, lng], SECTIONAL_DEFAULT_ZOOM);
      setFocusMarker(lat, lng, name);
    }}, 60);
  }}
  function renderMarkers(fitToBounds) {{
    if (!markerLayer) return;
    markerLayer.clearLayers();
    const visibleCards = cards.filter(c => !c.classList.contains('hidden'));
    let bounds = [];
    for (const c of visibleCards) {{
      const lat = parseFloat(c.dataset.lat);
      const lng = parseFloat(c.dataset.lng);
      if (!Number.isFinite(lat) || !Number.isFinite(lng)) continue;
      const popupHtml = '<div class="popup-title">' + c.dataset.name + '</div>' +
                   '<div class="popup-sub">' + c.dataset.subtitle + '</div>' +
                   '<a href="' + c.href + '" target="_blank" rel="noopener">View source →</a>';
      L.marker([lat, lng]).bindPopup(popupHtml, {{minWidth: 200}}).addTo(markerLayer);
      bounds.push([lat, lng]);
    }}
    // fitBounds only when explicitly asked (initial Grid->Map switch, or a
    // filter change while already in Map view) -- NOT after a deliberate
    // setView (sectional toggle auto-zoom, "View on sectional" deep link),
    // or it immediately overrides that intentional center/zoom.
    if (fitToBounds && bounds.length > 0) map.fitBounds(bounds, {{padding: [30, 30], maxZoom: 10}});
  }}
  const viewGrid = document.getElementById('view-grid');
  const viewFav = document.getElementById('view-favorites');
  const viewMap = document.getElementById('view-map');
  let mapShownOnce = false;
  // While true, apply()'s own renderMarkers() call is skipped -- used during
  // a focusStrip transition (showOnSectional) so apply()'s call inside
  // setView doesn't fit-bounds/recenter the map out from under the
  // intentional single-strip view that's about to be set.
  let suppressMapRefresh = false;
  // `focusStrip`: when set, the caller (showOnSectional) is about to center
  // on one specific strip -- skip the "fit everything in view" behavior
  // that a plain nav-bar click into Map view should still do.
  function setView(view, focusStrip) {{
    document.body.classList.toggle('map-view', view === 'map');
    document.body.classList.toggle('fav-view', view === 'favorites');
    viewGrid.classList.toggle('active', view === 'grid');
    viewFav.classList.toggle('active', view === 'favorites');
    viewMap.classList.toggle('active', view === 'map');
    suppressMapRefresh = !!focusStrip;
    apply();
    suppressMapRefresh = false;
    if (view === 'map') {{
      initMap();
      // #map has display:none until map-view is active, so Leaflet computed
      // its initial center/zoom against a zero-size container -- that drifts
      // the center. invalidateSize() fixes the container's measured size,
      // and (unless the caller is about to set its own focused view) the
      // drifted center/zoom is reset to the default view (or fit to
      // results, if filters are active) -- the expected first look.
      const needsRecenter = !mapShownOnce && !focusStrip;
      mapShownOnce = true;
      if (!focusStrip) {{
        setTimeout(() => {{
          map.invalidateSize();
          if (needsRecenter) map.setView(DEFAULT_MAP_CENTER, DEFAULT_MAP_ZOOM);
          renderMarkers(isFilteredNow());
        }}, 50);
      }}
    }}
  }}
  viewGrid.addEventListener('click', () => setView('grid'));
  viewFav.addEventListener('click', () => setView('favorites'));
  viewMap.addEventListener('click', () => setView('map'));

  // Deep links from a detail page's map buttons take priority over restored
  // filter state: ?sectional=lat,lng / ?maplink=lat,lng jump straight to Map
  // view, zoomed/pinned on that one strip. Read these BEFORE anything calls
  // apply() -- apply() triggers syncFiltersToUrl(), which only knows about
  // filter/view params and would otherwise silently strip sectional/maplink
  // off the URL (via replaceState) before this code got a chance to read it.
  const params = new URLSearchParams(location.search);
  const sectionalParam = params.get('sectional');
  const mapLinkParam = params.get('maplink');

  // Restore filter/chip state from the URL (set by syncFiltersToUrl on a
  // previous visit) before the first apply(), so a reload or Back
  // navigation lands on the same filtered view instead of resetting to
  // "All".
  const savedView = restoreFiltersFromUrl();

  if (sectionalParam) {{
    const [lat, lng] = sectionalParam.split(',').map(Number);
    if (Number.isFinite(lat) && Number.isFinite(lng)) showOnSectional(lat, lng);
  }} else if (mapLinkParam) {{
    const [lat, lng] = mapLinkParam.split(',').map(Number);
    if (Number.isFinite(lat) && Number.isFinite(lng)) showOnStreetMap(lat, lng);
  }} else if (savedView === 'map') {{
    setView('map');
  }} else if (savedView === 'favorites') {{
    setView('favorites');
  }} else {{
    apply();
  }}
</script>
</body>
</html>
"""

    DOCS_HTML_PATH.write_text(page, encoding="utf-8")
    return DOCS_HTML_PATH


if __name__ == "__main__":
    path = render()
    print(f"wrote {path}")
