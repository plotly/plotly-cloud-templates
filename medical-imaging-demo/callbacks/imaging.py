from dash import callback, ctx, Input, Output, State, ALL, no_update, Patch

from components.imaging import (load_xray_b64, create_xray_figure,
                                 get_ai_shapes, XRAY_DIR, _make_shape,
                                 newshape_for, severity_color)
from components.tables import create_findings_table
from utils.data_loader import get_studies, get_study
from pages.imaging import (_patient_banner_content, _image_overlays,
                            _status_bar, _pending_tag,
                            BG_INSET, BORDER, ACCENT,
                            CARD_ACTIVE_BG, CARD_ACTIVE_SHADOW)

df_studies = get_studies()
STUDY_IDS  = df_studies["study_id"].tolist()


# ── Select study via thumbnail buttons ────────────────────────────────────────
@callback(
    Output("current-study-id", "data"),
    Input({"type": "study-thumb", "index": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def select_study(n_clicks_list):
    if not ctx.triggered_id or not any(n_clicks_list):
        return no_update
    # Don't clear annotations — update_xray loads this study's saved set.
    return ctx.triggered_id["index"]


# ── Highlight the active study card ───────────────────────────────────────────
_INACTIVE_STYLE = {
    "width": "100%", "padding": "10px 12px",
    "backgroundColor": BG_INSET,
    "border": f"1px solid {BORDER}",
    "borderRadius": "8px", "textAlign": "left",
    "transition": "border-color 0.15s ease, background-color 0.15s ease",
}
_ACTIVE_STYLE = {
    **_INACTIVE_STYLE,
    "backgroundColor": CARD_ACTIVE_BG,
    "border": f"1px solid {ACCENT}",
    "boxShadow": CARD_ACTIVE_SHADOW,
}

@callback(
    Output({"type": "study-thumb", "index": ALL}, "style"),
    Input("current-study-id", "data"),
    State({"type": "study-thumb", "index": ALL}, "id"),
)
def highlight_active_study(active_id, ids):
    return [_ACTIVE_STYLE if i["index"] == active_id else _INACTIVE_STYLE
            for i in ids]


# ── Main imaging callback ─────────────────────────────────────────────────────
@callback(
    Output("xray-graph",              "figure"),
    Output("xray-annotations",        "data"),
    Output("annotations-store",       "data"),
    Output("findings-table-container","children"),
    Output("findings-count",          "children"),
    Input("xray-graph",            "relayoutData"),
    Input("current-study-id",      "data"),
    Input("window-slider",         "value"),
    Input("level-slider",          "value"),
    Input("invert-toggle",         "checked"),
    Input("reset-annotations-btn", "n_clicks"),
    Input("draw-mode-select",      "value"),
    State("xray-annotations",      "data"),
    State("annotations-store",     "data"),
    State("finding-label-select",  "value"),
    State("severity-select",       "value"),
    State("annotation-note",       "value"),
    prevent_initial_call=True,
)
def update_xray(relayout, study_id, window, level, invert,
                reset_clicks, draw_mode,
                stored, by_study, label, severity, note):
    triggered = ctx.triggered_id
    stored    = stored or []
    by_study  = dict(by_study or {})
    study     = get_study(study_id) if study_id else {}
    key       = study_id or ""

    drawing_event = False

    if triggered == "reset-annotations-btn":
        stored = []

    elif triggered == "current-study-id":
        # Switched study — load this study's saved annotations (persisted),
        # do NOT clear. New studies start empty.
        stored = list(by_study.get(key, []))

    elif triggered == "xray-graph" and relayout:
        if "shapes" in relayout:
            drawing_event = True
            raw_shapes = relayout["shapes"]
            n_raw  = len(raw_shapes)
            n_stored = len(stored)
            if n_raw > n_stored:
                new_raw = raw_shapes[-1]
                sev = severity or "Medium"
                color = severity_color(sev)
                width = 3 if sev == "High" else 2
                stored = stored + [{
                    **new_raw,
                    "line":      {"color": color, "width": width},
                    "_label":    label or "Unspecified",
                    "_severity": sev,
                    "_note":     note or "",
                }]
            elif n_raw < n_stored:
                stored = stored[:n_raw]
            elif n_raw == n_stored and n_raw > 0:
                updated = []
                for raw, old in zip(raw_shapes, stored):
                    updated.append({**raw,
                                    "_label":    old.get("_label", "Unspecified"),
                                    "_severity": old.get("_severity", "Medium"),
                                    "_note":     old.get("_note", "")})
                stored = updated
        else:
            # Pan/zoom relayout — nothing to update
            return (no_update,) * 5

    # Persist this study's annotations into the keyed store
    by_study[key]  = stored
    findings_table = create_findings_table(stored)
    count          = str(len(stored))

    if drawing_event:
        # Shape already rendered on canvas; skip figure rebuild to avoid flicker
        return no_update, stored, by_study, findings_table, count

    img_path = XRAY_DIR / study.get("image_file", "xray_01.png")
    img_b64  = load_xray_b64(img_path,
                              window=float(window or 220),
                              level =float(level  or 128),
                              invert=bool(invert))
    fig = create_xray_figure(img_b64, shapes=stored)
    fig.update_layout(dragmode=draw_mode or "drawrect",
                      newshape=newshape_for(severity))

    return fig, stored, by_study, findings_table, count


# ── Live annotation styling: severity drives the pen colour ───────────────────
@callback(
    Output("xray-graph",         "figure", allow_duplicate=True),
    Output("pending-annotation", "children"),
    Input("severity-select",     "value"),
    Input("finding-label-select","value"),
    Input("annotation-note",     "value"),
    prevent_initial_call=True,
)
def update_pen_style(severity, finding, note):
    """Update the next-shape style + pending badge as the user changes controls.

    Uses a Patch so the X-ray image is not reloaded on every keystroke.
    """
    patch = Patch()
    patch["layout"]["newshape"] = newshape_for(severity)
    return patch, _pending_tag(finding, severity, note)


# ── Patient banner follows the selected study ─────────────────────────────────
@callback(
    Output("patient-banner",  "children"),
    Input("current-study-id", "data"),
)
def update_patient_banner(study_id):
    if not study_id:
        return no_update
    return _patient_banner_content(get_study(study_id))


# ── Image chrome: DICOM corner overlays + status bar ──────────────────────────
@callback(
    Output("image-overlays",   "children"),
    Output("image-status-bar", "children"),
    Input("current-study-id",  "data"),
    Input("window-slider",     "value"),
    Input("level-slider",      "value"),
    Input("invert-toggle",     "checked"),
    Input("draw-mode-select",  "value"),
)
def update_image_chrome(study_id, window, level, invert, draw_mode):
    study = get_study(study_id) if study_id else {}
    overlays = _image_overlays(study, window, level, invert)
    status   = _status_bar(draw_mode, window, level, invert)
    return overlays, status
