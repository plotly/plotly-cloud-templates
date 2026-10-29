"""Volume rendering: a CT scan of a head with vtk.js's built-in transfer function editor."""

import dash_vtk
from dash_vtk.utils import to_volume_state
from vtkmodules.vtkImagingCore import vtkImageShrink3D
from vtkmodules.vtkIOXML import vtkXMLImageDataReader

from .common import DATA, View, section, tips

SLUG = "volume-rendering"
TITLE = "CT volume"
GROUP = "Volumes"
KICKER = "Medical scan with a live transfer function"
ABOUT = ("A head CT read with VTK on the server and handed to vtk.js as an image volume. It is shrunk "
         "2× in-plane for a lighter download; use the slice explorer for full resolution.")

_reader = vtkXMLImageDataReader()
_reader.SetFileName(str(DATA / "head.vti"))
_shrink = vtkImageShrink3D()
_shrink.SetInputConnection(_reader.GetOutputPort())
_shrink.SetShrinkFactors(2, 2, 1)
_shrink.AveragingOn()
_shrink.Update()
_image = _shrink.GetOutput()
VOLUME_STATE = to_volume_state(_image)


def view():
    return View(SLUG, cameraPosition=[0.25, 1, -0.1], cameraViewUp=[0, 0, -1], children=[
        dash_vtk.VolumeRepresentation([dash_vtk.VolumeController(), dash_vtk.Volume(state=VOLUME_STATE)])
    ])


def controls():
    return [
        section("Transfer function", tips(
            "The editor floats over the top-left of the view",
            "Drag the green handles to change which densities are opaque",
            "Pick a color map from the editor's dropdown",
            "Toggle shadows for depth cues",
        )),
    ]


def stats():
    x, y, z = _image.GetDimensions()
    lo, hi = _image.GetScalarRange()
    return [("Voxels", f"{x} × {y} × {z}"), ("Intensity", f"{lo:,.0f} – {hi:,.0f}"), ("Source", "head.vti")]
