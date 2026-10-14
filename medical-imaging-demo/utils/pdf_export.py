import copy
import io
from datetime import datetime

import plotly.io as pio
from PIL import Image as PILImage, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape, portrait
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as rl_canvas
from PyPDF2 import PdfWriter, PdfReader


def figure_to_image_bytes(figure, width: int = 1100, height: int = 650) -> bytes:
    try:
        fig = copy.deepcopy(figure)
        if isinstance(fig, dict):
            fig.setdefault("layout", {})
            fig["layout"]["paper_bgcolor"] = "white"
            fig["layout"]["plot_bgcolor"]  = "white"
        return pio.to_image(fig, format="png", width=width, height=height)
    except Exception as e:
        img = PILImage.new("RGB", (width, height), color=(220, 220, 220))
        ImageDraw.Draw(img).text((20, height // 2), f"Render error: {e}", fill="black")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()


def create_radiology_report(
    xray_figure,
    findings: list,
    patient_info: dict,
    study_info: dict,
) -> bytes:
    """
    Build a PDF radiology report with:
      - Title page (patient + study info)
      - Full-page annotated X-ray image
      - Findings table
    """
    port_w, port_h = portrait(A4)
    land_w, land_h = landscape(A4)

    out = io.BytesIO()
    writer = PdfWriter()

    # ── Title page ─────────────────────────────────────────────────────────────
    tp = io.BytesIO()
    cp = rl_canvas.Canvas(tp, pagesize=portrait(A4))

    # Header band
    cp.setFillColor(colors.HexColor("#0d9488"))
    cp.rect(0, port_h - 2.2 * inch, port_w, 2.2 * inch, fill=1, stroke=0)

    cp.setFillColor(colors.white)
    cp.setFont("Helvetica-Bold", 26)
    cp.drawCentredString(port_w / 2, port_h - 1.0 * inch, "VitalSight Radiology Report")
    cp.setFont("Helvetica", 13)
    cp.drawCentredString(port_w / 2, port_h - 1.65 * inch,
                         f"Generated: {datetime.now().strftime('%B %d, %Y  %H:%M')}")

    # Patient / study info table
    info_y = port_h - 3.2 * inch
    items = [
        ("Patient Name",    patient_info.get("name", "—")),
        ("Patient ID",      patient_info.get("patient_id", "—")),
        ("Age / Gender",    f"{patient_info.get('age','—')} / {patient_info.get('gender','—')}"),
        ("Study ID",        study_info.get("study_id", "—")),
        ("Accession",       study_info.get("accession", "—")),
        ("Study Date",      study_info.get("study_date", "—")),
        ("View",            study_info.get("view_position", "—")),
        ("Referring Physician", study_info.get("referrer", "—")),
    ]
    cp.setFont("Helvetica-Bold", 10)
    cp.setFillColor(colors.HexColor("#1e293b"))
    for label, value in items:
        cp.setFont("Helvetica-Bold", 10)
        cp.setFillColor(colors.HexColor("#475569"))
        cp.drawString(1.0 * inch, info_y, f"{label}:")
        cp.setFont("Helvetica", 10)
        cp.setFillColor(colors.HexColor("#1e293b"))
        cp.drawString(3.0 * inch, info_y, str(value))
        info_y -= 0.32 * inch

    # Disclaimer
    cp.setFont("Helvetica-Oblique", 8)
    cp.setFillColor(colors.HexColor("#94a3b8"))
    cp.drawCentredString(port_w / 2, 0.6 * inch,
                         "SYNTHETIC DATA — FOR DEMONSTRATION PURPOSES ONLY")
    cp.save()
    tp.seek(0)
    writer.add_page(PdfReader(tp).pages[0])

    # ── Annotated X-ray page ───────────────────────────────────────────────────
    xr = io.BytesIO()
    cl = rl_canvas.Canvas(xr, pagesize=landscape(A4))

    cl.setFillColor(colors.HexColor("#0d9488"))
    cl.setFont("Helvetica-Bold", 16)
    cl.drawString(0.8 * inch, land_h - 0.7 * inch, "Imaging Study")

    xray_bytes = figure_to_image_bytes(xray_figure, width=1100, height=750)
    reader = ImageReader(io.BytesIO(xray_bytes))
    img_w, img_h = 10 * inch, 6.8 * inch
    x_off = (land_w - img_w) / 2
    y_off = (land_h - img_h) / 2 - 0.3 * inch
    cl.drawImage(reader, x_off, y_off, width=img_w, height=img_h)

    cl.setFont("Helvetica", 7)
    cl.setFillColor(colors.HexColor("#94a3b8"))
    cl.drawCentredString(land_w / 2, 0.35 * inch,
                         "SYNTHETIC — NOT FOR CLINICAL USE")
    cl.save()
    xr.seek(0)
    writer.add_page(PdfReader(xr).pages[0])

    # ── Findings table page ────────────────────────────────────────────────────
    if findings:
        ft = io.BytesIO()
        fp = rl_canvas.Canvas(ft, pagesize=portrait(A4))

        fp.setFillColor(colors.HexColor("#0d9488"))
        fp.rect(0, port_h - 1.2 * inch, port_w, 1.2 * inch, fill=1, stroke=0)
        fp.setFillColor(colors.white)
        fp.setFont("Helvetica-Bold", 18)
        fp.drawCentredString(port_w / 2, port_h - 0.75 * inch, "Findings")

        headers = ["#", "Finding", "Location (px)", "Type", "Severity", "Note"]
        col_w   = [0.3, 2.0, 2.2, 1.0, 1.0, 1.5]
        col_x   = [1.0 * inch]
        for w in col_w[:-1]:
            col_x.append(col_x[-1] + w * inch)

        row_y = port_h - 1.7 * inch
        fp.setFont("Helvetica-Bold", 9)
        fp.setFillColor(colors.HexColor("#1e293b"))
        for i, h in enumerate(headers):
            fp.drawString(col_x[i], row_y, h)
        row_y -= 0.05 * inch
        fp.setStrokeColor(colors.HexColor("#e2e8f0"))
        fp.line(0.8 * inch, row_y, port_w - 0.8 * inch, row_y)
        row_y -= 0.28 * inch

        fp.setFont("Helvetica", 9)
        for idx, finding in enumerate(findings, 1):
            if row_y < 1.5 * inch:
                break
            fp.setFillColor(colors.HexColor("#1e293b") if idx % 2 else colors.HexColor("#f8fafc"))
            fp.rect(0.8*inch, row_y-0.05*inch, port_w-1.6*inch, 0.28*inch, fill=1, stroke=0)
            fp.setFillColor(colors.HexColor("#1e293b"))
            cells = [
                str(idx),
                finding.get("label", "Unspecified"),
                finding.get("location", "—"),
                finding.get("shape_type", "rect"),
                finding.get("severity", "—"),
                finding.get("note", ""),
            ]
            for i, cell in enumerate(cells):
                fp.drawString(col_x[i], row_y, str(cell)[:28])
            row_y -= 0.28 * inch

        fp.setFont("Helvetica-Oblique", 7)
        fp.setFillColor(colors.HexColor("#94a3b8"))
        fp.drawCentredString(port_w / 2, 0.5 * inch, "SYNTHETIC — NOT FOR CLINICAL USE")
        fp.save()
        ft.seek(0)
        writer.add_page(PdfReader(ft).pages[0])

    writer.write(out)
    out.seek(0)
    return out.getvalue()


def create_summary_pdf(figures: list, titles: list, report_title: str = "Clinical Report") -> bytes:
    """Multi-figure PDF (for future use)."""
    port_w, port_h = portrait(A4)
    land_w, land_h = landscape(A4)
    out = io.BytesIO()
    writer = PdfWriter()

    tp = io.BytesIO()
    cp = rl_canvas.Canvas(tp, pagesize=portrait(A4))
    cp.setFillColor(colors.HexColor("#0d9488"))
    cp.rect(0, port_h - 2*inch, port_w, 2*inch, fill=1, stroke=0)
    cp.setFillColor(colors.white)
    cp.setFont("Helvetica-Bold", 26)
    cp.drawCentredString(port_w/2, port_h - 1.1*inch, report_title)
    cp.setFont("Helvetica", 12)
    cp.drawCentredString(port_w/2, port_h - 1.7*inch,
                         datetime.now().strftime("%B %d, %Y"))
    cp.save()
    tp.seek(0)
    writer.add_page(PdfReader(tp).pages[0])

    for fig, title in zip(figures, titles):
        pb = io.BytesIO()
        cl = rl_canvas.Canvas(pb, pagesize=landscape(A4))
        cl.setFillColor(colors.HexColor("#0d9488"))
        cl.setFont("Helvetica-Bold", 18)
        cl.drawString(1*inch, land_h - 0.75*inch, title)
        img_bytes = figure_to_image_bytes(fig)
        reader = ImageReader(io.BytesIO(img_bytes))
        iw, ih = 10*inch, 6*inch
        cl.drawImage(reader, (land_w-iw)/2, (land_h-ih)/2-0.4*inch, width=iw, height=ih)
        cl.save()
        pb.seek(0)
        writer.add_page(PdfReader(pb).pages[0])

    writer.write(out)
    out.seek(0)
    return out.getvalue()
