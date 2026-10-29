from datetime import datetime

from dash import callback, Input, Output, State, dcc

from utils.pdf_export import create_radiology_report
from utils.data_loader import get_study, get_patient
from components.imaging import annotation_to_finding_dict


@callback(
    Output("download-radiology-pdf", "data"),
    Input("export-radiology-btn",    "n_clicks"),
    State("xray-graph",              "figure"),
    State("xray-annotations",        "data"),
    State("current-study-id",        "data"),
    prevent_initial_call=True,
)
def export_radiology_report(n_clicks, xray_figure, annotations, study_id):
    if not n_clicks:
        return None

    study      = get_study(study_id) if study_id else {}
    patient    = get_patient(study.get("patient_id", "")) if study else {}
    findings   = [annotation_to_finding_dict(a) for a in (annotations or [])]

    pdf_bytes = create_radiology_report(
        xray_figure  = xray_figure,
        findings     = findings,
        patient_info = patient,
        study_info   = study,
    )
    fname = f"radiology_report_{study_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return dcc.send_bytes(pdf_bytes, fname)
