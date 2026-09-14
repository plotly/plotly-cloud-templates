import dash_mantine_components as dmc
from dash import html

import pages
from constants import MANTINE_THEME, NAVY, app

server = app.server

header = html.Div(
    dmc.Group(
        gap=14,
        style={"height": "100%"},
        children=[
            dmc.Text(
                "Lithium Supply Chain Tracker",
                c="white",
                fw=600,
                size="lg",
                style={"lineHeight": 1.2},
            ),
        ],
    ),
    className="app-header",
)



app.layout = dmc.MantineProvider(
    theme=MANTINE_THEME,
    children=[
        html.Meta(
            name="viewport",
            content="width=device-width, initial-scale=1, shrink-to-fit=no",
        ),
        html.Link(
            rel="stylesheet",
            href="https://fonts.googleapis.com/css?family=Poppins",
        ),
        html.Meta(name="theme-color", content=NAVY),
        header,
        html.Div(
            id="content",
            className="app-content",
            children=pages.supply_sankey.layout(),
        )
    ],
)


if __name__ == "__main__":
    app.run(debug=True,port=8060)
