"""
Synthetic clinical trial portfolio and the two risk models that score it.

Every trial, sponsor, site and number here is made up. The portfolio is
generated once at import from a fixed seed, relative to the first day of the
current month, so the trials always look "in flight".

Enrollment risk: each site's recent enrollment rate is projected forward, with
sites still to be activated coming online on schedule, in a Monte Carlo
simulation with trial-level rate uncertainty. The result is the probability of
reaching the enrollment target by the planned end of enrollment, plus a
projected completion month with an 80% band.

Failure risk: a logistic model of the probability that the trial terminates
early or misses its primary endpoint. The baseline comes from phase and
therapeutic area, and each trial feature shifts the log-odds from there. The
coefficients are illustrative, loosely shaped by published phase transition
rates, not fitted to real data.
"""

import math
import zlib
from dataclasses import dataclass
from datetime import date

import numpy as np

SEED = 11
AS_OF = date.today().replace(day=1)
N_PATHS = 2000
HORIZON = 60  # months simulated past today

# name: (patients per site per month, failure log-odds shift, indications)
AREAS = {
    "Oncology": (0.45, 0.45, ["Non-small cell lung cancer", "HER2-low breast cancer", "Acute myeloid leukemia",
                              "Metastatic colorectal cancer", "Glioblastoma"]),
    "Neurology": (0.6, 0.4, ["Early Alzheimer's disease", "Parkinson's disease", "Relapsing MS", "ALS"]),
    "Cardiometabolic": (1.2, -0.1, ["Heart failure (HFpEF)", "Type 2 diabetes", "Resistant hypertension", "MASH"]),
    "Immunology": (0.9, 0.0, ["Plaque psoriasis", "Ulcerative colitis", "Systemic lupus", "Atopic dermatitis"]),
    "Infectious disease": (1.5, -0.35, ["RSV (older adults)", "Complicated UTI", "Chronic hepatitis B"]),
    "Rare disease": (0.15, -0.15, ["Duchenne muscular dystrophy", "Fabry disease", "Phenylketonuria",
                                   "Hemophilia A"]),
}
# name: (failure log-odds baseline, target enrollment range, site count range)
PHASES = {
    "Phase 1": (-0.55, (24, 72), (3, 8)),
    "Phase 2": (0.3, (80, 260), (12, 40)),
    "Phase 3": (-0.3, (300, 1100), (40, 140)),
}
SPONSORS = ["Halden Therapeutics", "Corvane Bio", "Meridian Pharma", "Ostrava Biologics", "Kestrel Oncology",
            "Brightwater Health", "Lumen Neuroscience", "Tessera Bio"]
COUNTRIES = ["United States", "United States", "United States", "Canada", "Germany", "Spain", "France",
             "United Kingdom", "Poland", "Japan", "South Korea", "Australia", "Brazil"]
SCREEN_FAIL_REASONS = ["Lab values out of range", "Prior or concomitant therapy", "Comorbidity",
                       "Disease severity criteria", "Withdrew consent", "Biomarker negative"]

# Typical values the failure drivers are measured against
REF = {"criteria": 24, "endpoints": 2, "competing": 4, "sponsor_trials": 12, "dropout": 0.12}


@dataclass
class Trial:
    id: str
    title: str
    sponsor: str
    area: str
    indication: str
    phase: str
    target: int
    criteria: int  # inclusion + exclusion criteria
    endpoints: int  # primary + key secondary endpoints
    biomarker: bool  # biomarker-selected population
    novel: bool  # first-in-class mechanism
    competing: int  # competing trials recruiting the same population
    sponsor_trials: int  # trials the sponsor has completed in this area
    plan_months: int  # planned enrollment duration
    elapsed: int  # months since first site activation
    start: date
    sites: list  # dicts: name, country, activated (month index or None), enrolled, screened, rate
    monthly: np.ndarray  # patients randomized per month since start
    screened: int
    discontinued: int
    fail_reasons: dict

    @property
    def enrolled(self):
        return int(self.monthly.sum())

    @property
    def screen_fail(self):
        return 1 - self.enrolled / self.screened if self.screened else 0.0

    @property
    def dropout(self):
        return self.discontinued / self.enrolled if self.enrolled else 0.0

    @property
    def complete(self):
        return self.enrolled >= self.target


def add_months(d, n):
    y, m = divmod(d.month - 1 + n, 12)
    return date(d.year + y, m + 1, 1)


def site_rate_factor(area, criteria, competing, biomarker):
    """Expected patients per active site per month for this trial design."""
    rate = AREAS[area][0]
    rate *= math.exp(-0.035 * (criteria - REF["criteria"]))
    rate *= math.exp(-0.06 * (competing - REF["competing"]))
    return rate * (0.55 if biomarker else 1.0)


def screen_fail_base(criteria, biomarker):
    return min(0.8, 0.12 + 0.007 * criteria + (0.2 if biomarker else 0))


def make_trial(rng, i):
    area = str(rng.choice(list(AREAS)))
    phase = str(rng.choice(list(PHASES), p=[0.2, 0.45, 0.35]))
    _, (n_lo, n_hi), (s_lo, s_hi) = PHASES[phase]
    scale = 0.3 if area == "Rare disease" else 1.0
    target = int(round(rng.uniform(n_lo, n_hi) * scale / 4) * 4) or 12
    n_sites = max(2, int(rng.uniform(s_lo, s_hi) * (0.5 if area == "Rare disease" else 1)))
    criteria = int(rng.integers(12, 42))
    biomarker = bool(rng.random() < (0.55 if area == "Oncology" else 0.15))
    competing = int(rng.poisson(4 if area in ("Oncology", "Neurology") else 2.5))
    rate = site_rate_factor(area, criteria, competing, biomarker)

    # Sponsors plan with the textbook rate and a ramp; reality is usually slower
    ramp = int(min(9, max(2, n_sites / 6)))
    plan_months = int(np.clip(math.ceil(target / (n_sites * rate * 0.85) + ramp), 6, 48))
    reality = rng.lognormal(math.log(0.97), 0.3)
    elapsed = int(rng.integers(3, min(plan_months + 2, 40)))
    start = add_months(AS_OF, -elapsed)

    sites, monthly_by_site = [], []
    for s in range(n_sites):
        planned_on = rng.uniform(0, ramp)
        activated = planned_on + rng.exponential(1 if reality > 0.8 else 2.5)
        act = int(activated) if activated < elapsed else None
        mult = 0.0 if rng.random() < 0.08 else rng.gamma(2.5, 1 / 2.5)
        site_rate = rate * reality * mult
        months = np.zeros(elapsed, dtype=int)
        if act is not None:
            months[act:] = rng.poisson(site_rate, elapsed - act)
        monthly_by_site.append(months)
        sites.append({"name": f"Site {s + 101}", "country": str(rng.choice(COUNTRIES)), "activated": act,
                      "planned_on": int(planned_on), "rate": site_rate})

    # Stop enrolling once the target is reached, trimming the overshoot from the last month
    monthly = np.vstack(monthly_by_site)
    cum = monthly.sum(axis=0).cumsum()
    full = np.flatnonzero(cum >= target)
    if len(full):
        m = full[0]
        monthly[:, m + 1:] = 0
        excess = cum[m] - target
        for s in np.argsort(-monthly[:, m]):
            take = min(excess, monthly[s, m])
            monthly[s, m] -= take
            excess -= take
    sfr = screen_fail_base(criteria, biomarker) * rng.uniform(0.85, 1.15)
    dropout_rate = rng.beta(2, 14) * (1.3 if area == "Neurology" else 1)
    screened_total = 0
    for site, months in zip(sites, monthly):
        enrolled = int(months.sum())
        screened = enrolled + int(rng.poisson(enrolled * sfr / (1 - sfr))) + int(rng.poisson(0.6) if site["activated"] is not None else 0)
        site.update(enrolled=enrolled, screened=screened)
        screened_total += screened
    enrolled = int(monthly.sum())
    discontinued = int(rng.binomial(enrolled, min(0.9, dropout_rate)))

    reasons = SCREEN_FAIL_REASONS if biomarker else SCREEN_FAIL_REASONS[:-1]
    weights = rng.dirichlet(np.array([4, 3, 2.5, 3, 1.2, 6][:len(reasons)]))
    fails = screened_total - enrolled
    counts = np.floor(weights * fails).astype(int)
    counts[0] += fails - counts.sum()
    fail_reasons = dict(zip(reasons, counts.tolist()))

    indication = str(rng.choice(AREAS[area][2]))
    sponsor = str(rng.choice(SPONSORS))
    return Trial(
        id=f"{sponsor[:3].upper()}-{100 + i * 7 + int(rng.integers(0, 7))}",
        title=f"{phase} study in {indication}",
        sponsor=sponsor, area=area, indication=indication, phase=phase, target=target,
        criteria=criteria, endpoints=int(rng.integers(1, 5)), biomarker=biomarker,
        novel=bool(rng.random() < 0.4), competing=competing, sponsor_trials=int(rng.integers(0, 40)),
        plan_months=plan_months, elapsed=elapsed, start=start, sites=sites, monthly=monthly.sum(axis=0),
        screened=screened_total, discontinued=discontinued, fail_reasons=fail_reasons,
    )


def projection(t, add_sites=0, drop_criteria=0):
    """Monte Carlo cumulative enrollment for the next HORIZON months: (paths, n_paths x HORIZON)."""
    remaining = t.target - t.enrolled
    if remaining <= 0:
        return np.zeros((N_PATHS, HORIZON), dtype=int)
    # Seeded by trial id so every worker and every reload gives the same projection
    rng = np.random.default_rng(zlib.crc32(t.id.encode()))

    # Observed rate per active site over the last 6 months, shrunk toward the design rate
    window = min(6, t.elapsed)
    active_months = sum(min(window, t.elapsed - s["activated"]) for s in t.sites if s["activated"] is not None)
    recent = t.monthly[-window:].sum()
    prior = site_rate_factor(t.area, t.criteria, t.competing, t.biomarker) * 0.8
    per_site = (recent + 3 * prior) / (active_months + 3)
    per_site *= math.exp(0.035 * drop_criteria)

    # Active sites each future month: already active, plus pending sites, plus added sites
    months = np.arange(HORIZON)
    active = np.full(HORIZON, sum(s["activated"] is not None for s in t.sites), dtype=float)
    for s in t.sites:
        if s["activated"] is None:
            active += months >= max(1, s["planned_on"] - t.elapsed + 2)
    if add_sites:
        # New sites take ~3 months to activate and enroll slower than established ones
        active += add_sites * 0.75 * np.clip((months - 2) / 3, 0, 1)

    uncertainty = rng.gamma(4, 1 / 4, size=(N_PATHS, 1))
    draws = rng.poisson(per_site * active[None, :] * uncertainty)
    return np.minimum(draws.cumsum(axis=1), remaining)


def enrollment_risk(t, add_sites=0, drop_criteria=0, extend=0):
    if t.complete:
        return {"p_on_time": 1.0, "median": None, "lo": None, "hi": None, "paths": None}
    paths = projection(t, add_sites, drop_criteria)
    remaining = t.target - t.enrolled
    deadline = t.plan_months + extend - t.elapsed  # months left in the planned window
    p = float((paths[:, deadline - 1] >= remaining).mean()) if deadline >= 1 else 0.0
    done = np.where(paths[:, -1] >= remaining, (paths < remaining).sum(axis=1) + 1, HORIZON + 1)
    lo, med, hi = np.percentile(done, [10, 50, 90])
    return {"p_on_time": p, "median": int(med), "lo": int(lo), "hi": int(hi), "paths": paths}


def failure_risk(t, p_on_time, drop_criteria=0):
    """Probability of early termination or a missed primary endpoint, with each driver's contribution."""
    base = -0.45 + PHASES[t.phase][0] + AREAS[t.area][1]
    terms = [
        ("Eligibility criteria", f"{t.criteria - drop_criteria} criteria",
         0.035 * (t.criteria - drop_criteria - REF["criteria"])),
        ("Endpoints", f"{t.endpoints} primary/key", 0.25 * (t.endpoints - REF["endpoints"])),
        ("Mechanism", "First in class" if t.novel else "Validated target", 0.45 if t.novel else -0.15),
        ("Population", "Biomarker-selected" if t.biomarker else "All-comers", -0.55 if t.biomarker else 0.1),
        ("Sponsor experience", f"{t.sponsor_trials} trials in area",
         -0.3 * (math.log1p(t.sponsor_trials) - math.log1p(REF["sponsor_trials"]))),
        ("Dropout", f"{t.dropout:.0%} discontinued", 3 * (t.dropout - REF["dropout"])),
        ("Competing trials", f"{t.competing} recruiting", 0.06 * (t.competing - REF["competing"])),
        ("Enrollment outlook", f"{p_on_time:.0%} on-time", 1.2 * (0.6 - p_on_time)),
    ]
    logit = base + sum(v for _, _, v in terms)
    return {"p_fail": sigmoid(logit), "baseline": sigmoid(base), "base_logit": base, "terms": terms}


def sigmoid(x):
    return 1 / (1 + math.exp(-x))


def level(kind, value):
    """Risk level for enrollment (value = P(on time)) or failure (value = P(fail))."""
    risk = 1 - value if kind == "enrollment" else value
    cuts = (0.25, 0.5, 0.75) if kind == "enrollment" else (0.35, 0.5, 0.62)
    return ("good", "warning", "serious", "critical")[sum(risk >= c for c in cuts)]


LEVEL_LABEL = {"good": "Low", "warning": "Moderate", "serious": "High", "critical": "Critical"}


def verdict(enroll_level, fail_level):
    worst = max(("good", "warning", "serious", "critical").index(x) for x in (enroll_level, fail_level))
    return ("On track", "Watch", "Intervene", "Intervene")[worst]


def score(t, add_sites=0, drop_criteria=0, extend=0):
    e = enrollment_risk(t, add_sites, drop_criteria, extend)
    f = failure_risk(t, e["p_on_time"], drop_criteria)
    el, fl = level("enrollment", e["p_on_time"]), level("failure", f["p_fail"])
    return {**e, **f, "enroll_level": el, "fail_level": fl, "verdict": verdict(el, fl)}


def build_portfolio(n=36):
    rng = np.random.default_rng(SEED)
    trials, seen = [], set()
    for i in range(n):
        t = make_trial(rng, i)
        while t.id in seen:
            t.id = f"{t.id}A"
        seen.add(t.id)
        trials.append(t)
    return trials


TRIALS = build_portfolio()
BY_ID = {t.id: t for t in TRIALS}
SCORES = {t.id: score(t) for t in TRIALS}
