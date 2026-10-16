"""
Live Well Drilling Monitor

A real-time view of surface drilling sensors for a rig: a depth-based log of
the last few hundred feet drilled, time-based strip charts of the hydraulic and
mechanical channels, and alarms for the events a driller watches for (pit
gain, flow out differential, pressure spikes, high torque and gas).

The sensor data is synthetic, see simulator.py.
"""

import time

import dash
import dash_mantine_components as dmc
import numpy as np
import plotly.graph_objects as go
from dash import Input, Output, State, dcc, html
from dash_iconify import DashIconify
from numpy.lib.stride_tricks import sliding_window_view
from plotly.subplots import make_subplots

import simulator as sim

REFRESH_MS = 2000
DEPTH_LOG_FT = 400
LOOKBACK_S = 10 * 60  # extra history needed by the rolling alarm checks

# Chart colors, kept in sync with assets/style.css
SURFACE = "#1a1a19"
INK = "#f0efec"
INK_2 = "#c3c2b7"
MUTED = "#898781"
GRID = "#2c2c2a"
AXIS = "#383835"
SERIES = ["#3987e5", "#d95926"]
STATUS = {"good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a", "critical": "#d03b3b"}
STATUS_ICON = {
    "warning": "tabler:alert-triangle",
    "serious": "tabler:alert-octagon",
    "critical": "tabler:urgent",
}
# Earth tones for lithology, always shown with the formation name
LITHOLOGY = {"Shale": "#4f5d4a", "Sandstone": "#9a7d3e", "Sand": "#9a7d3e", "Limestone": "#5f7a8c",
             "Dolomite": "#6f6a8c", "Marl": "#7d6a55", "Siltstone": "#7a7348", "Wash": "#8c5a4a"}
STATE_COLOR = {"Drilling": "green", "Connection": "gray", "Circulating": "blue"}

WINDOWS = {"15 min": 15 * 60, "1 hr": 3600, "6 hr": 6 * 3600}

# key, label, severity, explanation
ALARMS = [
    ("pit_gain", "Pit gain", "critical", "Active pit volume up more than 8 bbl in 10 min: possible influx"),
    ("flow_diff", "Flow out high", "serious", "Return flow more than 5% above flow in"),
    ("spp_spike", "Pressure spike", "serious", "Standpipe pressure 250 psi above its 5 min median: possible pack-off"),
    ("torque", "High torque", "warning", "Surface torque above 16 kft-lbf"),
    ("gas", "High gas", "warning", "Total gas above 4%"),
]
THRESHOLDS = {"torque": 16, "gas": 4}

THEME = {
    "fontFamily": "Inter, system-ui, sans-serif",
    "fontFamilyMonospace": "'IBM Plex Mono', ui-monospace, monospace",
    "primaryColor": "blue",
    "defaultRadius": "md",
    "colors": {
        "dark": ["#f0efec", "#c3c2b7", "#a3a29a", "#898781", "#4a4a46",
                 "#383835", "#232322", "#1a1a19", "#121211", "#0d0d0d"],
    },
}

app = dash.Dash(
    __name__,
    title="Live Well Drilling Monitor",
    external_stylesheets=[
        "https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=Inter:wght@400;500;600;700&display=swap"
    ],
)
server = app.server


def rolling(values, n, fn):
    """Trailing rolling statistic, padded at the start with the first full window's value."""
    if len(values) < n:
        return np.full(len(values), fn(values))
    rolled = fn(sliding_window_view(values, n), axis=1)
    return np.concatenate([np.full(n - 1, rolled[0]), rolled])


def alarm_conditions(d):
    per_min = 60 // sim.SAMPLE_SECONDS
    # Pump ramps after a connection look like spikes, so only check once pumps are steady
    pumping = rolling(d["flow_in"], 5 * per_min, np.min) > 600
    flow_in = rolling(d["flow_in"], 2 * per_min, np.mean)
    flow_out = rolling(d["flow_out"], 2 * per_min, np.mean)
    return {
        "pit_gain": d["pit_volume"] - rolling(d["pit_volume"], 10 * per_min, np.min) > 8,
        "flow_diff": pumping & (flow_out > 1.05 * np.maximum(flow_in, 1)),
        "spp_spike": pumping & (d["spp"] - rolling(d["spp"], 5 * per_min, np.median) > 250),
        "torque": d["torque"] > THRESHOLDS["torque"],
        "gas": d["gas"] > THRESHOLDS["gas"],
    }


def lithology_color(formation):
    return next(c for rock, c in LITHOLOGY.items() if rock in formation)


def style_axes(fig):
    fig.update_xaxes(
        gridcolor=GRID, linecolor=AXIS, zeroline=False, tickfont={"color": MUTED, "size": 11},
        showspikes=True, spikecolor=MUTED, spikethickness=1, spikedash="dot", spikemode="across",
    )
    fig.update_yaxes(
        gridcolor=GRID, linecolor=AXIS, zeroline=False, tickfont={"color": MUTED, "size": 11},
    )
    fig.update_annotations(font={"color": INK_2, "size": 12})
    fig.update_layout(
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font={"family": "Inter, system-ui, sans-serif", "color": INK_2},
        hoverlabel={"bgcolor": "#232322", "bordercolor": AXIS, "font": {"color": INK, "size": 12}},
        showlegend=False,
    )
    return fig


def depth_log(well_key, idx):
    """Depth-based tracks for the last DEPTH_LOG_FT of hole, averaged into 2 ft bins."""
    well = sim.WELLS_BY_KEY[well_key]
    d = sim.DATA[well_key]
    hole = d["hole_depth"][idx]
    bit = d["bit_depth"][idx]
    top = hole - DEPTH_LOG_FT
    drilled = slice(0, idx + 1)
    mask = (d["state"][drilled] == sim.DRILLING) & (d["hole_depth"][drilled] >= top)
    feet = (d["hole_depth"][drilled][mask] // 2).astype(int)
    first = feet.min()
    counts = np.bincount(feet - first)
    filled = counts > 0
    depth = 2 * (first + np.arange(len(counts)))[filled] + 1

    def binned(channel):
        sums = np.bincount(feet - first, weights=d[channel][drilled][mask])
        return sums[filled] / counts[filled]

    tracks = [
        ("rop", "ROP", "ft/hr"),
        ("wob", "WOB", "klbf"),
        ("torque", "Torque", "kft-lbf"),
        ("gas", "Total gas", "%"),
    ]
    fig = make_subplots(
        rows=1, cols=5, shared_yaxes=True, horizontal_spacing=0.025,
        column_widths=[0.7, 1, 1, 1, 1],
        subplot_titles=["Formation"] + [f"{label} <span style='color:{MUTED}'>{unit}</span>" for _, label, unit in tracks],
    )

    # Formation column: one block per formation that intersects the view
    starts = [f[1] + well.start_depth for f in sim.FORMATIONS] + [np.inf]
    for i, f in enumerate(sim.FORMATIONS):
        y0, y1 = max(starts[i], top), min(starts[i + 1], hole)
        if y0 >= y1:
            continue
        fig.add_shape(type="rect", x0=0, x1=1, y0=y0, y1=y1, xref="x", yref="y",
                      fillcolor=lithology_color(f[0]), line={"width": 2, "color": SURFACE}, layer="below")
        if y1 - y0 > 25:
            fig.add_annotation(x=0.5, y=(y0 + y1) / 2, xref="x", yref="y", text=f[0].replace(" ", "<br>"),
                               showarrow=False, font={"color": INK, "size": 11})
    fig.update_xaxes(nticks=4)
    fig.update_xaxes(range=[0, 1], visible=False, row=1, col=1)

    for col, (channel, label, unit) in enumerate(tracks, start=2):
        fig.add_trace(go.Scatter(
            x=binned(channel), y=depth, mode="lines", line={"color": SERIES[0], "width": 2},
            name=label, hovertemplate=f"%{{x:.1f}} {unit}<extra>{label}</extra>",
        ), row=1, col=col)
        if channel in THRESHOLDS:
            fig.add_vline(x=THRESHOLDS[channel], line={"color": STATUS["warning"], "width": 1, "dash": "dot"},
                          row=1, col=col)

    fig.add_hline(y=bit, line={"color": INK, "width": 1, "dash": "dash"})
    fig.add_annotation(x=1, y=bit, xref="paper", yref="y", text=f"Bit {bit:,.0f} ft", showarrow=False,
                       xanchor="right", yanchor="bottom", font={"color": INK, "size": 11})
    fig.update_yaxes(range=[hole + 5, top], title=None, ticksuffix=" ft", row=1, col=1)
    fig.update_layout(margin={"l": 64, "r": 12, "t": 36, "b": 24}, hovermode="y unified", uirevision=well_key)
    return style_axes(fig)


def strip_charts(stamps, d, well_key, window_label):
    rows = [
        ("Hookload", "klbf", ["hookload"]),
        ("Standpipe pressure", "psi", ["spp"]),
        ("Flow in / out", "gpm", ["flow_in", "flow_out"]),
        ("Active pit volume", "bbl", ["pit_volume"]),
        ("Rotary speed", "rpm", ["rpm"]),
    ]
    fig = make_subplots(
        rows=len(rows), cols=1, shared_xaxes=True, vertical_spacing=0.055,
        subplot_titles=[f"{label} <span style='color:{MUTED}'>{unit}</span>" for label, unit, _ in rows],
    )
    # Long windows get thinned out; the browser does not need 10k points per line
    step = max(1, len(stamps) // 1500)
    x = stamps[::step]
    for r, (label, unit, channels) in enumerate(rows, start=1):
        for k, channel in enumerate(channels):
            name = {"flow_in": "Flow in", "flow_out": "Flow out"}.get(channel, label)
            y = d[channel][::step]
            fig.add_trace(go.Scatter(
                x=x, y=y, mode="lines", name=name, line={"color": SERIES[k], "width": 2},
                hovertemplate=f"%{{y:,.1f}} {unit}<extra>{name}</extra>",
            ), row=r, col=1)
            if len(channels) > 1:
                fig.add_annotation(x=x[-1], y=y[-1], text=name, showarrow=False, xanchor="left", xshift=6,
                                   font={"color": INK_2, "size": 11}, row=r, col=1)
    fig.update_xaxes(showticklabels=False, range=[x[0], stamps[-1]])
    fig.update_xaxes(showticklabels=True, tickformat="%H:%M", row=len(rows), col=1)
    fig.update_layout(margin={"l": 56, "r": 64, "t": 28, "b": 24}, hovermode="x unified",
                      uirevision=f"{well_key}-{window_label}")
    return style_axes(fig)


def kpi(label, value, unit, fmt, delta=None, delta_fmt=None, status=None):
    delta_text = ""
    if delta is not None:
        arrow = "▲" if delta > 0 else "▼" if delta < 0 else "■"
        delta_text = f"{arrow} {abs(delta):{delta_fmt or fmt}} vs 10 min ago"
    return dmc.Paper(
        [
            dmc.Group(
                [
                    dmc.Text(label, className="kpi-label"),
                    status and DashIconify(icon=STATUS_ICON[status], width=16, color=STATUS[status]),
                ],
                justify="space-between",
                wrap="nowrap",
            ),
            dmc.Group(
                [dmc.Text(f"{value:{fmt}}", className="kpi-value"), dmc.Text(unit, className="kpi-unit")],
                gap=6,
                align="baseline",
                wrap="nowrap",
            ),
            dmc.Text(delta_text, className="kpi-delta"),
        ],
        className="kpi" + (f" kpi-{status}" if status else ""),
        style={"--status": STATUS[status]} if status else None,
    )


def alarm_badge(key, label, severity, active):
    return dmc.Badge(
        label,
        leftSection=DashIconify(icon=STATUS_ICON[severity] if active else "tabler:circle-check", width=14),
        color=STATUS[severity] if active else "dark.4",
        variant="filled" if active else "outline",
        size="lg",
        radius="sm",
        className="alarm-badge" + (" active" if active else ""),
        id={"type": "alarm", "key": key},
    )


def graph(graph_id):
    # A responsive dcc.Graph sizes itself to 100% of its parent, so the parent needs a real height
    return html.Div(
        dcc.Graph(id=graph_id, config={"displayModeBar": False, "responsive": True}, style={"height": "100%"}),
        className="graph-tall",
    )


def card(title, *children, extra=None, **kwargs):
    return dmc.Paper(
        [
            dmc.Group([dmc.Text(title, className="card-title"), extra], justify="space-between", mb="xs"),
            *children,
        ],
        className="card",
        **kwargs,
    )


header = dmc.AppShellHeader(
    dmc.Group(
        [
            dmc.Group(
                [
                    html.Div(DashIconify(icon="tabler:building-factory-2", width=20), className="brand-mark"),
                    dmc.Stack(
                        [
                            dmc.Text("Real-time operations", className="eyebrow", visibleFrom="md"),
                            dmc.Title("Live Well Drilling Monitor", order=3, className="app-title", visibleFrom="sm"),
                        ],
                        gap=0,
                    ),
                ],
                gap="sm",
                wrap="nowrap",
            ),
            dmc.Group(
                [
                    dmc.Select(
                        id="well",
                        data=[{"value": w.key, "label": w.name} for w in sim.WELLS],
                        value=sim.WELLS[0].key,
                        allowDeselect=False,
                        w={"base": 170, "sm": 190},
                        leftSection=DashIconify(icon="tabler:map-pin", width=16),
                        **{"aria-label": "Well"},
                    ),
                    dmc.SegmentedControl(id="window", data=list(WINDOWS), value="1 hr", visibleFrom="sm"),
                    dmc.Switch(id="live", label="Live", checked=True, color="green", size="md"),
                ],
                gap="md",
                wrap="nowrap",
            ),
        ],
        justify="space-between",
        h="100%",
        px="lg",
        wrap="nowrap",
    )
)

status_bar = dmc.Group(
    [
        dmc.Group(
            [
                html.Span(className="pulse", id="pulse"),
                dmc.Text(id="well-meta", className="meta"),
            ],
            gap="xs",
            wrap="nowrap",
        ),
        dmc.Group(
            [dmc.Badge(id="rig-state", size="lg", variant="light", radius="sm"),
             dmc.Text(id="clock", className="clock")],
            gap="sm",
            wrap="nowrap",
        ),
    ],
    justify="space-between",
    mb="md",
)

app.layout = dmc.MantineProvider(
    [
        dmc.AppShell(
            [
                header,
                dmc.AppShellMain(
                    [
                        status_bar,
                        html.Div(id="kpis", className="kpi-grid"),
                        card("Alarms", html.Div(id="alarm-badges", className="alarm-row"), mb="md"),
                        dmc.Grid(
                            [
                                dmc.GridCol(
                                    card(
                                        f"Depth log · last {DEPTH_LOG_FT} ft",
                                        graph("depth-log"),
                                    ),
                                    span={"base": 12, "lg": 5},
                                ),
                                dmc.GridCol(
                                    card(
                                        "Surface sensors",
                                        graph("strips"),
                                        extra=dmc.Text("UTC", className="card-hint"),
                                    ),
                                    span={"base": 12, "lg": 7},
                                ),
                            ],
                            gutter="md",
                        ),
                        card(
                            "Event log",
                            dmc.ScrollArea(html.Div(id="event-log"), mah=260, type="auto"),
                            extra=dmc.Text(id="event-count", className="card-hint"),
                        ),
                    ],
                    className="main",
                ),
            ],
            header={"height": 64},
            padding="lg",
        ),
        dcc.Interval(id="tick", interval=REFRESH_MS),
    ],
    theme=THEME,
    forceColorScheme="dark",
)


@app.callback(Output("tick", "disabled"), Output("pulse", "className"), Input("live", "checked"))
def toggle_live(live):
    return not live, "pulse" if live else "pulse paused"


@app.callback(
    Output("well-meta", "children"),
    Output("rig-state", "children"),
    Output("rig-state", "color"),
    Output("clock", "children"),
    Output("kpis", "children"),
    Output("alarm-badges", "children"),
    Output("depth-log", "figure"),
    Output("strips", "figure"),
    Output("event-log", "children"),
    Output("event-count", "children"),
    Input("tick", "n_intervals"),
    Input("well", "value"),
    Input("window", "value"),
)
def refresh(_, well_key, window_label):
    now = time.time()
    well = sim.WELLS_BY_KEY[well_key]
    seconds = WINDOWS[window_label]
    stamps, d = sim.window(well_key, seconds + LOOKBACK_S, now)
    cond = alarm_conditions(d)

    # The lookback is only for the rolling checks; trim it off before charting
    first = max(0, len(stamps) - seconds // sim.SAMPLE_SECONDS)
    view_stamps, view = stamps[first:], {c: v[first:] for c, v in d.items()}
    ago = -min(len(stamps), LOOKBACK_S // sim.SAMPLE_SECONDS)

    def now_and_delta(channel):
        return d[channel][-1], d[channel][-1] - d[channel][ago]

    active = {k: bool(v[-1]) for k, v in cond.items()}
    state = sim.STATES[int(d["state"][-1])]
    formation = sim.FORMATIONS[int(d["formation"][-1])][0]
    clock = str(stamps[-1]).replace("T", " ") + " UTC"

    def tile(label, channel, unit, fmt, alarm=None, delta_fmt=None):
        value, delta = now_and_delta(channel)
        status = next((sev for k, _, sev, _ in ALARMS if k == alarm and active[k]), None)
        return kpi(label, value, unit, fmt, delta, delta_fmt, status)

    kpis = [
        tile("Hole depth", "hole_depth", "ft", ",.1f"),
        tile("Bit depth", "bit_depth", "ft", ",.1f"),
        tile("ROP", "rop", "ft/hr", ".0f"),
        tile("Weight on bit", "wob", "klbf", ".1f"),
        tile("Torque", "torque", "kft-lbf", ".1f", alarm="torque"),
        tile("Standpipe", "spp", "psi", ",.0f", alarm="spp_spike"),
        tile("Pit volume", "pit_volume", "bbl", ".1f", alarm="pit_gain"),
        tile("Total gas", "gas", "%", ".2f", alarm="gas"),
    ]
    badges = [alarm_badge(k, label, sev, active[k]) for k, label, sev, _ in ALARMS]

    # An event is the first sample of each run of a raised alarm inside the view
    events = []
    for key, label, sev, why in ALARMS:
        c = cond[key][first:]
        before = cond[key][first - 1] if first else False
        for s in np.flatnonzero(c & ~np.concatenate([[before], c[:-1]])):
            cleared = np.flatnonzero(~c[s:])
            run = cleared[0] if len(cleared) else len(c) - s
            events.append((view_stamps[s], label, sev, why, run * sim.SAMPLE_SECONDS, not len(cleared)))
    events.sort(key=lambda e: e[0], reverse=True)

    rows = [
        html.Tr(
            [
                html.Td(str(t)[11:19], className="mono"),
                html.Td(dmc.Group([DashIconify(icon=STATUS_ICON[sev], width=16, color=STATUS[sev]),
                                   dmc.Text(sev.capitalize(), size="sm")], gap=6, wrap="nowrap")),
                html.Td(label, className="event-name"),
                html.Td(why, className="event-why"),
                html.Td("Active" if ongoing else f"{dur // 60}m {dur % 60:02d}s",
                        className="mono" + (" ongoing" if ongoing else "")),
            ]
        )
        for t, label, sev, why, dur, ongoing in events
    ]
    log = dmc.Table(
        [
            html.Thead(html.Tr([html.Th(h, className="event-why" if h == "Detail" else None)
                                for h in ["Time", "Severity", "Alarm", "Detail", "Duration"]])),
            html.Tbody(rows or [html.Tr(html.Td(f"No alarms in the last {window_label}.", colSpan=5,
                                                className="empty"))]),
        ],
        highlightOnHover=True,
        className="event-table",
    )

    meta = f"{well.name} · {well.rig} · {well.field} · {formation}"
    return (
        meta, state, STATE_COLOR[state], clock, kpis, badges,
        depth_log(well_key, sim.live_index(now)),
        strip_charts(view_stamps, view, well_key, window_label),
        log, f"{len(events)} in last {window_label}",
    )


if __name__ == "__main__":
    app.run(debug=True)
