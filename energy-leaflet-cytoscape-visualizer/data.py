"""Synthetic data generation for the BT (low-voltage) network demo.

Builds a handful of fake distribution-network trees (one per transformer)
with realistic-looking lat/lon positions, plus synthetic hourly load
curves for every connection point (PR - Point de Raccordement).

Everything is deterministic (seeded) so the app looks the same on every run.
"""
import math
import random

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Transformer metadata (shown in the search box on the left)
# ---------------------------------------------------------------------------
TRANSFO_META = {
    "IDM_K7G2R": {
        "note": None,
        "base": (45.5230, -73.5820),  # Plateau-Mont-Royal, Montreal
        "n_nodes": 11,
        "also_pr": False,
    },
    "IDM_H7Y8R": {
        "note": "transformer and PR on the same node",
        "base": (45.5450, -73.5800),  # Rosemont, Montreal
        "n_nodes": 9,
        "also_pr": True,
    },
    "IDM_9X3LQ": {
        "note": None,
        "base": (45.4590, -73.5680),  # Verdun, Montreal
        "n_nodes": 14,
        "also_pr": False,
    },
    "IDM_3F9PL": {
        "note": None,
        "base": (45.5240, -73.6050),  # Mile End, Montreal
        "n_nodes": 7,
        "also_pr": False,
    },
    "IDM_Q2N6Z": {
        "note": "large feeder, many downstream PRs",
        "base": (45.5480, -73.5560),  # Hochelaga-Maisonneuve, Montreal
        "n_nodes": 19,
        "also_pr": False,
    },
}

CONDUCTOR_TYPES = ["Alu 50mm2", "Alu 95mm2", "Cu 95mm2", "Cu 150mm2"]

EARTH_RADIUS_M = 6378137.0


def _local_to_latlon(base_lat, base_lon, dx_m, dy_m):
    """Offset (in meters) from a base lat/lon -> new lat/lon."""
    dlat = (dy_m / EARTH_RADIUS_M) * (180.0 / math.pi)
    dlon = (dx_m / (EARTH_RADIUS_M * math.cos(math.radians(base_lat)))) * (
        180.0 / math.pi
    )
    return base_lat + dlat, base_lon + dlon


def _random_tree(rng, n_total):
    """Return {child_index: parent_index} for a uniform random recursive tree."""
    parent = {0: None}
    for i in range(1, n_total):
        p = rng.randint(0, i - 1)
        parent[i] = p
    return parent


def _gen_pr_id(rng, used):
    while True:
        pid = str(rng.randint(100000, 999999))
        if pid not in used:
            used.add(pid)
            return pid


def build_transfo_elements(transfo_id, meta, seed):
    """Build the cytoscape elements (nodes + edges) for one transformer's subtree."""
    rng = random.Random(seed)
    n_total = meta["n_nodes"]
    parent = _random_tree(rng, n_total)

    children = {i: [] for i in range(n_total)}
    for child, p in parent.items():
        if p is not None:
            children[p].append(child)

    # local xy layout: root at origin, children fan out generally eastwards
    xy = {0: (0.0, 0.0)}
    order = sorted(parent.keys())
    for i in order[1:]:
        p = parent[i]
        px, py = xy[p]
        dx = rng.uniform(25, 55)
        dy = rng.uniform(-30, 30)
        xy[i] = (px + dx, py + dy)

    base_lat, base_lon = meta["base"]
    used_ids = set()
    node_id = {}
    node_kind = {}

    elements = []
    for i in order:
        dx, dy = xy[i]
        lat, lon = _local_to_latlon(base_lat, base_lon, dx, dy)
        if i == 0:
            nid = transfo_id
            kind = "transfo"
        else:
            is_leaf = len(children[i]) == 0
            kind = "pr" if is_leaf else rng.choice(["pole", "pole", "pr"])
            nid = _gen_pr_id(rng, used_ids) if kind == "pr" else f"N{seed}{i:02d}"
        node_id[i] = nid
        node_kind[i] = kind
        data = {"id": nid, "label": nid, "kind": kind, "lat": lat, "lon": lon}
        if kind == "transfo" and meta.get("also_pr"):
            data["also_pr"] = True
        elements.append({"data": data})

    for i in order[1:]:
        p = parent[i]
        eid = f"e-{node_id[p]}-{node_id[i]}"
        elements.append(
            {
                "data": {
                    "id": eid,
                    "source": node_id[p],
                    "target": node_id[i],
                    "kind": "conductor",
                    "length_m": round(math.hypot(*[a - b for a, b in zip(xy[i], xy[p])]), 1),
                    "conductor_type": rng.choice(CONDUCTOR_TYPES),
                }
            }
        )

    return elements


def build_network():
    """Return {transfo_id: elements} for every transformer in TRANSFO_META."""
    network = {}
    for seed, (tid, meta) in enumerate(TRANSFO_META.items()):
        network[tid] = build_transfo_elements(tid, meta, seed=seed + 1)
    return network


def all_pr_ids(network):
    ids = []
    for elements in network.values():
        for el in elements:
            d = el["data"]
            if "source" in d:
                continue
            if d.get("kind") == "pr" or d.get("also_pr"):
                ids.append(d["id"])
    return ids


def build_load_curves(pr_ids, start="2022-06-01", end="2023-05-31", freq="30min", seed=0):
    """Synthetic half-hourly load curves (kVA) for every PR, June 2022 - May 2023."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start=start, end=end, freq=freq, inclusive="left")
    n = len(idx)

    hour = idx.hour.values + idx.minute.values / 60.0
    day_of_year = idx.dayofyear.values

    # winter (heating) ramp: higher consumption from ~Nov to ~Mar
    winter_factor = 1 + 1.4 * np.clip(
        np.cos(2 * np.pi * (day_of_year - 15) / 365.0), 0, None
    )
    daily_pattern = 1 + 0.6 * np.exp(-((hour - 12.5) ** 2) / (2 * 4.0 ** 2)) + 0.5 * np.exp(
        -((hour - 20) ** 2) / (2 * 2.5 ** 2)
    )

    data = {}
    for pid in pr_ids:
        base = rng.uniform(2.5, 6.5)
        noise = rng.normal(0, 0.6, size=n)
        walk = np.cumsum(rng.normal(0, 0.03, size=n))
        walk -= walk.mean()
        series = base * daily_pattern * winter_factor + noise + walk
        spikes_idx = rng.choice(n, size=max(1, n // 900), replace=False)
        series[spikes_idx] += rng.uniform(8, 25, size=len(spikes_idx))
        series = np.clip(series, 0.1, None)
        data[pid] = series

    return pd.DataFrame(data, index=idx)
