"""App header: one light row — logo and title on the left, underline nav tabs on the right."""

import dash_mantine_components as dmc
from dash import get_asset_url, html

from config import APP_TITLE

TABS = [
    ("map", "Map View"),
    ("timeseries", "Time Series"),
    ("about", "About the Data"),
]


def header() -> dmc.AppShellHeader:
    logo = html.Img(src=get_asset_url("Dash_Enterprise_Logo_Dark.svg"), alt="Dash Enterprise", height=22, style={"display": "block"})
    title = dmc.Title(APP_TITLE, order=1, fz=15, fw=600, lh=1, lts="-0.01em", style={"whiteSpace": "nowrap"})
    brand = dmc.Group([logo, dmc.Divider(orientation="vertical", h=22, color="gray.3"), title], gap="md", wrap="nowrap")
    tabs = dmc.Tabs(
        dmc.TabsList([dmc.TabsTab(label, value=value) for value, label in TABS]),
        id="main-tabs",
        value="map",
        color="charcoal",
        h="100%",
        classNames={"list": "nav-tabs-list", "tab": "nav-tab"},
    )
    return dmc.AppShellHeader(
        dmc.Group([brand, tabs], justify="space-between", wrap="nowrap", h="100%", px="md"),
        withBorder=True,
    )
