import dash
from dash import dcc, html, Input, Output, callback, clientside_callback
import dash_mantine_components as dmc

from pages import cross_section, downhole_logs, comparison, explorer, block_model
from utils import create_header, create_nav_sidebar, NAV_ITEMS
import callbacks.cross_section  # noqa: F401 — registers callbacks
import callbacks.downhole       # noqa: F401
import callbacks.comparison     # noqa: F401
import callbacks.block_model   # noqa: F401
# Explorer page is fully driven by assets/explorer.js — no Python callbacks.

app = dash.Dash(
    __name__,
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
    external_stylesheets=dmc.styles.ALL,
    suppress_callback_exceptions=True,
)
app.title = "Drillhole Visualizer — WA Au-Cu Porphyry"
server = app.server

app.layout = dmc.MantineProvider(
    id="mantine-provider",
    forceColorScheme="light",
    children=[
        dcc.Location(id="url", refresh=False),
        dcc.Store(id="measure-store"),
        dmc.AppShell(
            [
                dmc.AppShellHeader(create_header(), withBorder=True),
                dmc.AppShellMain(
                    html.Div(
                        [
                            create_nav_sidebar(),
                            dmc.Container(id="page-content", fluid=True, p="md", className="main-content"),
                        ],
                        className="main-layout",
                    ),
                ),
            ],
            header={"height": 60},
            padding=0,
        ),
    ],
)

clientside_callback(
    """
    function(n_clicks) {
        if (n_clicks === undefined || n_clicks === null) {
            var nu = window.dash_clientside.no_update;
            return [nu, nu, nu, nu, nu, nu, nu, nu];
        }
        var collapsed = (n_clicks % 2) !== 0;
        if (collapsed) {
            return [
                "filter-sidebar collapsed",
                "pad-0 justify-center",
                "basil:caret-right-solid",
                {"display": "none"},
                null,
                {"display": "none"},
                {"display": "none"},
                {"display": "none"}
            ];
        }
        return [
            "filter-sidebar",
            "title-pad space-between",
            "charm:cross",
            null,
            {"display": "none"},
            null,
            null,
            null
        ];
    }
    """,
    Output("filter-sidebar", "className"),
    Output("sidebar-title-div", "className"),
    Output("sidebar-btn-icon", "icon"),
    Output("sidebar-title", "style"),
    Output("sidebar-collapsed-title-div", "style"),
    Output("sidebar-outer-div", "style"),
    Output("sidebar-inner-div", "style"),
    Output("sidebar-btn-div", "style"),
    Input("sidebar-btn", "n_clicks"),
)


@callback(Output("page-content", "children"), Input("url", "pathname"))
def display_page(pathname):
    if pathname == "/downhole-logs":
        return downhole_logs.layout()
    elif pathname == "/comparison":
        return comparison.layout()
    elif pathname == "/explorer":
        return explorer.layout()
    elif pathname == "/block-model":
        return block_model.layout()
    else:
        return cross_section.layout()


@callback(
    [Output(item["id"], "active") for item in NAV_ITEMS],
    Input("url", "pathname"),
)
def update_nav_active(pathname):
    path = pathname or "/"
    return [item["href"] == path for item in NAV_ITEMS]


if __name__ == "__main__":
    app.run(debug=True, port=8051)

