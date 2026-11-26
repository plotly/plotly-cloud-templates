"""
Yield Loss Finder

Find where a wafer fab is losing yield, and why, in a few clicks. Pick a fail bin
to see the route steps its losing wafers have in common, when the loss started and
the pattern it leaves on the wafer. Every view follows the bin and suspect you pick.

The fab and its probe data are synthetic, see fab.py.
"""

import zlib

import dash
import dash_mantine_components as dmc
import numpy as np
import plotly.graph_objects as go
from dash import ALL, Input, Output, State, ctx, dcc, html
from dash_iconify import DashIconify
from plotly.subplots import make_subplots

import fab

# Chart colors, kept in sync with assets/style.css (dark "fab control room" theme)
SURFACE = "#121826"
INK = "#e8ecf2"
INK_2 = "#aab3c2"
MUTED = "#6f7a8c"
GRID = "#1f2735"
AXIS = "#2c3646"
TYPICAL = "#334055"
EXCESS = "#8b7bff"
SUSPECT = "#ff7a45"
OTHERS = "#4aa3ff"
DIE_OK = "#1d2636"
DIE_OTHER = "#475369"
DIE_HIT = "#ff5a36"
SEQ = [[0, "#141b2a"], [0.12, "#2a1f5c"], [0.3, "#5b2a86"], [0.5, "#a8327a"], [0.7, "#e8574b"],
       [0.85, "#fca13a"], [1, "#fde68a"]]

FONT = "IBM Plex Sans, system-ui, sans-serif"
MONO = "IBM Plex Mono, ui-monospace, monospace"
THEME = {"fontFamily": FONT, "primaryColor": "violet", "defaultRadius": "md"}

WINDOWS = [7, 14, 30, 60]
NEXT_STEP = {
    "chamber": "Take {lvl} offline and inspect it: chamber clean, edge ring and recent maintenance.",
    "etch": "Hold {lvl} and compare its recipe and maintenance log with the other etchers.",
    "dep": "Run a film-thickness check on {lvl} and compare its center-to-edge profile.",
    "cmp": "Hold {lvl} and inspect the pad, conditioner and retaining ring.",
    "slurry": "Quarantine slurry lot {lvl} and ask the supplier for its certificate of analysis.",
    "imp": "Check {lvl} dose and energy calibration against its last maintenance.",
    "litho": "Review {lvl} focus and overlay data for the affected lots.",
    "probe": "Re-probe a sample of wafers on another card to rule out {lvl}.",
    "shift": "Compare procedures between shifts. Look for a step that differs on the {lvl} shift.",
    "product": "Review what's specific to {lvl}: its recipe settings and test limits.",
}

app = dash.Dash(
    __name__,
    title="Yield Loss Finder",
    external_stylesheets=[
        "https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700"
        "&family=IBM+Plex+Mono:wght@400;500;600&display=swap"
    ],
)
server = app.server


# ---------- formatting ----------

def pct(x, d=1):
    return f"{x * 100:.{d}f}%"


def pts(x):
    return f"{x * 100:.2f} pts"


def money(x):
    if x >= 1e6:
        return f"${x / 1e6:.2f}M"
    if x >= 1e3:
        return f"${x / 1e3:.0f}k"
    return f"${x:,.0f}"


def lower_steps(sid):
    return " + ".join(p if p.startswith("CMP") else p[0].lower() + p[1:] for p in fab.suspect_steps(sid).split(" + "))


def date_label(d):
    return d.strftime("%b %-d")


# ---------- selection helpers ----------

def default_bin(product, days):
    return int(np.argmax(fab.summary(product, days)["excess_value"]))


def default_suspect(product, days, b):
    top = fab.commonality(product, days, b)
    return top[0]["id"] if top and top[0]["z"] >= 3 else None


def find_stats(product, days, b, sid):
    return next((s for s in fab.commonality(product, days, b) if s["id"] == sid), None)


def base_layout(fig, height, **kw):
    fig.update_layout(
        height=height, margin={"l": 8, "r": 12, "t": 8, "b": 8},
        paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
        font={"family": FONT, "color": INK_2, "size": 12},
        hoverlabel={"bgcolor": "#0b0f17", "bordercolor": AXIS, "font": {"family": FONT, "color": INK, "size": 12}},
        legend={"orientation": "h", "x": 0, "y": 1.02, "yanchor": "bottom", "font": {"size": 12, "color": INK_2},
                "bgcolor": "rgba(0,0,0,0)"},
        **kw,
    )
    fig.update_xaxes(showgrid=False, linecolor=AXIS, tickcolor=AXIS, ticks="outside", ticklen=4,
                     tickfont={"color": MUTED}, zeroline=False)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, tickfont={"color": MUTED}, title_font={"color": MUTED, "size": 11})
    return fig


# ---------- figures ----------

def pareto_figure(s, sel):
    order = list(np.argsort(s["loss"]))  # smallest at the bottom
    names = [fab.BINS[i] for i in order]
    typ = np.minimum(s["typ"], s["loss"])[order]
    exc = s["excess"][order]
    op = [1 if i == sel else 0.38 for i in order]
    custom = np.stack([order, s["loss"][order] * 100, s["typ"][order] * 100, exc * 100,
                       [money(v) for v in s["excess_value"][order]]], axis=1)
    hover = ("<b>%{y}</b><br>Loss %{customdata[1]:.2f}% · typical %{customdata[2]:.2f}%"
             "<br>Above typical %{customdata[3]:.2f} pts · %{customdata[4]}<extra></extra>")
    fig = go.Figure()
    fig.add_trace(go.Bar(y=names, x=typ * 100, orientation="h", name="Typical loss", customdata=custom,
                         marker={"color": TYPICAL, "opacity": op, "line": {"color": SURFACE, "width": 2}},
                         hovertemplate=hover))
    fig.add_trace(go.Bar(y=names, x=exc * 100, orientation="h", name="Above typical", customdata=custom,
                         marker={"color": EXCESS, "opacity": op, "line": {"color": SURFACE, "width": 2}},
                         text=[pct(v, 2) for v in s["loss"][order]], textposition="outside", cliponaxis=False,
                         textfont={"family": MONO, "size": 11, "color": INK_2}, hovertemplate=hover))
    y = order.index(sel)
    fig.add_shape(type="rect", xref="paper", x0=-0.36, x1=1.02, y0=y - 0.5, y1=y + 0.5, layer="below",
                  fillcolor="rgba(139, 123, 255, 0.12)", line_width=0)
    base_layout(fig, 372, barmode="stack", bargap=0.34, barcornerradius=4, clickmode="event",
                hovermode="closest")
    fig.update_layout(margin={"l": 8, "r": 52, "t": 8, "b": 8})
    fig.update_xaxes(title="Share of die lost", ticksuffix="%", showgrid=True, gridcolor=GRID,
                     title_font={"color": MUTED, "size": 11}, rangemode="tozero")
    fig.update_yaxes(showgrid=False, tickfont={"color": INK, "size": 12}, ticks="")
    return fig


def trend_figure(product, days, b, sid, s, start):
    d = fab.daily(product, days, b, sid)
    x = d["dates"]
    typ = s["typ"][b] * 100
    fig = go.Figure()
    fig.add_hline(y=typ, line={"color": MUTED, "width": 1, "dash": "dot"})
    fig.add_annotation(x=x[0], y=typ, text=f"Typical {typ:.2f}%", showarrow=False, xanchor="left",
                       yanchor="bottom", yshift=10, bgcolor="rgba(18,24,38,0.85)", font={"size": 11, "color": MUTED})
    series = [("out", "All other wafers" if sid else "All wafers", OTHERS)]
    if sid:
        series.append(("in", f"Through {fab.suspect_label(sid)}", SUSPECT))
    for key, name, color in series:
        yv = d[key] * 100
        fig.add_trace(go.Scatter(
            x=x, y=yv, name=name, mode="lines+markers", connectgaps=True,
            line={"color": color, "width": 2.5, "shape": "spline", "smoothing": 0.6},
            marker={"size": 6, "color": color, "line": {"color": SURFACE, "width": 1}},
            fill="tonexty" if key == "in" else "tozeroy",
            fillcolor="rgba(255, 122, 69, 0.16)" if key == "in" else "rgba(74, 163, 255, 0.06)",
            customdata=d[f"n_{key}"],
            hovertemplate=f"{name} <b>%{{y:.2f}}%</b> · %{{customdata}} wafers<extra></extra>",
        ))
        last = np.where(np.isfinite(yv))[0]
        if len(last):
            i = last[-1]
            fig.add_annotation(x=x[i], y=yv[i], text=f"{yv[i]:.1f}%", showarrow=False, xanchor="left", xshift=8,
                               font={"family": MONO, "size": 11, "color": INK})
    if start is not None:
        fig.add_vline(x=x[start], line={"color": INK_2, "width": 1})
        fig.add_annotation(x=x[start], y=1, yref="paper", text=f"Started {date_label(x[start])}", showarrow=False,
                           xanchor="left", yanchor="top", xshift=6, font={"size": 11, "color": INK})
    base_layout(fig, 320, hovermode="x unified")
    fig.update_layout(margin={"l": 8, "r": 44, "t": 8, "b": 8})
    fig.update_xaxes(tickformat="%b %-d", hoverformat="%a %b %-d")
    fig.update_yaxes(title=f"{fab.BINS[b]}, share of die", ticksuffix="%", rangemode="tozero")
    return fig


def maps_figure(product, days, b, sid):
    m = fab.window_mask(product, days)
    if sid:
        a_mask, b_mask = m & fab.suspect_mask(sid), m & ~fab.suspect_mask(sid)
        titles = [f"Through {fab.suspect_label(sid)}", "All other wafers"]
    else:
        r = fab.FAILS[:, b]
        cut = np.percentile(r[m], 90)
        a_mask, b_mask = m & (r >= cut), m & (r < cut)
        titles = ["Worst 10% of wafers", "All other wafers"]
    seed = zlib.crc32(f"{product}{days}{b}{sid}".encode())
    za, zb = fab.composite(a_mask, b, seed), fab.composite(b_mask, b, seed + 1)

    # Time-lapse of the left wafer: a rolling 5-day stack for each day in the window
    day = fab.WAFERS["day"].to_numpy()
    first = fab.DAYS - days
    lapse = []
    for d in range(first, fab.DAYS):
        mm = a_mask & (day > d - 5) & (day <= d)
        lapse.append((fab.DATES[d], fab.composite(mm, b, seed + 7 + d), int(mm.sum())))
    zmax = max(np.nanpercentile(za, 99), np.nanpercentile(zb, 99), 1e-3) * 100 * 1.1

    hover = "Die %{x}, %{y}<br><b>%{z:.1f}%</b> failing · %{customdata:,} wafers<extra></extra>"
    fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.06)
    for col, (z, n) in enumerate([(za, a_mask.sum()), (zb, b_mask.sum())], start=1):
        fig.add_trace(go.Heatmap(
            z=z * 100, coloraxis="coloraxis", xgap=1, ygap=1, hoverongaps=False,
            customdata=np.full(z.shape, n), hovertemplate=hover,
        ), row=1, col=col)
        c = (fab.GRID - 1) / 2
        r = fab.GRID / 2
        fig.add_shape(type="circle", x0=c - r, x1=c + r, y0=c - r, y1=c + r, line={"color": AXIS, "width": 1.5},
                      row=1, col=col)
        fig.add_shape(type="path", path=f"M {c - 0.8} {c - r} L {c} {c - r + 0.9} L {c + 0.8} {c - r} Z",
                      fillcolor=SURFACE, line={"color": AXIS, "width": 1.5}, row=1, col=col)
    for i, t in enumerate(titles, start=1):
        n = (a_mask if i == 1 else b_mask).sum()
        fig.add_annotation(text=f"<b>{t}</b><br><span style='color:{MUTED}'>{n:,} wafers</span>", showarrow=False,
                           xref=f"x{'' if i == 1 else i} domain", yref="paper", x=0.5, y=1.0, yanchor="bottom",
                           font={"size": 12, "color": INK})
    window_label = f"All {days} days"
    fig.frames = [go.Frame(name=window_label, data=[go.Heatmap(z=za * 100, customdata=np.full(za.shape, a_mask.sum()))],
                           traces=[0])] + [
        go.Frame(name=date_label(t), traces=[0],
                 data=[go.Heatmap(z=z * 100, customdata=np.full(z.shape, n))]) for t, z, n in lapse]
    anim = {"frame": {"duration": 140, "redraw": True}, "transition": {"duration": 0}, "mode": "immediate"}
    steps = [{"label": f.name, "method": "animate", "args": [[f.name], anim]} for f in fig.frames]
    base_layout(fig, 400, coloraxis={
        "colorscale": SEQ, "cmin": 0, "cmax": zmax,
        "colorbar": {"orientation": "v", "x": 1.0, "xanchor": "left", "y": 0.55, "len": 0.7, "thickness": 8,
                     "ticksuffix": "%", "outlinewidth": 0, "tickfont": {"size": 10, "color": MUTED},
                     "title": {"text": "Die<br>failing", "side": "top", "font": {"size": 10, "color": MUTED}}}},
        updatemenus=[{
            "type": "buttons", "direction": "left", "showactive": False, "x": 0, "y": -0.06, "xanchor": "left",
            "yanchor": "top", "pad": {"r": 8, "t": 0}, "bgcolor": AXIS, "bordercolor": AXIS,
            "font": {"color": INK, "size": 11},
            "buttons": [
                {"label": "▶ Replay", "method": "animate",
                 "args": [[f.name for f in fig.frames[1:]], {**anim, "fromcurrent": False}]},
                {"label": "❚❚", "method": "animate", "args": [[None], {**anim, "frame": {"duration": 0}}]},
            ]}],
        sliders=[{
            "active": 0, "steps": steps, "x": 0.21, "len": 0.79, "y": -0.04, "yanchor": "top",
            "pad": {"t": 0, "b": 0}, "bgcolor": AXIS, "activebgcolor": SUSPECT, "bordercolor": AXIS,
            "tickcolor": AXIS, "font": {"size": 9, "color": "rgba(0,0,0,0)"}, "ticklen": 3, "minorticklen": 0,
            "currentvalue": {"prefix": "Left wafer: ", "font": {"size": 11, "color": INK}, "xanchor": "right", "offset": 6},
        }])
    fig.update_layout(margin={"l": 4, "r": 44, "t": 40, "b": 70})
    rng = [-1, fab.GRID]
    fig.update_xaxes(visible=False, range=rng, constrain="domain")
    fig.update_yaxes(visible=False, range=rng, scaleanchor="x", row=1, col=1)
    fig.update_yaxes(visible=False, range=rng, scaleanchor="x2", row=1, col=2)
    sig, score = fab.signature(za - zb)
    return fig, sig


def _heat(t):
    """Neutral steel to hot orange, for loss relative to typical."""
    t = float(np.clip(t, 0, 1))
    c0, c1 = (110, 125, 150, 0.16), (255, 90, 54, 0.85)
    r, g, b_, a = (c0[i] + (c1[i] - c0[i]) * t for i in range(4))
    return f"rgba({r:.0f},{g:.0f},{b_:.0f},{a:.2f})"


def suspect_nodes(sid):
    """Nodes of the line-flow chart that the suspect points at."""
    hit = set()
    m = fab.suspect_mask(sid) if sid else None
    for col, lvl in fab.parse_suspect(sid):
        if col in fab.PATH:
            hit.add((col, lvl))
        elif col == "etch":
            hit |= {("chamber", c) for c in fab.LEVELS["chamber"] if c.startswith(lvl)}
        elif col == "slurry":
            hit |= {("cmp", t) for t in fab.WAFERS.loc[m, "cmp"].unique()}
    return hit


def flow_figure(product, days, b, sid, typ):
    nodes, node_rate, links = fab.flow(product, days, b)
    hit = suspect_nodes(sid)
    node_color = [SUSPECT if n in hit else _heat((r / typ - 1) / 2.5).replace("0.16)", "0.55)")
                  for n, r in zip(nodes, node_rate)]
    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node={"label": [lvl for _, lvl in nodes], "color": node_color, "pad": 10, "thickness": 14,
              "line": {"color": SURFACE, "width": 0}, "customdata": node_rate * 100,
              "hovertemplate": f"<b>%{{label}}</b><br>%{{value:,}} wafers · %{{customdata:.2f}}% {fab.BINS[b].lower()}"
                               "<extra></extra>"},
        link={"source": [l[0] for l in links], "target": [l[1] for l in links], "value": [l[2] for l in links],
              "color": [_heat((l[3] / typ - 1) / 2.5) for l in links], "customdata": [l[3] * 100 for l in links],
              "hovertemplate": "%{source.label} → %{target.label}<br>%{value:,} wafers · "
                               f"<b>%{{customdata:.2f}}%</b> {fab.BINS[b].lower()}<extra></extra>"},
        textfont={"family": MONO, "size": 11, "color": INK},
    ))
    for i, col in enumerate(fab.PATH):
        fig.add_annotation(x=i / (len(fab.PATH) - 1), y=1.0, xref="paper", yref="paper", yanchor="bottom",
                           xanchor=["left", "center", "center", "center", "right"][i], showarrow=False,
                           text=fab.FACTORS[col].upper(), font={"size": 10, "color": MUTED})
    base_layout(fig, 380)
    fig.update_layout(margin={"l": 8, "r": 8, "t": 26, "b": 8})
    return fig


def lot_figure(lot, b, sid):
    idx = fab.lot_wafers(lot)
    G = fab.GRID
    S, cols = G + 4, 5
    rows = int(np.ceil(len(idx) / cols))
    Z = np.full((rows * S, cols * S), np.nan)
    T = np.full(Z.shape, "", dtype=object)
    names = np.array(["Good die"] + fab.BINS, dtype=object)
    inm = fab.suspect_mask(sid)[idx] if sid else np.zeros(len(idx), bool)
    fig = go.Figure()
    for k, i in enumerate(idx):
        r, c = divmod(k, cols)
        dm = fab.die_map(i)
        y0, x0 = (rows - 1 - r) * S + 2, c * S
        Z[y0:y0 + G, x0:x0 + G] = np.where(dm < 0, np.nan, np.where(dm == 0, 0, np.where(dm == b + 1, 2, 1)))
        w = fab.WAFERS.iloc[i]
        T[y0:y0 + G, x0:x0 + G] = f"Slot {w.slot} · {w.chamber}<br>" + names[np.clip(dm, 0, None)]
        cx, cy, rad = x0 + (G - 1) / 2, y0 + (G - 1) / 2, G / 2 + 0.5
        fig.add_shape(type="circle", x0=cx - rad, x1=cx + rad, y0=cy - rad, y1=cy + rad, layer="above",
                      line={"color": SUSPECT if inm[k] else AXIS, "width": 2 if inm[k] else 1})
        n_hit = int(fab.FAILS[i, b])
        fig.add_annotation(x=cx, y=y0 - 0.6, yanchor="top", showarrow=False, text=f"#{w.slot} · {n_hit}",
                           font={"family": MONO, "size": 9, "color": SUSPECT if inm[k] else MUTED})
    fig.add_trace(go.Heatmap(
        z=Z, text=T, zmin=0, zmax=2, showscale=False, xgap=1, ygap=1, hoverongaps=False,
        colorscale=[[0, DIE_OK], [0.33, DIE_OK], [0.33, DIE_OTHER], [0.66, DIE_OTHER], [0.66, DIE_HIT], [1, DIE_HIT]],
        hovertemplate="%{text}<extra></extra>",
    ))
    base_layout(fig, 560)
    fig.update_layout(margin={"l": 4, "r": 4, "t": 4, "b": 4})
    fig.update_xaxes(visible=False, range=[-1, cols * S - 3], constrain="domain")
    fig.update_yaxes(visible=False, range=[-1, rows * S], scaleanchor="x")
    return fig


# ---------- components ----------

def step_card(n, title, body, hint=None, hint_id=None, right=None, **kw):
    hint_el = dmc.Text(hint, className="card-hint", **({"id": hint_id} if hint_id else {}))
    head = dmc.Group([
        dmc.Group([html.Span(str(n), className="step-num"),
                   dmc.Stack([dmc.Text(title, className="card-title"), hint_el], gap=2)],
                  gap=12, align="flex-start", wrap="nowrap"),
        right,
    ], justify="space-between", align="flex-start", className="card-head", wrap="nowrap")
    return dmc.Paper([head, body], className="card", **kw)


def kpi(label, value, sub, icon, tone=None):
    return dmc.Paper([
        dmc.Group([DashIconify(icon=icon, width=16, className="kpi-icon"), dmc.Text(label, className="kpi-label")],
                  gap=6),
        dmc.Text(value, className=f"kpi-value {tone or ''}"),
        dmc.Text(sub, className="kpi-sub"),
    ], className="kpi")


def conf_badge(z):
    name, tone = fab.confidence(z)
    icon = {"critical": "tabler:target-arrow", "serious": "tabler:target", "warning": "tabler:question-mark",
            "neutral": "tabler:minus"}[tone]
    return html.Span([DashIconify(icon=icon, width=13), name], className=f"conf conf-{tone}")


def suspect_rows(product, days, b, sid):
    top = fab.commonality(product, days, b)
    if not top:
        return dmc.Text("Not enough wafers in this view to compare.", className="empty")
    rows = []
    for i, s in enumerate(top, start=1):
        lift = s["rate_in"] / s["rate_out"] if s["rate_out"] > 0 else np.inf
        rows.append(html.Button([
            html.Span(str(i), className="rank"),
            html.Div([
                html.Div([html.Span(fab.suspect_label(s["id"]), className="sus-name"),
                          html.Span(fab.suspect_steps(s["id"]), className="sus-step")], className="sus-title"),
                html.Div([
                    html.Span([html.B(pct(s["rate_in"], 2)), " lost vs ", pct(s["rate_out"], 2), " elsewhere"]),
                    html.Span("·", className="dot"),
                    html.Span(f"{lift:.1f}× more" if np.isfinite(lift) else "only here"),
                    html.Span("·", className="dot"),
                    html.Span(f"{s['n']:,} wafers in {s['lots']} lots"),
                ], className="sus-meta"),
            ], className="sus-body"),
            html.Div([
                html.Div([html.Div(className="share-fill", style={"width": f"{s['share'] * 100:.0f}%"})],
                         className="share-track"),
                html.Span(f"{s['share']:.0%}", className="share-val"),
            ], className="share", title="Share of this bin's above-typical loss on these wafers"),
            conf_badge(s["z"]),
        ], id={"type": "suspect", "index": s["id"]}, n_clicks=0,
            className="sus-row" + (" selected" if s["id"] == sid else "")))
    head = html.Div([html.Span("Rank"), html.Span("Shared step"), html.Span("Explains"), html.Span("Evidence")],
                    className="sus-head")
    return html.Div([head] + rows, className="sus-list")


def lots_table(g, b, lot):
    if g.empty:
        return dmc.Text("No lots in this view.", className="empty")
    hi = g["bin_rate"].max()
    head = html.Thead(html.Tr([html.Th(c) for c in
                               ["Lot", "Started", "Product", "Wafers", f"{fab.BINS[b]} loss", "Lot yield"]]))
    body = []
    for r in g.itertuples():
        body.append(html.Tr(id={"type": "lot", "index": r.lot}, n_clicks=0,
                            className="lot-row" + (" selected" if r.lot == lot else ""), children=[
            html.Td(r.lot, className="mono strong"),
            html.Td(r.date.strftime("%a %b %-d")),
            html.Td(r.product),
            html.Td(r.wafers, className="mono"),
            html.Td(html.Div([html.Div(html.Div(className="bar-fill", style={"width": f"{r.bin_rate / hi * 100:.0f}%"}),
                                       className="bar-track"),
                              html.Span(pct(r.bin_rate, 2), className="mono")], className="bar-cell")),
            html.Td(pct(r.lot_yield, 1), className="mono " + ("neg" if r.lot_yield < fab.TARGET_YIELD else "")),
        ]))
    return html.Div(html.Table([head, html.Tbody(body)], className="lots"), className="table-wrap")


def finding(product, days, b, sid, s, start, sig):
    bin_name = fab.BINS[b]
    exc = s["excess"][b]
    span = f"the last {days} days"
    if exc < 0.0005:
        head = f"{bin_name} is running at its typical rate over {span}."
    else:
        head = (f"{bin_name} is costing {pts(exc)} of yield, about {money(s['excess_value'][b])}, "
                f"over {span}.")
    st = find_stats(product, days, b, sid) if sid else None
    lines, action = [], None
    if st and st["z"] >= 3:
        cols = fab.parse_suspect(sid)
        lines.append(f"{st['share']:.0%} of the extra loss is on wafers through {fab.suspect_label(sid)} "
                     f"({lower_steps(sid)}): {pct(st['rate_in'], 2)} of die lost, against "
                     f"{pct(st['rate_out'], 2)} on all other wafers.")
        when = [f"Started around {date_label(start)}." if start is not None else "No clear start date in this window."]
        if sig:
            when.append(f"On the wafer it shows as {'an' if sig[0] in 'AEIOU' else 'a'} {sig.lower()}.")
        lines.append(" ".join(when))
        col, lvl = next(((c, v) for c, v in cols if c != "product"), cols[0])
        action = NEXT_STEP[col].format(lvl=lvl)
    elif exc >= 0.0005:
        lines.append("No single tool, slurry lot, probe card, shift or product stands out. "
                     "The loss is spread across the line, so look at defect inspection data next.")
    else:
        lines.append("Pick a bin with purple bars in step 1 to find what is driving its loss.")

    text = "\n".join([head] + lines + ([f"Next step: {action}"] if action else []))
    tone = "hot" if st and st["z"] >= 5 else "calm"
    return dmc.Paper([
        html.Div(DashIconify(icon="tabler:radar-2" if tone == "hot" else "tabler:circle-check", width=22),
                 className="finding-icon"),
        html.Div([
            dmc.Text("Finding", className="finding-kicker"),
            html.P(head, className="finding-head"),
            *[html.P(t, className="finding-body") for t in lines],
            action and html.P([html.Span("Next step", className="next-tag"), action], className="finding-next"),
        ], className="finding-text"),
        dcc.Clipboard(content=text, title="Copy this finding", className="copy",
                      children=dmc.Button("Copy", size="xs", variant="default",
                                          leftSection=DashIconify(icon="tabler:copy", width=14))),
    ], className=f"finding finding-{tone}")


# ---------- layout ----------

header = html.Header([
    html.Div([
        html.Div(DashIconify(icon="tabler:cpu", width=22), className="brand-mark"),
        html.Div([
            html.Div("Northbridge Fab 2 · 300 mm probe yield", className="brand-sub"),
            html.H1("Yield Loss Finder", className="title"),
        ]),
    ], className="brand"),
    html.Div([
        html.Span(id="alerts", className="alert-pill"),
        html.Span([DashIconify(icon="tabler:clock", width=14), f"Probe results through {fab.END.strftime('%b %-d')}"],
                  className="meta"),
        html.Span([DashIconify(icon="tabler:circle-dot", width=14), f"{fab.GROSS_DIE} die per wafer"],
                  className="meta"),
    ], className="header-meta"),
], className="header")

filters = html.Div([
    html.Div([
        dmc.Text("Product", className="filter-label"),
        dmc.SegmentedControl(id="product", value="All", size="sm", data=[{"value": "All", "label": "All products"}] + [
            {"value": p, "label": p} for p in fab.PRODUCTS]),
    ], className="filter"),
    html.Div([
        dmc.Text("Lots started in the last", className="filter-label"),
        dmc.SegmentedControl(id="window", value="30", size="sm",
                             data=[{"value": str(d), "label": f"{d} days"} for d in WINDOWS]),
    ], className="filter"),
], className="filters")

main = html.Main([
    filters,
    html.Div(id="finding"),
    html.Div(id="kpis", className="kpi-row"),
    dmc.Grid([
        dmc.GridCol(step_card(1, "Where is yield lost?", dcc.Graph(id="pareto", config={"displayModeBar": False}),
                              hint="Die lost by fail bin. Violet is loss above the bin's typical rate. "
                                   "Click a bin to investigate it."),
                    span={"base": 12, "lg": 5}),
        dmc.GridCol(step_card(2, "What do the losing wafers share?", html.Div(id="suspects"), hint_id="suspects-hint"),
                    span={"base": 12, "lg": 7}),
    ], gutter="md"),
    step_card(3, "Follow the wafers through the line", dcc.Graph(id="flow", config={"displayModeBar": False}),
              hint_id="flow-hint"),
    dmc.Grid([
        dmc.GridCol(step_card(4, "When did it start?", dcc.Graph(id="trend", config={"displayModeBar": False}),
                              hint_id="trend-hint"),
                    span={"base": 12, "lg": 7}),
        dmc.GridCol(step_card(5, "Watch it appear on the wafer",
                              dcc.Graph(id="maps", config={"displayModeBar": False}), hint_id="maps-hint"),
                    span={"base": 12, "lg": 5}),
    ], gutter="md"),
    dmc.Grid([
        dmc.GridCol(step_card(6, "Which lots to review", html.Div(id="lots"), hint_id="lots-hint"),
                    span={"base": 12, "lg": 7}),
        dmc.GridCol(step_card(7, "Open the lot", html.Div([
            dcc.Graph(id="lot-map", config={"displayModeBar": False}),
            html.Div([
                html.Span([html.I(className="sw sw-hit"), html.Span(id="legend-bin")]),
                html.Span([html.I(className="sw sw-other"), "Other fail bins"]),
                html.Span([html.I(className="sw sw-ok"), "Good die"]),
                html.Span([html.I(className="sw sw-ring"), "Ran through the suspect"]),
            ], className="legend"),
        ]), hint_id="lot-hint"), span={"base": 12, "lg": 5}),
    ], gutter="md"),
    html.P("All data is synthetic. Typical loss is each bin's 20th-percentile daily rate over 60 days. "
           "Suspects compare wafers through a step with wafers run on the same days, one sample per lot. "
           "Die positions in step 7 are simulated from each wafer's real fail counts.",
           className="footnote"),
], className="main")

_b0 = default_bin("All", 30)
app.layout = dmc.MantineProvider(
    html.Div([header, main, dcc.Store(id="sel", data={"bin": _b0, "suspect": default_suspect("All", 30, _b0),
                                                      "lot": None})],
             className="page"),
    theme=THEME, forceColorScheme="dark",
)


# ---------- callbacks ----------

@app.callback(
    Output("sel", "data"),
    Input("product", "value"), Input("window", "value"), Input("pareto", "clickData"),
    Input({"type": "suspect", "index": ALL}, "n_clicks"), Input({"type": "lot", "index": ALL}, "n_clicks"),
    State("sel", "data"), prevent_initial_call=True,
)
def select(product, window, click, _rows, _lots, sel):
    days = int(window)
    trig = ctx.triggered_id
    if isinstance(trig, dict):
        if not ctx.triggered[0]["value"]:
            return dash.no_update  # rows re-rendered, not clicked
        if trig["type"] == "lot":
            return {**sel, "lot": trig["index"]}
        return {**sel, "suspect": trig["index"], "lot": None}
    if trig == "pareto":
        if not click:
            return dash.no_update
        b = int(click["points"][0]["customdata"][0])
        return {"bin": b, "suspect": default_suspect(product, days, b), "lot": None}
    # filters changed: keep the bin, pick the new leading suspect
    b = sel["bin"]
    return {"bin": b, "suspect": default_suspect(product, days, b), "lot": None}


@app.callback(
    Output("finding", "children"), Output("kpis", "children"), Output("pareto", "figure"),
    Output("suspects", "children"), Output("suspects-hint", "children"), Output("trend", "figure"),
    Output("trend-hint", "children"), Output("maps", "figure"), Output("maps-hint", "children"),
    Output("lots", "children"), Output("lots-hint", "children"),
    Output("flow", "figure"), Output("flow-hint", "children"), Output("lot-map", "figure"),
    Output("lot-hint", "children"), Output("legend-bin", "children"), Output("alerts", "children"),
    Input("product", "value"), Input("window", "value"), Input("sel", "data"),
)
def render(product, window, sel):
    days = int(window)
    b, sid = sel["bin"], sel["suspect"]
    if sid and not find_stats(product, days, b, sid):
        sid = None
    s = fab.summary(product, days)
    bin_name = fab.BINS[b]

    d = fab.daily(product, days, b, sid)
    start = fab.onset(d["in"] if sid else d["out"], s["typ"][b])
    maps, sig = maps_figure(product, days, b, sid)

    gap = s["yield_"] - fab.TARGET_YIELD
    kpis = [
        kpi("Line yield", pct(s["yield_"]), f"Target {pct(fab.TARGET_YIELD)} · {abs(gap) * 100:.1f} pts "
            f"{'above' if gap >= 0 else 'below'}", "tabler:chart-donut-3", "pos" if gap >= 0 else "neg"),
        kpi("Loss above typical", pts(s["excess"].sum()), "Across all fail bins, vs a healthy day",
            "tabler:trending-down"),
        kpi("Value of that loss", money(s["excess_value"].sum()), "Good die not shipped, at die price",
            "tabler:coin"),
        kpi("Wafers probed", f"{s['wafers']:,}", f"{s['lots']:,} lots · {fab.GROSS_DIE * s['wafers'] / 1e6:.1f}M die",
            "tabler:stack-2"),
    ]

    who = "Selected" if sid else "No strong suspect"
    sus_hint = (f"{bin_name}: route steps ranked by how much more of it their wafers lose than wafers run the "
                "same days. Explains = share of the bin's above-typical loss. Click a row to follow it.")
    trend_hint = (f"Daily {bin_name.lower()} by lot start date, wafers through {fab.suspect_label(sid)} against the rest."
                  if sid else f"Daily {bin_name.lower()} by lot start date. {who} for this bin.")
    maps_hint = ("Fail rate at each die position, stacked across wafers. Press Replay to watch the left wafer "
                 "day by day (5-day rolling stack). "
                 + (f"Pattern match: {sig.lower()}." if sig else "No distinct pattern: the loss is spread evenly."))
    lots_hint = (f"Lots through {fab.suspect_label(sid)} with the most {bin_name.lower()}. Wafers counts only "
                 "the wafers that ran through it." if sid else f"Lots with the most {bin_name.lower()}.") + \
        " Click a lot to open it."

    g = fab.top_lots(product, days, b, sid)
    lot = sel.get("lot") if sel.get("lot") in set(g["lot"]) else (g["lot"].iloc[0] if not g.empty else None)
    flow_hint = (f"Every wafer's path through litho, etch, deposition, CMP and implant. Wider bands carry more wafers; "
                 f"hotter bands lose more {bin_name.lower()} than typical."
                 + (f" {fab.suspect_label(sid)} is lit up." if sid else ""))
    if lot:
        lw = fab.lot_wafers(lot)
        n_in = int(fab.suspect_mask(sid)[lw].sum()) if sid else 0
        lot_hint = (f"Lot {lot}, all {len(lw)} wafers, die by die. Number under each wafer: its {bin_name.lower()} "
                    "fails." + (f" {n_in} of {len(lw)} ran through {fab.suspect_label(sid)}." if sid else "")
                    + " Click another lot in step 6.")
        lot_fig = lot_figure(lot, b, sid)
    else:
        lot_hint, lot_fig = "No lot to show.", go.Figure()
    alerts = []
    for bb in range(len(fab.BINS)):
        top = fab.commonality(product, days, bb)
        if top and top[0]["z"] >= 5 and s["excess"][bb] >= 0.0005:
            alerts.append(bb)
    alert_pill = [html.I(className="pulse"), f"{len(alerts)} excursions detected"] if alerts else \
        [html.I(className="pulse calm"), "Line healthy"]

    return (finding(product, days, b, sid, s, d["dates"][start] if start is not None else None, sig), kpis,
            pareto_figure(s, b), suspect_rows(product, days, b, sid), sus_hint,
            trend_figure(product, days, b, sid, s, start), trend_hint, maps, maps_hint,
            lots_table(g, b, lot), lots_hint, flow_figure(product, days, b, sid, s["typ"][b]), flow_hint,
            lot_fig, lot_hint, f"{bin_name} fail", alert_pill)


if __name__ == "__main__":
    app.run(debug=True, port=8057)
