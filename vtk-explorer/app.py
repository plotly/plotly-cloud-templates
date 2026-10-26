"""
VTK Explorer

A gallery of seven interactive 3D scenes built with dash-vtk: procedural geometry, a terrain mesh,
a lidar point cloud, synthetic and CT volumes, orthogonal slices and CFD streamlines. Pick a scene
on the left, drive it from the inspector on the right; everything renders in the browser with vtk.js.
"""

import dash
import dash_mantine_components as dmc
from dash import ALL, Input, Output, callback, clientside_callback, dcc, html
from dash._hooks import HooksManager
from dash_iconify import DashIconify

from demos import BY_SLUG, DEMOS

FONTS = ("https://fonts.googleapis.com/css2?family=Syne:wght@500;600;700;800"
         "&family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600&family=DM+Mono:wght@400;500&display=swap")

# Acid lime on violet-black, kept in sync with assets/style.css
THEME = {
    "fontFamily": "'DM Sans', system-ui, sans-serif",
    "fontFamilyMonospace": "'DM Mono', ui-monospace, monospace",
    "headings": {"fontFamily": "Syne, 'DM Sans', sans-serif"},
    "primaryColor": "acid",
    "primaryShade": 4,
    "autoContrast": True,
    "defaultRadius": "sm",
    "colors": {
        "acid": ["#f8ffe6", "#effdc9", "#e2fb9f", "#d5f97a", "#c8f560",
                 "#b3e046", "#97c22f", "#779a22", "#58731a", "#3b4e12"],
        "dark": ["#ecebf2", "#c9c7d6", "#a9a6b8", "#6f6c80", "#3a3746",
                 "#2a2734", "#1f1d28", "#15131c", "#100e16", "#0c0b10"],
    },
}

# Skip installed Dash plugins (such as the Plotly Studio Embedded chat) so the
# explorer renders on its own. Dash loads them once per process, on first app init
HooksManager._registered = True

app = dash.Dash(__name__, title="VTK Explorer", suppress_callback_exceptions=True, compress=True,
                external_stylesheets=[FONTS])
server = app.server


def nav_item(n, demo):
    return dcc.Link(
        [
            html.Span(f"{n:02d}", className="nav-index"),
            html.Img(src=app.get_asset_url(f"thumbs/{demo.SLUG}.webp"), className="nav-thumb", alt=""),
            html.Span([html.Span(demo.TITLE, className="nav-title"), html.Span(demo.KICKER, className="nav-kicker")],
                      className="nav-text"),
        ],
        id={"type": "nav", "slug": demo.SLUG},
        href=dash.get_relative_path(f"/{demo.SLUG}"),
        className="nav-item",
    )


def nav():
    items, group = [], None
    for n, demo in enumerate(DEMOS, 1):
        if demo.GROUP != group:
            group = demo.GROUP
            items.append(html.Div(group, className="nav-group"))
        items.append(nav_item(n, demo))
    return html.Nav(items, className="rail")


header = html.Header(
    [
        html.Div(
            [
                html.Div([html.Span(className="mark-cube"), "VTK", html.Em("Explorer")], className="wordmark"),
                html.Span("3D scientific visualization in Dash", className="tagline"),
            ],
            className="brand",
        ),
        html.Div(
            [
                html.A([DashIconify(icon="tabler:book-2", width=16), "dash-vtk docs"],
                       href="https://dash.plotly.com/vtk", target="_blank", className="header-link"),
                html.A([DashIconify(icon="tabler:brand-github", width=16), "Source"],
                       href="https://github.com/plotly/dash-vtk", target="_blank", className="header-link"),
                html.A(html.Img(src=app.get_asset_url("dash-logo.png"), alt="Plotly"),
                       href="https://plotly.com/dash/", target="_blank", className="logo-chip"),
            ],
            className="header-actions",
        ),
    ],
    className="topbar",
)

stage = html.Main(
    [
        html.Div(
            [
                html.Div(id="viewport", className="viewport"),
                html.Div(id="scene-tag", className="scene-tag"),
            ],
            className="frame",
        ),
        html.Div(
            [
                html.Div(id="readout", className="readout-stats"),
                html.Div(
                    [
                        html.Span([html.Kbd("drag"), " orbit"]),
                        html.Span([html.Kbd("scroll"), " zoom"]),
                        html.Span([html.Kbd("shift"), "+", html.Kbd("drag"), " pan"]),
                    ],
                    className="readout-keys",
                ),
                dmc.Button("Reset camera", id="reset-camera", size="compact-xs", variant="outline",
                           leftSection=DashIconify(icon="tabler:focus-centered", width=14)),
            ],
            className="readout",
        ),
    ],
    className="stage",
)

app.layout = dmc.MantineProvider(
    theme=THEME,
    forceColorScheme="dark",
    children=html.Div(
        [
            dcc.Location(id="url"),
            header,
            html.Div([nav(), stage, html.Aside(id="inspector", className="inspector")], className="workspace"),
        ],
        className="shell",
    ),
)


def inspector(n, demo):
    return [
        html.Div(
            [
                html.Div([html.Span(f"{n:02d} / {len(DEMOS):02d}"), html.Span(demo.GROUP)], className="insp-meta"),
                html.H2(demo.TITLE, className="insp-title"),
                html.P(demo.ABOUT, className="insp-about"),
            ],
            className="insp-head",
        ),
        *demo.controls(),
    ]


@callback(
    Output("viewport", "children"),
    Output("inspector", "children"),
    Output("readout", "children"),
    Output("scene-tag", "children"),
    Output({"type": "nav", "slug": ALL}, "className"),
    Input("url", "pathname"),
)
def show_demo(pathname):
    slug = dash.strip_relative_path(pathname or "/")
    demo = BY_SLUG.get(slug, DEMOS[0])
    n = DEMOS.index(demo) + 1
    readout = [html.Span([html.Small(k), v], className="stat") for k, v in demo.stats()]
    nav_classes = ["nav-item active" if d is demo else "nav-item" for d in DEMOS]
    return demo.view(), inspector(n, demo), readout, f"{n:02d} · {demo.TITLE}", nav_classes


# Fit the camera once the freshly mounted view has its size and data (again a beat later for heavy
# meshes), and whenever Reset camera is pressed
clientside_callback(
    """
    (children, nClicks) => {
        const context = dash_clientside.callback_context;
        const outputs = context.outputs_list;
        if (context.triggered.some(t => t.prop_id === "viewport.children")) {
            [1200, 3000].forEach(delay => setTimeout(() => outputs.forEach(
                o => dash_clientside.set_props(o.id, {triggerResetCamera: Date.now()})), delay));
        }
        return new Promise(resolve => setTimeout(() => resolve(outputs.map(() => Date.now())), 300));
    }
    """,
    Output({"type": "vtk-view", "demo": ALL}, "triggerResetCamera"),
    Input("viewport", "children"),
    Input("reset-camera", "n_clicks"),
    prevent_initial_call=True,
)


if __name__ == "__main__":
    app.run(debug=True)
