"""
Object Detection for Self-Driving Cars

Compare the human annotations of the Udacity self-driving car dataset with the
objects found by a YOLO v3 network. Pick an object class to browse frames that
contain it, then tune the confidence and overlap thresholds of the model.
"""

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
WEIGHTS_PATH = "yolov3.weights"
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

# Road-line amber, the accent of the whole app
AMBER = ["#FFF8E1", "#FFEDB3", "#FFE082", "#FFD54F", "#FFCA28",
         "#FFB300", "#FFA000", "#FF8F00", "#E67E00", "#C66A00"]
THEME = {
    "fontFamily": "'Chakra Petch', system-ui, sans-serif",
    "fontFamilyMonospace": "'Martian Mono', ui-monospace, monospace",
    "headings": {"fontFamily": "'Chakra Petch', system-ui, sans-serif"},
    "colors": {"amber": AMBER},
    "primaryColor": "amber",
    "primaryShade": 5,
    "defaultRadius": "xs",
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
# answering requests right away

model = {"net": None, "error": None}
model_ready = threading.Event()
net_lock = threading.Lock()  # an OpenCV network can't run in two threads at once


def load_model():
    try:
        if not os.path.exists(WEIGHTS_PATH):
            print("Downloading YOLO v3 weights...", flush=True)
            tmp_path = WEIGHTS_PATH + ".part"
            with requests.get(WEIGHTS_URL, stream=True, timeout=60) as r:
                r.raise_for_status()
                with open(tmp_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1 << 20):
                        f.write(chunk)
            os.replace(tmp_path, WEIGHTS_PATH)
        model["net"] = cv2.dnn.readNetFromDarknet(CONFIG_PATH, WEIGHTS_PATH)
        print("YOLO v3 model loaded.", flush=True)
    except Exception as e:
        model["error"] = str(e)
        print(f"Could not load the YOLO v3 model: {e}", flush=True)
    finally:
        model_ready.set()


threading.Thread(target=load_model, daemon=True).start()


@lru_cache(maxsize=256)
def load_image(frame):
    with urllib.request.urlopen(IMAGE_BUCKET + frame, timeout=30) as response:
        data = np.frombuffer(response.read(), dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


@lru_cache(maxsize=256)
def yolo_candidates(frame):
    """Run the network once per frame and keep every plausible detection.
    Returns the boxes, scores and labels along with the inference time."""
    model_ready.wait()
    if model["net"] is None:
        raise RuntimeError(model["error"])
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
            hoverlabel={"bgcolor": "#0A0D12", "bordercolor": color, "font_color": "#E8ECF1"},
            name="",
        )
    fig.update_xaxes(range=[0, IMG_WIDTH], visible=False, fixedrange=True)
    fig.update_yaxes(
        range=[IMG_HEIGHT, 0],
        visible=False,
        fixedrange=True,
        scaleanchor="x",
        constrain="domain",
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
        font_family="Martian Mono, monospace",
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
        "https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@400;500;600;700&family=Martian+Mono:wght@400;500&display=swap"
    ],
)
server = app.server

header = dmc.AppShellHeader(
    dmc.Group(
        [
            dmc.Group(
                [
                    html.Div(DashIconify(icon="tabler:steering-wheel", width=22), className="brand-mark"),
                    dmc.Stack(
                        [
                            html.Div("Perception lab · YOLO v3", className="eyebrow"),
                            dmc.Title("Object Detection for Self-Driving Cars", order=1, className="app-title"),
                        ],
                        gap=0,
                    ),
                ],
                gap="sm",
                wrap="nowrap",
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


def feed(prefix, cam, title, subtitle):
    return html.Section(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.Span(cam, className="cam-tag"),
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
                    dcc.Graph(id=f"{prefix}-graph", config=GRAPH_CONFIG, className="feed-graph"),
                    type="circle",
                    color=AMBER[5],
                    delay_show=300,
                    overlay_style={"visibility": "visible", "opacity": 0.45},
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
                marks=[{"value": minimum, "label": f"{minimum:g}"}, {"value": 1, "label": "1"}],
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
                            variant="light",
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
                                    feed("truth", "CAM 01", "Ground truth", "human annotated"),
                                    feed("yolo", "CAM 01", "YOLO v3", "model predictions"),
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
    ],
    theme=THEME,
    forceColorScheme="dark",
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
)
def update_yolo(object_class, index, confidence, overlap):
    frames = FRAMES[object_class]
    frame = frames[index % len(frames)]
    try:
        boxes, elapsed = yolo_v3(frame, confidence, overlap)
    except Exception as e:
        print(f"YOLO v3 failed on {frame}: {e}", flush=True)
        empty = frame_figure(frame, pd.DataFrame(columns=["label"]))
        return empty, html.Span("Model unavailable, try again shortly", className="count-empty"), "offline"
    return frame_figure(frame, boxes), class_counts(boxes), f"inference {elapsed * 1000:,.0f} ms"


app.clientside_callback(
    "(c, o) => [c.toFixed(2), o.toFixed(2)]",
    Output("confidence-value", "children"),
    Output("overlap-value", "children"),
    Input("confidence", "value"),
    Input("overlap", "value"),
)


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
