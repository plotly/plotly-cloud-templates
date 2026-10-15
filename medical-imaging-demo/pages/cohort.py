import dash_mantine_components as dmc
from dash import dcc, html
from dash_iconify import DashIconify
import numpy as np

from components.charts import (create_crossfilter_scatter, create_diagnosis_donut,
                                create_age_sex_chart, create_risk_strat_chart,
                                create_vitals_chart)
from components.tables import create_patient_table
from utils.data_loader import get_cohort, get_vitals, df_patients

df_cohort = get_cohort()

VITALS_ALL = ["HR", "SpO2", "Temp", "SysBP", "DiaBP", "RR"]
PATIENT_OPTIONS = [
    {"value": row["patient_id"], "label": f"{row['patient_id']} — {row['name']}"}
    for _, row in df_patients.head(8).iterrows()
]
_default_patient = PATIENT_OPTIONS[0]["value"]
_df_vitals0 = get_vitals(_default_patient, "24h")

_cf1 = create_crossfilter_scatter(df_cohort, "age",        "bmi")
_cf2 = create_crossfilter_scatter(df_cohort, "systolic_bp","ldl")
_cf3 = create_crossfilter_scatter(df_cohort, "hba1c",      "egfr")

SCATTER_CONFIG = {
    "displayModeBar": True,
    "modeBarButtonsToRemove": [
        "zoom2d", "pan2d", "zoomIn2d", "zoomOut2d",
        "autoScale2d", "toImage", "hoverClosestCartesian",
        "hoverCompareCartesian", "toggleSpikelines",
    ],
    "displaylogo": False,
}

crossfilter_view = html.Div([
    dmc.Alert(
        "Lasso or box-select points on any chart — the selection propagates across all three plots.",
        color="navy", variant="light",
        icon=DashIconify(icon="tabler:filter"),
        mb="md",
    ),
    dmc.Grid([
        dmc.GridCol([
            dmc.Paper(
                dcc.Graph(id="cf-scatter1", figure=_cf1,
                          config=SCATTER_CONFIG,
                          style={"height": "320px"}),
                p=0, radius="md", withBorder=True,
                style={"overflow": "hidden"},
            ),
        ], span={"base": 12, "md": 4}),
        dmc.GridCol([
            dmc.Paper(
                dcc.Graph(id="cf-scatter2", figure=_cf2,
                          config=SCATTER_CONFIG,
                          style={"height": "320px"}),
                p=0, radius="md", withBorder=True,
                style={"overflow": "hidden"},
            ),
        ], span={"base": 12, "md": 4}),
        dmc.GridCol([
            dmc.Paper(
                dcc.Graph(id="cf-scatter3", figure=_cf3,
                          config=SCATTER_CONFIG,
                          style={"height": "320px"}),
                p=0, radius="md", withBorder=True,
                style={"overflow": "hidden"},
            ),
        ], span={"base": 12, "md": 4}),
    ], gutter="md"),

    dmc.Grid([
        dmc.GridCol([
            dmc.Paper(
                dmc.Stack([
                    dmc.Text("Cohort Summary", fw=600, size="lg"),
                    dmc.Divider(),
                    dmc.SimpleGrid(id="cf-summary-grid", cols=3, spacing="sm"),
                ], gap="sm"),
                p="md", radius="md", withBorder=True,
            ),
        ], span={"base": 12, "md": 4}),
        dmc.GridCol([
            dmc.Paper(
                dmc.Stack([
                    dmc.Text("Filtered Patients", fw=600, size="lg"),
                    html.Div(id="cf-patient-table"),
                ], gap="sm"),
                p="md", radius="md", withBorder=True,
            ),
        ], span={"base": 12, "md": 8}),
    ], gutter="md", mt="md"),

    # ── Vital Signs Trend (per-patient) ──────────────────────────────────────
    dmc.Divider(mt="xl", mb="md"),
    dmc.Group([
        DashIconify(icon="tabler:activity-heartbeat", width=20, color="#1e3a8a"),
        dmc.Text("Vital Signs Trend", fw=600, size="lg"),
        dmc.Text("per selected patient", c="dimmed", size="sm"),
    ], gap=8, align="center", mb="md"),
    dmc.Paper(
        dmc.Group([
            dmc.Group([
                dmc.Text("Patient", size="xs", fw=500, c="dimmed"),
                dmc.Select(
                    id="cohort-vitals-patient",
                    data=PATIENT_OPTIONS,
                    value=_default_patient,
                    w=260, size="xs",
                ),
            ], gap=6),
            dmc.Divider(orientation="vertical", style={"alignSelf": "stretch"}),
            dmc.Group([
                dmc.Text("Period", size="xs", fw=500, c="dimmed"),
                dmc.SegmentedControl(
                    id="cohort-vitals-period",
                    data=["6h", "12h", "24h", "48h", "72h"],
                    value="24h", size="xs", color="navy",
                ),
            ], gap=6),
            dmc.Divider(orientation="vertical", style={"alignSelf": "stretch"}),
            dmc.Group([
                dmc.Text("Vitals", size="xs", fw=500, c="dimmed"),
                dmc.MultiSelect(
                    id="cohort-vitals-select",
                    data=[{"value": v, "label": v} for v in VITALS_ALL],
                    value=["HR", "SpO2"],
                    w=260, size="xs", clearable=True,
                ),
            ], gap=6),
            dmc.Divider(orientation="vertical", style={"alignSelf": "stretch"}),
            dmc.Group([
                dmc.Text("Display", size="xs", fw=500, c="dimmed"),
                dmc.Switch(id="cohort-vitals-ref-toggle", label="Reference bands",
                           checked=True, size="xs", color="navy"),
                dmc.Select(
                    id="cohort-vitals-ma",
                    data=[{"value": "none", "label": "No smoothing"},
                          {"value": "20",   "label": "20-pt MA"},
                          {"value": "50",   "label": "50-pt MA"}],
                    value="none", w=130, size="xs",
                ),
            ], gap=8),
        ], gap="md", align="center"),
        p="sm", radius="md", withBorder=True, mb="md",
    ),
    dmc.Paper(
        dcc.Graph(
            id="cohort-vitals-trend-chart",
            figure=create_vitals_chart(_df_vitals0, ["HR", "SpO2"]),
            config={"displayModeBar": False},
            style={"height": "420px"},
        ),
        p="md", radius="md", withBorder=True,
    ),
], id="crossfilter-view")


# ── Combined Demographics & Risk view ────────────────────────────────────────
overview_view = html.Div([
    dmc.Grid([
        dmc.GridCol([
            dmc.Paper(
                dcc.Graph(id="demo-donut",
                          figure=create_diagnosis_donut(df_cohort),
                          config={"displayModeBar": False},
                          style={"height": "380px"}),
                p="md", radius="md", withBorder=True,
            ),
        ], span={"base": 12, "md": 6}),
        dmc.GridCol([
            dmc.Paper(
                dcc.Graph(id="demo-agesex",
                          figure=create_age_sex_chart(df_cohort),
                          config={"displayModeBar": False},
                          style={"height": "380px"}),
                p="md", radius="md", withBorder=True,
            ),
        ], span={"base": 12, "md": 6}),
    ], gutter="md"),
    dmc.Paper(
        dcc.Graph(id="risk-strat-chart",
                  figure=create_risk_strat_chart(df_cohort),
                  config={"displayModeBar": False},
                  style={"height": "420px"}),
        p="md", radius="md", withBorder=True, mt="md",
    ),
], id="overview-view", style={"display": "none"})


layout = dmc.Box(
    dmc.Stack([
        dmc.Group([
            dmc.Stack([
                dmc.Title("Cohort Explorer", order=2),
                dmc.Text("200-patient biomarker cohort — linked crossfilter brushing",
                         c="dimmed"),
            ], gap=4),
            dmc.SegmentedControl(
                id="cohort-view",
                data=[
                    {"value": "crossfilter", "label": "Crossfilter"},
                    {"value": "overview",    "label": "Demographics & Risk"},
                ],
                value="crossfilter", color="navy", size="sm", radius="md",
            ),
        ], justify="space-between", mb="lg"),

        crossfilter_view,
        overview_view,
    ], gap="md"),
    p="md",
)
