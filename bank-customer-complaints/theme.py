"""Colors and fonts used by the figures.

Keep these in sync with assets/style.css.
"""

FONT = "Inter, system-ui, sans-serif"

SURFACE = "#FFFFFF"
TEXT = "#1F2328"
MUTED = "#6B6F76"
GRID = "#ECEAE4"
NEUTRAL = "#C9C7C0"
ACCENT = "#2A78D6"

# Categorical slots, assigned in this fixed order. The two compared companies
# use the first two; the five LDA topics use the first five, with a marker
# symbol per topic as secondary encoding.
CATEGORICAL = ["#2A78D6", "#EB6834", "#1BAF7A", "#EDA100", "#E87BA4"]
TOPIC_SYMBOLS = ["circle", "square", "diamond", "triangle-up", "x"]

# Single-hue blue ramp (light -> dark) for magnitude
BLUE_RAMP = ["#B7D3F6", "#86B6EF", "#5598E7", "#2A78D6", "#1C5CAB", "#104281"]

BASE_LAYOUT = dict(
    font=dict(family=FONT, size=12, color=TEXT),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    hoverlabel=dict(
        bgcolor=SURFACE, bordercolor=GRID, font=dict(family=FONT, color=TEXT)
    ),
    margin=dict(l=8, r=8, t=8, b=8),
)
