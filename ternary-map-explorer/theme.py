"""Colors and fonts used by the figures.

Keep these in sync with assets/theme.js (DDK theme) and assets/style.css.
"""

FONT = "Inter, system-ui, sans-serif"

SURFACE = "#FFFFFF"
TEXT = "#1F2328"
MUTED = "#6B6F76"
GRID = "#E7E5E0"
ACCENT = "#2A78D6"

# Formation colors. Three categorical slots validated for colorblind
# separation as a scatter (all pairs); every smaller formation folds into a
# neutral "Other" so the map and ternary never need a fourth hue.
FORMATION_COLORS = {
    "Ohio Shale": "#2A78D6",
    "Corniferous": "#EB6834",
    "Clinton Shale": "#1BAF7A",
}
OTHER_FORMATIONS = "Other formations"
OTHER_COLOR = "#8A8984"
FORMATION_GROUPS = [*FORMATION_COLORS, OTHER_FORMATIONS]


def formation_color(group):
    return FORMATION_COLORS.get(group, OTHER_COLOR)


# Light neutral tints for the ternary rock-type regions, one per region family,
# so the well markers stay the loudest thing on the diagram.
ROCK_TYPE_FILLS = ["#ECEAE4", "#F3F1EC", "#E4E1D9", "#F8F7F3"]

BASE_LAYOUT = dict(
    font=dict(family=FONT, size=12, color=TEXT),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    hoverlabel=dict(
        bgcolor=SURFACE, bordercolor=GRID, font=dict(family=FONT, color=TEXT)
    ),
    margin=dict(l=8, r=8, t=8, b=8),
)
