"""
Interactive Image Segmentation

Draw a few marks on the image, one color per kind of region, and a random
forest trained on the marked pixels classifies the rest of the image. Add more
marks where it gets things wrong and the segmentation updates. The trained
classifier can be downloaded and applied to other images with
use_ml_image_segmentation_classifier.py.

Many thanks to Emmanuelle Gouillart for the image classifier training code.
"""

import json
import re
from functools import lru_cache

import dash
import dash_mantine_components as dmc
import numpy as np
import PIL.Image
import plotly.graph_objects as go
from dash import ALL, Input, Output, Patch, State, ctx, dcc, html
from dash.exceptions import PreventUpdate
from dash_iconify import DashIconify

import segmentation

IMAGE_PATH = "assets/segmentation_img.jpg"
IMG = np.array(PIL.Image.open(IMAGE_PATH).convert("RGB"))
IMG_HEIGHT, IMG_WIDTH = IMG.shape[:2]

# Okabe-Ito colors, distinguishable with common forms of color blindness
CLASS_COLORS = ["#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2"]
DEFAULT_CLASS = 0
DEFAULT_BRUSH = 3  # log2 of the line width, so 2^3 = 8 px
DEFAULT_FEATURES = ["intensity", "edges"]
DEFAULT_SIGMAS = [0.5, 16]

# Magenta accent borrowed from the H&E stain of the sample image
STAIN = ["#FFE9F3", "#FCD3E3", "#F4A6C4", "#ED76A3", "#E74E88",
         "#E43577", "#E3276E", "#CA1B5D", "#B51352", "#9F0446"]
MUTED = "#8A8F98"
THEME = {
    "fontFamily": "Inter, system-ui, sans-serif",
    "fontFamilyMonospace": "'IBM Plex Mono', ui-monospace, monospace",
    "headings": {"fontFamily": "'Space Grotesk', Inter, sans-serif"},
    "colors": {"stain": STAIN},
    "primaryColor": "stain",
    "primaryShade": {"light": 6, "dark": 4},
    "defaultRadius": "sm",
}
GRAPH_CONFIG = {
    "modeBarButtonsToAdd": ["drawopenpath", "drawrect", "eraseshape"],
    "modeBarButtonsToRemove": ["select2d", "lasso2d", "autoScale2d"],
    "displayModeBar": True,
    "displaylogo": False,
    "responsive": True,
}

app = dash.Dash(
    __name__,
    title="Interactive Image Segmentation",
    external_stylesheets=[
        "https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=Inter:wght@400;500;600&family=Space+Grotesk:wght@500;600;700&display=swap"
    ],
)
server = app.server

BASE_IMAGE = dict(
    source=app.get_asset_url("segmentation_img.jpg"),
    xref="x",
    yref="y",
    x=0,
    y=0,
    sizex=IMG_WIDTH,
    sizey=IMG_HEIGHT,
    sizing="stretch",
    layer="below",
)


def brush_width(value):
    return round(2**value)


def make_figure():
    fig = go.Figure(go.Scatter(x=[], y=[], hoverinfo="skip"))
    fig.update_xaxes(range=[0, IMG_WIDTH], visible=False)
    fig.update_yaxes(
        range=[IMG_HEIGHT, 0], visible=False, scaleanchor="x", constrain="domain"
    )
    fig.update_layout(
        images=[BASE_IMAGE],
        dragmode="drawopenpath",
        newshape={"line": {"color": CLASS_COLORS[DEFAULT_CLASS], "width": brush_width(DEFAULT_BRUSH)}},
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        modebar={"bgcolor": "rgba(0,0,0,0)", "color": MUTED, "activecolor": STAIN[6]},
        uirevision="segmentation",
    )
    return fig


@lru_cache(maxsize=2)
def cached_features(features, sigma_min, sigma_max):
    # Recomputing features is the slow part, and they only depend on these settings
    return segmentation.compute_features(IMG, features, sigma_min, sigma_max)


def segment(shapes, features, sigmas):
    feats = cached_features(tuple(sorted(features)), *sigmas)
    return segmentation.train_and_segment(feats, shapes, CLASS_COLORS)


def control(label, child, value_id=None):
    return dmc.Stack(
        [
            dmc.Group(
                [
                    dmc.Text(label, size="sm", fw=500),
                    value_id and dmc.Text(id=value_id, size="xs", ff="monospace", c="stain.7"),
                ],
                justify="space-between",
            ),
            child,
        ],
        gap=8,
    )


def stage(number, title, hint, *children):
    return dmc.Stack(
        [
            dmc.Group(
                [
                    dmc.Text(number, className="stage-number"),
                    dmc.Text(title, className="stage-title"),
                ],
                gap=8,
            ),
            dmc.Text(hint, size="xs", c="dimmed", mt=-8),
            *children,
        ],
        gap="sm",
        className="stage",
    )


with open("explanations.md") as f:
    howto_md = f.read()

howto_modal = dmc.Modal(
    dmc.Group(
        [
            html.Img(
                src=app.get_asset_url("segmentation_img_example_marks.jpg"),
                alt="Example of annotations drawn on the image",
                className="example-img",
            ),
            dcc.Markdown(howto_md, className="help-text", link_target="_blank"),
        ],
        align="flex-start",
        wrap="nowrap",
        gap="lg",
        className="howto",
    ),
    id="howto-modal",
    title=dmc.Text("How it works", className="modal-title"),
    size="xl",
    overlayProps={"backgroundOpacity": 0.7, "blur": 3},
)

header = dmc.AppShellHeader(
    dmc.Group(
        [
            dmc.Group(
                [
                    dmc.Burger(id="burger", size="sm", hiddenFrom="sm"),
                    html.Div(
                        DashIconify(icon="tabler:microscope", width=20),
                        className="brand-mark",
                    ),
                    dmc.Stack(
                        [
                            dmc.Text("Interactive ML", className="eyebrow", visibleFrom="md"),
                            dmc.Title("Image Segmentation", order=3, className="app-title"),
                        ],
                        gap=0,
                    ),
                ],
                gap="sm",
                wrap="nowrap",
                className="title-group",
            ),
            dmc.Group(
                [
                    dmc.Button(
                        "How it works",
                        id="howto-open",
                        variant="subtle",
                        color="dark",
                        size="sm",
                        leftSection=DashIconify(icon="tabler:book-2", width=16),
                    ),
                    html.A(
                        html.Img(src=app.get_asset_url("dash-logo.png"), height=26, alt="Plotly Dash"),
                        href="https://dash.plotly.com/",
                        className="dash-logo",
                    ),
                ],
                gap="md",
                wrap="nowrap",
            ),
        ],
        justify="space-between",
        h="100%",
        px="lg",
        wrap="nowrap",
    )
)

navbar = dmc.AppShellNavbar(
    dmc.Stack(
        [
            stage(
                "01",
                "Annotate",
                "Pick a class and draw over regions that belong to it.",
                control(
                    "Label class",
                    dmc.Group(
                        [
                            html.Button(
                                str(n + 1),
                                id={"type": "label-class", "index": n},
                                className="swatch selected" if n == DEFAULT_CLASS else "swatch",
                                style={"--swatch": color},
                                title=f"Class {n + 1}",
                            )
                            for n, color in enumerate(CLASS_COLORS)
                        ],
                        gap=8,
                    ),
                ),
                control(
                    "Brush width",
                    dmc.Slider(
                        id="brush",
                        min=0,
                        max=6,
                        step=0.25,
                        value=DEFAULT_BRUSH,
                        label=None,
                        size="xs",
                    ),
                    value_id="brush-label",
                ),
            ),
            stage(
                "02",
                "Features",
                "What the classifier looks at around each pixel.",
                dmc.ChipGroup(
                    dmc.Group(
                        [
                            dmc.Chip(f.capitalize(), value=f, size="xs", variant="outline")
                            for f in segmentation.FEATURE_TYPES
                        ],
                        gap=6,
                    ),
                    id="features",
                    multiple=True,
                    value=DEFAULT_FEATURES,
                ),
                control(
                    "Blurring scale",
                    dmc.RangeSlider(
                        id="sigmas",
                        min=0.5,
                        max=20,
                        step=0.5,
                        minRange=0.5,
                        value=DEFAULT_SIGMAS,
                        label=None,
                        size="xs",
                        updatemode="mouseup",
                    ),
                    value_id="sigmas-label",
                ),
            ),
            stage(
                "03",
                "Segment",
                "Classify every pixel from your marks.",
                dmc.Switch(
                    id="show-segmentation",
                    label="Show segmentation",
                    checked=False,
                    size="md",
                    fw=500,
                ),
            ),
            dmc.Stack(
                [
                    dmc.Button(
                        "Download classified image",
                        id="download-image-button",
                        variant="light",
                        size="sm",
                        leftSection=DashIconify(icon="tabler:photo-down", width=16),
                        disabled=True,
                    ),
                    dmc.Button(
                        "Download classifier",
                        id="download-classifier-button",
                        variant="default",
                        size="sm",
                        leftSection=DashIconify(icon="tabler:download", width=16),
                        disabled=True,
                    ),
                    dcc.Download(id="download-image"),
                    dcc.Download(id="download-classifier"),
                ],
                gap="xs",
                mt="auto",
            ),
        ],
        gap="xl",
        h="100%",
    ),
    p="lg",
    className="sidebar",
)

viewer = html.Div(
    [
        html.Div(
            [
                html.Span(className="live-dot"),
                f"Specimen · H&E stain · {IMG_WIDTH}×{IMG_HEIGHT}",
            ],
            className="specimen-tag",
        ),
        html.Div(
            [
                dcc.Graph(
                    id="graph",
                    figure=make_figure(),
                    config=GRAPH_CONFIG,
                    style={"position": "absolute", "inset": 0},
                ),
                dmc.LoadingOverlay(
                    id="segmentation-loading",
                    visible=False,
                    loaderProps={"color": "stain", "type": "dots"},
                    overlayProps={"backgroundOpacity": 0.4, "blur": 1},
                ),
            ],
            className="viz-body",
        ),
        html.Div(
            [
                DashIconify(icon="tabler:terminal-2", width=14),
                html.Span(id="viewer-status"),
            ],
            className="readout",
        ),
    ],
    className="viewer",
)

app.layout = dmc.MantineProvider(
    [
        dmc.AppShell(
            [header, navbar, dmc.AppShellMain(viewer)],
            id="shell",
            header={"height": 64},
            navbar={
                "width": 300,
                "breakpoint": "sm",
                "collapsed": {"mobile": True, "desktop": False},
            },
            padding="md",
        ),
        howto_modal,
        dcc.Store(id="label-class", data=DEFAULT_CLASS),
        dcc.Store(id="masks", data=[]),
    ],
    theme=THEME,
    forceColorScheme="light",
)


@app.callback(
    Output("shell", "navbar"),
    Input("burger", "opened"),
    State("shell", "navbar"),
)
def toggle_navbar(opened, navbar):
    navbar["collapsed"] = {"mobile": not opened, "desktop": False}
    return navbar


@app.callback(
    Output("howto-modal", "opened"),
    Input("howto-open", "n_clicks"),
    prevent_initial_call=True,
)
def open_howto(_):
    return True


@app.callback(
    Output("label-class", "data"),
    Output({"type": "label-class", "index": ALL}, "className"),
    Input({"type": "label-class", "index": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def select_label_class(_):
    selected = ctx.triggered_id["index"]
    return selected, [
        "swatch selected" if n == selected else "swatch" for n in range(len(CLASS_COLORS))
    ]


@app.callback(
    Output("brush-label", "children"),
    Output("sigmas-label", "children"),
    Input("brush", "value"),
    Input("sigmas", "value"),
)
def update_control_labels(brush, sigmas):
    return f"{brush_width(brush)} px", f"{sigmas[0]:g} – {sigmas[1]:g}"


@app.callback(
    Output("graph", "figure", allow_duplicate=True),
    Input("label-class", "data"),
    Input("brush", "value"),
    prevent_initial_call=True,
)
def update_brush(label_class, brush):
    # Only the style of new marks changes, so leave the rest of the figure alone
    fig = Patch()
    fig["layout"]["newshape"]["line"] = {
        "color": CLASS_COLORS[label_class],
        "width": brush_width(brush),
    }
    return fig


SHAPE_EDIT = re.compile(r"shapes\[(\d+)\]\.(\w+)")


@app.callback(
    Output("masks", "data"),
    Input("graph", "relayoutData"),
    State("masks", "data"),
    prevent_initial_call=True,
)
def update_masks(relayout, shapes):
    """Keep a copy of the drawn shapes, so the segmentation callbacks don't need
    the whole figure."""
    if not relayout:
        raise PreventUpdate
    if "shapes" in relayout:
        return relayout["shapes"]
    edits = [(SHAPE_EDIT.fullmatch(k), v) for k, v in relayout.items()]
    edits = [(m, v) for m, v in edits if m]
    if not edits:
        # A zoom, pan or mode change
        raise PreventUpdate
    for m, v in edits:
        shapes[int(m[1])][m[2]] = v
    return shapes


@app.callback(
    Output("graph", "figure"),
    Output("viewer-status", "children"),
    Output("download-image-button", "disabled"),
    Output("download-classifier-button", "disabled"),
    Output("segmentation-loading", "visible"),
    Input("masks", "data"),
    Input("show-segmentation", "checked"),
    Input("features", "value"),
    Input("sigmas", "value"),
)
def update_segmentation(shapes, show, features, sigmas):
    fig = Patch()
    fig["layout"]["images"] = [BASE_IMAGE]
    can_segment = bool(shapes) and bool(features)
    if not shapes:
        status = "Draw on the image to label it. Use the toolbar to draw rectangles or erase a selected mark."
    elif not features:
        status = "Select at least one feature to compute the segmentation."
    else:
        n = len(shapes)
        status = f"{n} mark{'s' * (n != 1)} drawn."
    if show and can_segment:
        try:
            seg, _ = segment(shapes, features, sigmas)
        except ValueError:
            status = "None of the marks are inside the image."
        else:
            overlay = segmentation.classes_to_rgba(seg, CLASS_COLORS)
            fig["layout"]["images"].append(
                {**BASE_IMAGE, "source": segmentation.to_data_uri(overlay), "layer": "above"}
            )
            status += " Showing the segmentation; add marks where it's wrong."
    elif can_segment:
        status += " Turn on Show segmentation to classify the rest of the image."
    return fig, status, not can_segment, not can_segment, False


# Show the loading overlay right away when the switch is turned on; the
# segmentation callback above hides it once the result is drawn
app.clientside_callback(
    "(checked) => checked",
    Output("segmentation-loading", "visible", allow_duplicate=True),
    Input("show-segmentation", "checked"),
    prevent_initial_call=True,
)


@app.callback(
    Output("download-image", "data"),
    Input("download-image-button", "n_clicks"),
    State("masks", "data"),
    State("features", "value"),
    State("sigmas", "value"),
    prevent_initial_call=True,
)
def download_image(_, shapes, features, sigmas):
    seg, _ = segment(shapes, features, sigmas)
    blended = segmentation.blend(IMG, segmentation.classes_to_rgba(seg, CLASS_COLORS))
    return dcc.send_bytes(segmentation.to_png_bytes(blended), "classified-image.png")


@app.callback(
    Output("download-classifier", "data"),
    Input("download-classifier-button", "n_clicks"),
    State("masks", "data"),
    State("features", "value"),
    State("sigmas", "value"),
    prevent_initial_call=True,
)
def download_classifier(_, shapes, features, sigmas):
    _, clf = segment(shapes, features, sigmas)
    saved = segmentation.serialize_classifier(clf, CLASS_COLORS, features, *sigmas)
    return dict(content=json.dumps(saved), filename="classifier.json")


if __name__ == "__main__":
    app.run(debug=True)
