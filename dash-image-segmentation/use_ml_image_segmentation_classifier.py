"""
Use the classifier that you downloaded from the interactive image segmentation app.
Specify files to use on the command line like so:

    CLF_PATH=path/to/classifier.json \\
    IMG_PATH=path/to/image/to/classify.some_image_ending \\
    OUT_IMG_PATH=path/to/where/to/put/classified/image.png \\
    OUT_BLEND_PATH=path/to/where/to/put/classified/blended/with/original/image.png \\
    python use_ml_image_segmentation_classifier.py

some_image_ending can be a common image format's ending, e.g., png or jpg.
Output images are written as png.
"""

import base64
import json
import os
import pickle
import sys

import numpy as np
import PIL.Image

import segmentation


def getenv(name):
    try:
        return os.environ[name]
    except KeyError:
        print(__doc__)
        sys.exit(1)


def classify(clf_path, img_path):
    """Returns the RGBA class overlay and the original image as arrays.

    The classifier was pickled by the app; only load files you created yourself.
    """
    with open(clf_path) as f:
        saved = json.load(f)
    clf = pickle.loads(base64.b64decode(saved["classifier"]))
    args = saved["segmenter_args"]
    img = np.array(PIL.Image.open(img_path).convert("RGB"))
    features = segmentation.compute_features(
        img, args["features"], args["sigma_min"], args["sigma_max"]
    )
    seg = segmentation.predict(features, clf)
    return segmentation.classes_to_rgba(seg, saved["colormap"]), img


if __name__ == "__main__":
    overlay, img = classify(getenv("CLF_PATH"), getenv("IMG_PATH"))
    PIL.Image.fromarray(overlay).save(getenv("OUT_IMG_PATH"))
    PIL.Image.fromarray(segmentation.blend(img, overlay)).save(getenv("OUT_BLEND_PATH"))
