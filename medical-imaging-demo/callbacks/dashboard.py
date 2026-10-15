import asyncio
import random

from dash import callback, ctx, Input, Output, set_props

from components.charts import create_admissions_chart, create_ecg_sparkline
from utils.data_loader import get_admissions_data

# ── ICU patient state ─────────────────────────────────────────────────────────
ICU_BASE = {
    "PT1001": {"hr": 72.0,  "spo2": 98.5, "sbp": 118.0, "dbp": 76.0,  "rr": 14.0},
    "PT1002": {"hr": 92.0,  "spo2": 96.8, "sbp": 148.0, "dbp": 90.0,  "rr": 18.0},
    "PT1003": {"hr": 88.0,  "spo2": 93.5, "sbp": 108.0, "dbp": 68.0,  "rr": 21.0},
    "PT1004": {"hr": 78.0,  "spo2": 99.1, "sbp": 168.0, "dbp": 97.0,  "rr": 16.0},
    "PT1005": {"hr": 66.0,  "spo2": 98.9, "sbp": 125.0, "dbp": 80.0,  "rr": 13.0},
}
PIDS = list(ICU_BASE.keys())


def _hr_color(hr):
    return "#22c55e" if 60 <= hr <= 100 else "#f59e0b" if 50 <= hr <= 120 else "#ef4444"

def _spo2_color(s):
    return "#22c55e" if s >= 95 else "#f59e0b" if s >= 90 else "#ef4444"

def _bp_color(sbp):
    return "#22c55e" if sbp <= 140 else "#f59e0b" if sbp <= 160 else "#ef4444"


# ── Toggle streaming ──────────────────────────────────────────────────────────
@callback(
    Output("live-streaming", "data"),
    Input("icu-live-toggle", "checked"),
)
def toggle_streaming(checked):
    return checked


# ── Admissions chart update ───────────────────────────────────────────────────
@callback(
    Output("admissions-chart", "figure"),
    Input("dashboard-dept",   "value"),
    Input("dashboard-period", "value"),
)
def update_admissions(dept, period):
    df = get_admissions_data(department=dept, period=period)
    return create_admissions_chart(df, department=dept)


# ── Persistent WebSocket: stream ICU vitals ───────────────────────────────────
@callback(persistent=True)
async def stream_patient_vitals():
    ws = ctx.websocket

    vitals = {pid: dict(v) for pid, v in ICU_BASE.items()}
    history = {pid: [vitals[pid]["hr"]] for pid in PIDS}

    while not ws.is_shutdown:
        streaming = await ws.get_prop("live-streaming", "data")

        if streaming:
            for pid in PIDS:
                v = vitals[pid]
                base = ICU_BASE[pid]

                # Mean-reverting Ornstein–Uhlenbeck drift
                v["hr"]  = max(40,  min(200, round(v["hr"]  + 0.15*(base["hr"] -v["hr"]) + random.gauss(0, 1.2),  1)))
                v["spo2"]= max(85,  min(100, round(v["spo2"]+ 0.20*(base["spo2"]-v["spo2"])+ random.gauss(0, 0.25), 1)))
                v["sbp"] = max(70,  min(220, round(v["sbp"] + 0.10*(base["sbp"]-v["sbp"]) + random.gauss(0, 2.0),  1)))
                v["dbp"] = max(40,  min(130, round(v["dbp"] + 0.10*(base["dbp"]-v["dbp"]) + random.gauss(0, 1.5),  1)))
                v["rr"]  = max(8,   min(40,  round(v["rr"]  + 0.15*(base["rr"] -v["rr"]) + random.gauss(0, 0.4),   1)))

                history[pid].append(v["hr"])
                if len(history[pid]) > 40:
                    history[pid] = history[pid][-40:]

                set_props(f"live-hr-{pid}", {
                    "children": f"{v['hr']:.0f}",
                    "style":    {"fontFamily": "monospace", "fontWeight": 700,
                                 "color": _hr_color(v["hr"])},
                })
                set_props(f"live-spo2-{pid}", {
                    "children": f"{v['spo2']:.1f}%",
                    "style":    {"fontFamily": "monospace", "fontWeight": 700,
                                 "color": _spo2_color(v["spo2"])},
                })
                set_props(f"live-bp-{pid}", {
                    "children": f"{int(v['sbp'])}/{int(v['dbp'])}",
                    "style":    {"fontFamily": "monospace", "fontWeight": 700,
                                 "color": _bp_color(v["sbp"])},
                })
                set_props(f"live-rr-{pid}", {
                    "children": f"{v['rr']:.0f}",
                    "style":    {"fontFamily": "monospace", "fontWeight": 700,
                                 "color": "#94a3b8"},
                })

            # ECG sparkline for selected patient
            selected = await ws.get_prop("ecg-patient-select", "value")
            if selected and selected in history and len(history[selected]) > 1:
                fig = create_ecg_sparkline(history[selected], selected)
                set_props("ecg-sparkline-chart", {"figure": fig})

            await asyncio.sleep(1)
        else:
            await asyncio.sleep(0.5)
