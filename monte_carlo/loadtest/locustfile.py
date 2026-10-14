"""Load test for the Monte Carlo Pricing Lab.

Simulates analysts using the app the way the browser does: load the page,
let the initial callbacks fire, then click "Run simulation" with new inputs.
Each simulation is 6 callback round-trips: run_simulation, then the five
render callbacks that each post the full result-store back to the server.

Callback payloads are built from the app's own /_dash-dependencies, so the
test keeps working if callback inputs or state are reordered.

    locust -f loadtest/locustfile.py --host https://<de-host>/<app-name>

Extra options (also settable in the web UI):
    --cache-hit-ratio  share of runs that reuse a cached (params, seed) combo
    --max-paths        cap on the path count picked for each run
    --think-time       max seconds a user pauses between actions
"""

import random

from locust import HttpUser, between, events, task
from locust.exception import StopUser

PATH_OPTIONS = [10_000, 50_000, 100_000, 250_000, 500_000]
STEP_OPTIONS = [12, 52, 252]
MAX_PATH_STEPS = 60_000_000  # mirrors app.validation_error
PRODUCTS = ["euro_call", "euro_put", "asian_call", "uo_call"]
MODELS = ["gbm", "merton"]
ESTIMATORS = ["plain", "anti", "cv", "anti_cv"]

# The page's default inputs, i.e. what the initial run_simulation sends.
DEFAULT_INPUTS = {
    "product-select.value": "euro_call",
    "model-radio.value": "gbm",
    "spot-input.value": 100,
    "strike-input.value": 100,
    "maturity-input.value": 1.0,
    "rate-input.value": 4,
    "div-input.value": 1,
    "vol-input.value": 20,
    "barrier-input.value": 130,
    "jump-lambda-input.value": 0.5,
    "jump-mean-input.value": -5,
    "jump-vol-input.value": 10,
    "paths-select.value": 100_000,
    "steps-select.value": 52,
    "seed-input.value": 2026,
    "estimator-select.value": "anti_cv",
}
RENDER_CALLBACKS = {
    "kpi-strip.children": "render_kpis",
    "fan-chart.figure": "render_fan",
    "distribution-chart.figure": "render_distribution",
    "convergence-chart.figure": "render_convergence",
    "..comparison-grid.rowData...comparison-note.children..": "render_comparison",
}


@events.init_command_line_parser.add_listener
def _(parser):
    parser.add_argument("--cache-hit-ratio", type=float, default=0.2,
                        help="Share of runs that repeat cached inputs (0-1)")
    parser.add_argument("--max-paths", type=int, default=250_000,
                        help="Largest path count a simulated user picks")
    parser.add_argument("--think-time", type=float, default=10,
                        help="Max seconds between user actions")  # fmt: skip


def output_spec(output: str):
    """'a.b' -> {'id','property'}; '..a.b...c.d..' -> list of those."""
    if output.startswith(".."):
        return [output_spec(o) for o in output[2:-2].split("...")]
    component_id, prop = output.rsplit(".", 1)
    return {"id": component_id, "property": prop}


class Analyst(HttpUser):
    def wait_time(self):
        return between(1, max(1, self.environment.parsed_options.think_time))(self)

    def on_start(self):
        self.load_page()

    # -- Dash protocol ------------------------------------------------------

    def fetch_dependencies(self):
        with self.client.get("/_dash-dependencies", name="GET _dash-dependencies",
                             catch_response=True) as resp:  # fmt: skip
            if resp.status_code != 200:
                resp.failure(f"HTTP {resp.status_code}")
                raise StopUser()
            self.deps = {d["output"]: d for d in resp.json()}

    def callback(self, output: str, values: dict, changed: list, name: str):
        """POST one callback the way dash-renderer does; returns the response JSON."""
        dep = self.deps[output]
        fill = lambda specs: [  # noqa: E731
            {**s, "value": values.get(f"{s['id']}.{s['property']}")} for s in specs
        ]
        payload = {
            "output": output,
            "outputs": output_spec(output),
            "inputs": fill(dep["inputs"]),
            "changedPropIds": changed,
            "state": fill(dep.get("state", [])),
        }
        with self.client.post("/_dash-update-component", json=payload,
                              name=f"callback {name}", catch_response=True) as resp:  # fmt: skip
            if resp.status_code == 204:  # PreventUpdate
                return None
            if resp.status_code != 200:
                resp.failure(f"HTTP {resp.status_code}: {resp.text[:200]}")
                return None
            return resp.json()

    # -- User flows ---------------------------------------------------------

    def load_page(self):
        self.client.get("/", name="GET page")
        self.client.get("/_dash-layout", name="GET _dash-layout")
        self.fetch_dependencies()
        self.callback("barrier-field.className", DEFAULT_INPUTS,
                      ["product-select.value"], "toggle_barrier")  # fmt: skip
        self.callback("jump-fields.className", DEFAULT_INPUTS,
                      ["model-radio.value"], "toggle_jumps")  # fmt: skip
        self.callback("report-list.children", {"report-history.data": None},
                      ["report-history.data"], "render_report_list")  # fmt: skip
        self.inputs = dict(DEFAULT_INPUTS)
        self.simulate(clicks=None)

    def simulate(self, clicks):
        values = {**self.inputs, "run-button.n_clicks": clicks}
        out = self.callback("..result-store.data...run-message.children..", values,
                            ["run-button.n_clicks"], "run_simulation")  # fmt: skip
        if not out:
            return
        result = out["response"].get("result-store", {}).get("data")
        if not result:
            return  # validation error; nothing to render
        # Server-side compute time, reported as its own row so callback latency
        # can be split into compute vs. queueing behind busy workers.
        events.request.fire(
            request_type="ENGINE", name="engine.run runtime",
            response_time=result["runtime_s"] * 1000, response_length=0,
            exception=None, context={},
        )  # fmt: skip
        for output, name in RENDER_CALLBACKS.items():
            self.callback(output, {"result-store.data": result},
                          ["result-store.data"], name)  # fmt: skip

    def random_inputs(self) -> dict:
        opts = self.environment.parsed_options
        steps = random.choice(STEP_OPTIONS)
        paths = random.choice([p for p in PATH_OPTIONS if p <= opts.max_paths]
                              or PATH_OPTIONS[:1])  # fmt: skip
        while paths * steps > MAX_PATH_STEPS:
            steps = STEP_OPTIONS[STEP_OPTIONS.index(steps) - 1]
        spot = random.randint(80, 120)
        strike = random.randint(80, 120)
        return {
            **DEFAULT_INPUTS,
            "product-select.value": random.choice(PRODUCTS),
            "model-radio.value": random.choice(MODELS),
            "spot-input.value": spot,
            "strike-input.value": strike,
            "vol-input.value": random.randint(10, 60),
            "barrier-input.value": max(spot, strike) + random.randint(10, 40),
            "paths-select.value": paths,
            "steps-select.value": steps,
            "seed-input.value": random.randint(0, 10**9),
            "estimator-select.value": random.choice(ESTIMATORS),
        }

    @task(5)
    def run_simulation(self):
        if random.random() >= self.environment.parsed_options.cache_hit_ratio:
            self.inputs = self.random_inputs()
        # else: rerun the previous inputs, which the worker has likely cached
        self.clicks = getattr(self, "clicks", 0) + 1
        self.simulate(self.clicks)

    @task(1)
    def reload_page(self):
        self.load_page()
