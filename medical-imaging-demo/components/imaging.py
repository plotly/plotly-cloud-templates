"""X-ray figure builder and annotation helpers."""
import base64
import io
import pathlib

import numpy as np
import plotly.graph_objects as go
from PIL import Image, ImageEnhance, ImageOps

XRAY_DIR = pathlib.Path(__file__).parent.parent / "assets" / "xrays"

# Approximate bounding boxes (in 512×512 space) for each finding type
FINDING_AI_BOXES = {
    "Cardiomegaly":    {"x0": 155, "y0": 192, "x1": 345, "y1": 368, "color": "#f59e0b"},
    "Pleural Effusion":{"x0": 308, "y0": 295, "x1": 460, "y1": 425, "color": "#3b82f6"},
    "Pneumothorax":    {"x0": 18,  "y0": 40,  "x1": 178, "y1": 260, "color": "#ef4444"},
    "Nodule":          {"x0": 345, "y0": 135, "x1": 400, "y1": 195, "color": "#8b5cf6"},
    "Mass":            {"x0": 315, "y0": 155, "x1": 430, "y1": 285, "color": "#8b5cf6"},
    "Atelectasis":     {"x0": 155, "y0": 295, "x1": 380, "y1": 340, "color": "#f97316"},
    "Pneumonia":       {"x0": 310, "y0": 258, "x1": 460, "y1": 360, "color": "#eab308"},
    "Consolidation":   {"x0": 300, "y0": 250, "x1": 465, "y1": 370, "color": "#eab308"},
    "Infiltration":    {"x0": 145, "y0": 230, "x1": 310, "y1": 340, "color": "#eab308"},
    "Cardiomegaly":    {"x0": 155, "y0": 192, "x1": 345, "y1": 368, "color": "#f59e0b"},
}

IMG_W = IMG_H = 512

# Severity → annotation colour (Low=green, Medium=amber, High=red)
# Darkened one step for legibility on the light cream theme.
SEVERITY_COLORS = {"Low": "#16a34a", "Medium": "#d97706", "High": "#dc2626"}


def severity_color(severity: str) -> str:
    """Hex colour for a severity level, defaulting to Medium amber."""
    return SEVERITY_COLORS.get(severity or "Medium", SEVERITY_COLORS["Medium"])


def newshape_for(severity: str) -> dict:
    """Plotly `newshape` style for the next-drawn shape, keyed by severity.

    High findings draw with a thicker line so urgency reads at a glance.
    """
    color = severity_color(severity)
    width = 3 if severity == "High" else 2
    return {
        "line": {"color": color, "width": width},
        "fillcolor": f"rgba({_hex_to_rgb(color)},0.08)",
    }


def load_xray_b64(image_path: pathlib.Path,
                  window: float = 255,
                  level: float = 128,
                  invert: bool = False) -> str:
    """Load grayscale X-ray PNG, apply window/level, return data-URI."""
    try:
        img = Image.open(image_path).convert("L").resize((IMG_W, IMG_H), Image.LANCZOS)
    except Exception:
        img = Image.new("L", (IMG_W, IMG_H), 60)

    arr = np.array(img, dtype=np.float32)
    lo  = max(0.0, level - window / 2)
    hi  = min(255.0, level + window / 2)
    if hi > lo:
        arr = (arr - lo) / (hi - lo) * 255.0
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr, mode="L")

    if invert:
        img = ImageOps.invert(img)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}"


def create_xray_figure(img_b64: str, shapes: list = None) -> go.Figure:
    """Build a Plotly figure that shows an X-ray with drawing tools."""
    fig = go.Figure()

    fig.add_layout_image(
        source=img_b64,
        xref="x", yref="y",
        x=0, y=IMG_H,
        xanchor="left", yanchor="top",
        sizex=IMG_W, sizey=IMG_H,
        sizing="stretch",
        layer="below",
    )

    fig.update_layout(
        xaxis=dict(range=[0, IMG_W], showgrid=False, zeroline=False,
                   showticklabels=False, fixedrange=False),
        yaxis=dict(range=[0, IMG_H], showgrid=False, zeroline=False,
                   showticklabels=False, scaleanchor="x", fixedrange=False),
        plot_bgcolor="#e7e9ec",
        paper_bgcolor="#eef0f2",
        margin=dict(l=0, r=0, t=0, b=0),
        dragmode="drawrect",
        newshape=dict(
            line={"color": "#1e3a8a", "width": 2},
            fillcolor="rgba(30,58,138,0.08)",
        ),
        modebar=dict(
            bgcolor="#eef0f2",
            color="#6b7280",
            activecolor="#1e3a8a",
        ),
    )

    if shapes:
        fig.layout.shapes = [_make_shape(s) for s in shapes]

    return fig


def _make_shape(s: dict) -> dict:
    """Convert stored annotation dict to Plotly layout shape dict."""
    line = s.get("line") if isinstance(s.get("line"), dict) else {}
    color = line.get("color", "#1e3a8a")
    width = line.get("width", 2)
    return {
        "type":      s.get("type", "rect"),
        "x0":        s.get("x0", 0),
        "y0":        s.get("y0", 0),
        "x1":        s.get("x1", 10),
        "y1":        s.get("y1", 10),
        "line":      {"color": color, "width": width},
        "fillcolor": f"rgba({_hex_to_rgb(color)},0.09)",
    }


def _hex_to_rgb(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    if len(h) == 6:
        r, g, b = int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)
        return f"{r},{g},{b}"
    return "30,58,138"


def get_ai_shapes(finding_labels_str: str) -> list:
    """Return a list of stored annotation dicts from finding-label string."""
    shapes = []
    for f in finding_labels_str.split("|"):
        f = f.strip()
        box = FINDING_AI_BOXES.get(f)
        if box:
            shapes.append({
                "type": "rect",
                "x0": box["x0"], "y0": IMG_H - box["y1"],
                "x1": box["x1"], "y1": IMG_H - box["y0"],
                "line": {"color": box["color"], "width": 2},
                "fillcolor": "rgba(0,0,0,0)",
                "_label":    f,
                "_severity": "Medium",
                "_note":     "AI suggested",
            })
    return shapes


def annotation_to_finding_dict(ann: dict) -> dict:
    """Convert stored annotation to finding dict for PDF export."""
    x0, y0 = ann.get("x0", 0), ann.get("y0", 0)
    x1, y1 = ann.get("x1", 0), ann.get("y1", 0)
    return {
        "label":      ann.get("_label", "Unspecified"),
        "location":   f"({int(x0)},{int(y0)})→({int(x1)},{int(y1)})",
        "shape_type": ann.get("type", "rect"),
        "severity":   ann.get("_severity", "—"),
        "note":       ann.get("_note", ""),
    }
