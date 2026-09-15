import os

import dash


app = dash.Dash(
    __name__,
    suppress_callback_exceptions=True,
    external_stylesheets=[
        "assets/styles.css",
        "assets/media_queries.css",
    ],
)

app.title = "Lithium Supply Chain Tracker"

# Dash always renders a favicon <link> (falling back to its own default
# icon when assets/favicon.ico is absent), so the only way to have none
# at all is to drop the {%favicon%} placeholder from the index template.
app.index_string = """<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%css%}
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>"""


DEFAULT_SANKEY_NODES = [
    "Resource Country",
    "Product",
]

# Brand color ramp (light -> dark) used as the Mantine primary color
# (drives buttons and other primary-colored controls).
BRAND_COLOR = [
    "#eef6fd",
    "#dcedfb",
    "#c3e0f7",
    "#a0cdf0",
    "#7ab9e8",
    "#56a5df",
    "#3a92d4",
    "#2778b8",
    "#1a6099",
    "#0f4a7a",
]
NAVY = "#155d90"
PAGE_BACKGROUND = "#fbfaf8"
CARD_BORDER = "#e7e3dd"

MANTINE_THEME = {
    "fontFamily": "'Poppins', sans-serif",
    "headings": {"fontFamily": "'Poppins', sans-serif", "fontWeight": 600},
    "primaryColor": "brand",
    "defaultRadius": "md",
    "colors": {"brand": BRAND_COLOR},
    "black": "#2f2821",
}
