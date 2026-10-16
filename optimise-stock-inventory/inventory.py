"""
Synthetic catalogue and the reorder model behind the planner.

The business is Ridgeline Cycle Supply, a made-up distributor of bicycle parts
and accessories. It buys 48 SKUs from four suppliers whose lead times run from
about a week (domestic) to two months (ocean freight from Asia), and demand is
seasonal: lights, fenders and indoor trainers peak in winter, tires and
drivetrain parts in spring.

The model simulates demand day by day for every SKU, with uncertainty both in
the forecast level and in the daily draws, and with random supplier lead times.
For each candidate order size it measures the expected lost sales and leftover
stock over the protection window (lead time + review cycle). A greedy
allocator then spends the budget one case pack at a time on whichever SKU buys
the most margin protection per dollar.
"""

import heapq
from dataclasses import dataclass, field
from datetime import date, timedelta
from functools import lru_cache

import numpy as np

AS_OF = date(2026, 10, 16)
HORIZON = 120  # days simulated
PATHS = 800
HISTORY_WEEKS = 26
CARRY_DAYS = 90  # leftover stock at the end of the cycle is charged this many days of holding cost

CATEGORIES = ["Drivetrain", "Brakes", "Tires & tubes", "Wheels", "Lights & fenders", "Trainers & tools"]


@dataclass(frozen=True)
class Supplier:
    name: str
    origin: str
    lead_mean: float
    lead_sd: float


SUPPLIERS = {
    "Kaohsiung Components": Supplier("Kaohsiung Components", "Taiwan · ocean", 48, 9),
    "Pearl River Gear": Supplier("Pearl River Gear", "China · ocean", 58, 12),
    "Schwarzwald Teile": Supplier("Schwarzwald Teile", "Germany · road + sea", 26, 5),
    "Cascade Rubber Co.": Supplier("Cascade Rubber Co.", "Oregon · truck", 8, 2),
}

# name, category, supplier, unit cost, price, case pack, base units/day, seasonal peak month, seasonal amplitude
CATALOGUE = [
    ("12-speed chain", "Drivetrain", "Kaohsiung Components", 18.5, 39, 25, 6.0, 4, 0.35),
    ("11-speed chain", "Drivetrain", "Kaohsiung Components", 13.2, 29, 25, 4.2, 4, 0.35),
    ("10-50T cassette", "Drivetrain", "Kaohsiung Components", 96.0, 189, 10, 1.4, 4, 0.30),
    ("11-34T road cassette", "Drivetrain", "Kaohsiung Components", 48.0, 99, 10, 1.6, 4, 0.30),
    ("Rear derailleur 12s", "Drivetrain", "Kaohsiung Components", 74.0, 149, 10, 0.9, 5, 0.30),
    ("Shift cable kit", "Drivetrain", "Pearl River Gear", 3.1, 9, 100, 7.5, 4, 0.20),
    ("32T narrow-wide chainring", "Drivetrain", "Pearl River Gear", 21.0, 49, 20, 1.1, 5, 0.25),
    ("Bottom bracket BSA", "Drivetrain", "Schwarzwald Teile", 19.0, 42, 20, 1.8, 4, 0.25),
    ("Hydraulic disc caliper", "Brakes", "Kaohsiung Components", 52.0, 109, 10, 1.3, 5, 0.25),
    ("Organic disc pads", "Brakes", "Kaohsiung Components", 6.4, 17, 50, 9.0, 11, 0.30),
    ("Sintered disc pads", "Brakes", "Schwarzwald Teile", 8.2, 21, 50, 5.5, 11, 0.30),
    ("160mm rotor", "Brakes", "Kaohsiung Components", 17.0, 39, 20, 2.2, 5, 0.20),
    ("180mm rotor", "Brakes", "Kaohsiung Components", 19.0, 44, 20, 1.7, 5, 0.20),
    ("Mineral brake fluid", "Brakes", "Schwarzwald Teile", 4.8, 14, 24, 2.8, 4, 0.15),
    ("Rim brake pads", "Brakes", "Pearl River Gear", 2.6, 9, 100, 3.4, 11, 0.25),
    ("Brake bleed kit", "Brakes", "Pearl River Gear", 11.0, 29, 20, 0.8, 1, 0.20),
    ("700x28 road tire", "Tires & tubes", "Schwarzwald Teile", 24.0, 54, 20, 5.0, 4, 0.40),
    ("700x40 gravel tire", "Tires & tubes", "Schwarzwald Teile", 27.0, 62, 20, 4.4, 5, 0.40),
    ("29x2.4 trail tire", "Tires & tubes", "Schwarzwald Teile", 31.0, 72, 20, 3.1, 5, 0.40),
    ("700c tube presta", "Tires & tubes", "Cascade Rubber Co.", 2.9, 9, 50, 22.0, 6, 0.25),
    ("29in tube presta", "Tires & tubes", "Cascade Rubber Co.", 3.4, 11, 50, 11.0, 6, 0.25),
    ("Tubeless sealant 1L", "Tires & tubes", "Cascade Rubber Co.", 9.5, 26, 12, 3.6, 5, 0.30),
    ("Tubeless valve pair", "Tires & tubes", "Pearl River Gear", 3.2, 12, 50, 4.0, 5, 0.25),
    ("700x35 winter studded tire", "Tires & tubes", "Schwarzwald Teile", 38.0, 89, 10, 1.6, 12, 0.85),
    ("Rim tape 25mm", "Tires & tubes", "Pearl River Gear", 1.4, 6, 100, 3.0, 5, 0.25),
    ("700c alloy wheelset", "Wheels", "Kaohsiung Components", 165.0, 349, 4, 0.55, 4, 0.30),
    ("29in trail wheelset", "Wheels", "Kaohsiung Components", 210.0, 449, 4, 0.40, 5, 0.30),
    ("Rear hub 12s", "Wheels", "Kaohsiung Components", 58.0, 129, 10, 0.6, 4, 0.25),
    ("Spoke pack 2.0mm", "Wheels", "Pearl River Gear", 7.5, 19, 40, 1.9, 4, 0.20),
    ("Quick release skewer set", "Wheels", "Pearl River Gear", 5.6, 16, 40, 1.5, 4, 0.20),
    ("Thru-axle 12x142", "Wheels", "Schwarzwald Teile", 14.0, 34, 20, 1.2, 4, 0.20),
    ("400 lm front light", "Lights & fenders", "Pearl River Gear", 14.5, 39, 24, 5.2, 12, 0.75),
    ("1200 lm front light", "Lights & fenders", "Pearl River Gear", 38.0, 99, 12, 2.4, 12, 0.75),
    ("Rear radar light", "Lights & fenders", "Kaohsiung Components", 72.0, 179, 10, 1.2, 12, 0.60),
    ("USB-C rear light", "Lights & fenders", "Pearl River Gear", 9.0, 26, 24, 6.0, 12, 0.75),
    ("Clip-on fender set", "Lights & fenders", "Schwarzwald Teile", 16.0, 39, 20, 3.3, 11, 0.80),
    ("Full fender set 45mm", "Lights & fenders", "Schwarzwald Teile", 23.0, 59, 10, 1.8, 11, 0.80),
    ("Reflective ankle band", "Lights & fenders", "Cascade Rubber Co.", 1.8, 7, 100, 4.0, 12, 0.60),
    ("Smart trainer", "Trainers & tools", "Kaohsiung Components", 420.0, 899, 2, 0.75, 1, 0.95),
    ("Wheel-on trainer", "Trainers & tools", "Pearl River Gear", 115.0, 249, 4, 0.60, 1, 0.95),
    ("Trainer mat", "Trainers & tools", "Cascade Rubber Co.", 18.0, 49, 10, 1.4, 1, 0.90),
    ("Floor pump", "Trainers & tools", "Pearl River Gear", 17.0, 45, 12, 2.5, 5, 0.25),
    ("Mini pump", "Trainers & tools", "Pearl River Gear", 8.0, 24, 24, 3.6, 5, 0.25),
    ("Multi-tool 18-in-1", "Trainers & tools", "Pearl River Gear", 11.0, 32, 24, 3.0, 12, 0.35),
    ("Chain checker", "Trainers & tools", "Schwarzwald Teile", 6.5, 18, 24, 1.0, 4, 0.20),
    ("Torque wrench 2-14Nm", "Trainers & tools", "Schwarzwald Teile", 44.0, 109, 6, 0.5, 12, 0.40),
    ("Chain lube wet 120ml", "Trainers & tools", "Cascade Rubber Co.", 3.4, 12, 48, 8.5, 11, 0.40),
    ("Degreaser 1L", "Trainers & tools", "Cascade Rubber Co.", 5.2, 16, 12, 2.6, 4, 0.20),
]


@dataclass
class Sku:
    id: str
    name: str
    category: str
    supplier: str
    unit_cost: float
    price: float
    case_pack: int
    base_rate: float
    peak_month: int
    amplitude: float
    level_cv: float  # forecast uncertainty on the demand level
    on_hand: int
    inbound: list = field(default_factory=list)  # [(qty, eta_days)]
    history: np.ndarray = None  # weekly units, oldest first

    @property
    def margin(self):
        return self.price - self.unit_cost

    @property
    def lead_mean(self):
        return SUPPLIERS[self.supplier].lead_mean

    @property
    def lead_sd(self):
        return SUPPLIERS[self.supplier].lead_sd

    def rate(self, days_from_now):
        """Expected units per day on the given day(s) relative to AS_OF."""
        d = np.asarray(days_from_now, dtype=float)
        doy = AS_OF.timetuple().tm_yday + d
        peak_doy = (self.peak_month - 0.5) * 30.4
        return self.base_rate * (1 + self.amplitude * np.cos(2 * np.pi * (doy - peak_doy) / 365))


def _build_catalogue():
    rng = np.random.default_rng(20261016)
    skus = []
    # Each SKU gets a stock position: how many days of forward demand it has on hand.
    # A few are deliberately short or bloated so the board has a story to tell.
    cover_plan = rng.choice([12, 20, 30, 42, 55, 70, 95, 150], size=len(CATALOGUE),
                            p=[0.12, 0.14, 0.16, 0.16, 0.14, 0.12, 0.10, 0.06])
    for i, (name, cat, sup, cost, price, pack, rate, peak, amp) in enumerate(CATALOGUE):
        s = Sku(id=f"RCS-{1001 + i}", name=name, category=cat, supplier=sup, unit_cost=cost, price=price,
                case_pack=pack, base_rate=rate, peak_month=peak, amplitude=amp,
                level_cv=float(rng.uniform(0.12, 0.28)), on_hand=0)
        cover = cover_plan[i] * rng.uniform(0.8, 1.2)
        s.on_hand = int(round(s.rate(np.arange(cover)).sum()))
        # Open purchase orders already on the water / road
        if rng.random() < 0.45:
            eta = int(rng.integers(5, max(8, int(s.lead_mean))))
            qty = int(np.ceil(s.rate(np.arange(eta, eta + 30)).sum() * rng.uniform(0.5, 1.2) / pack) * pack)
            s.inbound.append((qty, eta))
        weeks = np.arange(-HISTORY_WEEKS, 0) * 7 + 3
        s.history = rng.poisson(s.rate(weeks) * 7 * rng.lognormal(0, 0.12, HISTORY_WEEKS))
        skus.append(s)
    return skus


SKUS = _build_catalogue()
BY_ID = {s.id: s for s in SKUS}


def _demand_paths(s, rng):
    """Daily demand, shape (PATHS, HORIZON): a gamma level shock per path times Poisson draws."""
    k = 1 / s.level_cv**2
    level = rng.gamma(k, 1 / k, size=(PATHS, 1))
    return rng.poisson(s.rate(np.arange(HORIZON))[None, :] * level)


def _lead_paths(s, rng):
    return np.clip(np.round(rng.normal(s.lead_mean, s.lead_sd, PATHS)), 3, HORIZON - 30).astype(int)


def _inbound_paths(s, rng):
    """Arrivals of already-open POs, shape (PATHS, HORIZON), with a little slippage."""
    arr = np.zeros((PATHS, HORIZON))
    for qty, eta in s.inbound:
        slip = np.clip(eta + rng.poisson(1.5, PATHS), 0, HORIZON - 1)
        arr[np.arange(PATHS), slip] += qty
    return arr


def simulate_stock(s, order_qty, seed_offset=0):
    """Daily on-hand stock and lost units per path for an order placed today.

    Returns (stock, lost, lead) where stock and lost have shape (PATHS, HORIZON)."""
    rng = np.random.default_rng(int(s.id[-4:]) + seed_offset)
    demand = _demand_paths(s, rng)
    lead = _lead_paths(s, rng)
    arrivals = _inbound_paths(s, rng)
    arrivals[np.arange(PATHS), lead] += order_qty
    stock = np.empty((PATHS, HORIZON))
    lost = np.empty((PATHS, HORIZON))
    level = np.full(PATHS, float(s.on_hand))
    for d in range(HORIZON):
        level += arrivals[:, d]
        sold = np.minimum(level, demand[:, d])
        lost[:, d] = demand[:, d] - sold
        level -= sold
        stock[:, d] = level
    return stock, lost, lead


@lru_cache(maxsize=8)
def order_curves(review_days):
    """For every SKU, expected lost units / leftover / stockout chance over the
    protection window (lead time + review cycle) for each order size in case packs.

    The same demand paths are reused for every order size (common random numbers),
    so differences between sizes are not swamped by simulation noise."""
    curves = {}
    for s in SKUS:
        rng = np.random.default_rng(int(s.id[-4:]))
        demand = _demand_paths(s, rng)
        lead = _lead_paths(s, rng)
        arrivals = _inbound_paths(s, rng)
        window_end = np.minimum(lead + review_days, HORIZON - 1)
        window_demand = np.cumsum(demand, axis=1)[np.arange(PATHS), window_end].mean()
        max_packs = int(np.ceil(s.rate(np.arange(int(s.lead_mean) + review_days)).sum() * 2.2 / s.case_pack)) + 2
        q = np.arange(max_packs + 1) * s.case_pack  # (Q,)
        level = np.full((len(q), PATHS), float(s.on_hand))
        lost = np.zeros((len(q), PATHS))
        lost_after = np.zeros((len(q), PATHS))  # lost once the new order has landed
        end_stock = np.zeros((len(q), PATHS))
        for d in range(HORIZON):
            level += arrivals[:, d][None, :] + np.where(lead == d, 1, 0)[None, :] * q[:, None]
            sold = np.minimum(level, demand[:, d][None, :])
            in_window = (d <= window_end)[None, :]
            lost += (demand[:, d][None, :] - sold) * in_window
            lost_after += (demand[:, d][None, :] - sold) * (in_window & (d >= lead)[None, :])
            level -= sold
            end_stock = np.where((d == window_end)[None, :], level, end_stock)
            if d > window_end.max():
                break
        curves[s.id] = {
            "q": q,
            "lost": lost.mean(axis=1),
            "p_out": (lost > 0).mean(axis=1),
            "p_out_after": (lost_after > 0).mean(axis=1),
            "lost_before": (lost - lost_after).mean(axis=1),
            "leftover": end_stock.mean(axis=1),
            "window_demand": window_demand,
        }
    return curves


@lru_cache(maxsize=32)
def greedy_sequence(review_days, penalty, holding_rate):
    """Every case-pack purchase worth making, best value per dollar first.

    Each step is (sku_id, packs_after, spend, value) where value is margin
    protected (times the lost-sale penalty) minus the carrying cost of extra
    leftover stock. Steps stop for a SKU once the next pack is worth nothing."""
    curves = order_curves(review_days)
    hold = holding_rate * CARRY_DAYS / 365

    def step_value(s, c, n):
        gain = (c["lost"][n - 1] - c["lost"][n]) * s.margin * penalty
        carry = (c["leftover"][n] - c["leftover"][n - 1]) * s.unit_cost * hold
        return gain - carry

    heap = []
    for s in SKUS:
        c = curves[s.id]
        if len(c["q"]) > 1:
            v = step_value(s, c, 1)
            heapq.heappush(heap, (-v / (s.case_pack * s.unit_cost), s.id, 1, v))
    seq = []
    while heap:
        neg_ratio, sid, n, v = heapq.heappop(heap)
        if v <= 0:
            continue
        s = BY_ID[sid]
        seq.append((sid, n, s.case_pack * s.unit_cost, v))
        c = curves[sid]
        if n + 1 < len(c["q"]):
            v2 = step_value(s, c, n + 1)
            heapq.heappush(heap, (-v2 / (s.case_pack * s.unit_cost), sid, n + 1, v2))
    return seq


def plan(budget, review_days, penalty, holding_rate, ids):
    """Packs to order per SKU within the budget, for the SKUs in ids.

    Each SKU's steps are independent of the others, so filtering the global
    greedy sequence to a subset gives the greedy sequence for that subset."""
    packs = {sid: 0 for sid in ids}
    spend = 0.0
    for sid, n, cost, _ in greedy_sequence(review_days, penalty, holding_rate):
        if sid not in ids:
            continue
        if spend + cost > budget:
            break
        packs[sid] = n
        spend += cost
    return packs, spend


def frontier(review_days, penalty, holding_rate, ids):
    """Cumulative spend vs expected lost revenue for the SKUs in ids, following the greedy order."""
    curves = order_curves(review_days)
    lost_rev = sum(curves[sid]["lost"][0] * BY_ID[sid].price for sid in ids)
    xs, ys = [0.0], [lost_rev]
    spend = 0.0
    for sid, n, cost, _ in greedy_sequence(review_days, penalty, holding_rate):
        if sid not in ids:
            continue
        c = curves[sid]
        spend += cost
        lost_rev -= (c["lost"][n - 1] - c["lost"][n]) * BY_ID[sid].price
        xs.append(spend)
        ys.append(lost_rev)
    return np.array(xs), np.array(ys)


def forecast_weeks(s, weeks=12):
    """Weekly demand forecast: median and 10th/90th percentiles."""
    rng = np.random.default_rng(int(s.id[-4:]) + 7)
    k = 1 / s.level_cv**2
    level = rng.gamma(k, 1 / k, size=(PATHS, 1))
    days = np.arange(weeks * 7)
    daily = rng.poisson(s.rate(days)[None, :] * level)
    weekly = daily.reshape(PATHS, weeks, 7).sum(axis=2)
    return np.percentile(weekly, [10, 50, 90], axis=0)


def runway(s):
    """Median day of first stockout with no new order (HORIZON if it never runs out), from the
    same simulation as the projection chart."""
    stock, lost, _ = simulate_stock(s, 0)
    out = lost > 0
    first = np.where(out.any(axis=1), out.argmax(axis=1), HORIZON)
    return float(np.median(first))


RUNWAY = {s.id: runway(s) for s in SKUS}


def status(s, review_days):
    """critical: runs out before an order placed today can land.
    warning: runs out before the next review's order could land, so order this cycle.
    good: covered past the next cycle."""
    r = RUNWAY[s.id]
    if r < s.lead_mean:
        return "critical"
    if r < s.lead_mean + review_days:
        return "warning"
    return "good"


def day_label(n):
    d = AS_OF + timedelta(days=int(n))
    return f"{d:%b} {d.day}"
