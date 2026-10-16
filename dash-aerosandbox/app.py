import aerosandbox as asb
import dash_mantine_components as dmc
import numpy as np
import plotly.graph_objects as go
from dash import Dash, Input, Output, callback, dcc, html

from airplane import make_airplane

app = Dash(
    __name__,
    title="Solar Aircraft Design Studio",
    external_stylesheets=[
        "https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700"
        "&family=JetBrains+Mono:wght@400;500;700&display=swap"
    ],
)
server = app.server

FONT = "'Space Grotesk', sans-serif"
MONO = "'JetBrains Mono', monospace"
TEXT = "#d6e4f5"
TEXT_MUTED = "#6a87ab"
BODY_COLOR = "#6c8aa8"
STREAMLINE_COLOR = "#7fdbff"
EDGE_COLOR = "rgba(160, 210, 255, 0.1)"
# Navy to cyan to amber, so strong vortices glow against the dark scene
THERMAL = [
    [0.0, "#0f2a52"],
    [0.25, "#1565a8"],
    [0.5, "#1fb5c9"],
    [0.75, "#f2c14e"],
    [1.0, "#fff1c1"],
]

# Cruise condition of the original design study: 20 m/s at the altitude where
# the air density is 0.10 kg/m^3
VELOCITY = 20
ALTITUDE = 19_177
ATMOSPHERE = asb.Atmosphere(altitude=ALTITUDE)

ANALYSES = {
    "geometry": "Geometry",
    "ll": "Lifting line",
    "vlm": "Vortex lattice",
}


def section(number, title):
    return html.Div(
        [html.Span(number, className="section-number"), title], className="section-label"
    )


def readout(label, value_id, hint, hero=False):
    return dmc.Tooltip(
        html.Div(
            [
                html.Div(label, id=f"{value_id}-label", className="readout-label"),
                html.Div("–", id=value_id, className="readout-value"),
            ],
            className="readout readout-hero" if hero else "readout",
        ),
        label=hint,
        multiline=True,
        w=220,
        openDelay=400,
    )


def labeled(label, value_id, component):
    return dmc.Stack(
        [
            dmc.Group(
                [
                    dmc.Text(label, size="sm", fw=500),
                    html.Span(id=value_id, className="control-value"),
                ],
                justify="space-between",
            ),
            component,
        ],
        gap=4,
    )


def telemetry(label, value):
    return html.Span([html.Span(label, className="telemetry-label"), value])


header = dmc.AppShellHeader(
    dmc.Group(
        [
            dmc.Group(
                [
                    html.Span("HALE-01", className="tail-number"),
                    dmc.Stack(
                        [
                            dmc.Title("Solar Aircraft Design Studio", order=4),
                            html.Span(
                                "Aerodynamic analysis powered by AeroSandbox",
                                className="subtitle",
                            ),
                        ],
                        gap=0,
                    ),
                ],
                gap="md",
                wrap="nowrap",
            ),
            dmc.Group(
                [
                    dmc.Group(
                        [
                            telemetry("V", f"{VELOCITY} m/s"),
                            telemetry("ALT", f"{ALTITUDE / 1000:.1f} km"),
                            telemetry("ρ", f"{ATMOSPHERE.density():.2f} kg/m³"),
                        ],
                        gap="lg",
                        className="telemetry",
                        visibleFrom="md",
                    ),
                    html.A(
                        html.Img(
                            src=app.get_asset_url("dash-logo-dark.png"), height=32, alt="Plotly"
                        ),
                        href="https://dash.plotly.com/",
                        className="dash-logo",
                    ),
                ],
                gap="xl",
                wrap="nowrap",
            ),
        ],
        justify="space-between",
        h="100%",
        px="lg",
        wrap="nowrap",
    )
)

controls = html.Div(
    dmc.Stack(
        [
            section("01", "Airframe"),
            dmc.Stack(
                [
                    dmc.Text("Number of booms", size="sm", fw=500),
                    dmc.SegmentedControl(
                        id="n-booms",
                        data=["1", "2", "3"],
                        value="3",
                        fullWidth=True,
                    ),
                ],
                gap=4,
            ),
            labeled(
                "Wing span",
                "wing-span-value",
                dmc.Slider(
                    id="wing-span",
                    min=20,
                    max=60,
                    step=1,
                    value=30,
                    marks=[{"value": v, "label": f"{v} m"} for v in (20, 40, 60)],
                    mb="md",
                    mx="xs",
                ),
            ),
            labeled(
                "Angle of attack",
                "alpha-value",
                dmc.Slider(
                    id="alpha",
                    min=-5,
                    max=15,
                    step=0.5,
                    value=7,
                    marks=[{"value": v, "label": f"{v}°"} for v in (-5, 0, 5, 10, 15)],
                    mb="md",
                    mx="xs",
                ),
            ),
            section("02", "Solver"),
            dmc.SegmentedControl(
                id="analysis",
                data=[{"value": k, "label": v} for k, v in ANALYSES.items()],
                value="vlm",
                fullWidth=True,
                size="xs",
            ),
            dmc.Switch(
                id="streamlines",
                label="Show streamlines",
                checked=True,
                size="sm",
            ),
            section("03", "Readout"),
            html.Div(
                readout("L/D", "ld", "Lift-to-drag ratio, the aerodynamic efficiency", hero=True),
                className="readout-row",
            ),
            html.Div(
                [
                    readout("CL", "cl", "Lift coefficient of the whole aircraft"),
                    readout(
                        "CD",
                        "cd",
                        "Drag coefficient. The vortex lattice method is inviscid, so it "
                        "only reports induced drag (CDi).",
                    ),
                    readout("Cm", "cm", "Pitching moment coefficient about the wing root"),
                ],
                className="readout-grid",
            ),
            html.Div(className="spacer"),
            html.Div(
                [
                    html.P(
                        [
                            "Design by Peter Sharpe, analysis by ",
                            html.A(
                                "AeroSandbox",
                                href="https://github.com/peterdsharpe/AeroSandbox",
                                target="_blank",
                            ),
                            ". ",
                            html.A(
                                "Original demo",
                                href="https://github.com/peterdsharpe/AeroSandbox-Interactive-Demo",
                                target="_blank",
                            ),
                            ".",
                        ]
                    ),
                ],
                className="source",
            ),
        ],
        gap="sm",
        h="100%",
    ),
    className="card controls",
)

view_card = html.Div(
    [
        dmc.Group(
            [
                html.Span(id="view-title", className="view-title"),
                html.Span(id="view-meta", className="view-meta"),
            ],
            justify="space-between",
            className="card-head",
        ),
        dcc.Loading(
            dcc.Graph(
                id="view",
                className="view-graph",
                config={"displaylogo": False, "displayModeBar": "hover"},
                responsive=True,
            ),
            parent_className="view-loading",
            delay_show=400,
            overlay_style={"visibility": "visible", "opacity": 0.6},
            type="circle",
            color=STREAMLINE_COLOR,
        ),
        html.Span("Drag to rotate · scroll to zoom", className="view-hint"),
    ],
    className="card view-card",
)

app.layout = dmc.MantineProvider(
    dmc.AppShell(
        [header, dmc.AppShellMain(html.Div([controls, view_card], className="page"))],
        header={"height": 64},
    ),
    theme={
        "fontFamily": FONT,
        "fontFamilyMonospace": MONO,
        "headings": {"fontFamily": FONT},
        "primaryColor": "cyan",
        "defaultRadius": "xs",
        # Navy instead of Mantine's neutral grays for the dark scheme
        "colors": {
            "dark": [
                "#d6e4f5", "#b3c7e0", "#8ea8c8", "#6a87ab", "#2c4467",
                "#1c3254", "#132744", "#0d1e36", "#09172b", "#060f1d",
            ]  # fmt: skip
        },
    },
    forceColorScheme="dark",
)


def body_mesh(points, faces, color=BODY_COLOR, opacity=1.0, name="Airframe"):
    return go.Mesh3d(
        x=points[:, 0],
        y=points[:, 1],
        z=points[:, 2],
        i=faces[:, 0],
        j=faces[:, 1],
        k=faces[:, 2],
        color=color,
        opacity=opacity,
        flatshading=False,
        lighting={"ambient": 0.45, "diffuse": 0.8, "specular": 0.5, "roughness": 0.4},
        lightposition={"x": 1000, "y": -2000, "z": 3000},
        hoverinfo="skip",
        name=name,
    )


def panel_traces(analysis):
    """Panels of a solved lifting line / vortex lattice, colored by vortex strength."""
    corners = np.stack(
        [
            analysis.front_left_vertices,
            analysis.back_left_vertices,
            analysis.back_right_vertices,
            analysis.front_right_vertices,
        ],
        axis=1,
    )  # (n_panels, 4, 3)
    n = len(corners)
    points = corners.reshape(-1, 3)
    base = 4 * np.arange(n)[:, None]
    faces = np.concatenate([base + [0, 1, 2], base + [0, 2, 3]])
    strength = np.asarray(analysis.vortex_strengths)

    surface = go.Mesh3d(
        x=points[:, 0],
        y=points[:, 1],
        z=points[:, 2],
        i=faces[:, 0],
        j=faces[:, 1],
        k=faces[:, 2],
        intensity=np.concatenate([strength, strength]),
        intensitymode="cell",
        colorscale=THERMAL,
        colorbar={
            "title": {"text": "VORTEX<br>STRENGTH", "side": "top", "font": {"size": 10}},
            "thickness": 8,
            "len": 0.45,
            "x": 0.98,
            "outlinewidth": 0,
            "tickfont": {"family": MONO, "size": 10, "color": TEXT_MUTED},
        },
        flatshading=True,
        lighting={"ambient": 0.85, "diffuse": 0.35},
        hoverinfo="skip",
        name="Panels",
    )

    # Panel outlines, as one line trace with gaps between panels
    loops = np.concatenate([corners, corners[:, :1], np.full((n, 1, 3), np.nan)], axis=1)
    loops = loops.reshape(-1, 3)
    outlines = go.Scatter3d(
        x=loops[:, 0],
        y=loops[:, 1],
        z=loops[:, 2],
        mode="lines",
        line={"color": EDGE_COLOR, "width": 1},
        hoverinfo="skip",
        name="Panel edges",
    )
    return [surface, outlines]


def streamline_trace(vlm):
    lines = np.asarray(vlm.streamlines)  # (n_lines, 3, n_steps)
    lines = np.concatenate([lines, np.full((len(lines), 3, 1), np.nan)], axis=2)
    xyz = lines.transpose(0, 2, 1).reshape(-1, 3)
    return go.Scatter3d(
        x=xyz[:, 0],
        y=xyz[:, 1],
        z=xyz[:, 2],
        mode="lines",
        line={"color": STREAMLINE_COLOR, "width": 1.5},
        opacity=0.35,
        hoverinfo="skip",
        name="Streamlines",
    )


def make_figure(traces):
    fig = go.Figure(traces)
    # True proportions, scaled so the longest side is 1. aspectmode="data" would
    # normalize by the geometric mean instead, which blows up the span of such a
    # flat aircraft and pushes the wing tips out of view.
    lo = np.array([min(np.nanmin(np.asarray(t[a], float)) for t in traces) for a in "xyz"])
    hi = np.array([max(np.nanmax(np.asarray(t[a], float)) for t in traces) for a in "xyz"])
    extent = hi - lo
    aspect = extent / extent.max()
    axis = {"visible": False, "showspikes": False}
    fig.update_layout(
        font={"family": FONT, "color": TEXT, "size": 12},
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        # Keep the camera where the user left it while the design changes
        uirevision="view",
        scene={
            "xaxis": {**axis, "range": [lo[0], hi[0]]},
            "yaxis": {**axis, "range": [lo[1], hi[1]]},
            "zaxis": {**axis, "range": [lo[2], hi[2]]},
            "aspectmode": "manual",
            "aspectratio": dict(zip("xyz", aspect)),
            "bgcolor": "rgba(0,0,0,0)",
            "camera": {
                "eye": {"x": -0.64, "y": -0.8, "z": 0.45},
                "up": {"x": 0, "y": 0, "z": 1},
            },
        },
    )
    return fig


def fmt(value, digits=3):
    return f"{float(np.squeeze(value)):.{digits}f}"


@callback(
    Output("wing-span-value", "children"),
    Output("alpha-value", "children"),
    Output("streamlines", "disabled"),
    Input("wing-span", "value"),
    Input("alpha", "value"),
    Input("analysis", "value"),
)
def show_values(wing_span, alpha, analysis):
    return f"{wing_span} m", f"{alpha:g}°", analysis != "vlm"


@callback(
    Output("view", "figure"),
    Output("view-title", "children"),
    Output("cl", "children"),
    Output("cd", "children"),
    Output("cd-label", "children"),
    Output("ld", "children"),
    Output("cm", "children"),
    Output("view-meta", "children"),
    Input("n-booms", "value"),
    Input("wing-span", "value"),
    Input("alpha", "value"),
    Input("analysis", "value"),
    Input("streamlines", "checked"),
)
def update(n_booms, wing_span, alpha, analysis, streamlines):
    airplane = make_airplane(n_booms=int(n_booms), wing_span=wing_span)
    op_point = asb.OperatingPoint(atmosphere=ATMOSPHERE, velocity=VELOCITY, alpha=alpha)
    wing = airplane.wings[0]
    meta = (
        f"α {alpha:+.1f}°   b {wing_span} m   S {wing.area():.1f} m²   "
        f"AR {wing.aspect_ratio():.1f}"
    )

    if analysis == "geometry":
        # The geometry view also shows a quick AeroBuildup estimate
        points, faces = airplane.mesh_body(method="tri")
        figure = make_figure([body_mesh(points, faces)])
        aero = asb.AeroBuildup(airplane=airplane, op_point=op_point).run()
        cd_label = "CD"
        title = "Geometry // AeroBuildup estimate"
    else:
        solver = asb.LiftingLine if analysis == "ll" else asb.VortexLatticeMethod
        result = solver(airplane=airplane, op_point=op_point)
        aero = result.run()
        traces = panel_traces(result)
        for fuselage in airplane.fuselages:
            points, faces = fuselage.mesh_body(method="tri")
            traces.append(body_mesh(points, faces, opacity=0.6, name="Fuselage"))
        if analysis == "vlm" and streamlines:
            result.calculate_streamlines()
            traces.append(streamline_trace(result))
        figure = make_figure(traces)
        # The vortex lattice method is inviscid: its drag is induced drag only
        cd_label = "CDi" if analysis == "vlm" else "CD"
        title = f"{ANALYSES[analysis]} // {n_booms} boom{'s' if n_booms != '1' else ''}"

    cl, cd = float(np.squeeze(aero["CL"])), float(np.squeeze(aero["CD"]))
    return (
        figure,
        title,
        fmt(cl),
        fmt(cd, 4),
        cd_label,
        f"{cl / cd:.1f}",
        fmt(aero["Cm"]),
        meta,
    )


if __name__ == "__main__":
    app.run(debug=True)
