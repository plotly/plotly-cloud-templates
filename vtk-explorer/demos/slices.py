"""Slice explorer: three orthogonal planes through the same CT volume."""

import random

import dash_vtk
from dash import Input, Output, callback
from dash_vtk.utils import to_volume_state
from vtkmodules.vtkIOXML import vtkXMLImageDataReader

from .common import DATA, View, field, section, skip_mount, slider, tips, view_id

SLUG = "slices"
TITLE = "Slice explorer"
GROUP = "Volumes"
KICKER = "Orthogonal planes with window and level"
ABOUT = ("The full-resolution head CT is sent once and shared by three slice representations, so moving "
         "a plane or changing window and level only sends a few numbers.")

_reader = vtkXMLImageDataReader()
_reader.SetFileName(str(DATA / "head.vti"))
_reader.Update()
VOLUME_STATE = to_volume_state(_reader.GetOutput())
NI, NJ, NK = _reader.GetOutput().GetDimensions()
LEVEL, WINDOW = 1000, 4095


def _slice(axis, index):
    return dash_vtk.SliceRepresentation(id=f"slice-{axis}", property={"colorLevel": LEVEL, "colorWindow": WINDOW},
                                        children=dash_vtk.ShareDataSet(), **{f"{axis}Slice": index})


def view():
    return View(SLUG, cameraPosition=[1, 0.35, -0.25], cameraViewUp=[0, 0, -1], children=[
        dash_vtk.ShareDataSet(dash_vtk.Volume(state=VOLUME_STATE)),
        _slice("i", NI // 2), _slice("j", NJ // 2), _slice("k", NK // 2),
    ])


def controls():
    return [
        section(
            "Planes",
            field("Sagittal", slider("slice-i-index", 0, NI - 1, NI // 2), hint="i"),
            field("Coronal", slider("slice-j-index", 0, NJ - 1, NJ // 2), hint="j"),
            field("Axial", slider("slice-k-index", 0, NK - 1, NK // 2), hint="k"),
        ),
        section(
            "Contrast",
            field("Level", slider("slice-level", 0, 4095, LEVEL, step=5)),
            field("Window", slider("slice-window", 1, 4095, WINDOW, step=5)),
        ),
        section("Try", tips("Level 1200, window 600 isolates bone")),
    ]


def stats():
    return [("Voxels", f"{NI} × {NJ} × {NK}"), ("Planes", "3, one shared dataset"), ("Source", "head.vti")]


@callback(
    Output(view_id(SLUG), "triggerRender"),
    Output("slice-i", "iSlice"),
    Output("slice-j", "jSlice"),
    Output("slice-k", "kSlice"),
    Output("slice-i", "property"),
    Output("slice-j", "property"),
    Output("slice-k", "property"),
    Input("slice-i-index", "value"),
    Input("slice-j-index", "value"),
    Input("slice-k-index", "value"),
    Input("slice-level", "value"),
    Input("slice-window", "value"),
    prevent_initial_call=True,
)
def update_slices(i, j, k, level, window):
    skip_mount()
    prop = {"colorLevel": level, "colorWindow": window}
    return random.random(), i, j, k, prop, prop, prop
