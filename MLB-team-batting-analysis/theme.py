"""Colors and fonts used by the figures.

Keep these in sync with assets/style.css.
"""

FONT = "Inter, system-ui, sans-serif"

SURFACE = "#161A2E"
TEXT = "#E8EAF6"
MUTED = "#8A90B0"
GRID = "#262B45"
NEUTRAL = "#4A5070"

# Categorical slots, assigned in this fixed order within each chart
CATEGORICAL = ["#00E5FF", "#FF2E97", "#39FF88", "#FFD60A", "#B76EFF"]
# Lighter tints of the categorical slots, for the bars behind a rate line
TINTS = ["#0E4F63", "#6B1E4A", "#16613F", "#6B5A12", "#4C2D73"]

BASE_LAYOUT = dict(
    font=dict(family=FONT, size=12, color=TEXT),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    hoverlabel=dict(bgcolor=SURFACE, bordercolor=GRID, font=dict(family=FONT, color=TEXT)),
    hovermode="x unified",
    margin=dict(l=8, r=8, t=8, b=8),
    legend=dict(
        orientation="h", yanchor="bottom", y=1, xanchor="left", x=0, font=dict(size=11)
    ),
    xaxis=dict(gridcolor=GRID, zeroline=False, tickformat="d", automargin=True),
    yaxis=dict(gridcolor=GRID, zeroline=False, automargin=True, fixedrange=True),
)
