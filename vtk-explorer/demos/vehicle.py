"""Vehicle aerodynamics: surface pressure and velocity on a race car, with a hover probe."""

import math
import random

import dash_mantine_components as dmc
import dash_vtk
from dash import Input, Output, callback, html, no_update
from dash_vtk.utils import to_mesh_state
from vtkmodules.vtkIOXML import vtkXMLPolyDataReader

from .common import DATA, View, field, preset_select, section, skip_mount, slider, tips, view_id

SLUG = "vehicle"
TITLE = "Vehicle aerodynamics"
GROUP = "Simulation"
KICKER = "Surface fields on a race car, probed"
ABOUT = ("An OpenFOAM run around a race car, split into four parts. Color the surface by pressure or "
         "velocity and hover it to probe; the server looks up the nearest point and aims a cone along the flow.")

PARTS = {"body": "Body", "drive-train": "Drivetrain", "front-wing": "Front wing", "rear-wing": "Rear wing"}
FIELDS = {"solid": "Solid", "U": "Velocity", "p": "Pressure"}
COLOR_RANGES = {"U": [0, 100], "p": [-4464, 1700]}
SOLID = {"color": [0.82, 0.81, 0.78]}
ISO_COLOR = [0.36, 0.78, 1.0]
# The hidden probe cone starts mid-car so it never stretches the camera's bounds
CENTER = [1.4, 0, 0.5]


def _read(name):
    reader = vtkXMLPolyDataReader()
    reader.SetFileName(str(DATA / "vehicle" / f"{name}.vtp"))
    reader.Update()
    return reader.GetOutput()


# Raw datasets stay on the server for probing; the meshes are what the browser receives
DATASETS = {part: _read(part) for part in PARTS}
MESHES = {part: to_mesh_state(ds, point_arrays=["U", "p"]) for part, ds in DATASETS.items()}
ISO_MESH = to_mesh_state(_read("cp"))
N_POINTS = sum(ds.GetNumberOfPoints() for ds in DATASETS.values())


def rep_id(part):
    return f"vehicle-{part}-rep"


def _mapper(color_by):
    if color_by == "solid":
        return {"scalarVisibility": False}
    return {"colorByArrayName": color_by, "scalarMode": 3, "interpolateScalarsBeforeMapping": True,
            "scalarVisibility": True}


def _iso_property(opacity):
    return {"color": ISO_COLOR, "opacity": opacity}


def view():
    parts = [
        dash_vtk.GeometryRepresentation(id=rep_id(part), property=SOLID, mapper=_mapper("solid"),
                                        colorMapPreset="erdc_rainbow_bright", colorDataRange=COLOR_RANGES["U"],
                                        children=[dash_vtk.Mesh(state=mesh)])
        for part, mesh in MESHES.items()
    ]
    return View(SLUG, pickingModes=["hover"], cameraPosition=[-0.9, -1.3, 0.7], cameraViewUp=[0, 0, 1], children=[
        *parts,
        dash_vtk.GeometryRepresentation(id="vehicle-iso-rep", actor={"visibility": False},
                                        property=_iso_property(0.35), children=[dash_vtk.Mesh(state=ISO_MESH)]),
        dash_vtk.GeometryRepresentation(
            id="vehicle-pointer-rep",
            actor={"visibility": False},
            property={"color": ISO_COLOR},
            children=[dash_vtk.Algorithm(id="vehicle-pointer", vtkClass="vtkConeSource",
                                         state={"center": CENTER, "radius": 0.01, "height": 0.01})],
        ),
    ])


def controls():
    return [
        section(
            "Geometry",
            dmc.ChipGroup(
                dmc.Group([dmc.Chip(label, value=part, size="xs") for part, label in PARTS.items()], gap=6, mb="md"),
                id="vehicle-parts", multiple=True, value=list(PARTS),
            ),
        ),
        section(
            "Surface",
            dmc.SegmentedControl(id="vehicle-color-by", data=[{"label": v, "value": k} for k, v in FIELDS.items()],
                                 value="solid", fullWidth=True, size="xs", mb="md"),
            field("Color map", preset_select("vehicle-preset", "erdc_rainbow_bright")),
        ),
        section(
            "Isosurface",
            dmc.Switch(id="vehicle-iso", label="Pressure coefficient (Cp)", checked=False, size="sm", mb="md"),
            field("Opacity", slider("vehicle-iso-opacity", 0.1, 1, 0.35, step=0.05)),
        ),
        section(
            "Probe",
            html.Div(id="vehicle-probe", className="probe", children=_probe(None)),
        ),
        section("Try", tips("Color by pressure and look at the front wing's leading edge",
                            "Turn on the isosurface and hide the body")),
    ]


def stats():
    return [("Surface points", f"{N_POINTS:,}"), ("Parts", f"{len(PARTS)}"), ("Solver", "OpenFOAM")]


def _probe(part=None, p=None, speed=None):
    rows = [("Part", PARTS[part] if part else "—"),
            ("Pressure", f"{p:,.0f} Pa" if p is not None else "—"),
            ("Speed", f"{speed:,.1f} m/s" if speed is not None else "—")]
    return [html.Div([html.Span(k), html.B(v)], className="probe-row") for k, v in rows]


@callback(
    *[Output(rep_id(part), "actor") for part in PARTS],
    *[Output(rep_id(part), "mapper") for part in PARTS],
    *[Output(rep_id(part), "colorDataRange") for part in PARTS],
    *[Output(rep_id(part), "colorMapPreset") for part in PARTS],
    Output("vehicle-iso-rep", "actor"),
    Output("vehicle-iso-rep", "property"),
    Output("vehicle-preset", "disabled"),
    Output(view_id(SLUG), "triggerRender"),
    Input("vehicle-parts", "value"),
    Input("vehicle-color-by", "value"),
    Input("vehicle-preset", "value"),
    Input("vehicle-iso", "checked"),
    Input("vehicle-iso-opacity", "value"),
    prevent_initial_call=True,
)
def update_scene(parts, color_by, preset, iso, opacity):
    skip_mount()
    n = len(PARTS)
    actors = [{"visibility": part in parts} for part in PARTS]
    color_range = COLOR_RANGES.get(color_by, no_update)
    return (*actors, *[_mapper(color_by)] * n, *[color_range] * n, *[preset] * n,
            {"visibility": iso}, _iso_property(opacity), color_by == "solid", random.random())


@callback(
    Output("vehicle-probe", "children"),
    Output("vehicle-pointer", "state"),
    Output("vehicle-pointer-rep", "actor"),
    Input(view_id(SLUG), "hoverInfo"),
    prevent_initial_call=True,
)
def probe(info):
    part = (info or {}).get("representationId", "").removeprefix("vehicle-").removesuffix("-rep")
    if part not in PARTS:
        if info:
            return no_update, no_update, no_update
        return _probe(), no_update, {"visibility": False}

    mesh = DATASETS[part]
    idx = mesh.FindPoint(info["worldPosition"])
    if idx < 0:
        return no_update, no_update, no_update
    point = mesh.GetPoint(idx)
    u = mesh.GetPointData().GetArray("U").GetTuple3(idx)
    p = mesh.GetPointData().GetArray("p").GetValue(idx)
    speed = math.dist(u, (0, 0, 0))

    # A cone pointing along the local flow, its tip on the surface and its length scaled by speed
    direction = [c / speed for c in u] if speed else [1, 0, 0]
    height = 0.05 + 0.004 * speed
    center = [x - 0.5 * height * d for x, d in zip(point, direction)]
    cone = {"center": center, "direction": direction, "height": height, "radius": 0.04, "resolution": 16}
    return _probe(part, p, speed), cone, {"visibility": True}
