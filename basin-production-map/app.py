"""
Basin Production Map

Monthly oil, gas and water production for every well in a made-up basin, on a
full-screen map. Scrub or play through the months to watch the field get drilled
up and decline, color the wells by rate, gas-oil ratio, water cut, rock quality,
operator, bench or vintage, and lasso an area to add up what it makes. Click a
well for its production history, its events and how it compares with its
nearest offsets. All the map settings and filters live in a drawer on the left.

The wells and their production are synthetic, see basin.py.
"""

import dash
import dash_mantine_components as dmc
import numpy as np
import plotly.graph_objects as go
from dash import ALL, Input, Output, State, ctx, dcc, html, no_update
from dash._hooks import HooksManager
from dash_iconify import DashIconify
from plotly.subplots import make_subplots

import basin as bs

# Chart colors, kept in sync with assets/style.css
INK = "#f0efec"
INK_2 = "#c3c2b7"
MUTED = "#898781"
GRID = "#2c2c2a"
AXIS = "#383835"
PANEL = "#1a1a19"
GOOD, CRITICAL = "#0ca30c", "#d03b3b"
STREAM_COLOR = {"Oil": "#199e70", "Gas": "#d95926", "Water": "#3987e5"}

# Map palettes. On the dark and satellite basemaps bigger values are brighter;
# on the light basemap they are darker, so the busiest wells always stand out.
SEQ = {
    "dark": ["#184f95", "#2a78d6", "#5598e7", "#86b6ef", "#cde2fb"],
    "light": ["#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#104281"],
}
VINTAGE = {
    "dark": ["#184f95", "#1c5cab", "#256abf", "#2a78d6", "#3987e5", "#5598e7", "#6da7ec", "#86b6ef", "#b7d3f6"],
    "light": ["#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6", "#1c5cab", "#184f95", "#0d366b"],
}
CATEGORICAL = {
    "dark": ["#3987e5", "#d95926", "#199e70"],
    "light": ["#2a78d6", "#eb6834", "#1baf7a"],
}
OTHER = "#898781"
NO_DATA = {"dark": "#5c5b56", "light": "#b4b3ab"}
STATUS_COLOR = {"Producing": GOOD, "Shut in": CRITICAL, "Plugged": OTHER}
STATUS_ICON = {"Producing": "tabler:circle-check", "Shut in": "tabler:player-stop", "Plugged": "tabler:circle-x"}

BASEMAPS = {
    "dark": dict(style="carto-darkmatter"),
    "light": dict(style="carto-positron"),
    "satellite": dict(style="white-bg", layers=[dict(
        below="traces", sourcetype="raster",
        source=["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
        sourceattribution="Imagery © Esri, Maxar, Earthstar Geographics",
    )]),
}

# Binned metrics: value per well at the month, bin edges, unit
METRICS = {
    "boe": dict(label="Production, BOE/d", short="BOE/d", edges=[50, 100, 200, 400]),
    "oil": dict(label="Oil rate, bbl/d", short="bbl/d", edges=[25, 50, 100, 200]),
    "gas": dict(label="Gas rate, Mcf/d", short="Mcf/d", edges=[150, 300, 600, 1200]),
    "wcut": dict(label="Water cut, %", short="%", edges=[60, 70, 80, 90]),
    "gor": dict(label="Gas-oil ratio, scf/bbl", short="scf/bbl", edges=[2000, 4000, 8000, 16000]),
    "y1": dict(label="First-year oil per 1,000 ft, bbl", short="bbl", edges=[6000, 9000, 12000, 16000]),
}
COLOR_OPTIONS = [
    {"group": "This month", "items": [
        {"value": "boe", "label": "Production (BOE/d)"},
        {"value": "oil", "label": "Oil rate"},
        {"value": "gas", "label": "Gas rate"},
        {"value": "wcut", "label": "Water cut"},
        {"value": "gor", "label": "Gas-oil ratio"},
        {"value": "status", "label": "Well status"},
    ]},
    {"group": "Well", "items": [
        {"value": "y1", "label": "First-year oil per 1,000 ft"},
        {"value": "vintage", "label": "First production year"},
        {"value": "operator", "label": "Operator"},
        {"value": "formation", "label": "Formation (bench)"},
    ]},
]

LAST = bs.N_MONTHS - 1
BOE_SIZE_MAX = 900  # BOE/d at which a bubble reaches full size, fixed so months compare
MAP_CENTER = dict(lat=32.36, lon=-103.30)  # nudged east so the right panel doesn't cover the basin
YEARS = list(range(2018, bs.AS_OF.year + 1))  # 2018 stands for "before 2019"

FONT = "'Manrope', system-ui, sans-serif"
THEME = {
    "fontFamily": FONT,
    "headings": {"fontFamily": FONT},
    "primaryColor": "flare",
    "primaryShade": 5,
    "defaultRadius": "md",
    "colors": {
        "flare": ["#fff4e2", "#ffe7cc", "#fdcd9b", "#fbb265", "#f99b38", "#f88c1b", "#f8840a", "#dd7100", "#c56400", "#ab5500"],
        "dark": ["#f0efec", "#c3c2b7", "#a3a29a", "#898781", "#5c5b56", "#383835", "#252524", "#1a1a19", "#111110", "#0b0b0a"],
    },
}

# Skip installed Dash plugins (such as an embedded chat) so the app renders on its own
HooksManager._registered = True

app = dash.Dash(
    __name__,
    title="Basin Production Map",
    external_stylesheets=["https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap"],
)
server = app.server


# ---------------------------------------------------------------- helpers

def month_name(m, long=False):
    return bs.MONTHS[m].strftime("%B %Y" if long else "%b %Y")


def fmt(x, digits=0):
    if x is None or not np.isfinite(x):
        return "–"
    return f"{x:,.{digits}f}"


def ratio(num, den):
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(den > 0, num / den, np.nan)


def base_mask(ops, forms, wtype, vintage):
    """Wells that pass the filters that don't depend on the month."""
    mask = np.isin(bs.OPERATOR, ops or []) & np.isin(bs.FORMATION, forms or [])
    mask &= (bs.FIRST_YEAR >= vintage[0]) & (bs.FIRST_YEAR <= vintage[1])
    if wtype != "All":
        mask &= bs.TYPE == wtype
    return mask


def visible(mask, statuses, m):
    """Wells on the map in month m: on production (or shut in / plugged) and matching filters."""
    st = bs.STATUS[:, m]
    keep = np.zeros(bs.N_WELLS, bool)
    for code, name in enumerate(bs.STATUSES, start=1):
        if name in (statuses or []):
            keep |= st == code
    return np.flatnonzero(mask & keep)


def metric_values(key, idx, m):
    oil, gas, water = bs.OIL[idx, m], bs.GAS[idx, m], bs.WATER[idx, m]
    if key == "boe":
        return bs.BOE[idx, m]
    if key == "oil":
        return oil
    if key == "gas":
        return gas
    if key == "wcut":
        return 100 * ratio(water, water + oil)
    if key == "gor":
        return 1000 * ratio(gas, oil)
    return bs.Y1_OIL_PER_KFT[idx]


def bin_labels(edges, unit):
    e = [f"{v / 1000:g}k" if v >= 1000 else f"{v:g}" for v in edges]
    return [f"<{e[0]}"] + e[:-1] + [f"{e[-1]}+"]  # each bin labelled by where it starts


def well_colors(color_by, idx, m, tone):
    """A color per visible well and the legend that explains them."""
    nd = NO_DATA[tone]
    cat = CATEGORICAL[tone]
    if color_by in METRICS:
        spec = METRICS[color_by]
        v = metric_values(color_by, idx, m)
        b = np.digitize(np.nan_to_num(v, nan=-1), spec["edges"])
        ramp = SEQ["light" if tone == "light" else "dark"]
        live = np.isfinite(v) & ((bs.STATUS[idx, m] == 1) | (color_by == "y1"))
        colors = np.where(live, np.array(ramp)[b], nd)
        nd_label = "No first-year data" if color_by == "y1" else "Not producing"
        return list(colors), dict(kind="ramp", title=spec["label"], colors=ramp,
                                  labels=bin_labels(spec["edges"], spec["short"]), nd=(nd, nd_label))
    if color_by == "status":
        names = np.array(bs.STATUSES)[np.clip(bs.STATUS[idx, m] - 1, 0, 2)]
        return [STATUS_COLOR[n] for n in names], dict(
            kind="list", title="Status this month",
            items=[(STATUS_COLOR[s], s, STATUS_ICON[s]) for s in bs.STATUSES])
    if color_by == "operator":
        lut = dict(zip(bs.OPERATORS, cat + [OTHER]))
        return [lut[o] for o in bs.OPERATOR[idx]], dict(
            kind="list", title="Operator", items=[(lut[o], o, None) for o in bs.OPERATORS])
    if color_by == "formation":
        lut = dict(zip(bs.FORMATIONS, cat))
        return [lut[f] for f in bs.FORMATION[idx]], dict(
            kind="list", title="Formation", items=[(lut[f], f, None) for f in bs.FORMATIONS])
    ramp = VINTAGE["light" if tone == "light" else "dark"]
    colors = [ramp[y - YEARS[0]] for y in bs.FIRST_YEAR[idx]]
    return colors, dict(kind="ramp", title="First production year", colors=ramp,
                        labels=["< 2019"] + [f"’{str(y)[2:]}" for y in YEARS[1:]], nd=None)


def bubble_sizes(idx, m, size_by):
    if size_by == "same":
        return np.full(len(idx), 10.0)
    boe = bs.BOE[idx, m]
    return np.where(bs.STATUS[idx, m] == 1, 5 + 19 * np.sqrt(np.clip(boe / BOE_SIZE_MAX, 0, 1)), 5)


def hover_text(idx, m):
    out = []
    for i in idx:
        w = bs.WELLS[i]
        st = bs.STATUSES[bs.STATUS[i, m] - 1]
        out.append(
            f"<b>{w.name}</b><br>{w.operator} · {w.formation}<br>"
            f"Oil {fmt(bs.OIL[i, m])} bbl/d · Gas {fmt(bs.GAS[i, m])} Mcf/d<br>"
            f"Water {fmt(bs.WATER[i, m])} bbl/d · {st}"
        )
    return out


def _lines(pairs):
    lat, lon = [], []
    for a, b in pairs:
        lat += [a[0], b[0], None]
        lon += [a[1], b[1], None]
    return lat, lon


FAC = {f["name"]: f for f in bs.FACILITIES}


# ---------------------------------------------------------------- map

def map_figure(idx, m, color_by, size_by, basemap, layers, mode, sel, lasso, tool):
    tone = "light" if basemap == "light" else "dark"
    hi = "#0b0b0b" if tone == "light" else "#ffffff"
    fig = go.Figure()

    if "facilities" in layers:
        lat, lon = _lines([((FAC[a]["lat"], FAC[a]["lon"]), (FAC[b]["lat"], FAC[b]["lon"])) for a, b in bs.PIPELINES])
        fig.add_trace(go.Scattermap(lat=lat, lon=lon, mode="lines", hoverinfo="skip",
                                    line=dict(width=2, color="#8a8780" if tone == "dark" else "#7a7974")))
        fig.add_trace(go.Scattermap(
            lat=[f["lat"] for f in bs.FACILITIES], lon=[f["lon"] for f in bs.FACILITIES],
            mode="markers+text", text=[f["name"] for f in bs.FACILITIES], textposition="bottom right",
            textfont=dict(color=INK_2 if tone == "dark" else "#52514e", size=11),
            marker=dict(size=9, color="#e8e6df" if tone == "dark" else "#52514e"),
            hovertext=[f"<b>{f['name']}</b><br>{f['kind']}" for f in bs.FACILITIES],
            hovertemplate="%{hovertext}<extra></extra>",
        ))

    if "laterals" in layers:
        hz = [i for i in idx if bs.TYPE[i] == "Horizontal"]
        lat, lon = _lines([(bs.WELLS[i].heel, bs.WELLS[i].toe) for i in hz])
        fig.add_trace(go.Scattermap(lat=lat or [None], lon=lon or [None], mode="lines", hoverinfo="skip",
                                    line=dict(width=1.5, color="rgba(240,239,236,0.28)" if tone == "dark" else "rgba(11,11,11,0.25)")))

    # The selected well: its lateral, a halo, and dotted links to its nearest offsets
    if sel is not None:
        w = bs.WELLS[sel]
        offs = bs.offsets(sel)
        lat, lon = _lines([((w.lat, w.lon), (bs.LAT[j], bs.LON[j])) for j, _ in offs])
        fig.add_trace(go.Scattermap(lat=lat, lon=lon, mode="lines", hoverinfo="skip",
                                    line=dict(width=1, color=hi), opacity=0.45))
        fig.add_trace(go.Scattermap(lat=[bs.LAT[j] for j, _ in offs], lon=[bs.LON[j] for j, _ in offs],
                                    mode="markers", hoverinfo="skip", customdata=[j for j, _ in offs],
                                    marker=dict(size=16, color=hi, opacity=0.18)))
        if w.well_type == "Horizontal":
            lat, lon = _lines([(w.heel, w.toe)])
            fig.add_trace(go.Scattermap(lat=lat, lon=lon, mode="lines", hoverinfo="skip", line=dict(width=4, color=hi)))
        fig.add_trace(go.Scattermap(lat=[w.lat], lon=[w.lon], mode="markers", hoverinfo="skip", customdata=[sel],
                                    marker=dict(size=34, color=hi, opacity=0.3)))

    if mode == "heat" and len(idx):
        ramp = SEQ["light" if tone == "light" else "dark"]
        fig.add_trace(go.Densitymap(
            lat=bs.LAT[idx], lon=bs.LON[idx], z=bs.BOE[idx, m], radius=26, zmin=0, zmax=500,
            colorscale=[[0, "rgba(0,0,0,0)"], [0.15, ramp[0]], [0.45, ramp[2]], [1, ramp[4]]],
            showscale=False, hoverinfo="skip", opacity=0.85,
        ))
        fig.add_trace(go.Scattermap(
            lat=bs.LAT[idx], lon=bs.LON[idx], mode="markers", customdata=idx,
            marker=dict(size=5, color=hi, opacity=0.55),
            hovertext=hover_text(idx, m), hovertemplate="%{hovertext}<extra></extra>",
        ))
        legend = dict(kind="heat", title="Production density, BOE/d", colors=ramp)
    else:
        colors, legend = well_colors(color_by, idx, m, tone)
        sizes = bubble_sizes(idx, m, size_by)
        order = np.argsort(-sizes, kind="stable")  # small bubbles on top of big ones
        idx, colors, sizes = idx[order], [colors[k] for k in order], sizes[order]
        trace = dict(
            lat=bs.LAT[idx], lon=bs.LON[idx], mode="markers", customdata=idx,
            marker=dict(size=sizes, color=colors, opacity=0.9),
            hovertext=hover_text(idx, m), hovertemplate="%{hovertext}<extra></extra>",
            unselected=dict(marker=dict(opacity=0.18)),
        )
        if lasso:
            chosen = set(lasso)
            trace["selectedpoints"] = [k for k, i in enumerate(idx) if i in chosen]
        fig.add_trace(go.Scattermap(**trace))

    fig.update_layout(
        map=dict(center=MAP_CENTER, zoom=9.25, **BASEMAPS[basemap]),
        margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="#0e0e0d", showlegend=False,
        uirevision="basin", dragmode=tool, clickmode="event",
        selectionrevision="lasso" if lasso else f"clear-{m}",
        hoverlabel=dict(bgcolor="#252524", bordercolor="#383835", font=dict(color=INK, family=FONT, size=12)),
    )
    if not lasso:
        fig.update_layout(selections=[])
    return fig, legend


def legend_view(legend, size_by, mode):
    rows = [html.Div(legend["title"], className="legend-title")]
    if legend["kind"] == "ramp":
        rows.append(html.Div([html.Span(style={"background": c}) for c in legend["colors"]], className="ramp"))
        rows.append(html.Div([html.Span(t) for t in legend["labels"]], className="ramp-labels"))
        if legend.get("nd"):
            c, label = legend["nd"]
            rows.append(html.Div([html.Span(className="dot", style={"background": c}), label], className="legend-row muted"))
    elif legend["kind"] == "heat":
        rows.append(html.Div(className="heat-bar", style={"background": f"linear-gradient(90deg, transparent, {legend['colors'][0]}, {legend['colors'][2]}, {legend['colors'][4]})"}))
        rows.append(html.Div([html.Span("Sparse"), html.Span("Concentrated")], className="ramp-labels two"))
    else:
        for c, label, icon in legend["items"]:
            mark = DashIconify(icon=icon, width=14, color=c) if icon else html.Span(className="dot", style={"background": c})
            rows.append(html.Div([mark, label], className="legend-row"))
    if mode != "heat" and size_by != "same":
        rows.append(html.Div([
            html.Span(className="size-dot", style={"width": 6, "height": 6}),
            html.Span(className="size-dot", style={"width": 12, "height": 12}),
            html.Span(className="size-dot", style={"width": 20, "height": 20}),
            html.Span("Bubble size: BOE/d"),
        ], className="size-key"))
    return rows


# ---------------------------------------------------------------- side panel

def chart_layout(fig, height):
    fig.update_layout(
        height=height, margin=dict(l=8, r=8, t=24, b=8), paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)", font=dict(family=FONT, color=INK_2, size=11),
        hoverlabel=dict(bgcolor="#252524", bordercolor="#383835", font=dict(color=INK, family=FONT)),
        hovermode="x unified",
    )
    fig.update_xaxes(showgrid=False, linecolor=AXIS, tickcolor=AXIS, ticks="outside", ticklen=3,
                     tickfont=dict(color=MUTED))
    fig.update_yaxes(gridcolor=GRID, zeroline=False, tickfont=dict(color=MUTED))
    return fig


def month_marker(fig, m, **kw):
    fig.add_vline(x=bs.MONTHS[m], line=dict(color=INK, width=1, dash="dot"), opacity=0.6, **kw)


def stat(label, value, unit="", sub=None):
    return html.Div([
        html.Div(label, className="stat-label"),
        html.Div([value, html.Span(f" {unit}" if unit else "", className="stat-unit")], className="stat-value"),
        html.Div(sub, className="stat-sub") if sub else None,
    ], className="stat")


def well_chart(i, m):
    w = bs.WELLS[i]
    start = max(w.first_month, 0)
    x = bs.MONTHS[start:]
    oil, gas = bs.OIL[i, start:], bs.GAS[i, start:]
    wcut = 100 * ratio(bs.WATER[i, start:], bs.WATER[i, start:] + oil)
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.09,
                        subplot_titles=["Oil, bbl/d", "Gas, Mcf/d", "Water cut, %"])
    for row, (name, y, unit) in enumerate([("Oil", oil, "bbl/d"), ("Gas", gas, "Mcf/d"), ("Water", wcut, "%")], start=1):
        fig.add_trace(go.Scatter(x=x, y=y, mode="lines", line=dict(color=STREAM_COLOR[name], width=2),
                                 name=name, connectgaps=False,
                                 hovertemplate=f"%{{y:,.0f}} {unit}<extra>{'Water cut' if row == 3 else name}</extra>"),
                      row=row, col=1)
    ev = [(em, label) for em, label in w.events if em >= start]
    if ev:
        fig.add_trace(go.Scatter(
            x=[bs.MONTHS[em] for em, _ in ev], y=[max(bs.OIL[i, em], 1) for em, _ in ev], mode="markers",
            marker=dict(symbol="triangle-down", size=9, color=INK, line=dict(color=PANEL, width=1)),
            text=[label for _, label in ev], name="Event", hovertemplate="%{text}<extra></extra>",
        ), row=1, col=1)
    fig.update_yaxes(rangemode="tozero", tickformat="~s", nticks=4, row=1, col=1)
    fig.update_yaxes(rangemode="tozero", tickformat="~s", nticks=4, row=2, col=1)
    fig.update_yaxes(range=[0, 100], row=3, col=1)
    chart_layout(fig, 360)
    fig.update_layout(showlegend=False, margin=dict(t=20))
    for a in fig.layout.annotations:
        a.update(x=0, xanchor="left", font=dict(size=11, color=MUTED))
    if m >= start:
        month_marker(fig, m, row="all", col=1)
    return fig


def well_panel(i, m):
    w = bs.WELLS[i]
    code = bs.STATUS[i, m]
    online = code > 0
    st = bs.STATUSES[code - 1] if online else "Not online yet"
    badge_color = {"Producing": "green", "Shut in": "red", "Plugged": "gray"}.get(st, "gray")
    oil, gas, water = bs.OIL[i, m], bs.GAS[i, m], bs.WATER[i, m]
    y1 = bs.Y1_OIL_PER_KFT[i]
    same = bs.Y1_OIL_PER_KFT[(bs.FORMATION == w.formation) & np.isfinite(bs.Y1_OIL_PER_KFT)]
    rank = f"Better than {int(round(100 * (same < y1).mean()))}% of {w.formation} wells" if np.isfinite(y1) else "Needs 12 months on production"
    first = month_name(w.first_month, long=True) if w.first_month >= 0 else "before 2019"
    desc = f"{w.well_type} · {fmt(w.lateral_ft)} ft lateral" if w.lateral_ft else "Vertical"

    offs = bs.offsets(i)
    comp = [(i, 0.0)] + offs
    vals = [bs.Y1_OIL_PER_KFT[j] for j, _ in comp]
    top = np.nanmax(vals) if np.any(np.isfinite(vals)) else 1
    offset_rows = []
    for (j, d), v in zip(comp, vals):
        ow = bs.WELLS[j]
        offset_rows.append(html.Div([
            html.Div([
                html.Div("This well" if j == i else ow.name, className="row-name"),
                html.Div(ow.formation if j == i else f"{d:.1f} mi · {ow.formation}", className="row-sub"),
            ], className="row-text"),
            html.Div(html.Div(className="bar-fill" + (" self" if j == i else ""),
                              style={"width": f"{0 if not np.isfinite(v) else 100 * v / top:.0f}%"}), className="bar"),
            html.Div(fmt(v / 1000, 1) + "k" if np.isfinite(v) else "–", className="row-val"),
        ], className="pick-row" + (" is-self" if j == i else ""),
            id={"type": "pick", "i": int(j)} if j != i else f"self-{j}", n_clicks=0))

    events = [html.Div([html.Span(month_name(em), className="ev-date"), html.Span(label)], className="ev")
              for em, label in reversed(w.events[-6:])]

    return [
        html.Div([
            html.Div([
                html.Div(w.name, className="panel-title"),
                html.Div(f"{w.operator} · API {w.api}", className="panel-sub"),
            ]),
            dmc.ActionIcon(DashIconify(icon="tabler:x", width=18), id={"type": "close-well", "i": 0},
                           variant="subtle", color="gray", n_clicks=0, **{"aria-label": "Close well"}),
        ], className="panel-head"),
        html.Div([
            dmc.Badge(st, color=badge_color, variant="light", radius="sm"),
            html.Span(f"{w.formation} · {desc}", className="panel-meta"),
        ], className="panel-badges"),
        html.Div(f"First production {first}", className="panel-meta block"),
        html.Div(month_name(m, long=True), className="section-label"),
        html.Div([
            stat("Oil", fmt(oil), "bbl/d"),
            stat("Gas", fmt(gas), "Mcf/d"),
            stat("Water cut", fmt(100 * water / (water + oil), 0) if oil + water > 0 else "–", "%"),
            stat("Cum oil", fmt(bs.CUM_OIL[i, m] / 1000, 1), "Mbbl"),
            stat("Cum gas", fmt(bs.CUM_GAS[i, m] / 1e6, 2), "Bcf"),
            stat("GOR", fmt(1000 * gas / oil) if oil > 0 else "–", "scf/bbl"),
        ], className="stat-grid"),
        dcc.Graph(figure=well_chart(i, m), config={"displayModeBar": False}, className="panel-chart"),
        html.Div("▼ marks downtime events, hover for details.", className="note"),
        html.Div("First-year oil per 1,000 ft vs nearest offsets", className="section-label"),
        html.Div(rank, className="panel-meta block"),
        html.Div(offset_rows, className="pick-list"),
        html.Div("Events", className="section-label") if events else None,
        html.Div(events, className="ev-list") if events else None,
    ]


def group_panel(idx_all, idx_now, m, title, sub, clearable):
    """Totals and breakdowns for a set of wells: the whole filtered field or a lasso selection."""
    oil, gas, water = bs.OIL[idx_now, m].sum(), bs.GAS[idx_now, m].sum(), bs.WATER[idx_now, m].sum()
    producing = int((bs.STATUS[idx_now, m] == 1).sum())

    fig = go.Figure()
    for k, f in enumerate(bs.FORMATIONS):
        sub_idx = idx_all[bs.FORMATION[idx_all] == f]
        fig.add_trace(go.Scatter(
            x=bs.MONTHS, y=bs.BOE[sub_idx].sum(axis=0), name=f, stackgroup="b", mode="lines",
            line=dict(width=1, color=PANEL), fillcolor=CATEGORICAL["dark"][k],
            hovertemplate="%{y:,.0f}<extra>" + f + "</extra>",
        ))
    chart_layout(fig, 210)
    fig.update_layout(legend=dict(orientation="h", y=1.18, x=0, font=dict(size=11, color=INK_2)),
                      margin=dict(t=34))
    fig.update_yaxes(tickformat="~s", title=None)
    month_marker(fig, m)

    boe_now = bs.BOE[idx_now, m]
    top = idx_now[np.argsort(-boe_now)][:8]
    top_val = bs.BOE[top[0], m] if len(top) else 1
    rows = [html.Div([
        html.Div([html.Div(bs.WELLS[j].name, className="row-name"),
                  html.Div(f"{bs.WELLS[j].operator} · {bs.WELLS[j].formation}", className="row-sub")], className="row-text"),
        html.Div(html.Div(className="bar-fill", style={"width": f"{100 * bs.BOE[j, m] / max(top_val, 1):.0f}%"}), className="bar"),
        html.Div(fmt(bs.BOE[j, m]), className="row-val"),
    ], className="pick-row", id={"type": "pick", "i": int(j)}, n_clicks=0) for j in top if bs.BOE[j, m] > 0]

    by_op = [(o, bs.BOE[idx_now[bs.OPERATOR[idx_now] == o], m].sum()) for o in bs.OPERATORS]
    op_top = max([v for _, v in by_op] + [1])
    op_rows = [html.Div([
        html.Div(o, className="row-name"),
        html.Div(html.Div(className="bar-fill neutral", style={"width": f"{100 * v / op_top:.0f}%"}), className="bar"),
        html.Div(fmt(v), className="row-val"),
    ], className="op-row") for o, v in by_op]

    head_right = dmc.Button("Clear", id={"type": "clear-lasso", "i": 0}, size="compact-sm", variant="light",
                            color="gray", leftSection=DashIconify(icon="tabler:x", width=14), n_clicks=0) if clearable else None
    return [
        html.Div([html.Div([html.Div(title, className="panel-title"), html.Div(sub, className="panel-sub")]), head_right],
                 className="panel-head"),
        html.Div(month_name(m, long=True), className="section-label"),
        html.Div([
            stat("Oil", fmt(oil), "bbl/d"),
            stat("Gas", fmt(gas / 1000, 1), "MMcf/d"),
            stat("Water", fmt(water), "bbl/d"),
            stat("BOE", fmt(oil + gas / 6), "BOE/d"),
            stat("Wells producing", f"{producing}", f"of {len(idx_now)}"),
            stat("Water cut", fmt(100 * water / (water + oil)) if oil + water else "–", "%"),
        ], className="stat-grid"),
        html.Div("Production by formation, BOE/d", className="section-label"),
        dcc.Graph(figure=fig, config={"displayModeBar": False}, className="panel-chart"),
        html.Div(f"Top producers, {month_name(m)} (BOE/d)", className="section-label"),
        html.Div(rows or html.Div("No wells producing this month", className="note"), className="pick-list"),
        html.Div(f"By operator, {month_name(m)} (BOE/d)", className="section-label"),
        html.Div(op_rows, className="op-list"),
    ]


def kpi(label, value, unit, delta=None, good_up=True):
    d = None
    if delta is not None and np.isfinite(delta):
        up = delta >= 0
        color = (GOOD if up == good_up else CRITICAL) if good_up is not None else INK_2
        d = html.Div([
            DashIconify(icon="tabler:arrow-up-right" if up else "tabler:arrow-down-right", width=13, color=color),
            html.Span(f"{abs(delta):.0f}% y/y", style={"color": color}),
        ], className="kpi-delta")
    return html.Div([html.Div(label, className="kpi-label"),
                     html.Div([value, html.Span(unit, className="kpi-unit")], className="kpi-value"), d],
                    className="kpi")


def kpis(mask, idx_now, m):
    def yoy(arr):
        if m < 12:
            return None
        then = arr[mask, m - 12].sum()
        return 100 * (arr[mask, m].sum() / then - 1) if then > 0 else None

    oil, gas, water = bs.OIL[idx_now, m].sum(), bs.GAS[idx_now, m].sum(), bs.WATER[idx_now, m].sum()
    producing = int((bs.STATUS[idx_now, m] == 1).sum())
    return [
        kpi("Oil", fmt(oil), "bbl/d", yoy(bs.OIL)),
        kpi("Gas", fmt(gas / 1000, 1), "MMcf/d", yoy(bs.GAS)),
        kpi("Water", fmt(water), "bbl/d", yoy(bs.WATER), good_up=None),
        kpi("Producing", f"{producing}", f"/ {len(idx_now)} wells"),
    ]


def spark_figure(mask, m):
    y = bs.BOE[mask].sum(axis=0)
    fig = go.Figure(go.Scatter(
        x=bs.MONTHS, y=y, mode="lines", line=dict(color="#86b6ef", width=1.5), fill="tozeroy",
        fillcolor="rgba(134,182,239,0.14)", hovertemplate="%{x|%b %Y}: %{y:,.0f} BOE/d<extra></extra>",
    ))
    fig.add_trace(go.Scatter(x=[bs.MONTHS[m]], y=[y[m]], mode="markers", hoverinfo="skip",
                             marker=dict(size=8, color="#f88c1b", line=dict(color=PANEL, width=2))))
    fig.add_vline(x=bs.MONTHS[m], line=dict(color="#f88c1b", width=1))
    fig.update_layout(height=52, margin=dict(l=0, r=0, t=4, b=0), paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", showlegend=False, hovermode="x",
                      hoverlabel=dict(bgcolor="#252524", bordercolor="#383835", font=dict(color=INK, family=FONT)))
    fig.update_xaxes(visible=False, range=[bs.MONTHS[0], bs.MONTHS[-1]])
    fig.update_yaxes(visible=False, rangemode="tozero")
    return fig


# ---------------------------------------------------------------- layout

def swatch_label(color, text):
    return html.Span([html.Span(className="dot", style={"background": color}), text], className="swatch-label")


def section(title, *children):
    return html.Div([html.Div(title, className="drawer-section-title"), *children], className="drawer-section")


DEFAULTS = dict(
    color_by="boe", size_by="boe", basemap="dark", layers=["laterals"], mode="wells",
    ops=list(bs.OPERATORS), forms=list(bs.FORMATIONS), wtype="All",
    statuses=["Producing", "Shut in"], vintage=[YEARS[0], YEARS[-1]],
)

drawer = dmc.Drawer(
    id="controls", opened=False, position="left", size=340, withOverlay=False, zIndex=300,
    title=html.Div([DashIconify(icon="tabler:adjustments-horizontal", width=20), "Map controls"], className="drawer-title"),
    classNames={"content": "drawer-content", "header": "drawer-header"},
    children=[
        section("Color wells by",
                dmc.Select(id="color-by", data=COLOR_OPTIONS, value=DEFAULTS["color_by"], allowDeselect=False,
                           checkIconPosition="right", comboboxProps={"zIndex": 400})),
        section("Bubble size",
                dmc.SegmentedControl(id="size-by", fullWidth=True, value=DEFAULTS["size_by"],
                                     data=[{"value": "boe", "label": "By BOE/d"}, {"value": "same", "label": "All the same"}])),
        section("Map view",
                dmc.SegmentedControl(id="map-mode", fullWidth=True, value=DEFAULTS["mode"],
                                     data=[{"value": "wells", "label": "Wells"}, {"value": "heat", "label": "Heat map"}])),
        section("Basemap",
                dmc.SegmentedControl(id="basemap", fullWidth=True, value=DEFAULTS["basemap"],
                                     data=[{"value": "dark", "label": "Dark"}, {"value": "light", "label": "Light"},
                                           {"value": "satellite", "label": "Satellite"}])),
        section("Layers",
                dmc.CheckboxGroup(id="layers", value=DEFAULTS["layers"], children=dmc.Stack([
                    dmc.Checkbox(value="laterals", label="Horizontal laterals"),
                    dmc.Checkbox(value="facilities", label="Pipelines and facilities"),
                ], gap=8))),
        dmc.Divider(my="md", label="Filter wells", labelPosition="left"),
        section("Operator",
                dmc.CheckboxGroup(id="f-operator", value=DEFAULTS["ops"], children=dmc.Stack([
                    dmc.Checkbox(value=o, label=o) for o in bs.OPERATORS], gap=8))),
        section("Formation",
                dmc.CheckboxGroup(id="f-formation", value=DEFAULTS["forms"], children=dmc.Stack([
                    dmc.Checkbox(value=f, label=f) for f in bs.FORMATIONS], gap=8))),
        section("Well type",
                dmc.SegmentedControl(id="f-type", fullWidth=True, value=DEFAULTS["wtype"],
                                     data=["All", "Horizontal", "Vertical"])),
        section("Status in the month shown",
                dmc.CheckboxGroup(id="f-status", value=DEFAULTS["statuses"], children=dmc.Group([
                    dmc.Checkbox(value=s, label=swatch_label(STATUS_COLOR[s], s)) for s in bs.STATUSES], gap=14))),
        section("First production year",
                html.Div(dmc.RangeSlider(
                    id="f-vintage", min=YEARS[0], max=YEARS[-1], step=1, minRange=0, value=DEFAULTS["vintage"],
                    marks=[{"value": YEARS[0], "label": "<2019"}] + [{"value": y, "label": f"’{str(y)[2:]}"} for y in YEARS[2::2]],
                    label=None,
                ), className="slider-wrap")),
        dmc.Button("Reset map and filters", id="reset", variant="light", color="gray", fullWidth=True, mt="lg",
                   leftSection=DashIconify(icon="tabler:refresh", width=16)),
        html.Div("Status and production filters apply to the month on the timeline. "
                 "Charts over time use the operator, formation, type and year filters.", className="note drawer-note"),
    ],
)

app.layout = dmc.MantineProvider(
    forceColorScheme="dark", theme=THEME,
    children=html.Div([
        dcc.Graph(id="map", className="map", config={"displayModeBar": False, "scrollZoom": True},
                  style={"height": "100vh", "width": "100vw"}),

        # Top left: brand, drawer button, filter summary and map tool
        html.Div([
            html.Div([
                dmc.Tooltip(dmc.ActionIcon(DashIconify(icon="tabler:menu-2", width=20), id="menu-btn", size="lg",
                                           variant="filled", color="flare", **{"aria-label": "Open map controls"}),
                            label="Map controls and filters", position="right"),
                html.Img(src=app.get_asset_url("logo.svg"), className="brand-mark", alt=""),
                html.Div([html.Div("Caprock Basin", className="brand-name"),
                          html.Div("Production by well", className="brand-sub")]),
            ], className="brand"),
            html.Div(id="filter-summary", className="filter-summary"),
            dmc.SegmentedControl(id="tool", size="xs", value="pan", data=[
                {"value": "pan", "label": html.Span([DashIconify(icon="tabler:hand-move", width=14), "Pan"], className="seg-label")},
                {"value": "lasso", "label": html.Span([DashIconify(icon="tabler:lasso", width=14), "Lasso"], className="seg-label")},
            ]),
        ], className="glass top-left"),

        html.Div(id="kpis", className="glass kpis"),
        html.Div(id="legend", className="glass legend"),
        html.Div(id="panel", className="glass panel"),

        # Bottom: the timeline
        html.Div([
            dmc.ActionIcon(id="play-btn", size=42, radius="xl", variant="filled", color="flare",
                           **{"aria-label": "Play or pause"}),
            html.Div([html.Div(id="month-label", className="month-label"),
                      html.Div("Field BOE/d", className="month-sub")], className="month-box"),
            html.Div([
                dcc.Graph(id="spark", config={"displayModeBar": False}, className="spark"),
                dmc.Slider(id="month", min=0, max=LAST, step=1, value=LAST, updatemode="drag", size="sm",
                           color="flare", label=None,
                           marks=[{"value": k, "label": str(d.year)} for k, d in enumerate(bs.MONTHS) if d.month == 1]),
            ], className="timeline-track"),
        ], className="glass timeline"),

        drawer,
        dcc.Store(id="sel-well", data=None),
        dcc.Store(id="lasso", data=[]),
        dcc.Interval(id="ticker", interval=650, disabled=True),
    ], className="app"),
)


# ---------------------------------------------------------------- callbacks

FILTER_INPUTS = [
    Input("f-operator", "value"), Input("f-formation", "value"), Input("f-type", "value"),
    Input("f-status", "value"), Input("f-vintage", "value"), Input("month", "value"),
]


@app.callback(Output("controls", "opened"), Input("menu-btn", "n_clicks"), prevent_initial_call=True)
def open_drawer(_):
    return True


@app.callback(
    Output("color-by", "value"), Output("size-by", "value"), Output("basemap", "value"),
    Output("layers", "value"), Output("map-mode", "value"), Output("f-operator", "value"),
    Output("f-formation", "value"), Output("f-type", "value"), Output("f-status", "value"),
    Output("f-vintage", "value"),
    Input("reset", "n_clicks"), prevent_initial_call=True,
)
def reset(_):
    d = DEFAULTS
    return (d["color_by"], d["size_by"], d["basemap"], d["layers"], d["mode"], d["ops"], d["forms"],
            d["wtype"], d["statuses"], d["vintage"])


@app.callback(
    Output("ticker", "disabled"), Output("month", "value", allow_duplicate=True),
    Input("play-btn", "n_clicks"), State("ticker", "disabled"), State("month", "value"),
    prevent_initial_call=True,
)
def toggle_play(_, paused, m):
    if paused:
        return False, 0 if m >= LAST else no_update
    return True, no_update


@app.callback(
    Output("month", "value"), Output("ticker", "disabled", allow_duplicate=True),
    Input("ticker", "n_intervals"), Input("spark", "clickData"), State("month", "value"),
    prevent_initial_call=True,
)
def advance(_, click, m):
    if ctx.triggered_id == "spark":
        x = click["points"][0]["x"][:7]
        return next(k for k, d in enumerate(bs.MONTHS) if d.strftime("%Y-%m") == x), no_update
    m = min(m + 1, LAST)
    return m, m >= LAST


@app.callback(Output("play-btn", "children"), Input("ticker", "disabled"))
def play_icon(paused):
    return DashIconify(icon="tabler:player-play-filled" if paused else "tabler:player-pause-filled", width=20)


@app.callback(
    Output("sel-well", "data"),
    Input("map", "clickData"), Input({"type": "pick", "i": ALL}, "n_clicks"),
    Input({"type": "close-well", "i": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def select_well(click, _picks, _close):
    if not any(t["value"] for t in ctx.triggered):
        return no_update
    tid = ctx.triggered_id
    if tid == "map":
        cd = click["points"][0].get("customdata")
        if cd is None:
            return no_update
        return int(cd[0] if isinstance(cd, list) else cd)
    if tid["type"] == "close-well":
        return None
    return tid["i"]


@app.callback(
    Output("lasso", "data"),
    Input("map", "selectedData"), Input({"type": "clear-lasso", "i": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def set_lasso(selected, _clear):
    if ctx.triggered_id != "map":
        return [] if any(t["value"] for t in ctx.triggered) else no_update
    if not selected:
        return []
    out = set()
    for p in selected.get("points", []):
        cd = p.get("customdata")
        if cd is not None:
            out.add(int(cd[0] if isinstance(cd, list) else cd))
    return sorted(out)


@app.callback(
    Output("map", "figure"), Output("legend", "children"),
    *FILTER_INPUTS,
    Input("color-by", "value"), Input("size-by", "value"), Input("basemap", "value"),
    Input("layers", "value"), Input("map-mode", "value"), Input("sel-well", "data"),
    Input("lasso", "data"), Input("tool", "value"),
)
def update_map(ops, forms, wtype, statuses, vintage, m, color_by, size_by, basemap, layers, mode, sel, lasso, tool):
    idx = visible(base_mask(ops, forms, wtype, vintage), statuses, m)
    fig, legend = map_figure(idx, m, color_by, size_by, basemap, layers or [], mode, sel, lasso, tool)
    return fig, legend_view(legend, size_by, mode)


@app.callback(
    Output("kpis", "children"), Output("panel", "children"), Output("spark", "figure"),
    Output("month-label", "children"), Output("filter-summary", "children"),
    *FILTER_INPUTS, Input("sel-well", "data"), Input("lasso", "data"),
)
def update_side(ops, forms, wtype, statuses, vintage, m, sel, lasso):
    mask = base_mask(ops, forms, wtype, vintage)
    idx_now = visible(mask, statuses, m)

    if sel is not None:
        panel = well_panel(sel, m)
    elif lasso:
        chosen = np.array(lasso, dtype=int)
        now = np.intersect1d(chosen, idx_now)
        panel = group_panel(chosen, now, m, "Selected area", f"{len(chosen)} wells in the lasso", clearable=True)
    else:
        panel = group_panel(np.flatnonzero(mask), idx_now, m, "Field", "All wells matching the filters", clearable=False)

    n_filters = sum([
        len(ops or []) < len(bs.OPERATORS), len(forms or []) < len(bs.FORMATIONS), wtype != "All",
        sorted(statuses or []) != sorted(DEFAULTS["statuses"]), list(vintage) != DEFAULTS["vintage"],
    ])
    summary = [
        html.Span(f"{len(idx_now)} of {(bs.FIRST_MONTH <= m).sum()} wells on the map"),
        dmc.Badge(f"{n_filters} filter{'s' if n_filters > 1 else ''} on", color="flare", variant="light", size="sm")
        if n_filters else None,
    ]
    return kpis(mask, idx_now, m), panel, spark_figure(mask, m), month_name(m), summary


if __name__ == "__main__":
    app.run(debug=True, port=8061)
