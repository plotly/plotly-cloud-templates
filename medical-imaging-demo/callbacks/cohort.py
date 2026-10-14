import numpy as np
from dash import callback, Input, Output, html, no_update
import dash_mantine_components as dmc

from components.charts import create_crossfilter_scatter, create_vitals_chart
from components.tables import create_patient_table
from utils.data_loader import get_cohort, get_vitals

df = get_cohort()
N  = len(df)


@callback(
    Output("cf-scatter1", "figure"),
    Output("cf-scatter2", "figure"),
    Output("cf-scatter3", "figure"),
    Output("cf-summary-grid",   "children"),
    Output("cf-patient-table",  "children"),
    Input("cf-scatter1", "selectedData"),
    Input("cf-scatter2", "selectedData"),
    Input("cf-scatter3", "selectedData"),
)
def update_crossfilter(sel1, sel2, sel3):
    selected = df.index.tolist()
    for sel in [sel1, sel2, sel3]:
        if sel and sel.get("points"):
            pts = np.array([
                p["customdata"] if "customdata" in p else p["pointIndex"]
                for p in sel["points"]
            ])
            selected = list(np.intersect1d(selected, pts))

    fig1 = create_crossfilter_scatter(df, "age",        "bmi",        selected)
    fig2 = create_crossfilter_scatter(df, "systolic_bp","ldl",        selected)
    fig3 = create_crossfilter_scatter(df, "hba1c",      "egfr",       selected)

    sub = df.iloc[selected] if selected else df.iloc[[]]
    n   = len(sub)

    # Summary cards
    def _metric(label, val):
        return dmc.Paper(
            dmc.Stack([
                dmc.Text(label, size="xs", c="dimmed"),
                dmc.Text(str(val), size="lg", fw=700),
            ], gap=2),
            p="sm", radius="sm", withBorder=True,
        )

    cards = [
        _metric("Selected",     n),
        _metric("Avg Age",      f"{sub['age'].mean():.0f}" if n else "—"),
        _metric("Avg BMI",      f"{sub['bmi'].mean():.1f}" if n else "—"),
        _metric("Avg SysBP",    f"{sub['systolic_bp'].mean():.0f}" if n else "—"),
        _metric("Avg HbA1c",    f"{sub['hba1c'].mean():.1f}" if n else "—"),
        _metric("High Risk",    f"{(sub['risk_level']=='High').sum()}" if n else "—"),
    ]

    # Patient table (capped at 50 for display)
    if n == 0:
        table = dmc.Text("No patients match current selection.", size="sm", c="dimmed", ta="center")
    else:
        table = create_patient_table(
            sub.head(50),
            cols=["patient_id","age","gender","bmi","systolic_bp",
                  "hba1c","egfr","diagnosis","risk_level"],
        )

    return fig1, fig2, fig3, cards, table


@callback(
    Output("crossfilter-view", "style"),
    Output("overview-view",    "style"),
    Input("cohort-view", "value"),
)
def switch_cohort_view(view):
    show, hide = {}, {"display": "none"}
    return [show if v == view else hide for v in ("crossfilter", "overview")]


@callback(
    Output("cohort-vitals-trend-chart", "figure"),
    Input("cohort-vitals-patient",      "value"),
    Input("cohort-vitals-period",       "value"),
    Input("cohort-vitals-select",       "value"),
    Input("cohort-vitals-ref-toggle",   "checked"),
    Input("cohort-vitals-ma",           "value"),
)
def update_cohort_vitals(patient_id, period, vitals, show_ref, ma):
    vitals = vitals or ["HR", "SpO2"]
    df = get_vitals(patient_id, period)
    if df.empty:
        return {}
    return create_vitals_chart(df, vitals, show_reference=show_ref, ma_days=ma or "none")
