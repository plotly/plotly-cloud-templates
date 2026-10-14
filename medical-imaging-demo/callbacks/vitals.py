from dash import callback, Input, Output
import dash_mantine_components as dmc

from components.charts import (create_vitals_chart, create_vitals_variability,
                                VITAL_RANGES)
from utils.data_loader import get_vitals

UNITS = {"HR": "bpm", "SpO2": "%", "Temp": "°C",
         "SysBP": "mmHg", "DiaBP": "mmHg", "RR": "/min"}


@callback(
    Output("vitals-trend-chart", "figure"),
    Output("vitals-var-chart",   "figure"),
    Output("stat-current-hr",    "children"),
    Output("stat-high-hr",       "children"),
    Output("stat-low-hr",        "children"),
    Output("stat-current-spo2",  "children"),
    Output("stat-abnormal",      "children"),
    Output("vitals-summary-grid","children"),
    Input("vitals-patient-select","value"),
    Input("vitals-period",        "value"),
    Input("vitals-select",        "value"),
    Input("vitals-ref-toggle",    "checked"),
    Input("vitals-ma-select",     "value"),
)
def update_vitals(patient_id, period, vitals, show_ref, ma):
    vitals = vitals or ["HR", "SpO2"]
    df = get_vitals(patient_id, period)

    if df.empty:
        empty = dmc.Text("No data", c="dimmed")
        return empty, empty, "—", "—", "—", "—", "—", []

    trend_fig = create_vitals_chart(df, vitals, show_reference=show_ref, ma_days=ma or "none")
    var_fig   = create_vitals_variability(df, vitals)

    # Stat cards
    hr_cur  = f"{df['HR'].iloc[-1]:.0f} bpm"   if "HR"   in df.columns else "—"
    hr_hi   = f"{df['HR'].max():.0f}"           if "HR"   in df.columns else "—"
    hr_lo   = f"{df['HR'].min():.0f}"           if "HR"   in df.columns else "—"
    spo_cur = f"{df['SpO2'].iloc[-1]:.1f}%"     if "SpO2" in df.columns else "—"

    # Count readings outside reference range
    abnormal = 0
    for v in vitals:
        if v in df.columns and v in VITAL_RANGES:
            lo, hi = VITAL_RANGES[v]
            abnormal += int(((df[v] < lo) | (df[v] > hi)).sum())
    abn_str = str(abnormal)

    # Summary grid: one mini-card per vital
    cards = []
    for v in vitals:
        if v not in df.columns:
            continue
        col = df[v]
        lo_r, hi_r = VITAL_RANGES.get(v, (None, None))
        current_val = col.iloc[-1]
        in_range = (lo_r is None or lo_r <= current_val <= hi_r)
        badge_color = "teal" if in_range else "red"
        cards.append(dmc.Paper(
            dmc.Stack([
                dmc.Group([
                    dmc.Text(v, size="xs", fw=600),
                    dmc.Badge("OK" if in_range else "!", color=badge_color, size="xs"),
                ], justify="space-between"),
                dmc.Text(f"{current_val:.1f} {UNITS.get(v,'')}", size="sm", fw=700),
                dmc.Text(f"↓{col.min():.1f}  ↑{col.max():.1f}", size="xs", c="dimmed"),
            ], gap=2),
            p="xs", radius="sm", withBorder=True,
        ))

    return trend_fig, var_fig, hr_cur, hr_hi, hr_lo, spo_cur, abn_str, cards
