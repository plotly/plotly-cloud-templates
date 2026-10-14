"""
Download, load, and pre-process the OpenCelliD cell towers dataset.

The dataset is too large to upload alongside the app. Instead, the first time the app
starts it downloads the full database from Google Drive (or the URL in the
CELL_TOWERS_CSV_URL environment variable, see download_data.py) and saves it on disk.
On Plotly Cloud it is saved in the persistent /data directory, so it is only downloaded
once: later restarts load it straight from disk. Delete /data/cell_towers.parq to
download a fresh copy.

Loading happens in a background thread so the web server can start answering requests
(and show a loading message) while the data is being fetched.
"""
import fcntl
import os
import shutil
import tempfile
import threading
import time

import datashader as ds
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.dataset as pads

from dash_opencellid import download_data
from dash_opencellid.utils import epsg_3857_to_4326

CSV_URL = os.getenv("CELL_TOWERS_CSV_URL", download_data.DEFAULT_CSV_URL)
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Use Plotly Cloud's persistent /data directory when available
DEFAULT_DATA_DIR = "/data" if os.path.isdir("/data") else os.path.join(APP_DIR, "data")
DATA_DIR = os.getenv("CELL_TOWERS_DATA_DIR", DEFAULT_DATA_DIR)

# Columns used by the app
COLUMNS = [
    "radio",
    "x_3857",
    "y_3857",
    "range",
    "created",  # Filtering
    "lat",
    "lon",
    "Description",
    "Status",
    "mcc",
    "net",  # Hover info
]
CATEGORY_COLUMNS = ["radio", "Description", "Status"]
# Only read one file at a time to keep the memory used while loading low
READ_OPTIONS = {"fragment_readahead": 1, "batch_readahead": 1}

_datasets = {}
_ready = threading.Event()
_lock = threading.Lock()
_thread = None
status = "Starting..."
error = None


def _data_dir():
    """Return a writable directory to save the dataset in"""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        if os.access(DATA_DIR, os.W_OK):
            return DATA_DIR
    except OSError:
        pass
    fallback = os.path.join(tempfile.gettempdir(), "cell_towers_data")
    os.makedirs(fallback, exist_ok=True)
    return fallback


def _set_status(message):
    global status
    status = message
    print(message, flush=True)


def _memory_used():
    """Describe this process's current memory usage, for the logs"""
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return f"{int(line.split()[1]) / 1e6:.1f} GB memory used"
    except OSError:
        pass
    return "memory usage unknown"


def ensure_downloaded():
    """Return the path to the local dataset, downloading it first if needed"""
    data_dir = _data_dir()
    parquet_path = os.path.join(data_dir, "cell_towers.parq")

    # Several server processes may start at once, so use a file lock to make sure the
    # dataset is only downloaded once
    with open(os.path.join(data_dir, ".download.lock"), "w") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        if os.path.exists(parquet_path):
            return parquet_path

        # Remove partial downloads left behind if the app was stopped mid-download
        for name in os.listdir(data_dir):
            if name.startswith(download_data.WORK_DIR_PREFIX):
                shutil.rmtree(os.path.join(data_dir, name), ignore_errors=True)
        download_data.download_and_prepare(parquet_path, CSV_URL, _set_status)
        return parquet_path


def compute_range_created_radio_hist(df, created_bin_edges, min_log10_range, max_log10_range):
    """
    Use Datashader to compute a 3D histogram of df, binned by the created,
    log10_range, and radio dimensions
    """
    created_bins = created_bin_edges.astype("int64")

    cvs2 = ds.Canvas(
        # Specify created bins
        plot_width=len(created_bins) - 1,
        x_range=[min(created_bins), max(created_bins)],
        # Specify log10_range bins
        plot_height=20,
        y_range=[min_log10_range, max_log10_range],
    )
    return cvs2.points(df, x="created", y="log10_range", agg=ds.count_cat("radio"))


def _read_dataset(parquet_path):
    """
    Read the parquet dataset into a DataFrame using compact dtypes. The full dataset
    takes several GB, so the final columns are allocated up front and filled one batch
    at a time instead of building intermediate copies of the whole dataset.
    """
    dataset = pads.dataset(parquet_path, format="parquet")
    n_rows = dataset.count_rows()
    _set_status(f"Loading {n_rows:,} cell towers into memory ({_memory_used()})...")

    # Collect each text column's categories first, so every batch can be stored as
    # integer codes into the same categories
    categories = {col: set() for col in CATEGORY_COLUMNS}
    for batch in dataset.to_batches(columns=CATEGORY_COLUMNS, **READ_OPTIONS):
        for col in CATEGORY_COLUMNS:
            categories[col].update(pc.unique(batch[col]).drop_null().to_pylist())
    categories = {col: pd.Index(sorted(values)) for col, values in categories.items()}

    numeric_dtypes = {
        "x_3857": "float32",
        "y_3857": "float32",
        "lat": "float32",
        "lon": "float32",
        "log10_range": "float32",
        "created": "int64",
        "mcc": "int32",
        "net": "int32",
    }
    columns = {col: np.empty(n_rows, dtype) for col, dtype in numeric_dtypes.items()}
    codes = {col: np.empty(n_rows, "int16") for col in CATEGORY_COLUMNS}

    start = 0
    for batch in dataset.to_batches(columns=COLUMNS, **READ_OPTIONS):
        end = start + batch.num_rows
        for col in numeric_dtypes:
            if col == "log10_range":
                values = batch["range"].to_numpy()
                np.log10(values, out=columns[col][start:end], dtype="float32")
                continue
            values = batch[col]
            if pa.types.is_timestamp(values.type):
                values = values.cast(pa.int64())
            columns[col][start:end] = values.to_numpy(zero_copy_only=False)
        for col in CATEGORY_COLUMNS:
            encoded = pc.dictionary_encode(batch[col])
            # Code of each of this batch's values in the shared categories (-1 if null)
            lookup = categories[col].get_indexer(encoded.dictionary.to_numpy(zero_copy_only=False))
            indices = encoded.indices.fill_null(-1).to_numpy()
            codes[col][start:end] = np.where(indices >= 0, lookup[indices], -1)
        # Report progress every ~5M rows
        if end // 5_000_000 > start // 5_000_000:
            _set_status(
                f"Loading cell towers into memory ({end:,} of {n_rows:,} rows, "
                f"{_memory_used()})..."
            )
        start = end

    for col in CATEGORY_COLUMNS:
        columns[col] = pd.Categorical.from_codes(codes.pop(col), categories[col])
    return pd.DataFrame(columns, copy=False)


def load(parquet_path):
    """Load the dataset and pre-compute the values that the app needs"""
    _set_status("Loading cell towers dataset into memory...")
    df = _read_dataset(parquet_path)

    _set_status(f"Pre-computing histograms ({_memory_used()})...")
    data_3857 = [
        [float(df["x_3857"].min()), float(df["y_3857"].min())],
        [float(df["x_3857"].max()), float(df["y_3857"].max())],
    ]
    data_center_3857 = [
        [
            (data_3857[0][0] + data_3857[1][0]) / 2.0,
            (data_3857[0][1] + data_3857[1][1]) / 2.0,
        ]
    ]

    # Create bin edges
    quarter_bins = pd.date_range(
        "2003", str(pd.Timestamp.now().year + 1), freq="QS", unit="ns"
    )
    created_bin_edges = quarter_bins[0::4]
    created_bin_centers = quarter_bins[2::4]

    min_log10_range = float(df["log10_range"].min())
    max_log10_range = float(df["log10_range"].max())

    # The 3D histogram covers all observations, so it only needs to be computed once
    range_created_radio_agg = compute_range_created_radio_hist(
        df, created_bin_edges, min_log10_range, max_log10_range
    )
    # Set created index back to datetime values
    range_created_radio_agg = range_created_radio_agg.assign_coords(
        created=created_bin_centers
    )

    return {
        "cell_towers_df": df,
        "data_3857": data_3857,
        "data_4326": epsg_3857_to_4326(data_3857),
        "data_center_3857": data_center_3857,
        "data_center_4326": epsg_3857_to_4326(data_center_3857),
        "range_created_radio_agg": range_created_radio_agg,
        "total_radio_counts": range_created_radio_agg.sum(
            ["log10_range", "created"]
        ).to_series(),
        "total_range_counts": range_created_radio_agg.sum(
            ["radio", "created"]
        ).to_series(),
        "total_created_counts": range_created_radio_agg.sum(
            ["log10_range", "radio"]
        ).to_series(),
    }


def _load_in_background():
    global status, error
    try:
        t0 = time.time()
        print(f"Starting to load the cell towers dataset (process {os.getpid()})", flush=True)
        _datasets.update(load(ensure_downloaded()))
        status = "Ready"
        print(
            f"Cell towers dataset ready in {time.time() - t0:.1f}s ({_memory_used()})",
            flush=True,
        )
        _ready.set()
    except Exception as e:
        error = f"{type(e).__name__}: {e}"
        status = f"Failed to load the cell towers dataset. {error}"
        print(status, flush=True)


def start_loading():
    """Start downloading and loading the dataset in a background thread"""
    global _thread
    with _lock:
        if _thread is None:
            _thread = threading.Thread(target=_load_in_background, daemon=True)
            _thread.start()


def is_ready():
    return _ready.is_set()


def wait_until_ready(timeout=None):
    return _ready.wait(timeout)


def get_dataset(name):
    return _datasets[name]
