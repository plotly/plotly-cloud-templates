"""Terrain mesh: a crater DEM warped by elevation, with hover picking."""

import random

import dash_mantine_components as dmc
import dash_vtk
import numpy as np
from dash import Input, Output, State, callback, ctx, html, no_update

from .common import DATA, View, field, preset_select, section, skip_mount, slider, tips, view_id

SLUG = "terrain"
TITLE = "Terrain mesh"
GROUP = "Geometry"
KICKER = "Warped elevation surface with picking"
ABOUT = ("An 81 × 81 window of a crater elevation model, triangulated as quads and lifted by its own "
         "height. Hover the surface to probe it; the warp is recomputed in NumPy on the server.")

_dem = np.load(DATA / "terrain.npz")
NX, NY = (int(n) for n in _dem["dims"])
X, Y, ELEVATION = _dem["x"], _dem["y"], _dem["elevation"]
COLOR_RANGE = [float(ELEVATION.min()), float(ELEVATION.max())]
# The hidden pick marker starts mid-terrain so it never stretches the camera's bounds
CENTER = [float(X.mean()), float(Y.mean()), float(ELEVATION.mean())]

# One quad per grid cell, in VTK's flat [n, id0, id1, ...] cell layout
_i, _j = np.meshgrid(np.arange(NX - 1), np.arange(NY - 1))
_corner = (_j * NX + _i).ravel()
POLYS = np.column_stack([np.full_like(_corner, 4), _corner, _corner + 1, _corner + NX + 1, _corner + NX]).ravel()


def warp(factor):
    return np.column_stack([X, Y, ELEVATION * factor]).ravel()


def view():
    return View(SLUG, pickingModes=["hover"], cameraPosition=[0.35, -1, 0.75], cameraViewUp=[0, 0, 1], children=[
        dash_vtk.GeometryRepresentation(
            id="terrain-rep",
            colorMapPreset="erdc_blue2green_muted",
            colorDataRange=COLOR_RANGE,
            property={"edgeVisibility": True, "edgeColor": [0.04, 0.04, 0.05]},
            showCubeAxes=False,
            cubeAxesStyle={
                "axisLabels": ["Easting", "Northing", "Altitude"],
                "axisTextStyle": {"fontColor": "#c8f560", "fontFamily": "DM Mono, monospace", "fontSize": 15},
                "tickTextStyle": {"fontColor": "#a9a6b8", "fontFamily": "DM Mono, monospace", "fontSize": 12},
            },
            children=[
                dash_vtk.PolyData(
                    id="terrain-polydata", points=warp(1), polys=POLYS,
                    children=[dash_vtk.PointData([
                        dash_vtk.DataArray(registration="setScalars", name="elevation", values=ELEVATION)
                    ])],
                )
            ],
        ),
        dash_vtk.GeometryRepresentation(
            id="terrain-pick-rep",
            actor={"visibility": False},
            property={"color": [0.78, 0.96, 0.38]},
            children=[dash_vtk.Algorithm(id="terrain-pick", vtkClass="vtkSphereSource",
                                       state={"center": CENTER, "radius": 90})],
        ),
    ])


def controls():
    return [
        section(
            "Surface",
            field("Vertical exaggeration", slider("terrain-scale", 0.2, 5, 1, step=0.1)),
            field("Color map", preset_select("terrain-preset", "erdc_blue2green_muted")),
            dmc.Group([
                dmc.Switch(id="terrain-axes", label="Axis grid", checked=False, size="sm"),
                dmc.Switch(id="terrain-edges", label="Wireframe", checked=True, size="sm"),
            ], gap="lg", mt="md"),
        ),
        section(
            "Probe",
            html.Div(id="terrain-probe", className="probe", children=_probe(None)),
        ),
        section("Try", tips("Push exaggeration to 5 and orbit low over the rim")),
    ]


def stats():
    return [("Grid", f"{NX} × {NY}"), ("Quads", f"{(NX - 1) * (NY - 1):,}"),
            ("Elevation", f"{COLOR_RANGE[0]:,.0f} – {COLOR_RANGE[1]:,.0f} m")]


def _probe(info, scale=1):
    rows = [("Easting", "—"), ("Northing", "—"), ("Altitude", "—")]
    if info:
        x, y, z = info["worldPosition"]
        rows = [("Easting", f"{x:,.0f} m"), ("Northing", f"{y:,.0f} m"), ("Altitude", f"{z / scale:,.0f} m")]
    return [html.Div([html.Span(k), html.B(v)], className="probe-row") for k, v in rows]


@callback(
    Output("terrain-polydata", "points"),
    Output("terrain-rep", "colorMapPreset"),
    Output("terrain-rep", "showCubeAxes"),
    Output("terrain-rep", "property"),
    Output(view_id(SLUG), "triggerResetCamera", allow_duplicate=True),
    Input("terrain-scale", "value"),
    Input("terrain-preset", "value"),
    Input("terrain-axes", "checked"),
    Input("terrain-edges", "checked"),
    prevent_initial_call=True,
)
def update_surface(scale, preset, axes, edges):
    skip_mount()
    prop = {"edgeVisibility": edges, "edgeColor": [0.04, 0.04, 0.05]}
    reset = random.random() if ctx.triggered_id == "terrain-scale" else no_update
    return warp(scale), preset, axes, prop, reset


@callback(
    Output("terrain-probe", "children"),
    Output("terrain-pick", "state"),
    Output("terrain-pick-rep", "actor"),
    Input(view_id(SLUG), "hoverInfo"),
    State("terrain-scale", "value"),
    prevent_initial_call=True,
)
def probe(info, scale):
    if info and info.get("representationId") == "terrain-rep":
        return _probe(info, scale), {"center": info["worldPosition"], "radius": 90}, {"visibility": True}
    if info:
        return no_update, no_update, no_update
    return _probe(None), no_update, {"visibility": False}
