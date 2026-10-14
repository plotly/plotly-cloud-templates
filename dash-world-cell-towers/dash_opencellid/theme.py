"""
Colors and the Plotly figure template shared by the layout, the charts, and the
Datashader map rendering.
"""
import plotly.graph_objects as go

# Radio technologies in display order (newest first) and the color of each. The five
# colors were checked with a color vision deficiency validator on all pairs, since
# they are all shown together on the map; radio names are always shown next to the
# colors (bar labels, map legend, tooltips) so color is never the only cue.
RADIO_COLORS = {
    "NR": "#1baf7a",  # 5G
    "LTE": "#e34948",  # 4G
    "UMTS": "#008300",  # 3G
    "CDMA": "#eda100",
    "GSM": "#2a78d6",  # 2G
}
RADIO_LABELS = {
    "NR": "5G NR",
    "LTE": "4G LTE",
    "UMTS": "3G UMTS",
    "CDMA": "CDMA",
    "GSM": "2G GSM",
}
RADIO_CATEGORIES = list(RADIO_COLORS)

# Chart ink and neutral bar colors
TEXT = "#212529"
TEXT_MUTED = "#868e96"
GRID = "#e9ecef"
BAR_TOTAL = "#e9ecef"  # all towers, drawn underneath the selection
BAR_SELECTED = "#495057"  # towers in the current selection
BAR_UNSELECTED = "#adb5bd"  # bars outside a histogram's own selection

FONT_FAMILY = "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"

TEMPLATE = go.layout.Template(
    layout=go.Layout(
        font={"family": FONT_FAMILY, "color": TEXT, "size": 12},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin={"l": 8, "r": 8, "t": 8, "b": 8},
        hoverlabel={
            "bgcolor": "white",
            "bordercolor": GRID,
            "font": {"family": FONT_FAMILY, "color": TEXT, "size": 12},
        },
        xaxis={
            "gridcolor": GRID,
            "zeroline": False,
            "linecolor": GRID,
            "tickfont": {"color": TEXT_MUTED},
            "title": {"font": {"color": TEXT_MUTED}},
            "automargin": True,
        },
        yaxis={
            "gridcolor": GRID,
            "zeroline": False,
            "linecolor": GRID,
            "tickfont": {"color": TEXT_MUTED},
            "title": {"font": {"color": TEXT_MUTED}},
            "automargin": True,
        },
    )
)
