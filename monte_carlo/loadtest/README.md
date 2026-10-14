# Load testing the Monte Carlo Pricing Lab

Locust drives the deployed app over Dash's HTTP protocol (`/_dash-layout`,
`/_dash-dependencies`, `/_dash-update-component`), with no browser. Each user:

1. Loads the page and fires the initial callbacks (toggles, report list, default run).
2. Clicks **Run simulation** with randomized inputs. Each run makes 6 callback
   calls: `run_simulation` plus 5 render callbacks that post the result back.
3. Occasionally reloads the page.

PDF report generation is **not** exercised.

## Run

Run these commands from the `monte_carlo/` directory:

```bash
python -m venv .venv-loadtest && .venv-loadtest/bin/pip install -r loadtest/requirements.txt
```

Interactive web UI (http://localhost:8089) with live charts:

```bash
.venv-loadtest/bin/locust -f loadtest/locustfile.py --host https://<de-host>/<app-name>
```

Headless, with CSV output and an HTML report:

```bash
.venv-loadtest/bin/locust -f loadtest/locustfile.py --host https://<de-host>/<app-name> --headless -u 50 -r 2 -t 10m --csv results/run1 --html results/run1.html
```

`--host` is the app URL **without** a trailing slash.

| Option | Default | Meaning |
| --- | --- | --- |
| `--cache-hit-ratio` | 0.2 | Share of runs that repeat the previous inputs (served by `flask_caching`) |
| `--max-paths` | 250000 | Largest path count a user picks (500000 is the heaviest) |
| `--think-time` | 10 | Max seconds a user pauses between actions |

## Reading the results

- **`callback run_simulation`** is the headline number. It's compute plus time
  spent waiting for a free gunicorn worker.
- **`ENGINE engine.run runtime`** is pure compute, taken from the app's own
  `runtime_s`. When `run_simulation` latency climbs far above this row,
  requests are queueing. Note that cache hits report the original run's runtime.
- Failures with **HTTP 502/504** mean gunicorn workers timed out (`--timeout 120`)
  or the DE ingress gave up waiting.

## Suggested plan

1. **Baseline:** 5 users for 5 min.
2. **Step ramp:** 10 → 25 → 50 → 100 users, 5 min at each step, `-r 1`.
   Watch for the knee where p95 diverges from the ENGINE row.
3. **Soak:** run at about 70% of the knee for 30–60 min to catch memory growth.
   `SimpleCache` is per-process and unbounded in size apart from its TTL.
4. Watch container CPU and memory in the DE app manager while the test runs.

## Notes for Dash Enterprise

- Get approval from the DE admins before you start. The test shares cluster
  resources with other apps.
- Run Locust from a machine that's close to the cluster, not over VPN, so
  client bandwidth doesn't skew the numbers. For more than about 200 users, use
  `--processes -1` or distributed workers.
- Capacity levers to compare between runs: the number of gunicorn `--workers` in the
  `Procfile`, `--threads` (gthread; numpy releases the GIL during heavy work),
  DE container CPU/memory, and the number of web containers (scale in the DE
  app settings). Workers don't share `SimpleCache`. A Redis-backed cache would
  raise cache hit rates across processes.
