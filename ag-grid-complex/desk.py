"""
Synthetic book for the Rebalance Desk.

Accounts follow one of four model portfolios. Each account holds the model's
securities at weights that have drifted away from target, plus the odd legacy
position the model no longer wants. Every position is split into tax lots so
the desk can see what a sale would realize.

Everything is generated from a fixed seed, so the book is the same on every
worker and every restart.
"""

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np

TODAY = date(2026, 10, 21)
SEED = 20261021

ST_RATE = 0.37  # short-term federal rate
LT_RATE = 0.20  # long-term federal rate
MIN_TICKET = 5_000
CONCENTRATION_CAP = 0.10
ADV_LIMIT = 0.05

# ticker, name, asset class, sector, price, average daily volume (shares)
SECURITIES = [
    ("VTI", "Total US Market ETF", "US Equity", "Broad market", 312.40, 3_900_000),
    ("AAPL", "Apple", "US Equity", "Technology", 248.10, 52_000_000),
    ("MSFT", "Microsoft", "US Equity", "Technology", 512.85, 21_000_000),
    ("NVDA", "Nvidia", "US Equity", "Technology", 186.30, 190_000_000),
    ("JPM", "JPMorgan Chase", "US Equity", "Financials", 301.15, 9_100_000),
    ("UNH", "UnitedHealth", "US Equity", "Health care", 356.70, 6_200_000),
    ("XOM", "Exxon Mobil", "US Equity", "Energy", 114.25, 15_000_000),
    ("COST", "Costco", "US Equity", "Consumer staples", 931.40, 2_100_000),
    ("VEA", "Developed Markets ETF", "Intl Equity", "Broad market", 58.90, 11_000_000),
    ("ASML", "ASML Holding", "Intl Equity", "Technology", 968.20, 1_400_000),
    ("NVO", "Novo Nordisk", "Intl Equity", "Health care", 54.10, 9_800_000),
    ("TM", "Toyota Motor", "Intl Equity", "Consumer discretionary", 192.60, 380_000),
    ("VWO", "Emerging Markets ETF", "EM Equity", "Broad market", 52.35, 8_700_000),
    ("TSM", "Taiwan Semiconductor", "EM Equity", "Technology", 296.40, 14_000_000),
    ("BND", "Total Bond Market ETF", "Fixed Income", "Aggregate", 74.15, 6_800_000),
    ("TLT", "20+ Year Treasury ETF", "Fixed Income", "Treasuries", 90.70, 38_000_000),
    ("LQD", "IG Corporate Bond ETF", "Fixed Income", "Corporate", 111.30, 25_000_000),
    ("TIP", "TIPS Bond ETF", "Fixed Income", "Inflation-linked", 110.95, 2_600_000),
    ("MUB", "National Muni Bond ETF", "Fixed Income", "Municipal", 106.60, 4_400_000),
    ("HYG", "High Yield Corporate ETF", "Fixed Income", "High yield", 80.85, 31_000_000),
    ("VNQ", "Real Estate ETF", "Real Assets", "REITs", 92.40, 3_300_000),
    ("GLD", "Gold Trust", "Real Assets", "Commodities", 382.10, 9_500_000),
    ("PDBC", "Diversified Commodity ETF", "Real Assets", "Commodities", 13.45, 2_900_000),
    ("SGOV", "0-3 Month Treasury ETF", "Cash", "T-bills", 100.48, 7_400_000),
    # Legacy holdings that no model targets any more
    ("INTC", "Intel", "US Equity", "Technology", 36.80, 88_000_000),
    ("ARKK", "Innovation ETF", "US Equity", "Thematic", 74.20, 12_000_000),
    ("GE", "GE Aerospace", "US Equity", "Industrials", 297.55, 5_600_000),
]

ASSET_CLASSES = ["US Equity", "Intl Equity", "EM Equity", "Fixed Income", "Real Assets", "Cash"]

# Model portfolios: security targets (sum to 1) and drift tolerance band
MODELS = {
    "Growth 90/10": {
        "band": 0.025,
        "targets": {"VTI": .22, "AAPL": .07, "MSFT": .07, "NVDA": .06, "JPM": .04, "COST": .03,
                    "VEA": .12, "ASML": .04, "NVO": .03, "VWO": .07, "TSM": .05, "BND": .06,
                    "HYG": .02, "VNQ": .04, "GLD": .03, "SGOV": .05},
    },
    "Balanced 60/40": {
        "band": 0.03,
        "targets": {"VTI": .20, "AAPL": .04, "MSFT": .04, "JPM": .03, "UNH": .03, "XOM": .02,
                    "VEA": .10, "NVO": .02, "VWO": .05, "BND": .16, "LQD": .08, "TLT": .06,
                    "TIP": .05, "VNQ": .04, "GLD": .03, "SGOV": .05},
    },
    "Income 30/70": {
        "band": 0.03,
        "targets": {"VTI": .12, "JPM": .03, "UNH": .03, "XOM": .03, "VEA": .06, "TM": .03,
                    "BND": .20, "LQD": .12, "MUB": .10, "TIP": .07, "TLT": .05, "HYG": .05,
                    "VNQ": .04, "PDBC": .02, "SGOV": .05},
    },
    "Tax-aware Core": {
        "band": 0.035,
        "targets": {"VTI": .28, "MSFT": .05, "AAPL": .05, "COST": .03, "VEA": .14, "ASML": .03,
                    "VWO": .06, "MUB": .20, "TIP": .05, "GLD": .04, "SGOV": .07},
    },
}

ADVISORS = ["R. Okafor", "M. Lindqvist", "S. Patel", "J. Moreau", "A. Tanaka"]
HOUSEHOLDS = [
    "Abernathy Family Trust", "Castellano IRA", "Delacroix Joint", "Ferreira Rollover IRA",
    "Gallagher Foundation", "Hollis Revocable Trust", "Ibarra Roth IRA", "Jansen Joint",
    "Kowalczyk 401k Rollover", "Laurent Family LP", "Mbeki Individual", "Novak Charitable Trust",
    "Oyelaran Joint", "Petrov Individual", "Quintero SEP IRA", "Rasmussen Trust",
    "Sokolova Individual", "Takahashi Joint", "Underwood Endowment", "Valdez Roth IRA",
    "Whitcombe Family Trust", "Xu Individual", "Yilmaz Joint", "Zielinski Trust",
]
TAXABLE = {"Trust", "Joint", "Individual", "LP"}

# Securities on the restricted list for a given advisor's book (insider / employer stock)
RESTRICTED = {("S. Patel", "NVDA"), ("J. Moreau", "JPM"), ("A. Tanaka", "TSM")}


@dataclass
class Security:
    ticker: str
    name: str
    asset_class: str
    sector: str
    price: float
    adv: int
    change: float
    history: list


def _build():
    rng = np.random.default_rng(SEED)

    securities = {}
    for ticker, name, ac, sector, price, adv in SECURITIES:
        vol = {"Fixed Income": .004, "Cash": .0002, "Real Assets": .011}.get(ac, .017)
        steps = rng.normal(0.0004, vol, 60)
        path = price * np.exp(np.cumsum(steps) - steps.sum())  # ends at today's price
        securities[ticker] = Security(ticker, name, ac, sector, price, adv,
                                      float(path[-1] / path[-2] - 1), [round(float(p), 2) for p in path])

    models = list(MODELS)
    accounts, positions, lots = [], [], []
    for i, household in enumerate(HOUSEHOLDS):
        model = models[i % len(models)] if i % 7 else "Growth 90/10"
        advisor = ADVISORS[(i * 3) % len(ADVISORS)]
        acct_id = f"AC-{4100 + i * 37}"
        taxable = household.split()[-1] in TAXABLE
        value = float(np.round(rng.lognormal(14.6, 0.75), -3))
        cash_w = float(rng.uniform(0.005, 0.06))
        # A few accounts are badly out of tolerance, most are close
        intensity = rng.choice([0.25, 0.5, 0.9, 1.6], p=[.3, .35, .2, .15])

        targets = dict(MODELS[model]["targets"])
        weights = {t: max(0.0, w * np.exp(rng.normal(0, 0.18 * intensity))) for t, w in targets.items()}
        if rng.random() < 0.45:
            legacy = rng.choice(["INTC", "ARKK", "GE"])
            weights[legacy] = float(rng.uniform(0.01, 0.05))
            targets[legacy] = 0.0
        total = sum(weights.values())
        weights = {t: w / total * (1 - cash_w) for t, w in weights.items()}

        invested = 0.0
        acct_positions = []
        for ticker, w in weights.items():
            sec = securities[ticker]
            qty = int(value * w / sec.price)
            if qty == 0:
                continue
            mv = qty * sec.price
            invested += mv
            pos_id = f"{acct_id}-{ticker}"

            # Tax lots: older lots bought cheaper, the occasional recent loss lot
            n_lots = int(rng.integers(1, 5))
            split = rng.dirichlet(np.ones(n_lots))
            lot_qty = np.maximum(1, np.round(split * qty)).astype(int)
            lot_qty[-1] = max(1, qty - lot_qty[:-1].sum())
            cost_total, st_gain, lt_gain = 0.0, 0.0, 0.0
            pos_lots = []
            for k, q in enumerate(lot_qty):
                age = int(rng.integers(20, 1600))
                bought = TODAY - timedelta(days=age)
                drift = rng.normal(-0.00022 * age, 0.12 if sec.asset_class != "Cash" else 0.002)
                cost = sec.price * float(np.exp(drift))
                gain = (sec.price - cost) * q
                term = "Short" if age < 365 else "Long"
                if term == "Short":
                    st_gain += gain
                else:
                    lt_gain += gain
                cost_total += cost * q
                pos_lots.append({
                    "id": f"{pos_id}-L{k + 1}", "position_id": pos_id, "lot": f"L{k + 1}",
                    "acquired": bought.isoformat(), "days_held": age, "term": term, "qty": int(q),
                    "cost": round(cost, 2), "price": sec.price, "cost_basis": round(cost * q, 2),
                    "market_value": round(sec.price * q, 2), "gain": round(gain, 2),
                    "gain_pct": round(sec.price / cost - 1, 4),
                })
            held_qty = int(sum(l["qty"] for l in pos_lots))
            avg_cost = cost_total / held_qty
            # Per-share tax a pro-rata sale would realize (zero in tax-deferred accounts)
            tax_ps = 0.0
            if taxable:
                tax_ps = (max(st_gain, 0) * ST_RATE + max(lt_gain, 0) * LT_RATE) / held_qty
            recent_loss_sale = bool(taxable and rng.random() < 0.10)
            acct_positions.append({
                "id": pos_id, "account_id": acct_id, "ticker": ticker, "name": sec.name,
                "asset_class": sec.asset_class, "sector": sec.sector, "qty": held_qty,
                "price": sec.price, "change": round(sec.change, 4), "avg_cost": round(avg_cost, 2),
                "market_value": round(held_qty * sec.price, 2), "cost_basis": round(cost_total, 2),
                "gain": round(held_qty * sec.price - cost_total, 2),
                "st_gain": round(st_gain, 2), "lt_gain": round(lt_gain, 2),
                "tax_per_share": round(tax_ps, 4), "target": targets.get(ticker, 0.0),
                "lots": len(pos_lots), "wash_sale_window": recent_loss_sale, "adv": sec.adv,
                "history": sec.history[-30:],
            })
            lots.extend(pos_lots)

        cash = round(invested / (1 - cash_w) * cash_w, 2)
        total_value = invested + cash
        for p in acct_positions:
            p["weight"] = round(p["market_value"] / total_value, 5)
            p["drift"] = round(p["weight"] - p["target"], 5)
        positions.extend(acct_positions)

        drifts = [abs(p["drift"]) for p in acct_positions]
        band = MODELS[model]["band"]
        class_w = {ac: 0.0 for ac in ASSET_CLASSES}
        for p in acct_positions:
            class_w[p["asset_class"]] += p["weight"]
        # 90 day account value path from the holdings' price paths
        hist = np.zeros(30)
        for p in acct_positions:
            hist += np.array(p["history"]) * p["qty"]
        hist += cash
        last = int(rng.integers(30, 420))
        accounts.append({
            "id": acct_id, "household": household, "advisor": advisor, "model": model,
            "registration": "Taxable" if taxable else "Tax-deferred",
            "value": round(total_value, 2), "cash": cash, "cash_weight": round(cash / total_value, 4),
            "positions": len(acct_positions), "max_drift": round(max(drifts), 5),
            "abs_drift": round(sum(drifts) / 2, 5), "band": band,
            "status": "Out of band" if max(drifts) > band else ("Watch" if max(drifts) > band * 0.7 else "In band"),
            "equity_weight": round(class_w["US Equity"] + class_w["Intl Equity"] + class_w["EM Equity"], 4),
            "unrealized": round(sum(p["gain"] for p in acct_positions), 2),
            "last_rebalanced": (TODAY - timedelta(days=last)).isoformat(),
            "days_since": last, "history": [round(float(v), 0) for v in hist],
            "return_30d": round(float(hist[-1] / hist[0] - 1), 4),
        })

    return securities, accounts, positions, lots


SECURITY_MAP, ACCOUNTS, POSITIONS, LOTS = _build()
ACCOUNT_MAP = {a["id"]: a for a in ACCOUNTS}
POSITION_MAP = {p["id"]: p for p in POSITIONS}


def holdings(account_id):
    return [p for p in POSITIONS if p["account_id"] == account_id]


def lots(position_id):
    return [l for l in LOTS if l["position_id"] == position_id]


def propose_trades(account_ids):
    """Trades that take every drifted position in the chosen accounts back to target."""
    trades = []
    for acct_id in account_ids:
        acct = ACCOUNT_MAP[acct_id]
        for p in holdings(acct_id):
            # Only trade positions that have drifted more than half a point
            if abs(p["drift"]) < 0.005 and p["target"] > 0:
                continue
            value = (p["target"] - p["weight"]) * acct["value"]
            qty = abs(int(round(value / p["price"])))
            if qty == 0:
                continue
            side = "Buy" if value > 0 else "Sell"
            if side == "Sell":
                qty = min(qty, p["qty"])
            trades.append({
                "id": f"T-{p['id']}", "account_id": acct_id, "household": acct["household"],
                "advisor": acct["advisor"], "model": acct["model"], "registration": acct["registration"],
                "account_value": acct["value"], "ticker": p["ticker"], "name": p["name"],
                "asset_class": p["asset_class"], "side": side, "qty": qty, "price": p["price"],
                "order_type": "VWAP" if qty * p["price"] > 250_000 else "Market", "limit": None,
                "tif": "Day", "held_qty": p["qty"], "market_value": p["market_value"],
                "weight": p["weight"], "target": p["target"], "drift": p["drift"],
                "tax_per_share": p["tax_per_share"], "avg_cost": p["avg_cost"],
                "st_gain": p["st_gain"], "adv": p["adv"], "wash_sale_window": p["wash_sale_window"],
                "legacy": p["target"] == 0, "band": acct["band"],
                "out_of_band": abs(p["drift"]) > acct["band"] or p["target"] == 0,
            })
    return trades


def _post_weight(t):
    signed = t["qty"] * t["price"] * (1 if t["side"] == "Buy" else -1)
    return (t["market_value"] + signed) / t["account_value"]


def check_trades(trades):
    """Pre-trade compliance. Each rule returns pass / warn / fail with a reason."""
    results = []
    for t in trades:
        notional = t["qty"] * t["price"]
        post = _post_weight(t)
        checks = {}

        checks["restricted"] = ("fail", f"{t['ticker']} is on {t['advisor']}'s restricted list") \
            if (t["advisor"], t["ticker"]) in RESTRICTED and t["side"] == "Buy" else ("pass", "")
        checks["wash_sale"] = ("fail", "Sold at a loss in the last 30 days, buying back triggers a wash sale") \
            if t["wash_sale_window"] and t["side"] == "Buy" else ("pass", "")
        checks["concentration"] = ("fail", f"Post-trade weight {post:.1%} breaches the 10% single-name cap") \
            if post > CONCENTRATION_CAP and t["asset_class"] not in ("Fixed Income", "Cash") \
            and t["side"] == "Buy" and t["ticker"] not in ("VTI", "VEA", "VWO") else ("pass", "")
        if t["side"] == "Sell" and t["registration"] == "Taxable" and t["st_gain"] > 0:
            share = t["qty"] / t["held_qty"]
            st = t["st_gain"] * share
            checks["tax"] = ("warn", f"Realizes ~${st:,.0f} of short-term gains") if st > 1_500 else ("pass", "")
        else:
            checks["tax"] = ("pass", "")
        checks["liquidity"] = ("warn", f"{t['qty'] / t['adv']:.1%} of average daily volume") \
            if t["qty"] > t["adv"] * ADV_LIMIT else ("pass", "")
        checks["ticket"] = ("warn", f"${notional:,.0f} is below the ${MIN_TICKET:,} minimum ticket") \
            if notional < MIN_TICKET else ("pass", "")
        if t["order_type"] == "Limit" and not t.get("limit"):
            checks["ticket"] = ("fail", "Limit order without a limit price")

        statuses = [s for s, _ in checks.values()]
        overall = "fail" if "fail" in statuses else ("warn" if "warn" in statuses else "pass")
        reasons = [r for s, r in checks.values() if s != "pass"]
        results.append({
            **{k: t[k] for k in ("id", "account_id", "household", "ticker", "name", "side", "qty",
                                 "price", "order_type", "limit", "tif", "advisor", "asset_class")},
            "notional": round(notional, 2), "post_weight": round(post, 5), "target": t["target"],
            "est_tax": round(t["qty"] * t["tax_per_share"], 2) if t["side"] == "Sell" else 0.0,
            **{f"chk_{k}": s for k, (s, _) in checks.items()},
            "result": overall, "reasons": " · ".join(reasons) or "All checks passed",
        })
    return results


def fill_state(order, tick):
    """Deterministic fill progress for an order after `tick` market updates."""
    h = sum(ord(c) for c in order["id"])
    speed = {"Market": 0.55, "Limit": 0.18, "VWAP": 0.09}[order["order_type"]]
    delay = h % 4
    progress = max(0.0, min(1.0, (tick - delay) * speed * (0.75 + (h % 7) / 12)))
    if order["order_type"] == "Limit":
        progress = min(progress, 0.6 + (h % 5) / 10)  # a limit can sit partially filled
    filled = int(order["qty"] * progress) if progress < 1 else order["qty"]
    sign = 1 if order["side"] == "Buy" else -1
    slip = sign * 0.0006 * ((h % 9) - 3) / 3 + 0.0004 * np.sin(tick + h)
    avg_px = round(order["price"] * (1 + slip), 2) if filled else None
    if avg_px and order["order_type"] == "Limit" and order.get("limit"):
        avg_px = min(avg_px, order["limit"]) if sign > 0 else max(avg_px, order["limit"])
    if filled == 0:
        status = "Working" if tick > delay else "Routed"
    elif filled < order["qty"]:
        status = "Partial"
    else:
        status = "Filled"
    return {"filled": filled, "avg_px": avg_px, "status": status, "pct": filled / order["qty"],
            "last_px": round(order["price"] * (1 + 0.0009 * np.sin(tick * 0.9 + h)), 2)}
