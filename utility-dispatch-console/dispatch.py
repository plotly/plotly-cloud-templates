"""
Synthetic service territory, crews and work for a made-up electric utility,
plus the dispatch simulation the app drives.

The network (substations, feeders, critical facilities) is fixed and built once
at import. Everything that changes during a shift (jobs, crews, the clock) lives
in a plain JSON-able dict so it can sit in a dcc.Store and be advanced one tick
at a time by pure functions.
"""

import math

import numpy as np

UTILITY = "Cedar Valley Power"
SHIFT_START_HOUR = 6  # sim minute 0 is 06:00
SHIFT_END = 12 * 60  # crews are scheduled 06:00 to 18:00, later is overtime
DAY_END = 18 * 60  # the sim stops at 24:00
SPEED_KMH = 42
ROAD_FACTOR = 1.35  # straight-line to road distance

CENTER = (41.595, -93.625)
KM_LAT = 1 / 111.0
KM_LON = 1 / (111.0 * math.cos(math.radians(CENTER[0])))

PRIORITIES = {
    1: "P1 Emergency",
    2: "P2 Major outage",
    3: "P3 Outage",
    4: "P4 Planned",
}

SKILLS = ["Troubleshooter", "Line crew", "Vegetation", "Underground", "Service tech"]

STREETS = [
    "Ingersoll Ave", "Grand Ave", "Fleur Dr", "Hickman Rd", "Euclid Ave", "Army Post Rd",
    "Merle Hay Rd", "SE 14th St", "University Ave", "Douglas Ave", "Beaver Ave", "Park Ave",
    "Indianola Ave", "Easton Blvd", "Keo Way", "Polk Blvd", "Hubbell Ave", "Aurora Ave",
    "Forest Ave", "Bell Ave", "McKinley Ave", "Ashworth Rd", "Clark St", "Valley View Dr",
]

CAUSES = {
    "Tree contact": 0.30,
    "Equipment failure": 0.22,
    "Animal": 0.14,
    "Vehicle hit pole": 0.08,
    "Lightning": 0.10,
    "Unknown": 0.16,
}
STORM_CAUSES = {"Tree contact": 0.45, "Lightning": 0.25, "Equipment failure": 0.12, "Unknown": 0.18}

# Outage device: (share of outages, share in a storm, repair minutes range, crews that can take it)
DEVICES = {
    "Transformer": (0.40, 0.25, (50, 110), ["Troubleshooter", "Line crew"]),
    "Fuse": (0.35, 0.35, (40, 90), ["Troubleshooter", "Line crew"]),
    "Recloser": (0.18, 0.28, (90, 170), ["Line crew", "Troubleshooter"]),
    "Breaker": (0.07, 0.12, (120, 220), ["Line crew"]),
}

# Planned work: (minutes range, crews that can take it, weight)
ORDER_TYPES = {
    "Pole replacement": ((150, 220), ["Line crew"], 2),
    "Vegetation trim": ((90, 160), ["Vegetation"], 3),
    "Transformer inspection": ((30, 60), ["Troubleshooter"], 3),
    "New service connect": ((45, 90), ["Service tech", "Troubleshooter"], 3),
    "Meter exchange": ((20, 40), ["Service tech"], 3),
    "Underground cable repair": ((120, 200), ["Underground"], 2),
    "Streetlight repair": ((30, 50), ["Service tech", "Troubleshooter"], 2),
}

CREW_ROSTER = [
    ("T-101", "Troubleshooter", "Okafor", 1),
    ("T-102", "Troubleshooter", "Lindqvist", 1),
    ("T-103", "Troubleshooter", "Ramirez", 1),
    ("T-104", "Troubleshooter", "Haddad", 1),
    ("L-201", "Line crew", "Brennan", 4),
    ("L-202", "Line crew", "Nguyen", 3),
    ("L-203", "Line crew", "Castellanos", 4),
    ("L-204", "Line crew", "Whitfield", 3),
    ("V-301", "Vegetation", "Kowalski", 3),
    ("V-302", "Vegetation", "Abara", 2),
    ("U-401", "Underground", "Petrov", 3),
    ("S-501", "Service tech", "Delgado", 1),
    ("S-502", "Service tech", "Yamamoto", 1),
]

SERVICE_CENTERS = {
    "North yard": (41.660, -93.640),
    "South yard": (41.535, -93.600),
}


def clock(t):
    """Sim minutes since 06:00 as a 24h clock string."""
    m = int(round(SHIFT_START_HOUR * 60 + t))
    return f"{(m // 60) % 24:02d}:{m % 60:02d}"


def offset(p, dx_km, dy_km):
    return (p[0] + dy_km * KM_LAT, p[1] + dx_km * KM_LON)


def km_between(a, b):
    dy = (a[0] - b[0]) / KM_LAT
    dx = (a[1] - b[1]) / KM_LON
    return math.hypot(dx, dy)


def travel_minutes(a, b):
    return km_between(a, b) * ROAD_FACTOR / SPEED_KMH * 60


# ---------------------------------------------------------------------------
# Network, built once
# ---------------------------------------------------------------------------

def _build_network():
    rng = np.random.default_rng(11)
    subs = {
        "Saylor": offset(CENTER, -1.0, 6.5),
        "Highland": offset(CENTER, 2.6, 2.4),
        "Westover": offset(CENTER, -6.5, 1.0),
        "Riverbend": offset(CENTER, 1.4, -1.6),
        "Easton": offset(CENTER, 7.4, 0.6),
        "Fort Des": offset(CENTER, -3.0, -6.0),
        "Pleasant": offset(CENTER, 5.2, -5.6),
    }
    feeders = {}
    for si, (sub, p0) in enumerate(subs.items()):
        base = rng.uniform(0, 2 * math.pi)
        for fi, letter in enumerate("ABC"):
            ang = base + fi * 2 * math.pi / 3 + rng.normal(0, 0.25)
            pts = [p0]
            n = int(rng.integers(11, 16))
            for _ in range(n):
                ang += rng.normal(0, 0.22)
                step = rng.uniform(0.35, 0.6)
                pts.append(offset(pts[-1], step * math.cos(ang), step * math.sin(ang)))
            density = rng.uniform(40, 150)
            seg_cust = [0] + [int(rng.normal(density, density * 0.25)) for _ in range(n)]
            name = f"{sub[:2].upper()}-{si + 1}{letter}"
            feeders[name] = {"sub": sub, "pts": pts, "cust": [max(c, 5) for c in seg_cust]}
    names = list(feeders)
    critical = []
    for label, kind in [
        ("Mercy Medical Center", "Hospital"), ("Broadlawns Hospital", "Hospital"),
        ("Fleur Dr water pumping", "Water"), ("Maple Ridge care home", "Care home"),
        ("Emergency ops center", "Emergency"), ("Oak Park care home", "Care home"),
        ("Saylor lift station", "Water"),
    ]:
        f = names[int(rng.integers(len(names)))]
        idx = int(rng.integers(4, len(feeders[f]["pts"])))
        critical.append({"name": label, "kind": kind, "feeder": f, "idx": idx, "pt": feeders[f]["pts"][idx]})
    return subs, feeders, critical


SUBSTATIONS, FEEDERS, CRITICAL = _build_network()
TOTAL_CUSTOMERS = sum(sum(f["cust"]) for f in FEEDERS.values())
FEEDER_NAMES = list(FEEDERS)


def downstream(feeder, idx):
    """Customers and critical facilities fed from point idx onward on a feeder's main line."""
    f = FEEDERS[feeder]
    cust = sum(f["cust"][idx + 1:]) if idx < len(f["pts"]) - 1 else f["cust"][-1]
    crit = [c["name"] for c in CRITICAL if c["feeder"] == feeder and c["idx"] >= idx]
    return cust, crit


# ---------------------------------------------------------------------------
# Jobs and crews
# ---------------------------------------------------------------------------

def _pick(rng, weights):
    keys = list(weights)
    p = np.array([weights[k] for k in keys], dtype=float)
    return keys[int(rng.choice(len(keys), p=p / p.sum()))]


def _address(rng):
    return f"{int(rng.integers(1, 60)) * 100 + int(rng.integers(0, 99))} {STREETS[int(rng.integers(len(STREETS)))]}"


def priority_of(job):
    if job["kind"] == "order":
        return 4
    if job["hazard"] or job["critical"]:
        return 1
    return 2 if job["customers"] >= 500 else 3


def new_outage(state, rng, t, storm=False):
    device = _pick(rng, {k: v[1] if storm else v[0] for k, v in DEVICES.items()})
    feeder = FEEDER_NAMES[int(rng.integers(len(FEEDER_NAMES)))]
    f = FEEDERS[feeder]
    n = len(f["pts"])
    if device == "Breaker":
        idx = 0
    elif device == "Recloser":
        idx = int(rng.integers(n // 3, 2 * n // 3))
    else:
        idx = int(rng.integers(1, n))
    if device in ("Breaker", "Recloser"):
        pt = f["pts"][idx]
        customers, critical = downstream(feeder, idx)
    else:
        pt = offset(f["pts"][idx], rng.normal(0, 0.25), rng.normal(0, 0.25))
        customers = int(rng.integers(60, 320)) if device == "Fuse" else int(rng.integers(4, 32))
        critical = []
    cause = _pick(rng, STORM_CAUSES if storm else CAUSES)
    hazard = bool(rng.random() < (0.10 if device in ("Transformer", "Fuse") else 0.25)) or cause == "Vehicle hit pole"
    lo, hi = DEVICES[device][2]
    state["next_out"] += 1
    job = {
        "id": f"OUT-{state['next_out']}",
        "kind": "outage",
        "type": f"{device} outage",
        "device": f"{device[0]}-{feeder[-2:]}{idx:02d}",
        "feeder": feeder,
        "idx": idx,
        "main_line": device in ("Breaker", "Recloser"),
        "lat": pt[0],
        "lon": pt[1],
        "address": _address(rng),
        "cause": cause,
        "hazard": hazard,
        "customers": customers,
        "out": customers,
        "critical": critical,
        "skills": DEVICES[device][3],
        "duration": int(rng.integers(lo, hi)) + (30 if hazard else 0),
        "created": t,
        "due": None,
        "status": "Unassigned",
        "crew": None,
        "dispatched": None,
        "arrive": None,
        "done": None,
        "note": "Wire down reported, keep public clear" if hazard else "",
    }
    job["priority"] = priority_of(job)
    return job


def new_order(state, rng, t):
    otype = _pick(rng, {k: v[2] for k, v in ORDER_TYPES.items()})
    (lo, hi), skills, _ = ORDER_TYPES[otype]
    feeder = FEEDER_NAMES[int(rng.integers(len(FEEDER_NAMES)))]
    f = FEEDERS[feeder]
    pt = offset(f["pts"][int(rng.integers(1, len(f["pts"])))], rng.normal(0, 0.3), rng.normal(0, 0.3))
    state["next_wo"] += int(rng.integers(3, 40))
    return {
        "id": f"WO-{state['next_wo']}",
        "kind": "order",
        "type": otype,
        "device": "",
        "feeder": feeder,
        "idx": None,
        "main_line": False,
        "lat": pt[0],
        "lon": pt[1],
        "address": _address(rng),
        "cause": "",
        "hazard": False,
        "customers": 0,
        "out": 0,
        "critical": [],
        "skills": skills,
        "duration": int(rng.integers(lo, hi)),
        "created": t - int(rng.integers(60, 60 * 24 * 5)),
        "due": int(rng.integers(5, 11)) * 60,  # due by 11:00 to 17:00
        "status": "Unassigned",
        "crew": None,
        "dispatched": None,
        "arrive": None,
        "done": None,
        "note": "",
        "priority": 4,
    }


def _new_crews(rng):
    crews = []
    yards = list(SERVICE_CENTERS.values())
    for i, (cid, skill, lead, size) in enumerate(CREW_ROSTER):
        home = yards[i % 2]
        p = offset(home, rng.normal(0, 0.2), rng.normal(0, 0.2))
        crews.append({
            "id": cid, "skill": skill, "lead": lead, "size": size,
            "lat": p[0], "lon": p[1], "status": "Available", "job": None,
            "from": None, "log": [],
        })
    return crews


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def crew_free_at(crew, jobs_by_id, t):
    """When the crew finishes what it is doing now, and where it will be."""
    if crew["status"] == "Available":
        return t, (crew["lat"], crew["lon"])
    j = jobs_by_id[crew["job"]]
    work_end = (j["arrive"] if j["arrive"] is not None else t + travel_minutes((crew["lat"], crew["lon"]), (j["lat"], j["lon"]))) + j["duration"]
    return max(work_end, t), (j["lat"], j["lon"])


def recommend(state, job_id, n=6):
    """Crews that can take a job, ranked by how soon they could be on site."""
    jobs = {j["id"]: j for j in state["jobs"]}
    job = jobs[job_id]
    t = state["t"]
    out = []
    for c in state["crews"]:
        if c["skill"] not in job["skills"] or c["job"] == job_id:
            continue
        free, where = crew_free_at(c, jobs, t)
        travel = travel_minutes(where, (job["lat"], job["lon"]))
        eta = free - t + travel
        finish = t + eta + job["duration"]
        # first-listed skill is the preferred one for the job
        fit = "Preferred" if c["skill"] == job["skills"][0] else "Can cover"
        out.append({
            "crew": c["id"], "lead": c["lead"], "skill": c["skill"], "size": c["size"], "status": c["status"],
            "eta": eta, "travel": travel, "km": km_between(where, (job["lat"], job["lon"])) * ROAD_FACTOR,
            "finish": finish, "overtime": finish > SHIFT_END, "fit": fit,
            "available": c["status"] == "Available",
        })
    out.sort(key=lambda r: (not r["available"], r["eta"] + (15 if r["fit"] != "Preferred" else 0)))
    return out[:n]


def dispatch(state, job_id, crew_id):
    jobs = {j["id"]: j for j in state["jobs"]}
    crews = {c["id"]: c for c in state["crews"]}
    job, crew = jobs.get(job_id), crews.get(crew_id)
    if not job or not crew or crew["status"] != "Available" or job["status"] != "Unassigned":
        return state
    t = state["t"]
    travel = travel_minutes((crew["lat"], crew["lon"]), (job["lat"], job["lon"]))
    job.update(status="Dispatched", crew=crew_id, dispatched=t, arrive=t + max(travel, 3))
    crew.update(status="En route", job=job_id, **{"from": [crew["lat"], crew["lon"], t]})
    crew["log"].append({"job": job_id, "priority": job["priority"], "start": t, "arrive": job["arrive"],
                        "end": None, "eta_end": job["arrive"] + job["duration"]})
    state["events"].insert(0, [t, f"{crew_id} dispatched to {job_id} · ETA {clock(job['arrive'])}"])
    return state


def recall(state, job_id):
    """Send an en-route crew back to available, the job goes back in the queue."""
    jobs = {j["id"]: j for j in state["jobs"]}
    job = jobs.get(job_id)
    if not job or job["status"] != "Dispatched":
        return state
    crew = next(c for c in state["crews"] if c["id"] == job["crew"])
    crew.update(status="Available", job=None, **{"from": None})
    crew["log"] = [e for e in crew["log"] if e["job"] != job_id]
    state["events"].insert(0, [state["t"], f"{crew['id']} recalled from {job_id}"])
    job.update(status="Unassigned", crew=None, dispatched=None, arrive=None)
    return state


def queue_order(job, t):
    """Sort key for the dispatch queue: priority, then most customers, then oldest."""
    due_soon = job["kind"] == "order" and job["due"] is not None and job["due"] - t < 120
    return (job["priority"] - (0.5 if due_soon else 0), -job["out"], job["created"])


def auto_assign(state, max_priority=4):
    """Greedy: highest-priority unassigned job gets the soonest available crew that can do it."""
    t = state["t"]
    open_jobs = sorted((j for j in state["jobs"] if j["status"] == "Unassigned" and j["priority"] <= max_priority),
                       key=lambda j: queue_order(j, t))
    n = 0
    for job in open_jobs:
        best = [r for r in recommend(state, job["id"], n=20) if r["available"] and r["eta"] < 75]
        if best:
            dispatch(state, job["id"], best[0]["crew"])
            n += 1
    if n:
        state["events"].insert(0, [t, f"Auto-assign placed {n} job{'s' if n > 1 else ''}"])
    return state


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

def customers_out(state):
    return sum(j["out"] for j in state["jobs"] if j["kind"] == "outage" and j["status"] != "Restored")


def tick(state, dt):
    if state["t"] >= DAY_END:
        return state
    t0, t1 = state["t"], min(state["t"] + dt, DAY_END)
    jobs = {j["id"]: j for j in state["jobs"]}
    state["cmi"] += customers_out(state) * (t1 - t0)

    for c in state["crews"]:
        if c["status"] == "En route":
            j = jobs[c["job"]]
            if t1 >= j["arrive"]:
                c.update(status="On site", lat=j["lat"], lon=j["lon"], **{"from": None})
                j["status"] = "On site"
                if j["main_line"] and j["out"] > 300:
                    # crew isolates the fault and switches the healthy part back on
                    restored = int(j["out"] * 0.55)
                    j["out"] -= restored
                    j["note"] = f"Switched {restored:,} customers back on by isolating the fault"
                    state["events"].insert(0, [j["arrive"], f"{c['id']} on site at {j['id']}, switched {restored:,} back on"])
                else:
                    state["events"].insert(0, [j["arrive"], f"{c['id']} on site at {j['id']}"])
            else:
                f = c["from"]
                frac = (t1 - f[2]) / max(j["arrive"] - f[2], 1e-6)
                c["lat"] = f[0] + (j["lat"] - f[0]) * frac
                c["lon"] = f[1] + (j["lon"] - f[1]) * frac
        if c["status"] == "On site":
            j = jobs[c["job"]]
            if t1 >= j["arrive"] + j["duration"]:
                end = j["arrive"] + j["duration"]
                j.update(status="Restored" if j["kind"] == "outage" else "Complete", done=end, out=0)
                c.update(status="Available", job=None)
                for e in c["log"]:
                    if e["job"] == j["id"]:
                        e["end"] = end
                verb = "restored" if j["kind"] == "outage" else "completed"
                state["events"].insert(0, [end, f"{j['id']} {verb} by {c['id']}"])

    # new trouble calls
    rng = np.random.default_rng([state["seed"], int(t1 * 10)])
    rate = (0.11 if state["storm"] else 0.025) * (t1 - t0)
    for _ in range(int(rng.poisson(rate))):
        job = new_outage(state, rng, t1, storm=state["storm"])
        state["jobs"].append(job)
        state["events"].insert(0, [t1, f"New {job['type'].lower()} {job['id']} on {job['feeder']} · {job['out']:,} out"])

    if state.get("storm_until") is not None and t1 >= state["storm_until"]:
        state.update(storm=False, storm_until=None)
        state["events"].insert(0, [t1, "Thunderstorm warning expired"])

    state["t"] = t1
    state["history"].append([t1, customers_out(state)])
    # drop finished jobs that are more than 3 hours old so the store stays small
    state["jobs"] = [j for j in state["jobs"] if j["done"] is None or t1 - j["done"] < 180]
    state["events"] = sorted(state["events"], key=lambda e: -e[0])[:40]
    return state


def initial_state(seed=4):
    rng = np.random.default_rng(seed)
    state = {"seed": seed, "t": 0, "storm": False, "cmi": 0.0, "next_out": 3180, "next_wo": 58200,
             "jobs": [], "crews": _new_crews(rng), "history": [[0, 0]], "events": []}
    for _ in range(14):
        state["jobs"].append(new_order(state, rng, 0))
    for _ in range(4):
        state["jobs"].append(new_outage(state, rng, -int(rng.integers(5, 50))))
    # the overnight backlog went out with the first crews of the day
    auto_assign(state)
    state["history"] = [[0, customers_out(state)]]
    # run the first 90 minutes of the shift, a squall line rolls in at 07:00
    for step in range(18):
        state["storm"] = 12 <= step
        tick(state, 5)
        if step % 4 == 0:
            auto_assign(state, max_priority=2)
    state.update(storm=True, storm_until=270)
    state["events"].insert(0, [state["t"], "Severe thunderstorm warning for the territory until 10:30"])
    return state
