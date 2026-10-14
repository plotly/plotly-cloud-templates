import dash_mantine_components as dmc
from dash import dcc, html
from dash_iconify import DashIconify

from components.charts import create_admissions_chart, create_ecg_sparkline
from components.kpi_cards import create_kpi_card, create_risk_row
from utils.data_loader import get_census_metrics, get_risk_overview, get_admissions_data

metrics = get_census_metrics()
risk    = get_risk_overview()
adm_df  = get_admissions_data()

# ── 5 hardcoded ICU patients that the websocket callback streams ──────────────
ICU_PATIENTS = [
    {"id": "PT1001", "name": "J. Smith",    "dx": "Sepsis"},
    {"id": "PT1002", "name": "M. Johnson",  "dx": "Heart Failure"},
    {"id": "PT1003", "name": "R. Williams", "dx": "COPD Exacerbation"},
    {"id": "PT1004", "name": "P. Brown",    "dx": "Hypertensive Crisis"},
    {"id": "PT1005", "name": "J. Garcia",   "dx": "Pneumonia"},
]

# ── Alert thresholds ──────────────────────────────────────────────────────────
ICU_BASE = {
    "PT1001": {"hr": 72,  "spo2": 98.5, "sbp": 118, "dbp": 76,  "rr": 14},
    "PT1002": {"hr": 92,  "spo2": 96.8, "sbp": 148, "dbp": 90,  "rr": 18},
    "PT1003": {"hr": 88,  "spo2": 93.5, "sbp": 108, "dbp": 68,  "rr": 21},
    "PT1004": {"hr": 78,  "spo2": 99.1, "sbp": 168, "dbp": 97,  "rr": 16},
    "PT1005": {"hr": 66,  "spo2": 98.9, "sbp": 125, "dbp": 80,  "rr": 13},
}


def _vital_badge(value_str: str, pid: str, vital: str) -> html.Span:
    return html.Span(value_str, id=f"live-{vital}-{pid}",
                     style={"fontFamily": "monospace", "fontWeight": 700})


def _icu_row(p: dict) -> dmc.Paper:
    pid  = p["id"]
    base = ICU_BASE[pid]
    return dmc.Paper(
        dmc.Group([
            dmc.Stack([
                dmc.Text(p["name"], size="sm", fw=600),
                dmc.Text(p["dx"],   size="xs", c="dimmed"),
            ], gap=2, w=120),
            dmc.Divider(orientation="vertical"),
            dmc.Stack([
                dmc.Text("HR", size="xs", c="dimmed"),
                _vital_badge(str(base["hr"]), pid, "hr"),
                dmc.Text("bpm", size="xs", c="dimmed"),
            ], gap=1, align="center"),
            dmc.Stack([
                dmc.Text("SpO₂", size="xs", c="dimmed"),
                _vital_badge(f"{base['spo2']}%", pid, "spo2"),
            ], gap=1, align="center"),
            dmc.Stack([
                dmc.Text("BP", size="xs", c="dimmed"),
                _vital_badge(f"{base['sbp']}/{base['dbp']}", pid, "bp"),
                dmc.Text("mmHg", size="xs", c="dimmed"),
            ], gap=1, align="center"),
            dmc.Stack([
                dmc.Text("RR", size="xs", c="dimmed"),
                _vital_badge(str(base["rr"]), pid, "rr"),
                dmc.Text("/min", size="xs", c="dimmed"),
            ], gap=1, align="center"),
        ], gap="lg", align="center"),
        p="xs",
        radius="sm",
        withBorder=True,
        style={"backgroundColor": "rgba(0,0,0,0.01)"},
    )


layout = dmc.Stack([
    # ── Header ────────────────────────────────────────────────────────────────
    dmc.Group([
        dmc.Stack([
            dmc.Title("Clinical Dashboard", order=2),
            dmc.Text("Real-time census, ICU vitals, and risk overview", c="dimmed"),
        ], gap=4),
        dmc.Group([
            dmc.SegmentedControl(
                id="dashboard-period",
                data=[{"value": v, "label": v}
                      for v in ["7d","14d","30d"]],
                value="30d",
                size="sm",
            ),
            dmc.Select(
                id="dashboard-dept",
                data=[{"value": "All", "label": "All Departments"}] +
                     [{"value": d, "label": d} for d in
                      ["Cardiology","Pulmonology","Neurology",
                       "General Medicine","Surgery","Nephrology","Oncology"]],
                value="All",
                w=200,
                size="sm",
            ),
        ], gap="sm"),
    ], justify="space-between", mb="lg"),

    # ── KPI Cards ─────────────────────────────────────────────────────────────
    dmc.SimpleGrid([
        create_kpi_card("kpi-total",   "Total Patients",
                        str(metrics["total_patients"]),
                        icon="tabler:users"),
        create_kpi_card("kpi-icu",     "ICU Occupancy",
                        f"{metrics['icu_occupancy']:.1f}%",
                        trend="25 beds",
                        trend_positive=True,
                        icon="tabler:activity"),
        create_kpi_card("kpi-los",     "Avg Length of Stay",
                        f"{metrics['avg_los']} days",
                        icon="tabler:clock"),
        create_kpi_card("kpi-alerts",  "Critical Alerts",
                        str(metrics["critical_alerts"]),
                        trend="Risk score > 70",
                        trend_positive=False,
                        icon="tabler:alert-triangle",
                        alert_color="red"),
    ], cols={"base": 1, "sm": 2, "lg": 4}, spacing="md"),

    # ── Main Row: Live Vitals + Admissions chart ───────────────────────────────
    dmc.Grid([
        # Live ICU vitals panel
        dmc.GridCol([
            dcc.Store(id="live-streaming", data=True),
            dmc.Paper(
                dmc.Stack([
                    dmc.Group([
                        dmc.Group([
                            dmc.Text("Live ICU Monitor", fw=600, size="lg"),
                            html.Div(
                                style={
                                    "width": 8, "height": 8,
                                    "borderRadius": "50%",
                                    "backgroundColor": "#22c55e",
                                    "animation": "pulse 1.5s ease-in-out infinite",
                                },
                                id="live-indicator",
                            ),
                            dmc.Badge("LIVE", color="green", size="sm", variant="light"),
                        ], gap="xs"),
                        dmc.Switch(id="icu-live-toggle", label="Stream",
                                   checked=True, size="sm"),
                    ], justify="space-between"),
                    dmc.Divider(),

                    dmc.Stack([_icu_row(p) for p in ICU_PATIENTS], gap="xs"),

                    dmc.Divider(),
                    dmc.Group([
                        dmc.Text("ECG — ", size="xs", c="dimmed"),
                        dmc.Select(
                            id="ecg-patient-select",
                            data=[{"value": p["id"], "label": p["name"]}
                                  for p in ICU_PATIENTS],
                            value="PT1001",
                            size="xs", w=150,
                        ),
                    ], gap=4),
                    dcc.Graph(
                        id="ecg-sparkline-chart",
                        figure=create_ecg_sparkline([72], "PT1001"),
                        config={"displayModeBar": False},
                        style={"height": "100px"},
                    ),
                ], gap="sm"),
                p="md", radius="md", withBorder=True,
            ),
        ], span={"base": 12, "md": 6}),

        # Admissions chart
        dmc.GridCol([
            dmc.Paper(
                dmc.Stack([
                    dcc.Graph(
                        id="admissions-chart",
                        figure=create_admissions_chart(adm_df),
                        config={"displayModeBar": False},
                        style={"height": "360px"},
                    ),
                ]),
                p="md", radius="md", withBorder=True,
            ),
        ], span={"base": 12, "md": 6}),
    ], gutter="md"),

    # ── Bottom Row: Risk Overview + Quick Stats ────────────────────────────────
    dmc.Grid([
        dmc.GridCol([
            dmc.Paper(
                dmc.Stack([
                    dmc.Text("Population Risk Overview", fw=600, size="lg"),
                    dmc.Text("Average risk scores across all admitted patients",
                             size="xs", c="dimmed"),
                    dmc.Divider(my="sm"),
                    dmc.Stack([
                        create_risk_row("risk-sepsis",  "Sepsis Risk",
                                        f"{risk['sepsis']:.1f}%",
                                        risk["sepsis"], "red"),
                        create_risk_row("risk-fall",    "Fall Risk",
                                        f"{risk['fall']:.1f}%",
                                        risk["fall"],   "orange"),
                        create_risk_row("risk-readmit", "Readmission",
                                        f"{risk['readmit']:.1f}%",
                                        risk["readmit"], "yellow"),
                        create_risk_row("risk-deterioration", "Deterioration",
                                        f"{risk['deterioration']:.1f}%",
                                        risk["deterioration"], "grape"),
                    ], gap="md", mt="sm"),
                ], gap="sm"),
                p="md", radius="md", withBorder=True, h="100%",
            ),
        ], span={"base": 12, "md": 4}),

        dmc.GridCol([
            dmc.Paper(
                dmc.Stack([
                    dmc.Text("Department Snapshot", fw=600, size="lg"),
                    dmc.SimpleGrid([
                        dmc.Paper(
                            dmc.Stack([
                                dmc.Text(dept, size="xs", c="dimmed", fw=600),
                                dmc.Text(str(count), size="lg", fw=700),
                                dmc.Text("admitted today", size="xs", c="dimmed"),
                            ], gap=4),
                            p="sm", radius="sm", withBorder=True,
                        )
                        for dept, count in [
                            ("Cardiology", 12), ("Pulmonology", 8),
                            ("Neurology", 6),   ("Surgery", 10),
                            ("Nephrology", 5),  ("Oncology", 4),
                        ]
                    ], cols=2, spacing="sm"),
                ], gap="sm"),
                p="md", radius="md", withBorder=True,
            ),
        ], span={"base": 12, "md": 4}),

        dmc.GridCol([
            dmc.Paper(
                dmc.Stack([
                    dmc.Text("System Status", fw=600, size="lg"),
                    dmc.Stack([
                        dmc.Group([
                            DashIconify(icon="tabler:circle-filled",
                                        width=10, color="#22c55e"),
                            dmc.Text("EMR System", size="sm"),
                            dmc.Text("Online", size="sm", c="teal", fw=500,
                                     style={"marginLeft": "auto"}),
                        ]),
                        dmc.Group([
                            DashIconify(icon="tabler:circle-filled",
                                        width=10, color="#22c55e"),
                            dmc.Text("PACS Imaging", size="sm"),
                            dmc.Text("Online", size="sm", c="teal", fw=500,
                                     style={"marginLeft": "auto"}),
                        ]),
                        dmc.Group([
                            DashIconify(icon="tabler:circle-filled",
                                        width=10, color="#22c55e"),
                            dmc.Text("Lab Interface", size="sm"),
                            dmc.Text("Online", size="sm", c="teal", fw=500,
                                     style={"marginLeft": "auto"}),
                        ]),
                        dmc.Group([
                            DashIconify(icon="tabler:circle-filled",
                                        width=10, color="#f59e0b"),
                            dmc.Text("ICU Monitoring", size="sm"),
                            dmc.Text("Degraded", size="sm", c="yellow", fw=500,
                                     style={"marginLeft": "auto"}),
                        ]),
                    ], gap="md", mt="sm"),
                    dmc.Divider(my="sm"),
                    dmc.Alert(
                        "All patient data is synthetic and for demonstration only.",
                        color="blue", variant="light", icon=DashIconify(icon="tabler:info-circle"),
                    ),
                ], gap="sm"),
                p="md", radius="md", withBorder=True, h="100%",
            ),
        ], span={"base": 12, "md": 4}),
    ], gutter="md"),

], gap="md")
