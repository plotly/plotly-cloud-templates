import dash
from dash import html, dcc, Input, Output, callback, ctx
import dash_mantine_components as dmc
from dash_iconify import DashIconify

from pages import cohort, imaging
from callbacks import (
    cohort    as cohort_callbacks,
    imaging   as imaging_callbacks,
    export_all as export_all_callbacks,
)

app = dash.Dash(
    __name__,
    backend="fastapi",
    suppress_callback_exceptions=True,
    external_stylesheets=dmc.styles.ALL,
    title="Medical Imaging Demo",
)
server = app.server


# ── Header ─────────────────────────────────────────────────────────────────────
# (label, href, nav_id, leftSection)
NAV_LINKS = [
    ("Imaging Workstation", "/imaging", "nav-imaging",
     DashIconify(icon="tabler:x-ray", width=15)),
    ("Cohort Explorer", "/cohort", "nav-cohort", None),
]

_NAV_BTN_STYLES = {
    "root": {
        "paddingLeft": 14, "paddingRight": 18,
        "fontWeight": 500, "height": 34,
        "fontSize": "13px",
    },
}



def create_header():
    brand = dmc.Group([
        html.Img(src="/assets/DE-logo.png", height=36,
                 style={"opacity": "0.92"}),
        html.Div(style={
            "width": "1px", "height": "20px",
            "backgroundColor": "#d1d5db",
            "flexShrink": 0,
        }),
        dmc.Title("Medical Imaging Demo", order=3,
                   style={"color": "#1e2433", "letterSpacing": "-0.5px",
                          "fontSize": "16px", "fontWeight": 600}),
    ], gap=10, wrap="nowrap", align="center")

    nav_center = dmc.Group([
        dcc.Link(
            dmc.Button(
                label,
                id=nav_id,
                leftSection=left,
                variant="subtle",
                color="navy",
                size="sm",
                radius="md",
                styles=_NAV_BTN_STYLES,
            ),
            href=href,
            style={"textDecoration": "none"},
        )
        for label, href, nav_id, left in NAV_LINKS
    ], gap=4, wrap="nowrap")

    actions = dmc.Group([
        html.Div(
            dmc.Group([
                DashIconify(icon="tabler:building-hospital", width=12,
                            color="#6b7280"),
                dmc.Text("General Hospital", size="xs", fw=500,
                         style={"color": "#6b7280", "letterSpacing": "0.01em"}),
                html.Div(style={
                    "width": "3px", "height": "3px",
                    "borderRadius": "50%",
                    "backgroundColor": "#c2c6cc",
                    "flexShrink": 0,
                }),
                dmc.Text("325 beds", size="xs",
                         style={"color": "#6b7280"}),
                html.Div(style={
                    "width": "3px", "height": "3px",
                    "borderRadius": "50%",
                    "backgroundColor": "#c2c6cc",
                    "flexShrink": 0,
                }),
                dmc.Text("ICU 25", size="xs", fw=600,
                         style={"color": "#1e3a8a"}),
            ], gap=6, wrap="nowrap"),
            style={
                "display": "flex", "alignItems": "center",
                "padding": "4px 12px",
                "borderRadius": "20px",
                "backgroundColor": "#eef0f2",
                "border": "1px solid #e1e3e7",
            },
        ),
        dmc.Tooltip(
            label="Hide toolbar", withArrow=True,
            children=dmc.ActionIcon(
                DashIconify(icon="tabler:layout-navbar-collapse", width=18),
                id="header-collapse-btn", variant="subtle", color="navy",
                size="lg",
            ),
        ),
    ], gap="sm", wrap="nowrap", justify="flex-end")

    # Three-column grid: brand | nav (centered) | actions
    return html.Div(
        [brand, nav_center, actions],
        style={
            "display": "grid",
            "gridTemplateColumns": "1fr auto 1fr",
            "alignItems": "center",
            "height": "100%",
            "padding": "0 24px",
            "backgroundColor": "#fcfcfb",
            "borderBottom": "1px solid #e1e3e7",
        },
    )


# Floating button (overlays the page) to restore the header once collapsed.
_EXPAND_STYLE = {"position": "fixed", "top": "10px", "right": "14px",
                 "zIndex": 3000, "display": "none"}


# ── App layout ─────────────────────────────────────────────────────────────────
app.layout = dmc.MantineProvider(
    id="mantine-provider",
    forceColorScheme="light",
    theme={
        "primaryColor": "cyan",
        # Register the imaging "navy" ramp app-wide so the shared header's
        # navy-colored controls resolve (cohort accents stay on cyan).
        "colors": {"navy": imaging.NAVY_RAMP},
        "fontFamily": "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
    },
    children=[
        dcc.Location(id="url", refresh=False),
        dcc.Download(id="download-pdf-all"),
        html.Div(id="pdf-status-all", style={"display": "none"}),
        dmc.AppShell(
            [
                dmc.AppShellHeader(create_header()),
                dmc.AppShellMain(
                    html.Div(id="page-content", style={"width": "100%"}),
                ),
            ],
            id="app-shell",
            header={"height": 64},
            padding=0,
        ),
        dmc.Tooltip(
            label="Show toolbar", withArrow=True,
            children=dmc.ActionIcon(
                DashIconify(icon="tabler:layout-navbar-expand", width=18),
                id="header-expand-btn", variant="filled", color="navy",
                size="lg", style=_EXPAND_STYLE,
            ),
        ),
    ]
)


# ── Routing ────────────────────────────────────────────────────────────────────
@callback(
    Output("page-content", "children"),
    Input("url", "pathname"),
)
def display_page(pathname):
    # Imaging Workstation is the landing page ("/" and "/imaging").
    if pathname == "/cohort":
        return cohort.layout
    return imaging.layout


@callback(
    [Output(nav_id, "variant") for _, _, nav_id, _ in NAV_LINKS],
    Input("url", "pathname"),
)
def update_nav_active(pathname):
    hrefs = [href for _, href, _, _ in NAV_LINKS]
    active = pathname if pathname in hrefs else "/imaging"
    return ["filled" if active == h else "subtle" for h in hrefs]


@callback(
    Output("app-shell", "header"),
    Output("header-expand-btn", "style"),
    Input("header-collapse-btn", "n_clicks"),
    Input("header-expand-btn", "n_clicks"),
    prevent_initial_call=True,
)
def toggle_header(_collapse, _expand):
    collapsed = ctx.triggered_id == "header-collapse-btn"
    return ({"height": 64, "collapsed": collapsed},
            {**_EXPAND_STYLE, "display": "flex" if collapsed else "none"})


if __name__ == "__main__":
    app.run(debug=True, port=8051)
