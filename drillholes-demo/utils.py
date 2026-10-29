import pathlib
from functools import lru_cache
import numpy as np
import pandas as pd
from dash import html
import dash_mantine_components as dmc
from dash_iconify import DashIconify

PATH = pathlib.Path(__file__).parent
DATA_PATH = PATH / "data"

LITH_COLORS = {
    "Alluvium":              "#C2B280",
    "Weathered Granite":     "#D4A574",
    "Granite":               "#9E8B6B",
    "Quartz Diorite":        "#8B7355",
    "Mineralized Porphyry":  "#A0522D",
    "Fresh Granite":         "#6B5B45",
}

LITH_ORDER = list(LITH_COLORS.keys())

CHART_LAYOUT = dict(
    paper_bgcolor="#ffffff",
    plot_bgcolor="#f8f9fa",
    font=dict(family="Inter, sans-serif", size=12, color="#495057"),
    margin=dict(l=50, r=20, t=40, b=50),
)

# Keep alias so any external references still work
DARK_CHART_LAYOUT = CHART_LAYOUT

GRADE_COLORS = {
    "Au_ppm": "#FFD700",
    "Cu_pct": "#FF8C00",
    "Ag_ppm": "#C0C0C0",
}

GRADE_LABELS = {
    "Au_ppm": "Au (g/t)",
    "Cu_pct": "Cu (%)",
    "Ag_ppm": "Ag (ppm)",
}


@lru_cache(maxsize=1)
def load_data():
    collar = pd.read_csv(DATA_PATH / "collar.csv")
    assay  = pd.read_csv(DATA_PATH / "assay.csv")
    lith   = pd.read_csv(DATA_PATH / "lith.csv")
    survey = pd.read_csv(DATA_PATH / "survey.csv")
    return collar, assay, lith, survey


def compute_trace_easting_elevation(hole_id, collar_df, survey_df):
    """
    Minimum-curvature method: converts downhole survey (depth, az, dip)
    to (easting, elevation) pairs for cross-section plotting.
    """
    hole = collar_df[collar_df["HOLEID"] == hole_id].iloc[0]
    surveys = survey_df[survey_df["HOLEID"] == hole_id].sort_values("DEPTH").copy()

    e, z = float(hole["EAST"]), float(hole["ELEV"])
    east_list, elev_list = [e], [z]

    prev_depth = 0.0
    prev_az  = np.radians(float(hole["AZ"]))
    prev_dip = np.radians(abs(float(hole["DIP"])))

    for _, svy in surveys.iterrows():
        dl = float(svy["DEPTH"]) - prev_depth
        if dl <= 0:
            continue
        az2  = np.radians(float(svy["AZ"]))
        dip2 = np.radians(abs(float(svy["DIP"])))

        dl_cos = (np.cos(dip2 - prev_dip)
                  - np.sin(prev_dip) * np.sin(dip2) * (1 - np.cos(az2 - prev_az)))
        rf = 2.0 / (1.0 + dl_cos) if abs(1.0 + dl_cos) > 0.001 else 1.0

        de = (dl / 2.0) * (np.sin(prev_dip) * np.sin(prev_az)
                            + np.sin(dip2) * np.sin(az2)) * rf
        dz = -(dl / 2.0) * (np.cos(prev_dip) + np.cos(dip2)) * rf

        e += de
        z += dz
        east_list.append(round(e, 2))
        elev_list.append(round(z, 2))

        prev_depth = float(svy["DEPTH"])
        prev_az, prev_dip = az2, dip2

    return east_list, elev_list


NAV_ITEMS = [
    {"label": "Cross-Section", "href": "/",               "icon": "tabler:chart-grid-dots", "id": "nav-cross-section"},
    {"label": "Explorer",      "href": "/explorer",       "icon": "tabler:compass",         "id": "nav-explorer"},
    {"label": "Downhole Logs", "href": "/downhole-logs",  "icon": "tabler:align-left",      "id": "nav-downhole"},
    {"label": "Comparison",    "href": "/comparison",     "icon": "tabler:columns-3",       "id": "nav-comparison"},
    {"label": "Block Model",   "href": "/block-model",    "icon": "tabler:cube",            "id": "nav-block-model"},
]


def create_header():
    brand = dmc.Group([
        html.Img(src="/assets/plotly-logo.png", height=40, alt="Plotly"),
        dmc.Divider(orientation="vertical", size="sm"),
        html.Div([
            html.P("Drillhole Visualizer", className="brand-title"),
            html.P("Western Australia", className="brand-subtitle"),
        ]),
    ], gap="sm", align="center", wrap="nowrap")

    status = dmc.Group([
        dmc.Group([
            DashIconify(icon="tabler:circle-filled", width=10, color="#40c057"),
            dmc.Text("Active", size="xs", c="dimmed"),
        ], gap=4),
        dmc.Divider(orientation="vertical", size="sm"),
        dmc.Text("Prospect", size="xs", c="dimmed"),
        dmc.Badge("WA Au-Cu Porphyry", color="orange", variant="light", size="sm"),
        dmc.Divider(orientation="vertical", size="sm"),
        dmc.Text("Last Survey", size="xs", c="dimmed"),
        dmc.Text("Apr 2026", size="xs", fw=500),
        dmc.ActionIcon(
            DashIconify(icon="tabler:bell", width=18),
            variant="subtle",
            color="gray",
            size="lg",
        ),
    ], gap="sm", wrap="nowrap")

    return dmc.Paper(
        dmc.Group([brand, status], justify="space-between", align="center"),
        px="md",
        py="sm",
        radius=0,
        withBorder=False,
        className="app-header",
    )


def create_nav_sidebar():
    nav_links = [
        dmc.NavLink(
            label=item["label"],
            leftSection=DashIconify(icon=item["icon"], width=16),
            href=item["href"],
            id=item["id"],
            variant="subtle",
        )
        for item in NAV_ITEMS
    ]

    return html.Div(
        [
            dmc.Group(
                [
                    dmc.Text("Navigation", id="sidebar-title", size="xs", fw=600, c="dimmed", tt="uppercase"),
                    dmc.ActionIcon(
                        DashIconify(icon="charm:cross", width=14, id="sidebar-btn-icon"),
                        id="sidebar-btn",
                        size="sm",
                        variant="subtle",
                        color="gray",
                    ),
                ],
                id="sidebar-title-div",
                justify="space-between",
                align="center",
                className="title-pad space-between",
            ),
            html.Div(
                [
                    dmc.Space(h="35vh"),
                    html.Div(
                        html.Div("▾   Navigation   ▾", className="sidebar-collapsed-title"),
                        style={"transform": "rotate(270deg)"},
                    ),
                ],
                id="sidebar-collapsed-title-div",
                style={"display": "none"},
            ),
            html.Div(
                html.Div(
                    html.Div(nav_links, id="sidebar-inner-div", className="sidebar-inner"),
                    id="sidebar-outer-div",
                    className="sidebar-outer",
                ),
                id="sidebar-btn-div",
            ),
        ],
        id="filter-sidebar",
        className="filter-sidebar flex-column",
    )


def kpi_card(title, value, unit="", icon=None):
    header_children = [
        dmc.Text(title, size="xs", c="dimmed", tt="uppercase", fw=600),
    ]
    if icon:
        header_children.append(DashIconify(icon=icon, width=16, color="#868e96"))

    return dmc.Paper([
        dmc.Group(header_children, justify="space-between", align="center"),
        dmc.Text(value, size="xl", fw=700, c="dark", mt=4),
        dmc.Text(unit, size="xs", c="dimmed") if unit else None,
    ], p="md", radius="md", withBorder=True, className="kpi-card")
