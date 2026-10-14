"""
Download the full OpenCelliD cell towers database and write it out as a parquet
dataset that the app can load.

The raw cell_towers.csv (optionally gzipped) is downloaded from a copy of the
OpenCelliD export hosted on Google Drive. Set CELL_TOWERS_CSV_URL to use another public
URL instead (Google Drive files must be shared as "Anyone with the link").

The app runs this automatically on startup if the dataset is missing. To run it by hand:

    python -m dash_opencellid.download_data [dest]
"""
import gzip
import os
import re
import shutil
import sys
import tempfile
import time

import pandas as pd
import requests

from dash_opencellid.utils import transformer_4326_to_3857

# OpenCelliD's cell_towers.csv export, hosted on Google Drive
DEFAULT_CSV_URL = (
    "https://drive.google.com/file/d/1lCvFgEIANGQWwypVs8Irbc46k0MiMt7L/view"
)
# Mapping from MCC/MNC codes to network operator names and status, saved from
# https://github.com/pbakondy/mcc-mnc-list
MCC_MNC_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcc-mnc-list.json")

# Columns of OpenCelliD's cell_towers.csv
CSV_COLUMNS = [
    "radio", "mcc", "net", "area", "cell", "unit", "lon", "lat", "range",
    "samples", "changeable", "created", "updated", "averageSignal",
]
CSV_DTYPES = {
    "radio": "category",
    "mcc": "int32",
    "net": "int32",
    "lon": "float64",
    "lat": "float64",
    "range": "int64",
    "created": "int64",
}
CHUNK_SIZE = 1_000_000
# Prefix of the temporary directory used while downloading, so that partial downloads
# can be recognized and cleaned up
WORK_DIR_PREFIX = ".download-"
# The raw csv is kept next to the dataset while downloading so that a restarted app can
# resume the download
PARTIAL_CSV = "cell_towers.csv.partial"
# Consecutive connection failures without any progress before giving up
MAX_DOWNLOAD_RETRIES = 10


def _print(message):
    print(message, flush=True)


def _download(url, dest, source, progress):
    """
    Stream url to dest, reporting progress. If dest already holds part of the file (the
    app was restarted mid-download) or the connection drops, the download resumes where
    it left off instead of starting over.
    """
    failures = 0
    while True:
        done = os.path.getsize(dest) if os.path.exists(dest) else 0
        headers = {"Range": f"bytes={done}-"} if done else {}
        try:
            with requests.get(url, headers=headers, stream=True, timeout=60) as response:
                if response.status_code == 416:
                    # The partial file already holds the whole download
                    return
                response.raise_for_status()
                if response.headers.get("Content-Type", "").startswith("text/html"):
                    raise RuntimeError(
                        f"Downloading {url} returned a web page instead of the data. If "
                        "it is a Google Drive file, share it as \"Anyone with the link\"."
                    )
                if response.status_code != 206:
                    # The server doesn't support resuming, so start over
                    done = 0
                length = int(response.headers.get("Content-Length", 0))
                total = done + length if length else 0
                with open(dest, "ab" if done else "wb") as f:
                    for chunk in response.iter_content(chunk_size=8 * 1024 * 1024):
                        f.write(chunk)
                        done += len(chunk)
                        failures = 0
                        message = f"{done / 1e6:,.0f} MB"
                        if total:
                            message += f" of {total / 1e6:,.0f} MB"
                        progress(f"Downloading cell towers from {source} ({message})...")
            if not total or done >= total:
                return
        except (
            requests.ConnectionError,
            requests.Timeout,
            requests.exceptions.ChunkedEncodingError,
        ) as e:
            failures += 1
            if failures > MAX_DOWNLOAD_RETRIES:
                raise
            progress(f"Download interrupted ({type(e).__name__}), resuming...")
            time.sleep(5)


def _is_gzip(path):
    with open(path, "rb") as f:
        return f.read(2) == b"\x1f\x8b"


def download_csv_from_url(url, dest, progress=_print):
    """Download the cell towers csv from a URL, which may be a Google Drive link"""
    source = "URL"
    drive_id = re.search(r"drive\.google\.com/.*(?:/d/|[?&]id=)([\w-]+)", url)
    if drive_id:
        # Direct download link that skips Drive's virus scan page for large files
        url = (
            "https://drive.usercontent.google.com/download"
            f"?id={drive_id.group(1)}&export=download&confirm=t"
        )
        source = "Google Drive"
    _download(url, dest, source, progress)


def load_operators():
    """Load network operator descriptions and status indexed by (mcc, net)"""
    codes = pd.read_json(MCC_MNC_JSON, dtype=False)
    codes["mcc"] = pd.to_numeric(codes["mcc"], errors="coerce")
    codes["net"] = pd.to_numeric(codes["mnc"], errors="coerce")
    codes = codes.dropna(subset=["mcc", "net"])
    # Description is the brand name, falling back to the operator name
    codes["Description"] = codes["brand"].fillna(codes["operator"])
    codes = codes.rename(columns={"status": "Status"})
    codes = codes.astype({"mcc": "int32", "net": "int32"})
    return codes.drop_duplicates(["mcc", "net"]).set_index(["mcc", "net"])[
        ["Description", "Status"]
    ]


def prepare_chunk(df, operators):
    """Filter, project, and annotate one chunk of the raw csv"""
    created = pd.to_datetime(df["created"], unit="s")
    # Filter out outliers created before 2003 or with dates in the future
    df = df[(created >= "2003") & (created <= pd.Timestamp.now())].copy()
    # Store created as integer nanoseconds since the epoch
    df["created"] = df["created"].astype("int64") * 1_000_000_000

    # Convert lon/lat to epsg:3857 (pseudo-mercator) so generated images can be
    # overlaid on a Mercator projected map
    df["x_3857"], df["y_3857"] = transformer_4326_to_3857.transform(
        df["lat"].values, df["lon"].values
    )

    # float32 is precise enough for plotting and halves the memory needed to load them
    for col in ["x_3857", "y_3857", "lat", "lon"]:
        df[col] = df[col].astype("float32")

    df = df.join(operators, on=["mcc", "net"])
    for col in ["radio", "Description", "Status"]:
        df[col] = df[col].astype("string")
    return df.reset_index(drop=True)


def download_and_prepare(dest, csv_url=DEFAULT_CSV_URL, progress=_print):
    """Download the cell towers csv from csv_url and write it to dest as a parquet directory"""
    csv_path = os.path.join(os.path.dirname(dest), PARTIAL_CSV)
    download_csv_from_url(csv_url, csv_path, progress)

    work_dir = tempfile.mkdtemp(prefix=WORK_DIR_PREFIX, dir=os.path.dirname(dest))
    try:
        progress("Processing cell towers...")
        compression = "gzip" if _is_gzip(csv_path) else None
        operators = load_operators()

        parquet_dir = os.path.join(work_dir, "cell_towers.parq")
        os.makedirs(parquet_dir)
        opener = gzip.open if compression else open
        with opener(csv_path, "rt") as f:
            has_header = f.readline().startswith("radio")
        reader = pd.read_csv(
            csv_path,
            compression=compression,
            header=0 if has_header else None,
            names=CSV_COLUMNS,
            usecols=list(CSV_DTYPES),
            dtype=CSV_DTYPES,
            chunksize=CHUNK_SIZE,
        )
        n_rows = 0
        for i, chunk in enumerate(reader):
            df = prepare_chunk(chunk, operators)
            df.to_parquet(os.path.join(parquet_dir, f"part.{i:03d}.parquet"), index=False)
            n_rows += len(df)
            progress(f"Processing cell towers ({n_rows:,} rows so far)...")

        # Only move the dataset into place once it is complete
        os.replace(parquet_dir, dest)
        os.remove(csv_path)
        progress(f"Saved {n_rows:,} cell towers to {dest}")
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    from dash_opencellid.data import DATA_DIR

    csv_url = os.getenv("CELL_TOWERS_CSV_URL", DEFAULT_CSV_URL)
    dest = sys.argv[1] if len(sys.argv) > 1 else os.path.join(DATA_DIR, "cell_towers.parq")
    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    if os.path.exists(dest):
        sys.exit(f"{dest} already exists, delete it first to download it again")
    download_and_prepare(dest, csv_url)
