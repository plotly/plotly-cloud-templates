"""Turn annotations drawn on a plotly figure into a segmentation of the image.

The drawn shapes are rasterized into a mask of class labels, local features are
computed for every pixel with scikit-image, and a random forest trained on the
annotated pixels predicts a class for all the others.
"""

import base64
import io
import pickle
import re

import numpy as np
import PIL.Image
import PIL.ImageDraw
from skimage.feature import multiscale_basic_features
from skimage.future import fit_segmenter, predict_segmenter
from sklearn.ensemble import RandomForestClassifier

FEATURE_TYPES = ["intensity", "edges", "texture"]
OVERLAY_ALPHA = 128

_NUMBER_PAIR = re.compile(r"(-?[\d.]+(?:e-?\d+)?)[ ,](-?[\d.]+(?:e-?\d+)?)")


def compute_features(img, features, sigma_min, sigma_max):
    """Per-pixel features with shape ``img.shape[:2] + (n_features,)``."""
    return multiscale_basic_features(
        img,
        **{f: f in features for f in FEATURE_TYPES},
        sigma_min=sigma_min,
        sigma_max=sigma_max,
        channel_axis=-1 if img.ndim == 3 else None,
    )


def _shape_points(shape):
    if shape.get("type") == "rect":
        x0, y0, x1, y1 = (float(shape[k]) for k in ("x0", "y0", "x1", "y1"))
        return [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
    points = [(float(x), float(y)) for x, y in _NUMBER_PAIR.findall(shape["path"])]
    if shape["path"].rstrip().upper().endswith("Z") and points:
        points.append(points[0])
    return points


def shapes_to_mask(shapes, labels, size):
    """Rasterize shapes into a uint8 mask where 0 means unlabeled.

    ``labels[i]`` is the value written for ``shapes[i]``; later shapes are drawn
    over earlier ones.
    """
    mask = PIL.Image.new("L", size, 0)
    draw = PIL.ImageDraw.Draw(mask)
    for shape, label in zip(shapes, labels):
        points = _shape_points(shape)
        if not points:
            continue
        width = max(1, round(float(shape["line"]["width"])))
        if len(points) > 1:
            draw.line(points, fill=label, width=width, joint="curve")
        # Round caps, so short strokes and single clicks still label something
        r = width / 2
        for x, y in (points[0], points[-1]):
            draw.ellipse((x - r, y - r, x + r, y + r), fill=label)
    return np.array(mask)


def train_and_segment(features, shapes, colormap):
    """Returns (class index per pixel, fitted classifier). Raises ValueError if
    the shapes don't label any pixel of the image."""
    # Classes start at 1 because the segmenter treats 0 as unlabeled
    labels = [colormap.index(s["line"]["color"]) + 1 for s in shapes]
    height, width = features.shape[:2]
    mask = shapes_to_mask(shapes, labels, (width, height))
    if not mask.any():
        raise ValueError("No annotated pixels inside the image")
    clf = RandomForestClassifier(
        n_estimators=50, n_jobs=-1, max_depth=8, max_samples=0.05, random_state=0
    )
    fit_segmenter(mask, features, clf)
    return predict(features, clf), clf


def predict(features, clf):
    return predict_segmenter(features, clf) - 1


def classes_to_rgba(seg, colormap, alpha=OVERLAY_ALPHA):
    palette = np.array(
        [[int(c[i : i + 2], 16) for i in (1, 3, 5)] + [alpha] for c in colormap],
        dtype=np.uint8,
    )
    return palette[seg]


def blend(img, overlay):
    """Composite an RGBA overlay onto an RGB image, returning RGB uint8."""
    alpha = overlay[..., 3:] / 255
    out = img[..., :3] * (1 - alpha) + overlay[..., :3] * alpha
    return np.round(out).astype(np.uint8)


def to_png_bytes(arr):
    buf = io.BytesIO()
    PIL.Image.fromarray(arr).save(buf, format="png")
    return buf.getvalue()


def to_data_uri(arr):
    return "data:image/png;base64," + base64.b64encode(to_png_bytes(arr)).decode()


def serialize_classifier(clf, colormap, features, sigma_min, sigma_max):
    """JSON-compatible dict, read back by use_ml_image_segmentation_classifier.py."""
    return {
        "classifier": base64.b64encode(pickle.dumps(clf)).decode(),
        "segmenter_args": {
            "features": list(features),
            "sigma_min": sigma_min,
            "sigma_max": sigma_max,
        },
        "colormap": list(colormap),
    }
