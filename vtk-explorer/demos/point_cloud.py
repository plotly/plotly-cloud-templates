"""Lidar point cloud: buildings and trees scanned from the air, colored by elevation."""

import dash_mantine_components as dmc
import dash_vtk
import numpy as np
from dash import Input, Output, callback

from .common import DATA, View, field, preset_select, section, skip_mount, slider, tips, view_id

SLUG = "point-cloud"
TITLE = "Lidar point cloud"
GROUP = "Geometry"
KICKER = "Up to 250k points, colored by height"
ABOUT = ("An aerial lidar sweep over buildings and trees, randomly sampled from 3.4 million returns. Points are "
         "centred on the origin before they are sent, which keeps the GPU's single precision happy.")

_points = np.load(DATA / "lidar.npz")["points"].astype(np.float64)
POINTS = np.round(_points - _points.mean(axis=0), 2)
DENSITIES = {"50k": 50_000, "120k": 120_000, "250k": 250_000}


def _cloud(density, size, preset):
    pts = POINTS[:DENSITIES[density]]
    z = pts[:, 2]
    return dash_vtk.PointCloudRepresentation(
        xyz=pts.ravel(), scalars=z, colorMapPreset=preset,
        colorDataRange=[float(z.min()), float(z.max())], property={"pointSize": size},
    )


def view():
    return View(SLUG, [_cloud("120k", 2, "Inferno (matplotlib)")],
                cameraPosition=[0.4, -1, 0.9], cameraViewUp=[0, 0, 1])


def controls():
    return [
        section(
            "Sampling",
            field("Points", dmc.SegmentedControl(id="pc-density", data=list(DENSITIES), value="120k",
                                                 fullWidth=True, size="xs", mb="md")),
            field("Point size", slider("pc-size", 1, 6, 2)),
        ),
        section("Color", field("Elevation color map", preset_select("pc-preset", "Inferno (matplotlib)"))),
        section("Try", tips("Look along the street from ground level", "Use 50k on slower machines")),
    ]


def stats():
    span = POINTS.max(axis=0) - POINTS.min(axis=0)
    return [("Sampled", f"{len(POINTS):,} of 3.4M"), ("Extent", f"{span[0]:.0f} × {span[1]:.0f} m"),
            ("Relief", f"{span[2]:.1f} m")]


@callback(
    Output(view_id(SLUG), "children"),
    Input("pc-density", "value"),
    Input("pc-size", "value"),
    Input("pc-preset", "value"),
    prevent_initial_call=True,
)
def update_cloud(density, size, preset):
    skip_mount()
    return [_cloud(density, size, preset)]
