"""
Object Detection for Self-Driving Cars

Compare the human annotations of the Udacity self-driving car dataset with the
objects found by a YOLO v3 network. Pick an object class to browse frames that
contain it, then tune the confidence and overlap thresholds of the model.
"""

import fcntl
import os
import random
import threading
import time
import urllib.request
from datetime import datetime, timezone
from functools import lru_cache

import cv2
import dash
import dash_mantine_components as dmc
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
from dash import Input, Output, State, ctx, dcc, html
from dash_iconify import DashIconify

IMAGE_BUCKET = "https://images.plot.ly/udacity-self-driving-cars/"
WEIGHTS_URL = IMAGE_BUCKET + "yolov3.weights"
CONFIG_PATH = "yolov3.cfg"
# The weights (~250 MB) are downloaded once into Plotly Cloud's persistent /data
# volume, so restarts reuse them. Locally, where there is no /data, they go to a
# cache folder outside the project so they never end up in an upload
PERSISTENT_DIR = "/data"
if os.path.isdir(PERSISTENT_DIR) and os.access(PERSISTENT_DIR, os.W_OK):
    CACHE_DIR = PERSISTENT_DIR
else:
    CACHE_DIR = os.path.join(
        os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), "dash-self-driving"
    )
WEIGHTS_PATH = os.path.join(CACHE_DIR, "yolov3.weights")
IMG_WIDTH, IMG_HEIGHT = 512, 320

# Candidates below this score are dropped before caching, so the sliders only
# need to filter and run non-max suppression on a short list
MIN_CONFIDENCE = 0.05
DEFAULT_CONFIDENCE = 0.5
DEFAULT_OVERLAP = 0.5

# Udacity label -> display name, icon and box color
CLASSES = {
    "car": ("Car", "tabler:car", "#38BDF8"),
    "pedestrian": ("Pedestrian", "tabler:walk", "#FB4F6F"),
    "truck": ("Truck", "tabler:truck", "#A3E635"),
    "biker": ("Biker", "tabler:bike", "#C084FC"),
    "trafficLight": ("Traffic light", "tabler:traffic-lights", "#2DD4BF"),
}
DEFAULT_CLASS = "pedestrian"

# Map from YOLO (COCO) class ids to Udacity labels
YOLO_TO_UDACITY = {
    0: "pedestrian",
    1: "biker",
    2: "car",
    3: "biker",
    5: "truck",
    7: "truck",
    9: "trafficLight",
}

# Highway-sign green, the accent of the whole app. Overpass is based on the
# typeface of US road signs
SIGN = ["#E7F5EF", "#C9E9DA", "#9FD8BE", "#6FC39F", "#43AE82",
        "#1F9A6B", "#0E8659", "#00734B", "#005F3E", "#004A30"]
THEME = {
    "fontFamily": "Overpass, system-ui, sans-serif",
    "fontFamilyMonospace": "'Overpass Mono', ui-monospace, monospace",
    "headings": {"fontFamily": "Overpass, system-ui, sans-serif"},
    "colors": {"sign": SIGN},
    "primaryColor": "sign",
    "primaryShade": 7,
    "defaultRadius": "md",
}
GRAPH_CONFIG = {"displayModeBar": False, "responsive": True}


# Data

labels = pd.read_csv("labels.csv.gz")
# Number of objects of each class in each frame
summary = pd.crosstab(labels["frame"], labels["label"])
FRAMES = {c: summary.index[summary[c] > 0].tolist() for c in CLASSES}


def frame_time(frame):
    # Udacity frames are named after their capture time in nanoseconds
    ns = int(frame.split(".")[0])
    return datetime.fromtimestamp(ns / 1e9, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


# Model, downloaded and loaded in the background so that the server can start
# answering requests right away. Each gunicorn worker process loads its own copy

model = {"net": None, "error": None, "downloaded": 0, "total": 0, "pid": None}
net_lock = threading.Lock()  # an OpenCV network can't run in two threads at once
start_lock = threading.Lock()


def download_weights():
    # Only one process downloads; others wait on the lock and reuse its file
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(WEIGHTS_PATH + ".lock", "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX)
        except OSError:
            pass  # some network volumes don't support locks; download anyway
        if os.path.exists(WEIGHTS_PATH):
            return
        print(f"Downloading YOLO v3 weights to {WEIGHTS_PATH}...", flush=True)
        tmp_path = WEIGHTS_PATH + ".part"
        with requests.get(WEIGHTS_URL, stream=True, timeout=60) as r:
            r.raise_for_status()
            model["total"] = int(r.headers.get("content-length", 0))
            with open(tmp_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
                    model["downloaded"] += len(chunk)
        if model["total"] and os.path.getsize(tmp_path) != model["total"]:
            raise OSError("The weights download was incomplete")
        # Only a complete file ever appears under the final name
        os.replace(tmp_path, WEIGHTS_PATH)


def load_model():
    try:
        if not os.path.exists(WEIGHTS_PATH):
            download_weights()
        net = cv2.dnn.readNetFromDarknet(CONFIG_PATH, WEIGHTS_PATH)
        # With these optimizations on, OpenCV caches extra copies of the weights
        # and the first inference peaks at ~1.8 GB instead of ~0.7 GB, enough
        # to get the app killed on a small instance. It's no slower without them
        net.enableWinograd(False)
        net.enableFusion(False)
        model["net"] = net
        print("YOLO v3 model loaded.", flush=True)
    except Exception as e:
        model["error"] = str(e)
        print(f"Could not load the YOLO v3 model: {e}", flush=True)


def ensure_model_loading():
    """Start loading the model in this process, once. Checking the process id
    also covers servers that import the app before forking workers (gunicorn
    --preload), since threads don't survive the fork."""
    with start_lock:
        if model["pid"] != os.getpid():
            model.update(net=None, error=None, downloaded=0, total=0, pid=os.getpid())
            threading.Thread(target=load_model, daemon=True).start()


ensure_model_loading()


def model_state():
    ensure_model_loading()
    if model["net"] is not None:
        return "ready"
    return "error" if model["error"] else "loading"


def model_progress():
    if model["total"] and model["downloaded"] < model["total"]:
        return f"Downloading model {model['downloaded'] / model['total']:.0%}"
    return "Loading model"


@lru_cache(maxsize=256)
def load_image(frame):
    with urllib.request.urlopen(IMAGE_BUCKET + frame, timeout=30) as response:
        data = np.frombuffer(response.read(), dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


@lru_cache(maxsize=256)
def yolo_candidates(frame):
    """Run the network once per frame and keep every plausible detection.
    Returns the boxes, scores and labels along with the inference time."""
    if model["net"] is None:
        raise RuntimeError(model["error"] or "The model is still loading")
    image = load_image(frame)
    h, w = image.shape[:2]
    blob = cv2.dnn.blobFromImage(image, 1 / 255.0, (416, 416), swapRB=True, crop=False)
    t = time.perf_counter()
    with net_lock:
        net = model["net"]
        net.setInput(blob)
        outputs = net.forward(net.getUnconnectedOutLayersNames())
    elapsed = time.perf_counter() - t

    detections = np.vstack(outputs)
    class_ids = detections[:, 5:].argmax(axis=1)
    scores = detections[np.arange(len(detections)), 5 + class_ids]
    keep = (scores >= MIN_CONFIDENCE) & np.isin(class_ids, list(YOLO_TO_UDACITY))
    cx, cy, bw, bh = (detections[keep, :4] * [w, h, w, h]).T
    boxes = np.column_stack([cx - bw / 2, cy - bh / 2, bw, bh]).round().astype(int)
    return (
        boxes.tolist(),
        scores[keep].astype(float).tolist(),
        [YOLO_TO_UDACITY[i] for i in class_ids[keep]],
        elapsed,
    )


def yolo_v3(frame, confidence_threshold, overlap_threshold):
    boxes, scores, names, elapsed = yolo_candidates(frame)
    indices = cv2.dnn.NMSBoxes(boxes, scores, confidence_threshold, overlap_threshold)
    rows = [
        {
            "xmin": boxes[i][0],
            "ymin": boxes[i][1],
            "xmax": boxes[i][0] + boxes[i][2],
            "ymax": boxes[i][1] + boxes[i][3],
            "label": names[i],
            "confidence": scores[i],
        }
        for i in np.array(indices).flatten()
    ]
    columns = ["xmin", "ymin", "xmax", "ymax", "label", "confidence"]
    return pd.DataFrame(rows, columns=columns), elapsed


# Figures


def frame_figure(frame, boxes):
    fig = go.Figure()
    for box in boxes.itertuples():
        name, _, color = CLASSES[box.label]
        hover = f"<b>{name}</b>"
        if box.confidence < 1:
            hover += f"<br>confidence {box.confidence:.2f}"
        fig.add_scatter(
            x=[box.xmin, box.xmax, box.xmax, box.xmin, box.xmin],
            y=[box.ymin, box.ymin, box.ymax, box.ymax, box.ymin],
            mode="lines",
            fill="toself",
            fillcolor=hex_to_rgba(color, 0.18),
            line={"color": color, "width": 2},
            hoveron="fills",
            hoverinfo="text",
            text=hover,
            hoverlabel={"bgcolor": "#FFFFFF", "bordercolor": color, "font_color": "#1F2A24"},
            name="",
        )
    fig.update_xaxes(
        range=[0, IMG_WIDTH], visible=False, fixedrange=True, constrain="domain", constraintoward="center"
    )
    fig.update_yaxes(
        range=[IMG_HEIGHT, 0],
        visible=False,
        fixedrange=True,
        scaleanchor="x",
        constrain="domain",
        constraintoward="middle",
    )
    fig.update_layout(
        # The browser loads the frame straight from the bucket
        images=[
            dict(
                source=IMAGE_BUCKET + frame,
                xref="x",
                yref="y",
                x=0,
                y=0,
                sizex=IMG_WIDTH,
                sizey=IMG_HEIGHT,
                sizing="stretch",
                layer="below",
            )
        ],
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        font_family="Overpass, sans-serif",
    )
    return fig


def blank_figure():
    # Shown until the first frame arrives, instead of Plotly's empty axes
    fig = go.Figure()
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def hex_to_rgba(color, alpha):
    r, g, b = (int(color[i : i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r},{g},{b},{alpha})"


def class_counts(boxes):
    counts = boxes["label"].value_counts()
    if counts.empty:
        return html.Span("No objects", className="count-empty")
    return [
        html.Span(
            [html.Span(className="dot", style={"--c": CLASSES[c][2]}), CLASSES[c][0], html.B(n)],
            className="count",
        )
        for c, n in counts.items()
    ]


# Layout

app = dash.Dash(
    __name__,
    title="Object Detection for Self-Driving Cars",
    external_stylesheets=[
        "https://fonts.googleapis.com/css2?family=Overpass:wght@400;600;700;800&family=Overpass+Mono:wght@400;600&display=swap"
    ],
)
server = app.server

header = dmc.AppShellHeader(
    dmc.Group(
        [
            dmc.Group(
                [
                    html.Div(DashIconify(icon="tabler:car", width=24), className="brand-mark"),
                    dmc.Stack(
                        [
                            html.Div("Computer vision with YOLO v3", className="eyebrow"),
                            dmc.Title("Object Detection for Self-Driving Cars", order=1, className="app-title"),
                        ],
                        gap=0,
                        miw=0,
                    ),
                ],
                gap="sm",
                wrap="nowrap",
                miw=0,
            ),
            dmc.Group(
                [
                    dmc.Anchor(
                        dmc.Group(
                            [DashIconify(icon="tabler:book-2", width=16), "Learn more"],
                            gap=6,
                            wrap="nowrap",
                        ),
                        href="https://medium.com/plotly/productionizing-object-detection-models-with-dash-enterprise-dba1c9402c2f",
                        target="_blank",
                        className="header-link",
                        visibleFrom="md",
                    ),
                    html.A(
                        html.Img(src=app.get_asset_url("dash-logo.png"), alt="Plotly"),
                        href="https://plotly.com/",
                        target="_blank",
                        className="plotly-logo",
                    ),
                ],
                gap="lg",
                wrap="nowrap",
            ),
        ],
        justify="space-between",
        wrap="nowrap",
        h="100%",
        px="lg",
    )
)


def feed(prefix, icon, title, subtitle):
    return html.Section(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.Span(DashIconify(icon=icon, width=18), className="feed-badge"),
                            html.Span(title, className="feed-title"),
                            html.Span(subtitle, className="feed-subtitle"),
                        ],
                        className="feed-heading",
                    ),
                    html.Span(id=f"{prefix}-meta", className="feed-meta"),
                ],
                className="feed-head",
            ),
            html.Div(
                dcc.Loading(
                    dcc.Graph(
                        id=f"{prefix}-graph",
                        figure=blank_figure(),
                        config=GRAPH_CONFIG,
                        className="feed-graph",
                    ),
                    type="circle",
                    color=SIGN[7],
                    delay_show=300,
                    overlay_style={"visibility": "visible", "opacity": 0.6},
                    parent_className="feed-loading",
                ),
                className="feed-body",
            ),
            html.Div(id=f"{prefix}-counts", className="feed-counts"),
        ],
        className="feed",
    )


def readout_slider(label, slider_id, value, minimum):
    return html.Div(
        [
            html.Div(
                [
                    html.Span(label, className="control-label"),
                    html.Span(f"{value:.2f}", id=f"{slider_id}-value", className="control-value"),
                ],
                className="control-head",
            ),
            dmc.Slider(
                id=slider_id,
                min=minimum,
                max=1,
                step=0.01,
                value=value,
                size="sm",
                updatemode="mouseup",
                label=None,
            ),
        ],
        className="control",
    )


console = html.Div(
    [
        html.Div(
            [
                html.Span("Find frames containing", className="control-label"),
                dmc.SegmentedControl(
                    id="object-class",
                    value=DEFAULT_CLASS,
                    data=[
                        {
                            "value": c,
                            "label": dmc.Group(
                                [DashIconify(icon=icon, width=16), html.Span(name, className="seg-label")],
                                gap=6,
                                wrap="nowrap",
                                justify="center",
                            ),
                        }
                        for c, (name, icon, _) in CLASSES.items()
                    ],
                    size="xs",
                    fullWidth=True,
                    className="class-picker",
                ),
            ],
            className="control control-class",
        ),
        html.Div(
            [
                html.Span("Frame", className="control-label"),
                dmc.Group(
                    [
                        dmc.ActionIcon(
                            DashIconify(icon="tabler:player-skip-back", width=18),
                            id="prev-frame",
                            variant="default",
                            size="lg",
                            **{"aria-label": "Previous frame"},
                        ),
                        html.Div(id="frame-position", className="frame-position"),
                        dmc.ActionIcon(
                            DashIconify(icon="tabler:player-skip-forward", width=18),
                            id="next-frame",
                            variant="default",
                            size="lg",
                            **{"aria-label": "Next frame"},
                        ),
                        dmc.Button(
                            "Random",
                            id="random-frame",
                            leftSection=DashIconify(icon="tabler:arrows-shuffle", width=16),
                            variant="filled",
                            color="yellow.5",
                            autoContrast=True,
                            size="sm",
                        ),
                    ],
                    gap=6,
                    wrap="nowrap",
                ),
            ],
            className="control",
        ),
        readout_slider("Confidence threshold", "confidence", DEFAULT_CONFIDENCE, MIN_CONFIDENCE),
        readout_slider("Overlap threshold (NMS)", "overlap", DEFAULT_OVERLAP, 0),
    ],
    className="console",
)

app.layout = dmc.MantineProvider(
    [
        dmc.AppShell(
            [
                header,
                dmc.AppShellMain(
                    html.Div(
                        [
                            html.Div(
                                [
                                    feed("truth", "tabler:user-check", "Ground truth", "Human annotated"),
                                    feed("yolo", "tabler:cpu", "YOLO v3", "Model predictions"),
                                ],
                                className="feeds",
                            ),
                            console,
                        ],
                        className="page",
                    )
                ),
            ],
            header={"height": 60},
            padding=0,
        ),
        dcc.Store(id="frame-index", data=0),
        # Polls the background model download until the network is loaded
        dcc.Store(id="model-state", data="loading"),
        dcc.Interval(id="model-poll", interval=1000),
    ],
    theme=THEME,
    forceColorScheme="light",
)


# Callbacks


@app.callback(
    Output("frame-index", "data"),
    Input("object-class", "value"),
    Input("prev-frame", "n_clicks"),
    Input("next-frame", "n_clicks"),
    Input("random-frame", "n_clicks"),
    State("frame-index", "data"),
    prevent_initial_call=True,
)
def navigate(object_class, _prev, _next, _random, index):
    n = len(FRAMES[object_class])
    match ctx.triggered_id:
        case "prev-frame":
            return (index - 1) % n
        case "next-frame":
            return (index + 1) % n
        case "random-frame":
            return random.randrange(n)
    return 0


@app.callback(
    Output("truth-graph", "figure"),
    Output("truth-counts", "children"),
    Output("truth-meta", "children"),
    Output("frame-position", "children"),
    Input("object-class", "value"),
    Input("frame-index", "data"),
)
def update_ground_truth(object_class, index):
    frames = FRAMES[object_class]
    frame = frames[index % len(frames)]
    boxes = labels[labels["frame"] == frame].assign(confidence=1.0)
    position = [html.B(f"{index % len(frames) + 1:,}"), f" / {len(frames):,}"]
    return frame_figure(frame, boxes), class_counts(boxes), frame_time(frame), position


@app.callback(
    Output("yolo-graph", "figure"),
    Output("yolo-counts", "children"),
    Output("yolo-meta", "children"),
    Input("object-class", "value"),
    Input("frame-index", "data"),
    Input("confidence", "value"),
    Input("overlap", "value"),
    Input("model-state", "data"),
)
def update_yolo(object_class, index, confidence, overlap, state):
    frames = FRAMES[object_class]
    frame = frames[index % len(frames)]
    if model_state() == "loading":
        # Show the frame right away; the boxes are added once the model is ready
        waiting = html.Span(
            "YOLO v3 is loading (first start only), predictions will appear shortly",
            className="count-empty",
        )
        return frame_figure(frame, pd.DataFrame(columns=["label"])), waiting, model_progress()
    try:
        boxes, elapsed = yolo_v3(frame, confidence, overlap)
    except Exception as e:
        print(f"YOLO v3 failed on {frame}: {e}", flush=True)
        empty = frame_figure(frame, pd.DataFrame(columns=["label"]))
        return empty, html.Span("Model unavailable, try again shortly", className="count-empty"), "Offline"
    return frame_figure(frame, boxes), class_counts(boxes), f"Inference {elapsed * 1000:,.0f} ms"


@app.callback(
    Output("model-state", "data"),
    Output("yolo-meta", "children", allow_duplicate=True),
    Output("model-poll", "disabled"),
    Input("model-poll", "n_intervals"),
    prevent_initial_call=True,
)
def poll_model(_):
    state = model_state()
    if state == "loading":
        return dash.no_update, model_progress(), False
    # Changing the state re-runs update_yolo, which now has the model
    return state, dash.no_update, True


app.clientside_callback(
    "(c, o) => [c.toFixed(2), o.toFixed(2)]",
    Output("confidence-value", "children"),
    Output("overlap-value", "children"),
    Input("confidence", "value"),
    Input("overlap", "value"),
)


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False, port=8080)
