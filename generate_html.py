"""Render merged strip records as a single self-contained HTML page with
grid/map views and sort/filter UI. Pattern mirrors the sibling project
backcountry-aircraft's generate_html.py.
"""

import html
from datetime import date
from pathlib import Path

import merge
from fetch_all import fetch_all

PROJECT_ROOT = Path(__file__).resolve().parent
DOCS_DIR = PROJECT_ROOT / "docs"
DOCS_DIR.mkdir(exist_ok=True)
DOCS_HTML_PATH = DOCS_DIR / "index.html"

SOURCE_LABELS = {
    "faa_nasr": "FAA",
    "idaho_itd": "Idaho ITD",
    "montana_mdt": "Montana MDT",
    "ubcp": "UBCP",
    "shortfield": "Shortfield",
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


def _source_label(source_key):
    parts = [SOURCE_LABELS.get(p, p) for p in source_key.split("+")]
    return " + ".join(parts)


def _fmt_number(value, suffix=""):
    if value is None:
        return ""
    try:
        return f"{int(value):,}{suffix}"
    except (TypeError, ValueError):
        return str(value)


def _build_cards(strips):
    cards_html = []
    states = set()
    surfaces = set()

    for strip in strips:
        name = html.escape(strip.get("name") or "Unnamed strip")
        identifier = html.escape(strip.get("identifier") or "")
        state = html.escape(strip.get("state") or "")
        surface = html.escape((strip.get("runway_surface") or "").strip())
        surface_key = _surface_category(strip.get("runway_surface"))
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

        notes = " ".join(
            filter(None, [strip.get("access_notes"), strip.get("condition_notes"), strip.get("hazards")])
        )
        notes_preview = html.escape(notes[:220] + ("…" if len(notes) > 220 else "")) if notes else ""

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

        cards_html.append(
            f"""<a class="card" href="{source_url}" target="_blank" rel="noopener"
   data-state="{state}" data-surface="{surface_key}" data-source="{html.escape(source_key)}"
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
    <div class="footer">
      <span class="source">{source_label}</span>
      {'<span class="attribution">' + attribution + '</span>' if attribution else ''}
    </div>
  </div>
</a>"""
        )

    return cards_html, sorted(states), sorted(surfaces)


def render():
    record_lists, stale_sources = fetch_all()
    if stale_sources:
        print(f"Using cached data for: {', '.join(stale_sources)}")
    strips = merge.merge(*record_lists)
    strips.sort(key=lambda s: s.get("name") or "")

    cards_html, states, surfaces = _build_cards(strips)

    state_buttons = "".join(
        f'<button class="chip state-chip" data-state="{html.escape(s, quote=True)}">{html.escape(s)}</button>'
        for s in states
    )
    surface_buttons = "".join(
        f'<button class="chip surface-chip" data-surface="{html.escape(s, quote=True)}">{html.escape(s)}</button>'
        for s in surfaces
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
  .filter-toggle {{ display:none; padding:6px 14px; border:1px solid var(--border);
                    border-radius:6px; background:var(--bg); color:var(--fg); font:inherit;
                    cursor:pointer; }}
  #filter-panel {{ display:block; }}
  @media (max-width: 759px) {{
    header {{ position:static; padding:10px 14px; }}
    .filter-toggle {{ display:inline-flex; align-items:center; gap:6px; }}
    #filter-panel {{ display:none; margin-top:10px; }}
    #filter-panel.open {{ display:block; }}
    #floating-filter {{ position:fixed; right:14px; bottom:14px; z-index:5;
                        background:var(--accent); color:#fff; border:0; padding:10px 16px;
                        border-radius:999px; font:inherit; font-weight:600;
                        box-shadow:0 4px 12px rgba(0,0,0,0.25); cursor:pointer; }}
  }}
  @media (min-width: 760px) {{
    #floating-filter {{ display:none; }}
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
  #map {{ height: calc(100vh - 220px); min-height: 500px; margin:0 20px 20px 20px;
          border-radius: 10px; border:1px solid var(--border); display:none; }}
  body.map-view #grid, body.map-view #empty {{ display:none; }}
  body.map-view #map {{ display:block; }}
  .leaflet-popup-content {{ margin:8px 10px; }}
  .leaflet-popup-content .popup-title {{ font-weight:600; font-size:13px; margin-bottom:2px; }}
  .leaflet-popup-content .popup-sub {{ font-size:11px; color:#666; margin-bottom:4px; }}
  .leaflet-popup-content a {{ color:#0366d6; text-decoration:none; font-size:11px; }}
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
      <button class="filter-toggle" id="filter-toggle" aria-expanded="false">Filters ▾</button>
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
  </div><!-- /#filter-panel -->
</header>
<button id="floating-filter" type="button">☰ Filters</button>
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

  // Mobile filter-panel toggle
  const filterPanel = document.getElementById('filter-panel');
  const filterToggle = document.getElementById('filter-toggle');
  const floatingFilter = document.getElementById('floating-filter');
  function toggleFilters() {{
    const open = !filterPanel.classList.contains('open');
    filterPanel.classList.toggle('open', open);
    filterToggle.setAttribute('aria-expanded', String(open));
    filterToggle.textContent = open ? 'Filters ▴' : 'Filters ▾';
    if (open) filterPanel.scrollIntoView({{behavior: 'smooth', block: 'start'}});
  }}
  filterToggle.addEventListener('click', toggleFilters);
  floatingFilter.addEventListener('click', toggleFilters);

  const searchEl = document.getElementById('search');
  const lengthMinEl = document.getElementById('length-min');
  const lengthMaxEl = document.getElementById('length-max');
  const elevationMinEl = document.getElementById('elevation-min');
  const elevationMaxEl = document.getElementById('elevation-max');

  function activeChips(selector) {{
    return new Set(
      Array.from(document.querySelectorAll(selector + '.active'))
        .map(c => c.dataset.state || c.dataset.surface)
        .filter(v => v && v !== '__all__')
    );
  }}

  function num(v) {{ const n = parseInt(v, 10); return Number.isFinite(n) ? n : null; }}

  function apply() {{
    const q = searchEl.value.trim().toLowerCase();
    const lMin = num(lengthMinEl.value), lMax = num(lengthMaxEl.value);
    const eMin = num(elevationMinEl.value), eMax = num(elevationMaxEl.value);
    const activeStates = activeChips('.state-chip');
    const activeSurfaces = activeChips('.surface-chip');
    const favView = document.body.classList.contains('fav-view');

    let visible = [];
    for (const c of cards) {{
      const state = c.dataset.state;
      const surface = c.dataset.surface;
      const length = parseInt(c.dataset.length, 10) || 0;
      const elevation = parseInt(c.dataset.elevation, 10) || 0;
      const search = c.dataset.search;

      let show = true;
      if (activeStates.size > 0 && !activeStates.has(state)) show = false;
      if (activeSurfaces.size > 0 && !activeSurfaces.has(surface)) show = false;
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
    if (document.body.classList.contains('map-view')) renderMarkers();
  }}

  function wireChipRow(rowSelector) {{
    const chips = document.querySelectorAll(rowSelector);
    const allChip = Array.from(chips).find(c =>
      (c.dataset.state || c.dataset.surface) === '__all__'
    );
    chips.forEach(b => b.addEventListener('click', () => {{
      const key = b.dataset.state || b.dataset.surface;
      if (key === '__all__') {{
        chips.forEach(x => x.classList.remove('active'));
        b.classList.add('active');
      }} else {{
        b.classList.toggle('active');
        const others = Array.from(chips).filter(c =>
          (c.dataset.state || c.dataset.surface) !== '__all__' && c.classList.contains('active')
        );
        if (allChip) allChip.classList.toggle('active', others.length === 0);
      }}
      apply();
    }}));
  }}
  wireChipRow('.state-chip');
  wireChipRow('.surface-chip');
  for (const el of [searchEl, lengthMinEl, lengthMaxEl, elevationMinEl, elevationMaxEl]) {{
    el.addEventListener('input', apply);
    el.addEventListener('change', apply);
  }}

  // ---- Map view (Leaflet) ----
  let map = null;
  let markerLayer = null;
  function initMap() {{
    if (map) return;
    map = L.map('map', {{ scrollWheelZoom: true }}).setView([39.8, -98.5], 4);
    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 18,
    }}).addTo(map);
    markerLayer = L.markerClusterGroup({{ maxClusterRadius: 50 }}).addTo(map);
  }}
  function renderMarkers() {{
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
    if (bounds.length > 0) map.fitBounds(bounds, {{padding: [30, 30], maxZoom: 10}});
  }}
  const viewGrid = document.getElementById('view-grid');
  const viewFav = document.getElementById('view-favorites');
  const viewMap = document.getElementById('view-map');
  function setView(view) {{
    document.body.classList.toggle('map-view', view === 'map');
    document.body.classList.toggle('fav-view', view === 'favorites');
    viewGrid.classList.toggle('active', view === 'grid');
    viewFav.classList.toggle('active', view === 'favorites');
    viewMap.classList.toggle('active', view === 'map');
    apply();
    if (view === 'map') {{
      initMap();
      setTimeout(() => {{ map.invalidateSize(); renderMarkers(); }}, 50);
    }}
  }}
  viewGrid.addEventListener('click', () => setView('grid'));
  viewFav.addEventListener('click', () => setView('favorites'));
  viewMap.addEventListener('click', () => setView('map'));
  apply();
</script>
</body>
</html>
"""

    DOCS_HTML_PATH.write_text(page, encoding="utf-8")
    return DOCS_HTML_PATH


if __name__ == "__main__":
    path = render()
    print(f"wrote {path}")
