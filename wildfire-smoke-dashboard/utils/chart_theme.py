"""Plotly template for the Time Series and Exposure & Health charts (slate / charcoal-blue chrome).

Built on DMC's `mantine_light` and registered on import as CHART_TEMPLATE. The map
keeps `mantine_light` itself (see the MAP_* constants in config.py).
"""

import copy

import dash_mantine_components as dmc
import plotly.io as pio

from config import TS_COLORS
from theme import FONT_FAMILY, SLATE

CHART_TEMPLATE = "wildfire"

if "mantine_light" not in pio.templates:
    dmc.add_figure_templates()

_template = copy.deepcopy(pio.templates["mantine_light"])
_axis = {"gridcolor": SLATE[1], "linecolor": SLATE[3], "zerolinecolor": SLATE[2]}
_template.layout.update(
    font={"family": FONT_FAMILY, "color": SLATE[8]},
    colorway=TS_COLORS,
    xaxis=_axis,
    yaxis=_axis,
    hoverlabel={"bgcolor": "white", "bordercolor": SLATE[3], "font": {"family": FONT_FAMILY, "color": SLATE[9]}},
)
pio.templates[CHART_TEMPLATE] = _template
