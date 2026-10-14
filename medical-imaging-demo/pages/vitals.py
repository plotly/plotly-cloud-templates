import dash_mantine_components as dmc
from dash import dcc
from dash_iconify import DashIconify

from components.charts import create_vitals_chart, create_vitals_variability
from utils.data_loader import get_vitals, df_patients

VITALS_ALL = ["HR", "SpO2", "Temp", "SysBP", "DiaBP", "RR"]
UNITS = {"HR": "bpm", "SpO2": "%", "Temp": "°C",
         "SysBP": "mmHg", "DiaBP": "mmHg", "RR": "/min"}

PATIENT_OPTIONS = [
    {"value": row["patient_id"], "label": f"{row['patient_id']} — {row['name']}"}
    for _, row in df_patients.head(8).iterrows()
]

DEFAULT_PATIENT = PATIENT_OPTIONS[0]["value"]
DEFAULT_VITALS  = ["HR", "SpO2"]
DEFAULT_PERIOD  = "24h"

_df0 = get_vitals(DEFAULT_PATIENT, DEFAULT_PERIOD)

layout = dmc.Stack([
    # ── Page Header ────────────────────────────────────────────────────────────
    dmc.Group([
        dmc.Stack([
            dmc.Title("Patient Vitals", order=2),
            dmc.Text("Vital-sign trends with normal-range reference bands",
                     c="dimmed"),
        ], gap=4),
    ], justify="space-between", mb="md"),

    # ── Filter bar ─────────────────────────────────────────────────────────────
    dmc.Paper(
        dmc.Group([
            dmc.Group([
                dmc.Text("Patient", size="xs", fw=500, c="dimmed"),
                dmc.Select(
                    id="vitals-patient-select",
                    data=PATIENT_OPTIONS,
                    value=DEFAULT_PATIENT,
                    w=260, size="xs",
                ),
            ], gap=6),
            dmc.Divider(orientation="vertical", style={"alignSelf": "stretch"}),
            dmc.Group([
                dmc.Text("Period", size="xs", fw=500, c="dimmed"),
                dmc.SegmentedControl(
                    id="vitals-period",
                    data=["6h", "12h", "24h", "48h", "72h"],
                    value=DEFAULT_PERIOD, size="xs",
                ),
            ], gap=6),
            dmc.Divider(orientation="vertical", style={"alignSelf": "stretch"}),
            dmc.Group([
                dmc.Text("Vitals", size="xs", fw=500, c="dimmed"),
                dmc.MultiSelect(
                    id="vitals-select",
                    data=[{"value": v, "label": v} for v in VITALS_ALL],
                    value=DEFAULT_VITALS,
                    w=260, size="xs", clearable=True,
                ),
            ], gap=6),
            dmc.Divider(orientation="vertical", style={"alignSelf": "stretch"}),
            dmc.Group([
                dmc.Text("Display", size="xs", fw=500, c="dimmed"),
                dmc.Switch(id="vitals-ref-toggle", label="Reference bands",
                           checked=True, size="xs"),
                dmc.Select(
                    id="vitals-ma-select",
                    data=[{"value": "none", "label": "No smoothing"},
                          {"value": "20",   "label": "20-pt MA"},
                          {"value": "50",   "label": "50-pt MA"}],
                    value="none", w=130, size="xs",
                ),
            ], gap=8),
        ], gap="md", align="center"),
        p="sm", radius="md", withBorder=True,
    ),

    # ── Stat Cards ─────────────────────────────────────────────────────────────
    dmc.SimpleGrid([
        dmc.Paper(
            dmc.Stack([
                dmc.Text("Current HR", size="sm", c="dimmed"),
                dmc.Text(
                    f"{_df0['HR'].iloc[-1]:.0f} bpm" if not _df0.empty else "—",
                    size="xl", fw=700, id="stat-current-hr",
                ),
                dmc.Text("Latest reading", size="xs", c="dimmed"),
            ], gap=4),
            p="md", radius="md", withBorder=True,
        ),
        dmc.Paper(
            dmc.Stack([
                dmc.Text("Period High / Low", size="sm", c="dimmed"),
                dmc.Group([
                    dmc.Text(
                        f"{_df0['HR'].max():.0f}" if not _df0.empty else "—",
                        size="xl", fw=700, c="red", id="stat-high-hr",
                    ),
                    dmc.Text("/", size="xl", c="dimmed"),
                    dmc.Text(
                        f"{_df0['HR'].min():.0f}" if not _df0.empty else "—",
                        size="xl", fw=700, c="blue", id="stat-low-hr",
                    ),
                ], gap=4),
                dmc.Text("bpm", size="xs", c="dimmed"),
            ], gap=4),
            p="md", radius="md", withBorder=True,
        ),
        dmc.Paper(
            dmc.Stack([
                dmc.Text("Current SpO₂", size="sm", c="dimmed"),
                dmc.Text(
                    f"{_df0['SpO2'].iloc[-1]:.1f}%" if not _df0.empty else "—",
                    size="xl", fw=700, id="stat-current-spo2",
                ),
                dmc.Text("Latest reading", size="xs", c="dimmed"),
            ], gap=4),
            p="md", radius="md", withBorder=True,
        ),
        dmc.Paper(
            dmc.Stack([
                dmc.Text("Abnormal Readings", size="sm", c="dimmed"),
                dmc.Text("—", size="xl", fw=700, c="red", id="stat-abnormal"),
                dmc.Text("Outside reference range", size="xs", c="dimmed"),
            ], gap=4),
            p="md", radius="md", withBorder=True,
        ),
    ], cols={"base": 2, "md": 4}, spacing="md"),

    # ── Charts with tabs ───────────────────────────────────────────────────────
    dmc.Paper(
        dmc.Stack([
            dmc.Tabs([
                dmc.TabsList([
                    dmc.TabsTab("Trend", value="trend"),
                    dmc.TabsTab("Variability", value="var"),
                ]),
                dmc.TabsPanel(
                    dcc.Graph(
                        id="vitals-trend-chart",
                        figure=create_vitals_chart(_df0, DEFAULT_VITALS),
                        config={"displayModeBar": False},
                        style={"height": "400px"},
                    ),
                    value="trend", pt="md",
                ),
                dmc.TabsPanel(
                    dcc.Graph(
                        id="vitals-var-chart",
                        figure=create_vitals_variability(_df0, DEFAULT_VITALS),
                        config={"displayModeBar": False},
                        style={"height": "400px"},
                    ),
                    value="var", pt="md",
                ),
            ], value="trend"),
        ], gap="sm"),
        p="md", radius="md", withBorder=True,
    ),

    # ── Vitals Summary Table ───────────────────────────────────────────────────
    dmc.Paper(
        dmc.Stack([
            dmc.Text("Vitals Summary", fw=600, size="lg"),
            dmc.Text("Min / Mean / Max for the selected period",
                     size="xs", c="dimmed"),
            dmc.Divider(my="xs"),
            dmc.SimpleGrid(id="vitals-summary-grid", cols=3, spacing="sm"),
        ], gap="sm"),
        p="md", radius="md", withBorder=True,
    ),

], gap="md")
