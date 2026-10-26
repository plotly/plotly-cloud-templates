"""Synthetic volume: scalar fields computed in NumPy and ray cast in the browser."""

import dash_mantine_components as dmc
import dash_vtk
import numpy as np
from dash import Input, Output, callback

from .common import View, field, preset_select, section, skip_mount, slider, tips, view_id

SLUG = "synthetic-volume"
TITLE = "Synthetic volume"
GROUP = "Volumes"
KICKER = "Math fields, ray cast on the GPU"
ABOUT = ("Each field is a 3D array evaluated in NumPy and streamed as a flat list of scalars. vtk.js "
         "ray casts it, and the floating editor in the corner reshapes the opacity transfer function.")

FIELDS = {
    "gyroid": "Gyroid",
    "shells": "Shells",
    "noise": "Noise",
}


def scalars(kind, n):
    t = np.linspace(-np.pi, np.pi, n)
    z, y, x = np.meshgrid(t, t, t, indexing="ij")  # x varies fastest, as VTK expects
    if kind == "gyroid":
        f = np.sin(2 * x) * np.cos(2 * y) + np.sin(2 * y) * np.cos(2 * z) + np.sin(2 * z) * np.cos(2 * x)
    elif kind == "shells":
        f = np.cos(3 * np.sqrt(x**2 + y**2 + z**2)) * np.exp(-(x**2 + y**2 + z**2) / 8)
    else:
        f = np.random.default_rng(42).random((n, n, n))
    f = (f - f.min()) / (f.max() - f.min())
    return np.round(f.ravel(), 3)


def _volume(kind, n, preset):
    return dash_vtk.VolumeDataRepresentation(
        dimensions=[n, n, n], spacing=[1, 1, 1], origin=[0, 0, 0],
        scalars=scalars(kind, n), colorMapPreset=preset, colorDataRange=[0, 1], rescaleColorMap=False,
    )


def view():
    return View(SLUG, [_volume("gyroid", 40, "erdc_rainbow_bright")])


def controls():
    return [
        section(
            "Field",
            dmc.SegmentedControl(id="synth-field", data=[{"label": v, "value": k} for k, v in FIELDS.items()],
                                 value="gyroid", fullWidth=True, size="xs", mb="md"),
            field("Resolution", slider("synth-res", 10, 64, 40, step=2), hint="voxels per side"),
            field("Color map", preset_select("synth-preset", "erdc_rainbow_bright")),
        ),
        section("Try", tips("Drag the opacity curve's points in the top-left editor",
                            "Shells at 64³ shows nested spheres")),
    ]


def stats():
    return [("Grid", "10³ – 64³ voxels"), ("Fields", "gyroid · shells · noise"), ("Renderer", "GPU ray cast")]


@callback(
    Output(view_id(SLUG), "children"),
    Input("synth-field", "value"),
    Input("synth-res", "value"),
    Input("synth-preset", "value"),
    prevent_initial_call=True,
)
def update_volume(kind, n, preset):
    skip_mount()
    return [_volume(kind, n, preset)]
