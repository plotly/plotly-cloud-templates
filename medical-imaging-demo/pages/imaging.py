import dash_mantine_components as dmc
from dash import dcc, html
from dash_iconify import DashIconify

from components.imaging import (load_xray_b64, create_xray_figure, XRAY_DIR,
                                 SEVERITY_COLORS, severity_color, newshape_for)
from components.charts import create_ecg_sparkline
from utils.data_loader import (get_studies, get_patient, get_labs,
                                get_vitals, get_vitals_stats)

df_studies = get_studies()
STUDIES = df_studies.to_dict("records")

# ── Palette (scoped to this page) — light cream + deep navy ─────────────────────
BG_DEEP    = "#f4f3ef"   # off-white, faint cream wash (page backdrop — minimal cream)
BG_SURFACE = "#fcfcfb"   # clean near-white (panels / Paper)
BG_INSET   = "#eef0f2"   # very light cool grey (cards, toolbars, insets)
BORDER     = "#e1e3e7"   # neutral grey border
TEXT_HI    = "#1e2433"   # charcoal (primary text)
TEXT_DIM   = "#6b7280"   # cool slate (secondary text)
ACCENT     = "#1e3a8a"   # deep navy highlight
ACCENT_DK  = "#172554"   # deepest navy (top accent borders)

# Custom Mantine "navy" color ramp (shade 9 = ACCENT)
NAVY_RAMP = ["#eef2fb", "#d9e1f4", "#b3c2e8", "#8aa1db", "#6886d0",
             "#5274c9", "#456bc6", "#37539e", "#27407f", "#1e3a8a"]

# Active study-card tint (replaces the old cyan glow)
CARD_ACTIVE_BG     = "#e6eaf5"   # pale navy
CARD_ACTIVE_SHADOW = "0 0 0 1px rgba(30,58,138,0.2)"
# Neutral light grey behind the X-ray canvas (light viewport)
VIEWPORT_BG = "#e7e9ec"
# DICOM corner overlays render ON TOP of the (inherently dark) X-ray image,
# so they keep light text regardless of the light chrome around them.
OVERLAY_HI     = "#eef2f8"   # near-white
OVERLAY_DIM    = "#aab4c5"   # light slate
OVERLAY_ACCENT = "#7da2e8"   # light navy (legible on the dark X-ray)


# Key labs → one-line clinical interpretation when flagged abnormal
_LAB_INTERPRETATION = {
    "WBC":        "infection / pneumonia",
    "Troponin":   "cardiac injury",
    "Lactate":    "sepsis / hypoperfusion",
    "Creatinine": "renal function",
    "BUN":        "renal function",
    "Hemoglobin": "anemia / bleeding",
    "Glucose":    "glycemic control",
    "Potassium":  "electrolyte imbalance",
    "Sodium":     "electrolyte imbalance",
}


def _risk_badge(patient: dict):
    """Coloured risk badge from a patient's risk_score."""
    score = patient.get("risk_score")
    if score is None:
        return None
    color = "red" if score > 70 else "yellow" if score > 40 else "teal"
    return dmc.Badge(f"Risk {score:.0f}", color=color, variant="light", size="sm")


# ── Premium PACS chrome: patient banner, image overlays, status bar ───────────
_MONO = "ui-monospace, SFMono-Regular, Menlo, monospace"

_DRAW_LABELS = {
    "drawrect": "Rectangle", "drawline": "Line",
    "drawcircle": "Circle", "drawopenpath": "Freehand",
}


def _meta_chip(label: str, value, mono: bool = False):
    """A compact label/value pair for the banner identity row."""
    return dmc.Group([
        dmc.Text(label, size="9px", c=TEXT_DIM, tt="uppercase",
                 style={"letterSpacing": "0.6px", "fontWeight": 700}),
        dmc.Text(str(value), size="xs", fw=600, c=TEXT_HI,
                 style={"fontFamily": _MONO} if mono else None),
    ], gap=5, wrap="nowrap")


def _vitals_tile(pid: str):
    """HR/SpO₂ readout + HR sparkline for the banner."""
    df_vit = get_vitals(pid, "24h")
    if df_vit.empty:
        return dmc.Text("No vitals", size="xs", c=TEXT_DIM)
    hr   = get_vitals_stats(pid, "HR", "24h")
    spo2 = get_vitals_stats(pid, "SpO2", "24h")
    spark = create_ecg_sparkline(df_vit["HR"].tolist())
    return dmc.Group([
        dmc.Stack([
            dmc.Text(f"HR {hr.get('current', '—')}", size="sm", fw=700, c="#22c55e"),
            dmc.Text(f"SpO₂ {spo2.get('current', '—')}%", size="xs", fw=600, c=ACCENT),
        ], gap=2),
        html.Div(
            dcc.Graph(figure=spark, config={"displayModeBar": False},
                      style={"height": "34px", "width": "96px"}),
            style={"width": "96px"},
        ),
    ], gap=8, wrap="nowrap", align="center")


def _lab_chip(test: str, value, unit: str, flag: str):
    up = flag == "H"
    color = "#dc2626" if up else ACCENT
    return dmc.Tooltip(
        label=f"{test} {value:.1f} {unit} — {_LAB_INTERPRETATION.get(test, 'abnormal')}",
        withArrow=True, position="bottom", color="dark",
        children=dmc.Group([
            dmc.Text(test, size="xs", fw=700, c=TEXT_HI),
            DashIconify(icon="tabler:arrow-up" if up else "tabler:arrow-down",
                        width=13, color=color),
        ], gap=3, wrap="nowrap",
           style={"padding": "3px 9px", "borderRadius": "6px",
                  "backgroundColor": BG_INSET,
                  "border": f"1px solid {color}55"}),
    )


def _patient_banner_content(study: dict):
    """Full-width PACS banner: identity (left) + clinical signal (right)."""
    if not study:
        return dmc.Text("No study selected.", size="sm", c=TEXT_DIM)
    pid     = study.get("patient_id")
    patient = get_patient(pid) if pid else {}

    # Identity ────────────────────────────────────────────────────────────────
    identity = dmc.Stack([
        dmc.Group([
            dmc.Text(study.get("patient_name", "—"), size="lg", fw=700, c=TEXT_HI),
            (_risk_badge(patient) or html.Span()),
            (dmc.Text(patient.get("diagnosis", ""), size="xs", c=TEXT_DIM)
             if patient.get("diagnosis") else html.Span()),
        ], gap=10, align="center", wrap="nowrap"),
        dmc.Group([
            _meta_chip("MRN", pid or "—", mono=True),
            _meta_chip("Age/Sex", f"{study.get('age', '—')}/{study.get('gender', '—')}"),
            _meta_chip("Modality", f"CXR {study.get('view_position', '')}".strip()),
            _meta_chip("Acc", study.get("accession", "—"), mono=True),
            _meta_chip("Date", study.get("study_date", "—"), mono=True),
        ], gap=18, wrap="nowrap"),
    ], gap=8)

    # Clinical signal ───────────────────────────────────────────────────────────
    df_labs  = get_labs(pid) if pid else None
    abnormal = (df_labs[df_labs["flag"] != "N"]
                if df_labs is not None and not df_labs.empty else None)
    if abnormal is None or abnormal.empty:
        lab_block = dmc.Text("Labs WNL", size="xs", c="#22c55e", fw=600)
    else:
        lab_block = dmc.Group(
            [_lab_chip(r["test"], r["value"], r["unit"], r["flag"])
             for _, r in abnormal.iterrows()],
            gap=8, wrap="nowrap",
        )

    clinical = dmc.Group([
        dmc.Stack([
            dmc.Text("ABNORMAL LABS", size="9px", c=TEXT_DIM, tt="uppercase",
                     style={"letterSpacing": "0.6px", "fontWeight": 700}),
            lab_block,
        ], gap=4),
        dmc.Divider(orientation="vertical", color=BORDER),
        dmc.Stack([
            dmc.Text("VITALS · 24H", size="9px", c=TEXT_DIM, tt="uppercase",
                     style={"letterSpacing": "0.6px", "fontWeight": 700}),
            _vitals_tile(pid) if pid else dmc.Text("—", size="xs", c=TEXT_DIM),
        ], gap=4),
    ], gap=16, wrap="nowrap", align="center")

    return dmc.Group(
        [identity, clinical],
        justify="space-between", align="center", wrap="nowrap",
        style={"flex": 1},
    )


def _corner(children, vertical: str, horizontal: str, align: str):
    # A subtle dark "scrim" chip keeps the light DICOM text legible whether it
    # falls over the dark X-ray or the light letterbox margins.
    style = {"position": "absolute", vertical: "10px", horizontal: "12px",
             "pointerEvents": "none", "textAlign": align,
             "fontFamily": _MONO, "fontSize": "10px", "lineHeight": "1.5",
             "color": OVERLAY_DIM,
             "backgroundColor": "rgba(15,23,42,0.62)",
             "padding": "5px 9px", "borderRadius": "6px",
             "backdropFilter": "blur(1.5px)"}
    return html.Div(children, style=style)


def _image_overlays(study: dict, window, level, invert: bool):
    """DICOM-style text overlaid in the four corners of the image."""
    study = study or {}
    tl = [html.Div(study.get("patient_name", "—"),
                   style={"color": OVERLAY_HI, "fontWeight": 700}),
          html.Div(f"MRN {study.get('patient_id', '—')}"),
          html.Div(f"{study.get('age', '—')}/{study.get('gender', '—')}")]
    tr = [html.Div(f"ACC {study.get('accession', '—')}",
                   style={"color": OVERLAY_HI, "fontWeight": 700}),
          html.Div(f"{study.get('view_position', '—')}  ·  {study.get('study_date', '—')}")]
    bl = [html.Div(f"W: {int(window or 0)}   L: {int(level or 0)}",
                   style={"color": OVERLAY_ACCENT}),
          html.Div(f"Invert: {'ON' if invert else 'OFF'}")]
    br = [html.Div("CXR", style={"color": OVERLAY_HI, "fontWeight": 700}),
          html.Div("General Hospital"),
          html.Div(study.get("referrer", ""))]
    return [
        _corner(tl, "top", "left", "left"),
        _corner(tr, "top", "right", "right"),
        _corner(bl, "bottom", "left", "left"),
        _corner(br, "bottom", "right", "right"),
    ]


def _status_bar(draw_mode, window, level, invert: bool):
    """Thin professional readout strip under the image."""
    def seg(label, value, accent=False):
        return dmc.Group([
            dmc.Text(label, size="10px", c=TEXT_DIM, tt="uppercase",
                     style={"letterSpacing": "0.5px"}),
            dmc.Text(str(value), size="11px", fw=600,
                     c=ACCENT if accent else TEXT_HI,
                     style={"fontFamily": _MONO}),
        ], gap=5, wrap="nowrap")

    return dmc.Group([
        dmc.Group([
            DashIconify(icon="tabler:pencil", width=13, color=TEXT_DIM),
            seg("Tool", _DRAW_LABELS.get(draw_mode, "Rectangle")),
        ], gap=6, wrap="nowrap"),
        seg("Window", int(window or 0), accent=True),
        seg("Level", int(level or 0), accent=True),
        seg("Invert", "On" if invert else "Off"),
        seg("Matrix", "512×512"),
    ], gap=20, wrap="nowrap",
       style={"padding": "6px 14px", "backgroundColor": BG_DEEP,
              "borderTop": f"1px solid {BORDER}"})


def _study_card(study: dict) -> dmc.UnstyledButton:
    sid      = study["study_id"]
    name     = study.get("patient_name", sid)
    age_sex  = f"{study.get('age', '—')} / {study.get('gender', '—')}"
    view     = study.get("view_position", "")
    finding  = study.get("finding_labels", "").split("|")[0]
    is_normal = finding.lower() in ("no finding", "")
    badge_color = "gray" if is_normal else "navy"

    return dmc.UnstyledButton(
        dmc.Stack([
            dmc.Group([
                dmc.Text(sid, size="xs", c=TEXT_DIM, ff="monospace", fw=600),
                dmc.Badge(view, size="xs", variant="outline",
                          color="gray", radius="sm"),
            ], justify="space-between", wrap="nowrap"),
            dmc.Text(name, size="sm", fw=600, c=TEXT_HI, truncate=True),
            dmc.Group([
                dmc.Text(age_sex, size="xs", c=TEXT_DIM),
                dmc.Badge(finding or "—", size="xs", variant="light",
                          color=badge_color, radius="sm"),
            ], justify="space-between", wrap="nowrap"),
        ], gap=6),
        id={"type": "study-thumb", "index": sid},
        className="study-card",
        style={
            "width": "100%",
            "padding": "10px 12px",
            "backgroundColor": BG_INSET,
            "border": f"1px solid {BORDER}",
            "borderRadius": "8px",
            "textAlign": "left",
            "transition": "border-color 0.15s ease, background-color 0.15s ease",
        },
    )


# ── Defaults ───────────────────────────────────────────────────────────────────
_default  = STUDIES[0]
_img_path = XRAY_DIR / _default["image_file"]
_img_b64  = load_xray_b64(_img_path)
_fig0     = create_xray_figure(_img_b64)
_fig0.update_layout(newshape=newshape_for("Medium"))  # match default severity

DRAW_TOOLS = [
    {"value": "drawrect",     "label": "Rect"},
    {"value": "drawline",     "label": "Line"},
    {"value": "drawcircle",   "label": "Circle"},
    {"value": "drawopenpath", "label": "Path"},
]

FINDING_OPTIONS = [{"value": v, "label": v} for v in [
    "Nodule", "Mass", "Effusion", "Cardiomegaly", "Pneumothorax",
    "Atelectasis", "Consolidation", "Pneumonia", "Infiltration",
    "Fibrosis", "Fracture", "Foreign Body", "Unspecified",
]]


_panel_style = {
    "backgroundColor": BG_SURFACE,
    "border": f"1px solid {BORDER}",
}

_section_label = lambda text: dmc.Text(
    text, size="xs", fw=700, c=TEXT_DIM, tt="uppercase",
    style={"letterSpacing": "0.6px"},
)


# ── Studies panel ──────────────────────────────────────────────────────────────
studies_panel = dmc.Paper(
    dmc.Stack([
        dmc.Group([
            _section_label("Studies"),
            dmc.Badge(str(len(STUDIES)), size="sm", color="navy",
                      variant="light"),
        ], justify="space-between"),
        dmc.Divider(color=BORDER),
        dmc.ScrollArea(
            dmc.Stack([_study_card(s) for s in STUDIES], gap="xs"),
            type="auto", offsetScrollbars=True,
            style={"height": "calc(100vh - 200px)"},
        ),
    ], gap="sm"),
    p="md", radius="md",
    style={**_panel_style, "height": "100%"},
)


# ── Viewport toolbar ───────────────────────────────────────────────────────────
def _slider_control(label, slider_id, mn, mx, val, step=5):
    return dmc.Group([
        dmc.Text(label, size="xs", fw=600, c=TEXT_DIM, w=52),
        html.Div(
            dmc.Slider(
                id=slider_id, min=mn, max=mx, step=step, value=val,
                color="navy", size="sm",
                label=None,
                showLabelOnHover=False,
                marks=[],
            ),
            style={"width": "150px"},
        ),
    ], gap=8, wrap="nowrap")


viewport_toolbar = dmc.Group([
    dmc.Group([
        _slider_control("Window", "window-slider", 30, 255, 220),
        _slider_control("Level",  "level-slider",  10, 245, 128),
        dmc.Switch(
            id="invert-toggle",
            label="Invert",
            checked=False,
            size="sm", color="navy",
            styles={"label": {"color": TEXT_HI, "fontSize": "12px"}},
        ),
    ], gap="lg", wrap="nowrap"),
    dmc.Group([
        dmc.SegmentedControl(
            id="draw-mode-select",
            data=DRAW_TOOLS,
            value="drawrect",
            size="xs", color="navy",
            styles={
                "root": {"backgroundColor": BG_INSET,
                         "border": f"1px solid {BORDER}"},
            },
        ),
        dmc.Button(
            "Reset",
            id="reset-annotations-btn",
            size="xs", variant="subtle", color="gray",
            leftSection=DashIconify(icon="tabler:rotate-clockwise", width=14),
        ),
    ], gap="sm", wrap="nowrap"),
], justify="space-between", align="center", wrap="wrap",
   style={"padding": "10px 14px",
          "backgroundColor": BG_INSET,
          "borderBottom": f"1px solid {BORDER}",
          "borderRadius": "8px 8px 0 0"})


def _severity_dot(level: str):
    return dmc.Group([
        html.Div(style={"width": 8, "height": 8, "borderRadius": "50%",
                        "backgroundColor": SEVERITY_COLORS[level]}),
        dmc.Text(level, size="xs", c=TEXT_DIM),
    ], gap=4, wrap="nowrap")


def _pending_tag(finding="Nodule", severity="Medium", note=""):
    """Live badge showing how the next-drawn shape will be tagged."""
    children = [
        DashIconify(icon="tabler:pencil-plus", width=13,
                    color=severity_color(severity)),
        dmc.Text("Next:", size="xs", c=TEXT_DIM),
        dmc.Text(f"{finding or 'Unspecified'} · {severity or 'Medium'}",
                 size="xs", fw=700, c=severity_color(severity)),
    ]
    if note:
        children.append(dmc.Text(f"“{note}”", size="xs", c=TEXT_DIM,
                                 style={"fontStyle": "italic"}, truncate=True))
    return dmc.Group(children, gap=6, wrap="nowrap")


severity_legend = dmc.Group(
    [dmc.Text("Severity", size="xs", fw=600, c=TEXT_DIM)]
    + [_severity_dot(l) for l in ("Low", "Medium", "High")],
    gap=10, wrap="nowrap",
)


annotation_bar = dmc.Stack([
    dmc.Group([
        dmc.Select(
            id="finding-label-select",
            data=FINDING_OPTIONS,
            value="Nodule",
            placeholder="Finding",
            size="xs", w=150,
            leftSection=DashIconify(icon="tabler:tag", width=14),
        ),
        dmc.Select(
            id="severity-select",
            data=[{"value": v, "label": v} for v in ["Low", "Medium", "High"]],
            value="Medium", size="xs", w=100,
        ),
        dmc.TextInput(
            id="annotation-note",
            placeholder="Note (optional)",
            size="xs",
            style={"flex": 1, "minWidth": "80px"},
            leftSection=DashIconify(icon="tabler:note", width=14),
        ),
    ], gap="sm", wrap="wrap"),
    dmc.Group([
        html.Div(id="pending-annotation", children=_pending_tag()),
        severity_legend,
    ], justify="space-between", align="center", wrap="nowrap"),
], gap=8,
   style={"padding": "10px 14px",
          "backgroundColor": BG_INSET,
          "borderTop": f"1px solid {BORDER}",
          "borderRadius": "0 0 8px 8px"})


viewport_panel = dmc.Paper(
    dmc.Stack([
        dcc.Store(id="xray-annotations", data=[]),
        dcc.Store(id="annotations-store", data={}),   # {study_id: [annotations]}
        dcc.Store(id="current-study-id", data=_default["study_id"]),
        viewport_toolbar,
        html.Div([
            dcc.Graph(
                id="xray-graph",
                figure=_fig0,
                config={
                    "displayModeBar": "hover",
                    "modeBarButtonsToAdd": [
                        "drawrect", "drawline",
                        "drawcircle", "drawopenpath", "eraseshape",
                    ],
                    "modeBarButtonsToRemove": ["toImage"],
                    "scrollZoom": True,
                    "displaylogo": False,
                },
                style={"height": "520px",
                       "backgroundColor": VIEWPORT_BG},
            ),
            html.Div(
                id="image-overlays",
                children=_image_overlays(_default, 220, 128, False),
                style={"position": "absolute", "inset": 0,
                       "pointerEvents": "none"},
            ),
        ], style={"position": "relative", "backgroundColor": VIEWPORT_BG}),
        html.Div(id="image-status-bar",
                 children=_status_bar("drawrect", 220, 128, False)),
        annotation_bar,
    ], gap=0),
    p=0, radius="md",
    style={**_panel_style, "overflow": "hidden"},
)


# ── Right detail panel — Findings (primary focus) ─────────────────────────────
detail_panel = dmc.Paper(
    dmc.Stack([
        dmc.Group([
            dmc.Group([
                DashIconify(icon="tabler:list-search", width=16, color=ACCENT),
                _section_label("Findings"),
            ], gap=8),
            dmc.Badge(id="findings-count", children="0",
                      color="navy", variant="light", size="sm"),
        ], justify="space-between"),
        dmc.Divider(color=BORDER),
        html.Div(
            id="findings-table-container",
            children=dmc.Text(
                "No annotations yet. Draw on the X-ray to add findings.",
                size="sm", c=TEXT_DIM, ta="center", py="md",
            ),
        ),
    ], gap="sm"),
    p="md", radius="md",
    style={**_panel_style, "height": "100%",
           "borderTop": f"2px solid {ACCENT_DK}"},
)


# ── Full layout (scoped dark provider, full-bleed) ────────────────────────────
layout = dmc.MantineProvider(
    forceColorScheme="light",
    theme={
        "primaryColor": "navy",
        "primaryShade": 9,
        "colors": {"navy": NAVY_RAMP},
        "fontFamily": "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
        "components": {
            "Paper": {"defaultProps": {"shadow": "none"}},
        },
    },
    children=dmc.Box(
        dmc.Stack([
            dcc.Download(id="download-radiology-pdf"),

            # ── PACS patient banner ──────────────────────────────────────────
            dmc.Paper(
                dmc.Group([
                    html.Div(id="patient-banner",
                             children=_patient_banner_content(_default),
                             style={"flex": 1, "minWidth": 0}),
                    dmc.Button(
                        "Export",
                        id="export-radiology-btn",
                        size="xs", variant="subtle", color="navy",
                        leftSection=DashIconify(icon="tabler:file-type-pdf", width=15),
                    ),
                ], gap="md", wrap="nowrap", align="center"),
                px="lg", py="sm", radius="md",
                style={**_panel_style, "borderTop": f"2px solid {ACCENT_DK}"},
            ),

            dmc.Grid([
                dmc.GridCol(studies_panel,  span={"base": 12, "md": 2}),
                dmc.GridCol(viewport_panel, span={"base": 12, "md": 6}),
                dmc.GridCol(detail_panel,   span={"base": 12, "md": 4}),
            ], gutter="md", align="stretch"),
        ], gap="md", p="md"),
        style={
            "backgroundColor": BG_DEEP,
            "minHeight": "calc(100vh - 64px)",
            "color": TEXT_HI,
        },
    ),
)
