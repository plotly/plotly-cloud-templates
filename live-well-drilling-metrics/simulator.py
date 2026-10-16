"""
Synthetic rig sensor data.

Each well is simulated once at import as a 48 hour run sampled every 2 seconds.
The live position in that run is derived from the wall clock, so every gunicorn
worker (and every browser tab) sees the same well at the same moment without
any shared state.
"""

import time
from dataclasses import dataclass

import numpy as np

SAMPLE_SECONDS = 2
RUN_HOURS = 48
N_SAMPLES = RUN_HOURS * 3600 // SAMPLE_SECONDS
# Live playback never goes back further than this, so charts always have history
MIN_HISTORY = 6 * 3600 // SAMPLE_SECONDS

STAND_FT = 93.0
STATES = ["Drilling", "Connection", "Circulating"]
DRILLING, CONNECTION, CIRCULATING = range(3)

# name, top (ft below the well's start depth), ROP factor, background gas (%), hardness
FORMATIONS = [
    ("Upper Shale", 0, 1.00, 0.6, 0.2),
    ("Sandstone A", 170, 1.45, 1.8, 0.1),
    ("Limestone", 330, 0.55, 0.4, 0.9),
    ("Marl", 470, 0.80, 0.7, 0.5),
    ("Lower Shale", 640, 0.85, 0.9, 0.4),
    ("Sandstone B", 820, 1.35, 2.0, 0.1),
    ("Dolomite", 960, 0.45, 0.3, 1.0),
    ("Siltstone", 1110, 0.95, 1.1, 0.3),
    ("Pay Sand", 1290, 1.30, 2.6, 0.2),
    ("Basal Shale", 1500, 0.90, 1.0, 0.4),
    ("Granite Wash", 1720, 0.60, 1.4, 0.8),
    ("Sandstone C", 1880, 1.40, 2.2, 0.1),
    ("Deep Shale", 2050, 0.90, 1.0, 0.4),
    ("Limestone B", 2200, 0.55, 0.4, 0.9),
]


@dataclass(frozen=True)
class Well:
    key: str
    name: str
    field: str
    rig: str
    start_depth: float
    seed: int


WELLS = [
    Well("raven", "Raven 14-2H", "Permian Basin", "Rig 27", 8150, 7),
    Well("granite", "Granite Ridge 7H", "Williston Basin", "Rig 41", 9420, 11),
    Well("fork", "Basin Fork 3", "Anadarko Basin", "Rig 12", 7380, 23),
]
WELLS_BY_KEY = {w.key: w for w in WELLS}

CHANNELS = [
    "bit_depth", "hole_depth", "rop", "wob", "rpm", "torque", "spp",
    "flow_in", "flow_out", "hookload", "pit_volume", "gas", "state", "formation",
]


def formation_at(depth_below_start):
    idx = 0
    for i, f in enumerate(FORMATIONS):
        if depth_below_start >= f[1]:
            idx = i
    return idx


def simulate(well):
    rng = np.random.default_rng(well.seed)
    n = N_SAMPLES
    out = {c: np.zeros(n) for c in CHANNELS}
    dt_hr = SAMPLE_SECONDS / 3600

    # A handful of scripted events per run, at seeded random times
    kick_starts = set(rng.choice(np.arange(MIN_HISTORY, n - 2000), 3, replace=False))
    packoff_starts = set(rng.choice(np.arange(MIN_HISTORY, n - 2000), 2, replace=False))

    hole = well.start_depth
    since_connection = rng.uniform(0, STAND_FT)
    state, state_left = DRILLING, 0
    rop_noise = wob_noise = tq_noise = gas_noise = 0.0
    hl_noise = spp_noise = rpm_noise = 0.0
    pit = 520.0
    kick_left = packoff_left = 0
    conn_gas = 0.0
    pump = 1.0

    for i in range(n):
        if i in kick_starts:
            kick_left = int(rng.uniform(8, 14) * 60 / SAMPLE_SECONDS)
        if i in packoff_starts:
            packoff_left = int(rng.uniform(3, 6) * 60 / SAMPLE_SECONDS)

        # State machine: drill a stand, make a connection, sometimes circulate
        if state != DRILLING:
            state_left -= 1
            if state_left <= 0:
                if state == CONNECTION:
                    conn_gas = rng.uniform(1.5, 3.5)  # trip gas after pumps come back on
                state = DRILLING
        elif since_connection >= STAND_FT:
            since_connection = 0
            if rng.random() < 0.15:
                state, state_left = CIRCULATING, int(rng.uniform(15, 30) * 60 / SAMPLE_SECONDS)
            else:
                state, state_left = CONNECTION, int(rng.uniform(5, 9) * 60 / SAMPLE_SECONDS)

        f_idx = formation_at(hole - well.start_depth)
        _, _, rop_factor, gas_base, hardness = FORMATIONS[f_idx]

        # Slowly varying AR(1) noise so curves look like real sensors, not white noise
        rop_noise = 0.995 * rop_noise + rng.normal(0, 0.9)
        wob_noise = 0.99 * wob_noise + rng.normal(0, 0.15)
        tq_noise = 0.98 * tq_noise + rng.normal(0, 0.1)
        gas_noise = 0.99 * gas_noise + rng.normal(0, 0.02)
        hl_noise = 0.98 * hl_noise + rng.normal(0, 0.15)
        spp_noise = 0.98 * spp_noise + rng.normal(0, 5)
        rpm_noise = 0.97 * rpm_noise + rng.normal(0, 0.4)

        on_bottom = state == DRILLING
        pump_target = 0.0 if state == CONNECTION and state_left > 60 else 1.0
        pump += (pump_target - pump) * 0.08

        wob = max(0.0, 26 + 4 * hardness + wob_noise) if on_bottom else 0.0
        rpm = (120 - 15 * hardness + rpm_noise + rng.normal(0, 0.3)) if state != CONNECTION else 0.0
        rop = max(0.0, (65 * rop_factor * (wob / 28) ** 0.8 + rop_noise)) if on_bottom else 0.0

        torque = 0.0
        if rpm > 0:
            torque = 6.5 + (0.18 * wob if on_bottom else 0) + tq_noise
            if hardness > 0.8 and on_bottom:
                # Stick-slip in hard rock shows up as a torque oscillation
                torque += 1.6 * np.sin(i / 6.0) + rng.normal(0, 0.2)

        flow_in = (680 + rng.normal(0, 1.5)) * pump
        spp = (3150 + 0.04 * (hole - 8000) + spp_noise + rng.normal(0, 4)) * pump**2
        flow_out = flow_in * (1 + rng.normal(0, 0.004))

        if packoff_left > 0:
            ramp = min(1.0, packoff_left / 60)
            spp += 420 * ramp * pump
            torque += 4.5 * ramp if rpm > 0 else 0
            rop *= 0.4
            packoff_left -= 1

        # Pit level falls as new hole is filled with mud, rises on an influx
        pit -= rop * dt_hr * 0.07  # 8.5" hole takes about 0.07 bbl of mud per ft
        if kick_left > 0:
            flow_out *= 1.09
            pit += 0.045 * pump
            gas_noise += 0.05
            kick_left -= 1
        pit += rng.normal(0, 0.02)
        if pit < 470 and state == CIRCULATING and rng.random() < 0.01:
            pit += 40  # mud engineer tops up the active system

        string_weight = 0.026 * hole + 12
        hookload = string_weight - wob + hl_noise + rng.normal(0, 0.1)
        if state == CONNECTION:
            hookload = 30 + rng.normal(0, 0.4)  # string in the slips, only the blocks hang

        conn_gas *= 0.997
        gas = max(0.05, gas_base + gas_noise + conn_gas * pump) if pump > 0.2 else 0.05

        hole += rop * dt_hr
        since_connection += rop * dt_hr

        values = (
            hole if on_bottom else hole - (8 if state == CONNECTION else 2),
            hole, rop, wob, rpm, torque, spp, flow_in, flow_out, hookload, pit, gas,
            state, f_idx,
        )
        for c, v in zip(CHANNELS, values):
            out[c][i] = v

    return out


DATA = {w.key: simulate(w) for w in WELLS}


def live_index(now=None):
    """Index of the 'current' sample, looping over the run but never inside the first MIN_HISTORY."""
    now = time.time() if now is None else now
    tick = int(now // SAMPLE_SECONDS)
    return MIN_HISTORY + tick % (N_SAMPLES - MIN_HISTORY)


def window(well_key, seconds, now=None):
    """Return (timestamps, channels) for the last `seconds` of data ending at the live sample."""
    now = time.time() if now is None else now
    end = live_index(now) + 1
    start = max(0, end - seconds // SAMPLE_SECONDS)
    data = DATA[well_key]
    ages = (end - 1 - np.arange(start, end)) * SAMPLE_SECONDS
    stamps = (np.floor(now / SAMPLE_SECONDS) * SAMPLE_SECONDS - ages).astype("datetime64[s]")
    return stamps, {c: v[start:end] for c, v in data.items()}
