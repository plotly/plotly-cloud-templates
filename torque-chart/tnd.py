"""
Synthetic torque and drag model for one made-up well.

A soft-string model (Johancsik) is run along a 2D build-and-hold trajectory for
every bit depth and a grid of friction factors. It returns surface hookload for
pick-up, slack-off and rotating off bottom, and off-bottom rotating torque.
The "measured" rig readings are generated from the same model with known
friction factors plus noise, and a tight-hole section from 10,250 ft.

The rig is "live": the bit drills from 8,000 ft to near TD on a loop driven by
the wall clock, so every worker and browser tab sees the same moment, and a
reading lands each time a stand is drilled down.
"""

import time

import numpy as np

WELL = {
    "name": "Kestrel 14H",
    "field": "Harrow Basin",
    "rig": "Rig 7 · Top drive",
    "section": "8½ in hole",
    "mud": "10.5 ppg OBM",
    "string": "5 in 19.5# S-135 DP",
    "bha": "RSS · 6¾ in collars",
    "model": "Soft string · Johancsik",
}

TD = 12_000  # planned section TD, ft MD
LOOP_START, LOOP_END = 8_000, 11_950  # live bit depth range, ft MD
LOOP_SECONDS = 900  # one pass from LOOP_START to LOOP_END
STAND = 93.0  # ft drilled between readings
TIGHT_FROM = 10_250  # drag starts climbing here
SHOE = 4_850  # 9⅝ in casing shoe
BLOCK = 45.0  # travelling block weight, klbf
MAKEUP_LIMIT = 27.0  # 5 in DP tool joint make-up torque, kft-lbf
BF = 1 - 10.5 / 65.5  # buoyancy factor in 10.5 ppg mud
TJ_RADIUS = 6.625 / 2 / 12  # tool joint radius, ft
FF_FAN = (0.10, 0.20, 0.30, 0.40, 0.50)
FF_GRID = np.round(np.arange(0.10, 0.501, 0.01), 2)

DS = 25.0
md = np.arange(0, TD + DS, DS)
bit_depths = np.arange(0, TD + 100, 100.0)


def _inclination(s):
    """Vertical to 2,500 ft, build to 58°, hold, then a second build to 72°."""
    inc = np.clip((s - 2_500) * 2.5 / 100, 0, 58)
    inc += np.clip((s - 9_400) * 1.5 / 100, 0, 14)
    return np.radians(inc)


inc = _inclination(md)
tvd = np.concatenate([[0], np.cumsum(DS * np.cos((inc[1:] + inc[:-1]) / 2))])


def _air_weight(from_bit):
    """Pipe weight in lb/ft by distance above the bit."""
    return np.where(from_bit < 300, 98.0, np.where(from_bit < 900, 49.3, 21.9))


def _run(ff, bottom_load=0.0):
    """Surface loads for each bit depth. ff is an array of friction factors."""
    ff = np.asarray(ff, dtype=float)[:, None]
    n = len(bit_depths)
    pu, so, rot, tq = (np.zeros((ff.shape[0], n)) for _ in range(4))
    for j, depth in enumerate(bit_depths):
        k = int(depth // DS)
        t_pu = np.full(ff.shape, bottom_load)
        t_so = t_pu.copy()
        t_rot = 0.0
        torque = np.zeros(ff.shape)
        for i in range(k, 0, -1):
            ia = (inc[i] + inc[i - 1]) / 2
            di = inc[i] - inc[i - 1]
            w = _air_weight(depth - (md[i] - DS / 2)) * BF * DS
            axial = w * np.cos(ia)
            lateral = w * np.sin(ia)
            n_rot = abs(t_rot * di + lateral)
            t_pu = t_pu + axial + ff * np.abs(t_pu * di + lateral)
            t_so = t_so + axial - ff * np.abs(t_so * di + lateral)
            t_rot = t_rot + axial
            torque = torque + ff * n_rot * TJ_RADIUS
        pu[:, j], so[:, j], rot[:, j], tq[:, j] = t_pu[:, 0], t_so[:, 0], t_rot, torque[:, 0]
    return {
        "pick_up": pu / 1000 + BLOCK,
        "slack_off": so / 1000 + BLOCK,
        "rotating": rot[0] / 1000 + BLOCK,
        "torque": tq / 1000,
    }


def _helical_limit():
    """Hookload below which the 5 in DP buckles helically in the tangent while slacking off."""
    e, i_dp = 30e6, np.pi / 64 * (5**4 - 4.276**4)
    w = 19.5 * BF / 12
    rc = (8.5 - 5.0) / 2
    f_hel = 2 * np.sqrt(2) * np.sqrt(e * i_dp * w * np.sin(np.radians(58)) / rc)
    hook = _run([0.30], bottom_load=-f_hel)["slack_off"][0]
    return np.clip(hook, BLOCK, None), f_hel / 1000


GRID = _run(FF_GRID)
BUCKLING, F_HELICAL = _helical_limit()


def curve(kind, ff):
    """One curve from the precomputed grid, nearest 0.01 friction factor."""
    i = int(np.argmin(np.abs(FF_GRID - ff)))
    return GRID[kind][i] if kind != "rotating" else GRID["rotating"]


def _at(kind, ff, depths):
    """Interpolate the model at arbitrary depths and (per-depth) friction factors."""
    ff = np.broadcast_to(ff, depths.shape)
    out = np.empty_like(depths)
    for n, (d, f) in enumerate(zip(depths, ff)):
        lo = int(np.clip(np.searchsorted(FF_GRID, f) - 1, 0, len(FF_GRID) - 2))
        t = (f - FF_GRID[lo]) / (FF_GRID[lo + 1] - FF_GRID[lo])
        a = np.interp(d, bit_depths, GRID[kind][lo])
        b = np.interp(d, bit_depths, GRID[kind][lo + 1])
        out[n] = a + t * (b - a)
    return out


def _measured():
    rng = np.random.default_rng(14)
    depth = np.arange(2_000, TD, STAND)
    # The hole starts packing off below TIGHT_FROM: drag on pick-up climbs
    tight = np.clip((depth - TIGHT_FROM) / 650, 0, 1) ** 1.6
    ff_pu = 0.24 + 0.15 * tight + rng.normal(0, 0.012, depth.size)
    ff_so = 0.31 + 0.03 * tight + rng.normal(0, 0.012, depth.size)
    ff_tq = 0.26 + 0.08 * tight + rng.normal(0, 0.012, depth.size)
    rot = np.interp(depth, bit_depths, GRID["rotating"]) + rng.normal(0, 1.2, depth.size)
    return {
        "depth": depth,
        "pick_up": _at("pick_up", ff_pu, depth) + rng.normal(0, 1.5, depth.size),
        "slack_off": _at("slack_off", ff_so, depth) + rng.normal(0, 1.5, depth.size),
        "rotating": rot,
        "torque": _at("torque", ff_tq, depth) + rng.normal(0, 0.25, depth.size),
    }


MEASURED = _measured()


def live(now=None):
    """Bit depth right now, how many readings are in, and seconds since the last one."""
    t = (time.time() if now is None else now) % LOOP_SECONDS
    rate = (LOOP_END - LOOP_START) / LOOP_SECONDS  # ft per second
    bit = LOOP_START + t * rate
    n = int(np.searchsorted(MEASURED["depth"], bit, side="right"))
    ago = (bit - MEASURED["depth"][n - 1]) / rate
    return bit, n, ago


def fit(kind, n, min_depth=SHOE, max_depth=np.inf):
    """Friction factor on the grid that best matches the first n readings between the two depths."""
    depth = MEASURED["depth"][:n]
    m = (depth >= min_depth) & (depth <= max_depth)
    d, y = depth[m], MEASURED[kind][:n][m]
    sse = [np.sum((np.interp(d, bit_depths, GRID[kind][i]) - y) ** 2) for i in range(len(FF_GRID))]
    return float(FF_GRID[int(np.argmin(sse))])
