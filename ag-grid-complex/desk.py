"""
Sample data for the Rebalance Desk.

Twelve clients each pick a target mix of five funds (for example 60% US stocks,
30% bonds). Markets move, so over time each account drifts away from its mix.
An account needs rebalancing once any fund is more than 5 points off target.
Each holding is made up of a few past purchases, so a sale can show its gain.

Everything is generated from a fixed seed, so the data is the same on every
worker and every restart.
"""

from datetime import date, timedelta

import numpy as np

TODAY = date(2026, 10, 21)
SEED = 20261021

BAND = 0.05  # a fund more than 5 points off target needs rebalancing
MIN_ORDER = 2_000  # orders smaller than this are not worth placing
GAIN_WARNING = 2_000  # selling more than this much gain in a taxable account may cost tax

# ticker, plain name, price
FUNDS = [
    ("VTI", "US Stocks", 312.40),
    ("VXUS", "International Stocks", 68.90),
    ("BND", "Bonds", 74.15),
    ("VNQ", "Real Estate", 92.40),
    ("SGOV", "Cash Fund", 100.48),
]

# Target mixes. Each adds up to 100%
MIXES = {
    "Growth": {"VTI": .55, "VXUS": .25, "BND": .10, "VNQ": .05, "SGOV": .05},
    "Balanced": {"VTI": .35, "VXUS": .15, "BND": .35, "VNQ": .05, "SGOV": .10},
    "Conservative": {"VTI": .20, "VXUS": .10, "BND": .50, "VNQ": .05, "SGOV": .15},
}

# client, account type, mix
CLIENTS = [
    ("Maria Lopez", "Retirement", "Growth"),
    ("James Chen", "Taxable", "Balanced"),
    ("Priya Shah", "Taxable", "Growth"),
    ("Tom & Ana Berg", "Taxable", "Conservative"),
    ("Lucas Martin", "Retirement", "Balanced"),
    ("Grace Kim", "Retirement", "Conservative"),
    ("Omar Haddad", "Taxable", "Growth"),
    ("Sofia Rossi", "Retirement", "Balanced"),
    ("Daniel Wright", "Taxable", "Balanced"),
    ("Aiko Sato", "Retirement", "Growth"),
    ("Noah Fischer", "Taxable", "Conservative"),
    ("Emma Clarke", "Taxable", "Growth"),
]


def _build():
    rng = np.random.default_rng(SEED)

    history = {}
    for ticker, _, price in FUNDS:
        vol = {"BND": .004, "SGOV": .0002, "VNQ": .011}.get(ticker, .014)
        steps = rng.normal(0.0004, vol, 30)
        history[ticker] = [round(float(p), 2) for p in price * np.exp(np.cumsum(steps) - steps.sum())]

    accounts, positions, lots = [], [], []
    for i, (client, kind, mix) in enumerate(CLIENTS):
        acct_id = f"AC-{101 + i}"
        value = float(np.round(rng.uniform(60_000, 900_000), -3))
        cash_w = float(rng.uniform(0.005, 0.02))
        # Some accounts have drifted a lot, others hardly at all
        spread = [0.06, 0.14, 0.28][i % 3]

        targets = MIXES[mix]
        weights = {t: w * np.exp(rng.normal(0, spread)) for t, w in targets.items()}
        total = sum(weights.values())
        weights = {t: w / total * (1 - cash_w) for t, w in weights.items()}

        acct_positions = []
        for ticker, name, price in FUNDS:
            qty = int(value * weights[ticker] / price)
            pos_id = f"{acct_id}-{ticker}"

            # Two to four past purchases, older ones bought cheaper
            n = int(rng.integers(2, 5))
            split = rng.dirichlet(np.ones(n))
            lot_qty = np.maximum(1, np.round(split * qty)).astype(int)
            lot_qty[-1] = max(1, qty - lot_qty[:-1].sum())
            pos_lots = []
            for k, q in enumerate(lot_qty):
                age = int(rng.integers(60, 1800))
                # The cash fund barely moves; the others have grown over time
                move, noise = (0.000005, 0.001) if ticker == "SGOV" else (0.00025, 0.05)
                cost = round(price * float(np.exp(-move * age + rng.normal(0, noise))), 2)
                pos_lots.append({
                    "id": f"{pos_id}-{k + 1}", "position_id": pos_id, "lot": f"#{k + 1}",
                    "acquired": (TODAY - timedelta(days=age)).isoformat(), "qty": int(q), "cost": cost,
                    "cost_basis": round(cost * q, 2), "market_value": round(price * q, 2),
                    "gain": round((price - cost) * q, 2), "gain_pct": round(price / cost - 1, 4),
                })
            pos_lots.sort(key=lambda l: l["acquired"])
            held = int(sum(l["qty"] for l in pos_lots))
            cost_total = sum(l["cost_basis"] for l in pos_lots)
            gain = held * price - cost_total
            acct_positions.append({
                "id": pos_id, "account_id": acct_id, "ticker": ticker, "name": name, "qty": held,
                "price": price, "market_value": round(held * price, 2), "avg_cost": round(cost_total / held, 2),
                "gain": round(gain, 2), "gain_per_share": round(gain / held, 4), "target": targets[ticker],
                "lots": len(pos_lots), "history": history[ticker],
            })
            lots.extend(pos_lots)

        invested = sum(p["market_value"] for p in acct_positions)
        cash = round(invested / (1 - cash_w) * cash_w, 2)
        total_value = invested + cash
        for p in acct_positions:
            p["weight"] = round(p["market_value"] / total_value, 5)
            p["drift"] = round(p["weight"] - p["target"], 5)
        positions.extend(acct_positions)

        biggest = max((p["drift"] for p in acct_positions), key=abs)
        hist = sum(np.array(p["history"]) * p["qty"] for p in acct_positions) + cash
        last = int(rng.integers(40, 420))
        accounts.append({
            "id": acct_id, "household": client, "registration": kind, "model": mix,
            "value": round(total_value, 2), "cash": cash, "cash_weight": round(cash / total_value, 4),
            "max_drift": round(biggest, 5), "band": BAND,
            "status": "Off target" if abs(biggest) > BAND else "On target",
            "unrealized": round(sum(p["gain"] for p in acct_positions), 2),
            "last_rebalanced": (TODAY - timedelta(days=last)).isoformat(), "days_since": last,
            "history": [round(float(v), 0) for v in hist], "return_30d": round(float(hist[-1] / hist[0] - 1), 4),
        })

    return accounts, positions, lots


ACCOUNTS, POSITIONS, LOTS = _build()
ACCOUNT_MAP = {a["id"]: a for a in ACCOUNTS}
POSITION_MAP = {p["id"]: p for p in POSITIONS}


def holdings(account_id):
    return [p for p in POSITIONS if p["account_id"] == account_id]


def lots(position_id):
    return [l for l in LOTS if l["position_id"] == position_id]


def propose_trades(account_ids):
    """Buys and sells that take every fund in the chosen accounts back to its target."""
    trades = []
    for acct_id in account_ids:
        acct = ACCOUNT_MAP[acct_id]
        for p in holdings(acct_id):
            # Leave funds that are already within a quarter point of target
            if abs(p["drift"]) < 0.0025:
                continue
            amount = (p["target"] - p["weight"]) * acct["value"]
            side = "Buy" if amount > 0 else "Sell"
            # Round buys down and sells up so the sells always cover the buys
            shares = abs(amount) / p["price"]
            qty = int(shares) if side == "Buy" else min(int(np.ceil(shares)), p["qty"])
            if qty == 0:
                continue
            trades.append({
                "id": f"T-{p['id']}", "account_id": acct_id, "household": acct["household"],
                "model": acct["model"], "registration": acct["registration"], "account_value": acct["value"],
                "cash": acct["cash"], "ticker": p["ticker"], "name": p["name"], "side": side, "qty": qty,
                "price": p["price"], "order_type": "Market", "limit": None, "held_qty": p["qty"],
                "market_value": p["market_value"], "weight": p["weight"], "target": p["target"],
                "drift": p["drift"], "gain_per_share": p["gain_per_share"],
                "out_of_band": abs(p["drift"]) > BAND,
            })
    return trades


def _post_weight(t):
    signed = t["qty"] * t["price"] * (1 if t["side"] == "Buy" else -1)
    return (t["market_value"] + signed) / t["account_value"]


def check_trades(trades):
    """Three house rules per order. Each returns pass / warn / fail with a reason."""
    # Buys in an account have to be paid for by its sells plus the cash it already holds
    money = {}
    for t in trades:
        m = money.setdefault(t["account_id"], {"in": t["cash"], "out": 0.0})
        m["in" if t["side"] == "Sell" else "out"] += t["qty"] * t["price"]

    results = []
    for t in trades:
        amount = t["qty"] * t["price"]
        gain = t["qty"] * t["gain_per_share"] if t["side"] == "Sell" else 0.0
        m = money[t["account_id"]]
        checks = {}

        checks["size"] = ("fail", f"${amount:,.0f} is below the ${MIN_ORDER:,} minimum order") \
            if amount < MIN_ORDER else ("pass", "")
        if t["order_type"] == "Limit" and not t.get("limit"):
            checks["size"] = ("fail", "Limit order needs a limit price")
        checks["cash"] = ("fail", f"Buys are ${m['out'] - m['in']:,.0f} more than this account can pay for") \
            if t["side"] == "Buy" and m["out"] > m["in"] else ("pass", "")
        checks["tax"] = ("warn", f"Sale makes a ${gain:,.0f} gain, which may be taxed") \
            if t["registration"] == "Taxable" and gain > GAIN_WARNING else ("pass", "")

        statuses = [s for s, _ in checks.values()]
        overall = "fail" if "fail" in statuses else ("warn" if "warn" in statuses else "pass")
        reasons = [r for s, r in checks.values() if s != "pass"]
        results.append({
            **{k: t[k] for k in ("id", "account_id", "household", "ticker", "name", "side", "qty",
                                 "price", "order_type", "limit")},
            "notional": round(amount, 2), "post_weight": round(_post_weight(t), 5), "target": t["target"],
            "gain": round(gain, 2), **{f"chk_{k}": s for k, (s, _) in checks.items()},
            "result": overall, "reasons": " · ".join(reasons) or "All checks passed",
        })
    return results


def fill_state(order, tick):
    """How much of an order has been filled after `tick` market updates."""
    h = sum(ord(c) for c in order["id"])
    speed = {"Market": 0.45, "Limit": 0.18}[order["order_type"]]
    delay = h % 4
    progress = max(0.0, min(1.0, (tick - delay) * speed * (0.75 + (h % 7) / 12)))
    if order["order_type"] == "Limit":
        progress = min(progress, 0.6 + (h % 5) / 10)  # a limit order can wait part-filled
    filled = int(order["qty"] * progress) if progress < 1 else order["qty"]
    sign = 1 if order["side"] == "Buy" else -1
    avg_px = round(order["price"] * (1 + sign * 0.0006 * ((h % 9) - 3) / 3), 2) if filled else None
    if avg_px and order["order_type"] == "Limit" and order.get("limit"):
        avg_px = min(avg_px, order["limit"]) if sign > 0 else max(avg_px, order["limit"])
    if filled == 0:
        status = "Sent" if tick <= delay else "Working"
    elif filled < order["qty"]:
        status = "Partly filled"
    else:
        status = "Filled"
    return {"filled": filled, "avg_px": avg_px, "status": status, "pct": filled / order["qty"]}
