"""Procedural geometry: a vtk.js source algorithm configured entirely from Python."""

import random

import dash_mantine_components as dmc
import dash_vtk
from dash import Input, Output, callback, ctx, no_update

from .common import View, field, section, skip_mount, slider, tips, view_id

SLUG = "procedural"
TITLE = "Procedural source"
GROUP = "Geometry"
KICKER = "vtk.js algorithm, built in the browser"
ABOUT = ("No mesh is sent from the server. Python only describes which vtk.js source to run and "
         "its parameters, and the geometry is generated client side on every change.")

SOURCES = {
    "cone": "vtkConeSource",
    "cylinder": "vtkCylinderSource",
    "sphere": "vtkSphereSource",
}
SWATCHES = ["#5cc8ff", "#ff7a59", "#c8f560", "#f2efe6", "#c58bff"]


def _state(source, resolution, capping):
    if source == "sphere":
        return {"thetaResolution": resolution, "phiResolution": resolution}
    return {"resolution": resolution, "capping": capping}


def _rgb(hex_color):
    return [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]


def _property(color, edges):
    return {"color": _rgb(color), "edgeVisibility": edges, "edgeColor": [0.05, 0.05, 0.07]}


def _algorithm(source, resolution, capping):
    return dash_vtk.Algorithm(vtkClass=SOURCES[source], state=_state(source, resolution, capping))


def view():
    return View(SLUG, [
        dash_vtk.GeometryRepresentation(id="proc-rep", property=_property(SWATCHES[0], True),
                                        children=[_algorithm("cone", 32, True)])
    ])


def controls():
    return [
        section(
            "Source",
            dmc.SegmentedControl(id="proc-source", data=[{"label": k.title(), "value": k} for k in SOURCES],
                                 value="cone", fullWidth=True, size="xs", mb="md"),
            field("Resolution", slider("proc-resolution", 3, 96, 32)),
            dmc.Group([
                dmc.Switch(id="proc-capping", label="Capping", checked=True, size="sm"),
                dmc.Switch(id="proc-edges", label="Edges", checked=True, size="sm"),
            ], gap="lg", mb="md"),
            field("Surface", dmc.ColorPicker(id="proc-color", format="hex", value=SWATCHES[0],
                                             swatches=SWATCHES, withPicker=False, swatchesPerRow=5,
                                             fullWidth=True)),
        ),
        section("Try", tips("Drop the resolution to 3 to see the faceting",
                            "Turn capping off and look inside")),
    ]


def stats():
    return [("Sources", "cone · cylinder · sphere"), ("Payload", "≈ 200 bytes"), ("Built", "client side")]


@callback(
    Output("proc-rep", "children"),
    Output("proc-rep", "property"),
    Output("proc-capping", "disabled"),
    Output(view_id(SLUG), "triggerResetCamera", allow_duplicate=True),
    Input("proc-source", "value"),
    Input("proc-resolution", "value"),
    Input("proc-capping", "checked"),
    Input("proc-edges", "checked"),
    Input("proc-color", "value"),
    prevent_initial_call=True,
)
def update_source(source, resolution, capping, edges, color):
    skip_mount()
    reset = random.random() if ctx.triggered_id == "proc-source" else no_update
    return [_algorithm(source, resolution, capping)], _property(color, edges), source == "sphere", reset
