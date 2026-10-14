import copy
import io
from datetime import datetime

import plotly.io as pio
from PIL import Image as PILImage, ImageDraw
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape, portrait
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from PyPDF2 import PdfWriter, PdfReader


def figure_to_image_bytes(figure, width=1000, height=600):
    try:
        fig = copy.deepcopy(figure)
        if isinstance(fig, dict):
            fig.setdefault('layout', {})
            fig['layout']['paper_bgcolor'] = 'white'
            fig['layout']['plot_bgcolor'] = 'white'
        return pio.to_image(fig, format="png", width=width, height=height)
    except Exception as e:
        img = PILImage.new("RGB", (width, height), color=(220, 220, 220))
        draw = ImageDraw.Draw(img)
        draw.text((width // 2 - 100, height // 2), f"Render failed: {e}", fill="black")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()


def create_pdf_report(figures, titles=None, report_title="Financial Report"):
    if titles is None:
        titles = [f"Chart {i + 1}" for i in range(len(figures))]

    portrait_w, portrait_h = portrait(A4)
    landscape_w, landscape_h = landscape(A4)

    out = io.BytesIO()
    writer = PdfWriter()

    # Title page
    p_buf = io.BytesIO()
    cp = canvas.Canvas(p_buf, pagesize=portrait(A4))
    cp.setFillColor(colors.HexColor("#2563eb"))
    cp.rect(0, portrait_h - 2 * inch, portrait_w, 2 * inch, fill=1, stroke=0)
    cp.setFillColor(colors.white)
    cp.setFont("Helvetica-Bold", 28)
    cp.drawCentredString(portrait_w / 2, portrait_h - 1.2 * inch, report_title)
    cp.setFont("Helvetica", 14)
    cp.drawCentredString(
        portrait_w / 2,
        portrait_h - 1.8 * inch,
        f"Generated on {datetime.now().strftime('%B %d, %Y')}",
    )
    cp.setFillColor(colors.HexColor("#666666"))
    cp.setFont("Helvetica", 10)
    cp.drawCentredString(portrait_w / 2, 0.5 * inch, "Confidential — not for redistribution")
    cp.save()
    p_buf.seek(0)
    writer.add_page(PdfReader(p_buf).pages[0])

    # One landscape page per figure
    for figure, chart_title in zip(figures, titles):
        fig_img = figure_to_image_bytes(figure)
        l_buf = io.BytesIO()
        cl = canvas.Canvas(l_buf, pagesize=landscape(A4))
        cl.setFillColor(colors.HexColor("#2563eb"))
        cl.setFont("Helvetica-Bold", 20)
        cl.drawString(1 * inch, landscape_h - 0.8 * inch, chart_title)
        img_reader = ImageReader(io.BytesIO(fig_img))
        chart_w, chart_h = 10 * inch, 6 * inch
        x = (landscape_w - chart_w) / 2
        y = (landscape_h - chart_h) / 2 - 0.5 * inch
        cl.drawImage(img_reader, x, y, width=chart_w, height=chart_h)
        cl.setFillColor(colors.HexColor("#666666"))
        cl.setFont("Helvetica", 8)
        cl.drawCentredString(landscape_w / 2, 0.5 * inch, "CONFIDENTIAL")
        cl.save()
        l_buf.seek(0)
        writer.add_page(PdfReader(l_buf).pages[0])

    writer.write(out)
    out.seek(0)
    return out.getvalue()
