"""Colors and fonts used by the figures.

Keep these in sync with assets/style.css.
"""

FONT = "Barlow, system-ui, sans-serif"
HEADING_FONT = "'Barlow Condensed', Barlow, system-ui, sans-serif"

SURFACE = "#FFFFFF"
TEXT = "#1B2A41"  # navy ink
MUTED = "#6E6658"
GRID = "#EEE7DB"
NEUTRAL = "#D3CABB"  # warm gray for the groups not in focus
ACCENT = "#E8590C"  # basketball orange

# Categorical slots, assigned in this fixed order. Positions use the first five,
# player groups use up to all eight, with a marker symbol per slot as secondary
# encoding on scatter plots.
CATEGORICAL = [
    "#EB6834",
    "#2A78D6",
    "#1BAF7A",
    "#EDA100",
    "#6250D6",
    "#E87BA4",
    "#008300",
    "#E34948",
]
SYMBOLS = [
    "circle",
    "square",
    "diamond",
    "triangle-up",
    "x",
    "cross",
    "triangle-down",
    "star",
]

BASE_LAYOUT = dict(
    font=dict(family=FONT, size=13, color=TEXT),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    hoverlabel=dict(
        bgcolor=SURFACE, bordercolor=GRID, font=dict(family=FONT, color=TEXT)
    ),
    margin=dict(l=8, r=8, t=8, b=8),
)
