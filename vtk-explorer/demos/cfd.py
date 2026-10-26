"""CFD streamlines: airflow around a motorbike, traced on the server with VTK."""

import random

import dash_mantine_components as dmc
import dash_vtk
from dash import Input, Output, callback
from dash_vtk.utils import to_mesh_state
from vtkmodules.vtkFiltersCore import vtkTubeFilter
from vtkmodules.vtkFiltersFlowPaths import vtkStreamTracer
from vtkmodules.vtkFiltersSources import vtkLineSource
from vtkmodules.vtkIOXML import vtkXMLPolyDataReader, vtkXMLUnstructuredGridReader

from .common import DATA, View, field, preset_select, section, skip_mount, slider, tips, view_id

SLUG = "cfd"
TITLE = "CFD streamlines"
GROUP = "Simulation"
KICKER = "Wind tunnel flow, traced server side"
ABOUT = ("An OpenFOAM wind tunnel run around a motorbike and rider. VTK seeds a line of particles, "
         "integrates them through the velocity field and wraps the paths in tubes before sending them.")

FIELDS = {"p": "Pressure", "U": "Velocity", "k": "Turbulence", "Vorticity": "Vorticity", "Rotation": "Rotation"}
LOW, HIGH = -0.55, 0.6
X_SEED, Z_BOTTOM, Z_TOP = -0.4, 0.05, 1.5

_bike = vtkXMLPolyDataReader()
_bike.SetFileName(str(DATA / "bike.vtp"))
_bike.Update()
BIKE_MESH = to_mesh_state(_bike.GetOutput())

_tunnel = vtkXMLUnstructuredGridReader()
_tunnel.SetFileName(str(DATA / "tunnel.vtu"))
_tunnel.Update()
N_CELLS = _tunnel.GetOutput().GetNumberOfCells()

_seed = vtkLineSource()
_tracer = vtkStreamTracer()
_tracer.SetInputConnection(_tunnel.GetOutputPort())
_tracer.SetSourceConnection(_seed.GetOutputPort())
_tracer.SetIntegrationDirectionToForward()
_tracer.SetIntegratorTypeToRungeKutta45()
_tracer.SetMaximumPropagation(3)
_tracer.SetIntegrationStepUnit(2)
_tracer.SetInitialIntegrationStep(0.2)
_tracer.SetMinimumIntegrationStep(0.01)
_tracer.SetMaximumIntegrationStep(0.5)
_tracer.SetMaximumError(1e-6)
_tracer.SetMaximumNumberOfSteps(2000)
_tracer.SetTerminalSpeed(1e-11)
_tubes = vtkTubeFilter()
_tubes.SetInputConnection(_tracer.GetOutputPort())
_tubes.SetRadius(0.01)
_tubes.SetNumberOfSides(6)
_tubes.CappingOn()


def seed_state(y_bottom, y_top, resolution):
    return {"point1": [X_SEED, y_bottom, Z_BOTTOM], "point2": [X_SEED, y_top, Z_TOP], "resolution": resolution}


def trace(y_bottom, y_top, resolution, color_by):
    """Stream tubes from a seed line; gunicorn's sync workers serve one request at a time, so the pipeline is safe to share."""
    state = seed_state(y_bottom, y_top, resolution)
    _seed.SetPoint1(*state["point1"])
    _seed.SetPoint2(*state["point2"])
    _seed.SetResolution(resolution)
    _tubes.Update()
    mesh = to_mesh_state(_tubes.GetOutput(), color_by)
    return mesh, mesh["field"]["dataRange"]


def view():
    tubes, color_range = trace(0, 0, 10, "p")
    return View(SLUG, cameraPosition=[-1, -1.6, 0.8], cameraViewUp=[0, 0, 1], children=[
        dash_vtk.GeometryRepresentation(id="cfd-bike-rep", property={"color": [0.82, 0.81, 0.78]},
                                        children=[dash_vtk.Mesh(state=BIKE_MESH)]),
        dash_vtk.GeometryRepresentation(id="cfd-tubes-rep", colorMapPreset="Cool to Warm",
                                        colorDataRange=color_range,
                                        children=[dash_vtk.Mesh(id="cfd-tubes", state=tubes)]),
        dash_vtk.GeometryRepresentation(
            property={"color": [0.78, 0.96, 0.38], "representation": 0, "pointSize": 7},
            children=[dash_vtk.Algorithm(id="cfd-seed", vtkClass="vtkLineSource", state=seed_state(0, 0, 10))],
        ),
    ])


def controls():
    marks = [{"value": LOW, "label": "L"}, {"value": 0, "label": "0"}, {"value": HIGH, "label": "R"}]
    return [
        section(
            "Seed line",
            field("Bottom end", slider("cfd-y1", LOW, HIGH, 0, step=0.05, marks=marks), hint="lateral offset"),
            field("Top end", slider("cfd-y2", LOW, HIGH, 0, step=0.05, marks=marks), hint="lateral offset"),
            field("Streamlines", slider("cfd-resolution", 5, 50, 10)),
        ),
        section(
            "Color",
            field("Field", dmc.Select(id="cfd-color-by", data=[{"label": v, "value": k} for k, v in FIELDS.items()],
                                      value="p", allowDeselect=False, size="xs", mb="sm")),
            field("Color map", preset_select("cfd-preset", "Cool to Warm")),
        ),
        section("Try", tips("Swing the top end right to sweep the rider's helmet")),
    ]


def stats():
    return [("Tunnel cells", f"{N_CELLS:,}"), ("Integrator", "Runge–Kutta 4-5"), ("Solver", "OpenFOAM")]


@callback(
    Output("cfd-seed", "state"),
    Output("cfd-tubes", "state"),
    Output("cfd-tubes-rep", "colorDataRange"),
    Output("cfd-tubes-rep", "colorMapPreset"),
    Output(view_id(SLUG), "triggerRender"),
    Input("cfd-y1", "value"),
    Input("cfd-y2", "value"),
    Input("cfd-resolution", "value"),
    Input("cfd-color-by", "value"),
    Input("cfd-preset", "value"),
    prevent_initial_call=True,
)
def update_streamlines(y1, y2, resolution, color_by, preset):
    skip_mount()
    tubes, color_range = trace(y1, y2, resolution, color_by)
    return seed_state(y1, y2, resolution), tubes, color_range, preset, random.random()
