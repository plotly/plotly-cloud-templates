"""Tab switching — panels stay mounted (map keeps its zoom), only visibility changes.

The sidebar is tab-aware: SECTION_TABS decides which sections each tab shows, the
navbar collapses entirely on tabs without controls, and DARK_SIDEBAR_TABS switch it
to the dark treatment.
"""

from dash import Input, Output, callback

from components.sidebar import SECTION_TABS, TABS_WITH_SIDEBAR, section_style, sidebar_class
from config import SIDEBAR_WIDTH

PANELS = ["map", "timeseries", "about"]


@callback(
    output=dict(
        panels=[Output(f"panel-{p}", "style") for p in PANELS],
        sections=[Output(s, "style") for s in SECTION_TABS],
        navbar=Output("appshell", "navbar"),
        sidebar_class=Output("sidebar", "className"),
    ),
    inputs=dict(tab=Input("main-tabs", "value")),
)
def switch_tab(tab: str) -> dict:
    """Show the active tab's panel and its sidebar sections."""
    return {
        "panels": [{"display": "block" if tab == p else "none"} for p in PANELS],
        "sections": [section_style(s, tab) for s in SECTION_TABS],
        "navbar": {
            "width": SIDEBAR_WIDTH,
            "breakpoint": "sm",
            "collapsed": {"mobile": True, "desktop": tab not in TABS_WITH_SIDEBAR},
        },
        "sidebar_class": sidebar_class(tab),
    }
