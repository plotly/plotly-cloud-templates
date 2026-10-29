"""
Torque & Drag Broomstick

Hookload and surface torque against bit depth for one 8½ in section. Model
curves for a fan of friction factors (the "broomstick") are drawn behind the
rig's pick-up, slack-off, rotating and torque readings, so the friction the hole
is actually showing can be read off at a glance. Drag the slider to lay a single
friction factor over the readings. The page refreshes every two seconds and a new
reading lands each time a stand is drilled down.

All data is synthetic, see tnd.py.
"""

from datetime import datetime, timezone

import dash
import dash_mantine_components as dmc
import numpy as np
import plotly.graph_objects as go
from dash import Input, Output, dcc, html
from dash._hooks import HooksManager
from dash_iconify import DashIconify
from plotly.subplots import make_subplots

import tnd

# Chart colors, kept in sync with assets/style.css
SURFACE = "#ffffff"
INK = "#13212b"
INK_2 = "#4a5b67"
MUTED = "#7a8a96"
GRID = "rgba(19, 33, 43, 0.07)"
AXIS = "rgba(19, 33, 43, 0.22)"
WARNING = "#c98500"
CRITICAL = "#d03b3b"

# One hue per family; within a family the ramp runs darker with friction factor
PICK_UP = ["#f3c3a0", "#e9925a", "#d0601f", "#a8481a", "#7a3313"]
SLACK_OFF = ["#a9cdea", "#64a2d6", "#1f74b8", "#185c93", "#11426b"]
TORQUE = ["#c9bff0", "#9d8de0", "#6a52c8", "#5240a2", "#3a2d77"]
ROTATING = "#23a07a"
MAIN = {"pick_up": PICK_UP[2], "slack_off": SLACK_OFF[2], "torque": TORQUE[2]}

FONT = "Archivo, system-ui, sans-serif"
MONO = "'Martian Mono', ui-monospace, monospace"

# Skip installed Dash plugins (such as the Plotly Studio Embedded chat) so the
# chart renders on its own. Dash loads them once per process, on first app init
HooksManager._registered = True

app = dash.Dash(
    __name__,
    title="Torque & Drag",
    external_stylesheets=[
        "https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,400..800"
        "&family=Martian+Mono:wdth,wght@75..112.5,300..600&display=swap"
    ],
)
server = app.server

KINDS = ("pick_up", "slack_off", "torque")
DEFAULT_FF = 0.28
RISING = 0.04  # recent friction this far above trend raises the alert
OVERPULL_WARN = 15  # klbf above trend


def fits(bit, n):
    """Trend friction factor (shoe to 500 ft above the bit) and the last 500 ft, per reading type."""
    trend = {k: tnd.fit(k, n, max_depth=bit - 500) for k in KINDS}
    recent = {k: tnd.fit(k, n, min_depth=bit - 500) for k in KINDS}
    return trend, recent


def hex_rgba(h, a):
    h = h.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{a})"


# ---------------------------------------------------------------- figure


def broomstick(ff, bit, n, trend):
    d = tnd.bit_depths
    m = {k: v[:n] for k, v in tnd.MEASURED.items()}
    fig = make_subplots(rows=1, cols=2, shared_yaxes=True, column_widths=[0.64, 0.36], horizontal_spacing=0.035)

    # Helical buckling: slacking off below this hookload buckles the drill pipe
    fig.add_trace(go.Scatter(
        x=tnd.BUCKLING, y=d, mode="lines", fill="tozerox", name="Helical buckling zone",
        line={"color": hex_rgba(SLACK_OFF[2], 0.45), "width": 1},
        fillcolor=hex_rgba(SLACK_OFF[0], 0.12),
        fillpattern={"shape": "/", "fgcolor": hex_rgba(SLACK_OFF[2], 0.18), "bgcolor": "rgba(0,0,0,0)",
                     "size": 9, "solidity": 0.12},
        hovertemplate="Helical buckling below %{x:.0f} klbf<extra></extra>",
    ), 1, 1)

    # The broomstick: model curves at fixed friction factors, behind everything
    for kind, ramp, col, group in (("pick_up", PICK_UP, 1, "Pick-up"), ("slack_off", SLACK_OFF, 1, "Slack-off"),
                                   ("torque", TORQUE, 2, "Rotating torque")):
        for i, f in enumerate(tnd.FF_FAN):
            fig.add_trace(go.Scatter(
                x=tnd.curve(kind, f), y=d, mode="lines", legendgroup=group, showlegend=False, hoverinfo="skip",
                line={"color": ramp[i], "width": 1.1},
            ), 1, col)

    fig.add_trace(go.Scatter(
        x=tnd.GRID["rotating"], y=d, mode="lines", name="Rotating off bottom", legendgroup="Rotating",
        line={"color": ROTATING, "width": 1.6, "dash": "dash"},
        hovertemplate="Rotating %{x:.0f} klbf<extra></extra>",
    ), 1, 1)

    # The overlay at the slider's friction factor
    for kind, col, label in (("pick_up", 1, "Pick-up"), ("slack_off", 1, "Slack-off"), ("torque", 2, "Rotating torque")):
        unit = "kft·lbf" if kind == "torque" else "klbf"
        fig.add_trace(go.Scatter(
            x=tnd.curve(kind, ff), y=d, mode="lines", name=f"{label} model", legendgroup=label,
            line={"color": MAIN[kind], "width": 3},
            hovertemplate=f"{label} μ {ff:.2f}: %{{x:.1f}} {unit}<extra></extra>",
        ), 1, col)

    # Rig readings, one per stand; the newest is drawn larger
    size = np.full(n, 8)
    size[-1] = 13
    for kind, col, symbol, color, label in (
        ("pick_up", 1, "triangle-up", PICK_UP[3], "Pick-up"),
        ("slack_off", 1, "triangle-down", SLACK_OFF[3], "Slack-off"),
        ("rotating", 1, "circle", ROTATING, "Rotating"),
        ("torque", 2, "diamond", TORQUE[3], "Rotating torque"),
    ):
        unit = "kft·lbf" if kind == "torque" else "klbf"
        fig.add_trace(go.Scatter(
            x=m[kind], y=m["depth"], mode="markers", name=f"{label} measured", legendgroup=label,
            marker={"symbol": symbol, "size": size, "color": color, "line": {"color": SURFACE, "width": 1.5}},
            hovertemplate=f"{label} measured %{{x:.1f}} {unit}<extra></extra>",
        ), 1, col)

    # Fan labels along the bottom of the plot, in text ink
    for kind, col, stagger in (("pick_up", 1, False), ("slack_off", 1, True), ("torque", 2, False)):
        for i, f in enumerate(tnd.FF_FAN):
            fig.add_annotation(
                x=tnd.curve(kind, f)[-1], y=tnd.TD, text=f"{f:.1f}", showarrow=False, row=1, col=col,
                yanchor="top", yshift=-4 - (12 if stagger and i % 2 else 0),
                font={"family": MONO, "size": 9, "color": INK_2 if abs(f - ff) < 0.005 else MUTED},
            )

    # Reference lines
    fig.add_vline(x=tnd.BLOCK, line={"color": AXIS, "width": 1}, row=1, col=1)
    fig.add_annotation(x=tnd.BLOCK, y=0, text="Block weight", textangle=-90, showarrow=False, xanchor="right",
                       yanchor="top", xshift=-2, yshift=-6, font={"size": 10, "color": MUTED}, row=1, col=1)
    fig.add_vline(x=tnd.MAKEUP_LIMIT, line={"color": CRITICAL, "width": 1.5, "dash": "dot"}, row=1, col=2)
    fig.add_annotation(x=tnd.MAKEUP_LIMIT, y=0, text=f"Make-up torque {tnd.MAKEUP_LIMIT:.0f}", textangle=-90,
                       showarrow=False, xanchor="left", yanchor="top", xshift=3, yshift=-6,
                       font={"size": 10, "color": INK_2}, row=1, col=2)

    for y, text in ((tnd.SHOE, f"9⅝ in shoe · {tnd.SHOE:,} ft"), (bit, f"Bit · {bit:,.0f} ft")):
        fig.add_shape(type="line", xref="paper", x0=0, x1=1, y0=y, y1=y,
                      line={"color": INK_2 if y == bit else AXIS, "width": 1, "dash": "dash"})
        fig.add_annotation(xref="paper", x=1, y=y, text=text, showarrow=False, xanchor="right", yanchor="bottom",
                           font={"family": MONO, "size": 10, "color": INK_2}, bgcolor=SURFACE)
    # Hole still to drill
    fig.add_shape(type="rect", xref="paper", x0=0, x1=1, y0=bit, y1=tnd.TD + 200, layer="below",
                  line={"width": 0}, fillcolor="rgba(19,33,43,0.035)")

    # Call out the latest pick-up against the trend; it turns amber once overpull builds
    pu, at = m["pick_up"][-1], m["depth"][-1]
    over = pu - np.interp(at, d, tnd.curve("pick_up", trend["pick_up"]))
    edge = WARNING if over >= OVERPULL_WARN else AXIS
    title = f"+{over:.0f} klbf overpull" if over >= OVERPULL_WARN else f"Latest pick-up {pu:.0f} klbf"
    fig.add_annotation(
        x=pu, y=at, ax=60, ay=-70, row=1, col=1,
        text=f"<b>{title}</b><br>{'' if over >= OVERPULL_WARN else f'{over:+.0f} '}vs μ {trend['pick_up']:.2f} trend",
        showarrow=True, arrowhead=0, arrowwidth=1, standoff=8, arrowcolor=edge, align="left",
        font={"size": 11, "color": INK}, bgcolor="rgba(255,255,255,0.94)", bordercolor=edge, borderpad=6,
    )

    axis = dict(gridcolor=GRID, linecolor=AXIS, zeroline=False, ticks="outside", ticklen=4, tickcolor=AXIS,
                tickfont={"family": MONO, "size": 10, "color": MUTED},
                title_font={"size": 11, "color": INK_2}, showspikes=False)
    fig.update_xaxes(**axis, side="top")
    fig.update_yaxes(**axis)
    fig.update_xaxes(title_text="HOOKLOAD · klbf", range=[0, 420], dtick=50, row=1, col=1)
    fig.update_xaxes(title_text="SURFACE TORQUE · kft·lbf", range=[0, 40], dtick=10, row=1, col=2)
    fig.update_yaxes(title_text="BIT DEPTH · ft MD", range=[tnd.TD + 450, -150], tickformat=",", dtick=1000,
                     showspikes=True, spikemode="across", spikethickness=1, spikecolor=INK_2, spikedash="solid",
                     row=1, col=1)
    fig.update_layout(
        paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
        font={"family": FONT, "color": INK_2},
        margin={"l": 64, "r": 16, "t": 58, "b": 40},
        hovermode="y unified", hoverdistance=30, spikedistance=-1,
        hoverlabel={"bgcolor": "#ffffff", "bordercolor": AXIS, "font": {"family": MONO, "size": 11, "color": INK}},
        legend={"orientation": "h", "x": 0, "y": -0.015, "yanchor": "top", "font": {"size": 11, "color": INK_2},
                "itemwidth": 30, "tracegroupgap": 0, "groupclick": "togglegroup"},
        uirevision="broomstick",
    )
    return fig


# ---------------------------------------------------------------- layout


def fit_row(whole, recent, label, swatch, symbol):
    rising = recent - whole >= RISING
    return html.Div([
        html.Div([
            html.Span(symbol, className="fit-glyph", style={"color": swatch}),
            html.Span(label, className="fit-label"),
        ], className="fit-head"),
        html.Div([
            html.Div([html.Span(f"{whole:.2f}", className="fit-value"), html.Span("trend", className="fit-sub")]),
            html.Div([
                html.Span([f"{recent:.2f}",
                           DashIconify(icon="tabler:trending-up", width=14, className="fit-icon") if rising else None],
                          className="fit-value fit-recent" + (" is-rising" if rising else "")),
                html.Span("last 500 ft", className="fit-sub"),
            ]),
        ], className="fit-values"),
    ], className="fit-row")


def fit_panel(trend, recent):
    rows = [fit_row(trend[k], recent[k], label, color, glyph) for k, label, color, glyph in (
        ("pick_up", "Pick-up", PICK_UP[3], "▲"), ("slack_off", "Slack-off", SLACK_OFF[3], "▼"),
        ("torque", "Torque", TORQUE[3], "◆"))]
    if any(recent[k] - trend[k] >= RISING for k in KINDS):
        note = html.Div([DashIconify(icon="tabler:alert-triangle", width=16),
                         html.Span("Drag is climbing near the bit. Check hole cleaning before the next trip.")],
                        className="alert")
    else:
        note = html.Div([DashIconify(icon="tabler:circle-check", width=16),
                         html.Span("Readings are tracking the trend.")], className="alert is-ok")
    return [html.Div("Fitted to readings", className="panel-title"), *rows, note]


def live_tags(bit, n, ago):
    stamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
    return [
        html.Div([html.Span(className="pulse"), html.Span("Live", className="live-k"), html.Span(f"{stamp} UTC")],
                 className="tag tag-live"),
        html.Div([html.Span("Bit", className="tag-k"), html.Span(f"{bit:,.0f} ft")], className="tag"),
        html.Div([html.Span("Stand", className="tag-k"), html.Span(f"#{n}"),
                  html.Span(f"{ago:.0f}s ago", className="tag-k")], className="tag"),
        html.Div([html.Span("TD", className="tag-k"), html.Span(f"{tnd.TD:,} ft")], className="tag"),
    ]


app.layout = dmc.MantineProvider(
    forceColorScheme="light",
    theme={"fontFamily": FONT, "primaryColor": "orange"},
    children=html.Div([
        html.Header([
            html.Div([
                html.Div("Torque & drag · friction factor sensitivity", className="eyebrow"),
                html.H1([tnd.WELL["name"], html.Span(f" / {tnd.WELL['section']}", className="h1-dim")]),
                html.Div(" · ".join(tnd.WELL[k] for k in ("field", "string", "mud", "model")), className="subline"),
            ]),
            html.Div(id="live-tags", className="tags"),
        ], className="top"),
        html.Main([
            html.Aside([
                html.Section([
                    html.Div("Friction overlay", className="panel-title"),
                    html.Div(id="ff-readout", className="ff-readout"),
                    dmc.Slider(id="ff", min=0.10, max=0.50, step=0.01, value=DEFAULT_FF, color="orange", size="sm",
                               label=None, marks=[{"value": f, "label": f"{f:.1f}"} for f in tnd.FF_FAN],
                               className="ff-slider"),
                ], className="panel"),
                html.Section(id="fit-panel", className="panel"),
            ], className="side"),
            html.Section(
                dcc.Graph(id="chart", className="chart", style={"height": "100%"},
                          config={"displaylogo": False, "responsive": True,
                                  "modeBarButtonsToRemove": ["select2d", "lasso2d", "autoScale2d"]}),
                className="chart-card",
            ),
        ], className="body"),
        dcc.Interval(id="tick", interval=2_000),
    ], className="shell"),
)


@app.callback(
    Output("chart", "figure"), Output("ff-readout", "children"), Output("fit-panel", "children"),
    Output("live-tags", "children"),
    Input("ff", "value"), Input("tick", "n_intervals"),
)
def update(ff, _):
    ff = round(ff or DEFAULT_FF, 2)
    bit, n, ago = tnd.live()
    trend, recent = fits(bit, n)
    at_bit = {k: float(np.interp(bit, tnd.bit_depths, tnd.curve(k, ff))) for k in KINDS}
    readout = [
        html.Div([html.Span("μ", className="mu"), html.Span(f"{ff:.2f}", className="ff-big")], className="ff-line"),
        html.Div([
            html.Div([html.Span("Pick-up", className="k", style={"color": PICK_UP[3]}),
                      html.Span(f"{at_bit['pick_up']:.0f}", className="v"), html.Span("klbf", className="u")]),
            html.Div([html.Span("Slack-off", className="k", style={"color": SLACK_OFF[3]}),
                      html.Span(f"{at_bit['slack_off']:.0f}", className="v"), html.Span("klbf", className="u")]),
            html.Div([html.Span("Torque", className="k", style={"color": TORQUE[3]}),
                      html.Span(f"{at_bit['torque']:.1f}", className="v"), html.Span("kft·lbf", className="u")]),
        ], className="ff-at"),
        html.Div(f"Model at the bit, {bit:,.0f} ft", className="fit-sub"),
    ]
    return broomstick(ff, bit, n, trend), readout, fit_panel(trend, recent), live_tags(bit, n, ago)


if __name__ == "__main__":
    app.run(debug=True)
