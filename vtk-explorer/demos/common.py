"""Shared building blocks for the demos: the 3D view, inspector sections and color presets."""

from pathlib import Path

import dash_mantine_components as dmc
import dash_vtk
from dash import ctx, html
from dash.exceptions import PreventUpdate
from dash_vtk.utils import presets

DATA = Path(__file__).resolve().parent.parent / "data"

# Viewport background, kept in sync with --viewport in assets/style.css
BACKGROUND = [0.035, 0.031, 0.047]

# A short list of presets that read well on the dark viewport, followed by the full catalogue
FAVOURITE_PRESETS = ["Inferno (matplotlib)", "Viridis (matplotlib)", "Plasma (matplotlib)",
                     "Cool to Warm", "erdc_rainbow_bright", "erdc_blue2green_muted", "Turbo"]
PRESET_DATA = [
    {"group": "Favourites", "items": [p for p in FAVOURITE_PRESETS if p in presets]},
    {"group": "All presets", "items": sorted(set(presets) - set(FAVOURITE_PRESETS), key=str.lower)},
]


def skip_mount():
    """Controls arrive together with their view, which already reflects their defaults. Dash still fires
    the control callback with every input marked as changed, so skip that call; real edits change one."""
    if len(ctx.triggered) > 1:
        raise PreventUpdate


def view_id(slug):
    return {"type": "vtk-view", "demo": slug}


def View(slug, children, **kwargs):
    return dash_vtk.View(id=view_id(slug), background=BACKGROUND, children=children,
                         style={"width": "100%", "height": "100%"}, **kwargs)


def section(label, *children):
    return html.Section([html.H3(label, className="section-label"), *children], className="section")


def field(label, control, hint=None):
    return html.Div(
        [html.Div([html.Span(label), hint and html.Span(hint, className="field-hint")], className="field-label"),
         control],
        className="field",
    )


def slider(id, min, max, value, step=1, marks=None):
    marks = marks or [{"value": min, "label": f"{min:g}"}, {"value": max, "label": f"{max:g}"}]
    return dmc.Slider(id=id, min=min, max=max, step=step, value=value, marks=marks,
                      updatemode="mouseup", size="sm", mb="md")


def preset_select(id, value):
    return dmc.Select(id=id, data=PRESET_DATA, value=value, searchable=True, allowDeselect=False,
                      size="xs", comboboxProps={"withinPortal": True})


def tips(*lines):
    return html.Ul([html.Li(line) for line in lines], className="hints")
