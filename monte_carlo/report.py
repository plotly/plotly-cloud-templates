"""Printable pricing report, built as a PDF with ReportLab.

Two landscape Letter pages: inputs and pricing results, then the simulation
diagnostics charts. Charts are drawn natively with reportlab.graphics from the
same engine.run() output the dashboard uses, so no browser is needed.
"""

import io
import math
import re

from reportlab.graphics.shapes import Drawing, Line, PolyLine, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

import engine
from figures import _settled_range
from theme import (
    BAND_INNER,
    BAND_OUTER,
    BASELINE,
    BRAND_ACCENT,
    BRAND_PRIMARY,
    GRID_LINE,
    INK,
    KNOCKED,
    MUTED,
    REFERENCE,
    SAMPLE_PATH,
    SELECTED,
)

PAGE_W, PAGE_H = landscape(letter)
MARGIN = 30
HEADER_H = 46
CONTENT_W = PAGE_W - 2 * MARGIN
FONT = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
RULE = "#EEF2F1"
SOFT_INK = "#4A5A5C"


def _color(value: str) -> colors.Color:
    """A ReportLab color from '#RRGGBB' or 'rgba(r, g, b, a)'."""
    match = re.match(r"rgba\(([\d.]+),\s*([\d.]+),\s*([\d.]+),\s*([\d.]+)\)", value)
    if match:
        r, g, b, a = (float(v) for v in match.groups())
        return colors.Color(r / 255, g / 255, b / 255, alpha=a)
    return colors.HexColor(value)


# ---------------------------------------------------------------------------
# Text styles
# ---------------------------------------------------------------------------

H3 = ParagraphStyle(
    "h3",
    fontName=FONT_BOLD,
    fontSize=9,
    leading=11,
    textColor=_color(BRAND_PRIMARY),
    spaceBefore=8,
    spaceAfter=4,
)
CELL = ParagraphStyle("cell", fontName=FONT, fontSize=8.5, leading=11, textColor=_color(INK))
CELL_LABEL = ParagraphStyle("cell-label", parent=CELL, textColor=_color(SOFT_INK))
CELL_VALUE = ParagraphStyle("cell-value", parent=CELL, fontName=FONT_BOLD)
CELL_HEAD = ParagraphStyle(
    "cell-head", parent=CELL, fontName=FONT_BOLD, textColor=_color(MUTED)
)
NOTE = ParagraphStyle("note", fontName=FONT, fontSize=7.5, leading=9.5, textColor=_color(MUTED))
BULLET = ParagraphStyle(
    "bullet",
    parent=CELL,
    fontSize=8,
    leading=10.5,
    textColor=_color(SOFT_INK),
    leftIndent=10,
    bulletIndent=0,
    spaceAfter=3,
)


# ---------------------------------------------------------------------------
# Page chrome: brand bar and footer
# ---------------------------------------------------------------------------


def _draw_logo(canvas, x, y):
    """Five rising bars, the last in the accent color (matches .brand-flag)."""
    heights = [0.30, 0.50, 0.42, 0.72, 1.0]
    bar_w, gap, full_h = 4, 1.5, 20
    for i, h in enumerate(heights):
        last = i == len(heights) - 1
        canvas.setFillColor(_color(BRAND_ACCENT) if last else colors.Color(1, 1, 1, alpha=0.55))
        canvas.rect(x + i * (bar_w + gap), y, bar_w, full_h * h, stroke=0, fill=1)


def _page_decorator(title: str, subtitle: str):
    def draw(canvas, doc):
        canvas.saveState()
        top = PAGE_H - MARGIN + 12
        canvas.setFillColor(_color(BRAND_PRIMARY))
        canvas.rect(MARGIN, top - HEADER_H, CONTENT_W, HEADER_H, stroke=0, fill=1)
        canvas.setFillColor(_color(BRAND_ACCENT))
        canvas.rect(MARGIN, top - HEADER_H - 3, CONTENT_W, 3, stroke=0, fill=1)

        _draw_logo(canvas, MARGIN + 16, top - HEADER_H / 2 - 10)
        canvas.setFillColor(colors.white)
        canvas.setFont(FONT_BOLD, 13)
        canvas.drawString(MARGIN + 52, top - HEADER_H / 2 - 4.5, "Halcyon Capital")

        right = MARGIN + CONTENT_W - 16
        canvas.setFont(FONT_BOLD, 14)
        canvas.drawRightString(right, top - 21, title)
        canvas.setFillColor(colors.Color(1, 1, 1, alpha=0.75))
        canvas.setFont(FONT, 8.5)
        canvas.drawRightString(right, top - 35, subtitle)

        canvas.setFillColor(_color(MUTED))
        canvas.setFont(FONT, 7)
        canvas.drawString(
            MARGIN,
            MARGIN - 12,
            "Halcyon Capital · Quantitative research demonstration · "
            "Illustrative only; not a trade valuation or investment advice.",
        )
        canvas.drawRightString(MARGIN + CONTENT_W, MARGIN - 12, f"Page {doc.page}")
        canvas.restoreState()

    return draw


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


def _kv_table(rows: list[list[str]], width: float) -> Table:
    data = [[Paragraph("Parameter", CELL_HEAD), Paragraph("Value", CELL_HEAD)]]
    data += [[Paragraph(k, CELL_LABEL), Paragraph(v, CELL_VALUE)] for k, v in rows]
    return _styled(Table(data, colWidths=[width * 0.55, width * 0.45]))


def _grid_table(header: list[str], rows: list[list[str]], widths: list[float]) -> Table:
    data = [[Paragraph(h, CELL_HEAD) for h in header]]
    data += [[Paragraph(c, CELL) for c in row] for row in rows]
    return _styled(Table(data, colWidths=widths))


def _styled(table: Table) -> Table:
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 2.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("LINEBELOW", (0, 0), (-1, 0), 0.75, colors.HexColor("#C7D1D0")),
                ("LINEBELOW", (0, 1), (-1, -1), 0.5, colors.HexColor(RULE)),
            ]
        )
    )
    return table


def _layout(cells: list[list], widths: list[float], row_heights=None) -> Table:
    """An invisible grid used purely for page layout."""
    table = Table(cells, colWidths=widths, rowHeights=row_heights)
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return table


# ---------------------------------------------------------------------------
# Page 1: inputs and results
# ---------------------------------------------------------------------------


def _parameters(result: dict, width: float) -> list:
    p = result["params"]
    rows = [
        ["Product", engine.PRODUCTS[p["product"]]],
        ["Model", engine.MODELS[p["model"]]],
        ["Spot S<sub>0</sub>", f"{p['s0']:g}"],
        ["Strike K", f"{p['k']:g}"],
        ["Maturity T", f"{p['t']:g} yrs"],
        ["Volatility <greek>s</greek>", f"{p['sigma']:.2%}"],
        ["Rate r", f"{p['r']:.2%}"],
        ["Dividend yield q", f"{p['q']:.2%}"],
    ]
    if p["product"] == "uo_call":
        rows.append(["Barrier H", f"{p['barrier']:g} (discrete)"])
    if p["model"] == "merton":
        rows += [
            ["Jump intensity <greek>l</greek>", f"{p['jump_lambda']:g} / yr"],
            ["Jump mean <greek>m</greek><sub>J</sub>", f"{p['jump_mean']:.2%}"],
            ["Jump vol <greek>s</greek><sub>J</sub>", f"{p['jump_vol']:.2%}"],
        ]
    steps = result["steps"]
    rows += [
        ["Paths per estimator", f"{p['n_paths']:,}"],
        ["Time steps", f"{steps}" if steps > 1 else "1 (exact draw at maturity)"],
        ["Seed", f"{p['seed']}"],
    ]
    return [Paragraph("INPUTS", H3), _kv_table(rows, width)]


def _results(result: dict, width: float) -> list:
    head = result["headline"]
    bench = result["benchmark"]
    rows = [
        ["Monte Carlo price", f"{head['price']:.4f}"],
        ["Headline estimator", engine.ESTIMATORS[result["estimator"]]],
        ["Standard error", f"{head['se']:.5f}"],
        ["95% confidence interval", f"{head['ci_low']:.4f} – {head['ci_high']:.4f}"],
        ["Benchmark", result["benchmark_label"]],
    ]
    if bench is not None:
        rows += [
            ["Benchmark price", f"{bench:.4f}"],
            [
                "Error vs benchmark",
                f"{head['price'] - bench:+.4f} ({result['z_score']:+.2f} s.e.)",
            ],
        ]
    rows.append(["Simulation time", f"{result['runtime_s'] * 1000:,.0f} ms"])

    analytic = result["analytic_greeks"] or {}
    greek_rows = [
        [
            name,
            f"{result['greeks'][name]:.4f}",
            f"{analytic[name]:.4f}" if name in analytic else "—",
        ]
        for name in ("Delta", "Gamma", "Vega", "Rho")
    ]
    comparison_rows = [
        [
            row["Estimator"],
            f"{row['Price']:.4f}",
            f"{row['Std error']:.5f}",
            f"{row['Efficiency']:.1f}×" if row["Efficiency"] else "—",
        ]
        for row in result["comparison"]
    ]

    gap = 18
    half = (width - gap) / 2
    greeks = [
        Paragraph("GREEKS", H3),
        _grid_table(
            ["Greek", "Monte Carlo", "Black-Scholes"],
            greek_rows,
            [half * 0.3, half * 0.35, half * 0.35],
        ),
        Spacer(1, 3),
        Paragraph(
            "Bump-and-revalue with common random numbers; "
            "Vega per vol point, Rho per 1% rate move.",
            NOTE,
        ),
    ]
    variance = [
        Paragraph("VARIANCE REDUCTION", H3),
        _grid_table(
            ["Estimator", "Price", "Std error", "Efficiency"],
            comparison_rows,
            [half * 0.32, half * 0.2, half * 0.22, half * 0.26],
        ),
        Spacer(1, 3),
        Paragraph(
            "All estimators use the same number of paths. "
            "Efficiency = plain variance ÷ estimator variance.",
            NOTE,
        ),
    ]
    return [
        Paragraph("PRICING RESULT", H3),
        _kv_table(rows, width),
        Spacer(1, 4),
        _layout([[greeks, "", variance]], [half, gap, half]),
    ]


# ---------------------------------------------------------------------------
# Page 2: charts
# ---------------------------------------------------------------------------


def _nice_step(span: float, target: int = 5) -> float:
    raw = span / target if span > 0 else 1.0
    mag = 10 ** math.floor(math.log10(raw))
    for mult in (1, 2, 2.5, 5, 10):
        if raw <= mult * mag:
            return mult * mag
    return 10 * mag


def _si(v: float) -> str:
    for div, suffix in ((1e9, "G"), (1e6, "M"), (1e3, "k")):
        if abs(v) >= div:
            return f"{v / div:g}{suffix}"
    return f"{v:g}"


class _Plot:
    """A small cartesian plot: grid, right-side y ticks, legend, clipped lines."""

    LEFT, RIGHT, TOP, BOTTOM = 4, 38, 16, 26

    def __init__(self, width, height, x_range, y_range, x_log=False, x_title="", y_fmt=None):
        self.d = Drawing(width, height)
        self.x0, self.x1 = x_range
        self.y0, self.y1 = y_range
        self.x_log = x_log
        self.px0, self.px1 = self.LEFT, width - self.RIGHT
        self.py0, self.py1 = self.BOTTOM, height - self.TOP
        self._legend = []
        self._axes(x_title, y_fmt)

    def _tx(self, x):
        x = min(max(x, self.x0), self.x1)
        if self.x_log:
            x, lo, hi = math.log10(x), math.log10(self.x0), math.log10(self.x1)
        else:
            lo, hi = self.x0, self.x1
        return self.px0 + (x - lo) / (hi - lo) * (self.px1 - self.px0)

    def _ty(self, y):
        return self.py0 + (y - self.y0) / (self.y1 - self.y0) * (self.py1 - self.py0)

    def _clamp_y(self, y):
        return min(max(y, self.y0), self.y1)

    def _axes(self, x_title, y_fmt):
        muted, grid = _color(MUTED), _color(GRID_LINE)
        step = _nice_step(self.y1 - self.y0)
        decimals = next(d for d in range(8) if abs(round(step, d) - step) < 1e-9)
        fmt = y_fmt or (lambda v: f"{v:,.{decimals}f}")
        y = math.ceil(self.y0 / step) * step
        while y <= self.y1 + step * 1e-9:
            py = self._ty(y)
            self.d.add(Line(self.px0, py, self.px1, py, strokeColor=grid, strokeWidth=0.5))
            self.d.add(String(self.px1 + 4, py - 2.5, fmt(y), fontName=FONT, fontSize=7, fillColor=muted))
            y += step

        if self.x_log:
            ticks = [
                10**k
                for k in range(math.ceil(math.log10(self.x0)), math.floor(math.log10(self.x1)) + 1)
            ]
            label = _si
        else:
            xstep = _nice_step(self.x1 - self.x0, 6)
            first = math.ceil(self.x0 / xstep) * xstep
            ticks = [first + i * xstep for i in range(int((self.x1 - first) / xstep + 1e-9) + 1)]
            label = lambda v: f"{v:g}"  # noqa: E731
        for x in ticks:
            px = self._tx(x)
            self.d.add(Line(px, self.py0, px, self.py1, strokeColor=grid, strokeWidth=0.5))
            self.d.add(
                String(px, self.py0 - 9, label(round(x, 10)), fontName=FONT, fontSize=7, fillColor=muted, textAnchor="middle")
            )
        if x_title:
            self.d.add(
                String((self.px0 + self.px1) / 2, 2, x_title, fontName=FONT, fontSize=7.5, fillColor=muted, textAnchor="middle")
            )

    def band(self, xs, lows, highs, fill):
        top = [(self._tx(x), self._ty(self._clamp_y(y))) for x, y in zip(xs, highs)]
        bottom = [(self._tx(x), self._ty(self._clamp_y(y))) for x, y in zip(xs, lows)]
        points = [c for pt in top + bottom[::-1] for c in pt]
        self.d.add(Polygon(points, fillColor=_color(fill), strokeColor=None, strokeWidth=0))

    def line(self, xs, ys, color, width=1.0, name=None):
        """Polyline that breaks wherever it leaves the y-range."""
        segment = []
        for x, y in zip(xs, ys):
            if self.y0 <= y <= self.y1:
                segment += [self._tx(x), self._ty(y)]
            else:
                self._polyline(segment, color, width)
                segment = []
        self._polyline(segment, color, width)
        if name:
            self._legend.append((name, color, "line"))

    def _polyline(self, points, color, width):
        if len(points) >= 4:
            self.d.add(PolyLine(points, strokeColor=_color(color), strokeWidth=width, strokeLineJoin=1))

    def stacked_bars(self, centers, bar_width, layers):
        base = [0.0] * len(centers)
        for name, counts, color in layers:
            for i, (c, n) in enumerate(zip(centers, counts)):
                if n:
                    x0, x1 = self._tx(c - bar_width / 2), self._tx(c + bar_width / 2)
                    y0, y1 = self._ty(base[i]), self._ty(base[i] + n)
                    self.d.add(
                        Rect(x0, y0, x1 - x0, y1 - y0, fillColor=_color(color), strokeColor=colors.white, strokeWidth=0.4)
                    )
                base[i] += n
            self._legend.append((name, color, "box"))

    def hline(self, y, label, dashed=(3, 2)):
        if not self.y0 <= y <= self.y1:
            return
        py = self._ty(y)
        self.d.add(Line(self.px0, py, self.px1, py, strokeColor=_color(REFERENCE), strokeWidth=0.8, strokeDashArray=dashed))
        self.d.add(String(self.px0 + 3, py + 3, label, fontName=FONT, fontSize=7, fillColor=_color(REFERENCE)))

    def vline(self, x, label, dashed=(3, 2)):
        if not self.x0 <= x <= self.x1:
            return
        px = self._tx(x)
        self.d.add(Line(px, self.py0, px, self.py1, strokeColor=_color(REFERENCE), strokeWidth=0.8, strokeDashArray=dashed))
        self.d.add(String(px + 3, self.py1 - 8, label, fontName=FONT, fontSize=7, fillColor=_color(REFERENCE)))

    def legend_item(self, name, color, kind="box"):
        self._legend.append((name, color, kind))

    def drawing(self) -> Drawing:
        x, y = self.px0, self.py1 + 5
        for name, color, kind in self._legend:
            if kind == "line":
                self.d.add(Line(x, y + 2.5, x + 12, y + 2.5, strokeColor=_color(color), strokeWidth=1.5))
            else:
                self.d.add(Rect(x, y, 10, 6, fillColor=_color(color), strokeColor=None))
            self.d.add(String(x + 15, y, name, fontName=FONT, fontSize=7, fillColor=_color(INK)))
            x += 15 + len(name) * 3.6 + 12
        return self.d


def _fan_chart(result: dict, width: float, height: float) -> Drawing:
    fan = result["fan"]
    t = fan["t"]
    values = fan["p05"] + fan["p95"] + [v for path in fan["samples"] for v in path]
    values.append(result["strike"])
    if result["barrier"]:
        values.append(result["barrier"])
    lo, hi = min(values), max(values)
    pad = (hi - lo) * 0.05
    plot = _Plot(width, height, (t[0], t[-1]), (lo - pad, hi + pad), x_title="Years")
    for path in fan["samples"]:
        plot.line(t, path, SAMPLE_PATH, 0.6)
    plot.band(t, fan["p05"], fan["p95"], BAND_OUTER)
    plot.band(t, fan["p25"], fan["p75"], BAND_INNER)
    plot.line(t, fan["p50"], BRAND_PRIMARY, 1.6)
    plot.hline(result["strike"], f"Strike {result['strike']:g}")
    if result["barrier"]:
        plot.hline(result["barrier"], f"Barrier {result['barrier']:g}", dashed=(1, 2))
    plot.legend_item("Sample paths", SAMPLE_PATH, "line")
    plot.legend_item("5–95%", BAND_OUTER)
    plot.legend_item("25–75%", BAND_INNER)
    plot.legend_item("Median", BRAND_PRIMARY, "line")
    return plot.drawing()


def _distribution_chart(result: dict, width: float, height: float) -> Drawing:
    dist = result["distribution"]
    layers = [
        ("Pays off", dist["pays"], SELECTED),
        ("Expires worthless", dist["worthless"], BASELINE),
    ]
    if result["barrier"]:
        layers.append(("Knocked out", dist["knocked"], KNOCKED))
    totals = [sum(col) for col in zip(*(counts for _, counts, _ in layers))]
    half = dist["width"] / 2
    xs = [dist["centers"][0] - half, dist["centers"][-1] + half, result["strike"]]
    if result["barrier"]:
        xs.append(result["barrier"])
    plot = _Plot(
        width,
        height,
        (min(xs), max(xs)),
        (0, max(totals) * 1.08),
        x_title="Terminal price S_T",
        y_fmt=_si,
    )
    plot.stacked_bars(dist["centers"], dist["width"], layers)
    plot.vline(result["strike"], "K")
    if result["barrier"]:
        plot.vline(result["barrier"], "H", dashed=(1, 2))
    return plot.drawing()


def _convergence_chart(result: dict, width: float, height: float) -> Drawing:
    conv = result["convergence"]
    series = [
        ("plain", "Plain", BASELINE, "rgba(169, 184, 182, 0.25)"),
        ("selected", engine.ESTIMATORS[result["estimator"]], SELECTED, "rgba(42, 157, 143, 0.20)"),
    ]
    if result["estimator"] == "plain":
        series = series[1:]
    paths = [n for key, *_ in series for n in conv[key]["paths"]]
    plot = _Plot(
        width,
        height,
        (min(paths), max(paths)),
        tuple(_settled_range(result)),
        x_log=True,
        x_title="Paths (log scale)",
    )
    for key, _name, _color_, fill in series:
        c = conv[key]
        plot.band(c["paths"], c["low"], c["high"], fill)
    for key, name, color, _fill in series:
        c = conv[key]
        plot.line(c["paths"], c["mean"], color, 1.4, name=f"{name} ± 95% CI")
    if result["benchmark"] is not None:
        plot.hline(result["benchmark"], f"{result['benchmark_label']} {result['benchmark']:.4f}")
    return plot.drawing()


METHODOLOGY = [
    "Paths follow risk-neutral GBM, or Merton jump-diffusion with compound-"
    "Poisson log-normal jumps and the martingale compensator "
    "-<greek>lk</greek> dt.",
    "Europeans are sampled exactly at maturity; path-dependent payoffs are "
    "monitored on the discrete time grid shown in the inputs.",
    "Antithetic variates pair each draw Z with -Z. The control variate is the "
    "discounted terminal price, whose expectation S<sub>0</sub>e<super>-qT</super> "
    "is known.",
    "The barrier benchmark shifts the barrier by "
    "exp(0.5826·<greek>s</greek>·<greek>D</greek>t<super>1/2</super>) "
    "(Broadie–Glasserman–Kou) to approximate discrete monitoring; residual "
    "differences include that approximation error.",
]


def _diagnostics(result: dict) -> Table:
    gap = 24
    col = (CONTENT_W - gap) / 2
    chart_h = 205

    def cell(title, drawing):
        return [Paragraph(title, H3), drawing]

    methodology = [Paragraph("METHODOLOGY", H3)] + [
        Paragraph(item, BULLET, bulletText="•") for item in METHODOLOGY
    ]
    return _layout(
        [
            [
                cell("SIMULATED PATHS · PERCENTILE FAN", _fan_chart(result, col, chart_h)),
                "",
                cell(
                    "TERMINAL DISTRIBUTION · BY OUTCOME",
                    _distribution_chart(result, col, chart_h),
                ),
            ],
            [""] * 3,
            [
                cell(
                    "CONVERGENCE · RUNNING ESTIMATE, 95% BAND",
                    _convergence_chart(result, col, chart_h),
                ),
                "",
                methodology,
            ],
        ],
        [col, gap, col],
        row_heights=[None, 10, None],
    )


# ---------------------------------------------------------------------------
# Document
# ---------------------------------------------------------------------------


def report_title(result: dict) -> str:
    p = result["params"]
    return f"{engine.PRODUCTS[p['product']]} · {engine.MODELS[p['model']]}"


def build_report(result: dict, generated_at: str) -> bytes:
    """The two-page pricing report as PDF bytes."""
    p = result["params"]
    subtitle = f"{engine.MODELS[p['model']]} · generated {generated_at}"
    title = f"Monte Carlo pricing report · {engine.PRODUCTS[p['product']]}"

    buffer = io.BytesIO()
    doc = BaseDocTemplate(
        buffer,
        pagesize=(PAGE_W, PAGE_H),
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
        title=title,
        author="Halcyon Capital",
    )
    frame_top = PAGE_H - MARGIN + 12 - HEADER_H - 3 - 6
    frame = lambda name: Frame(  # noqa: E731
        MARGIN, MARGIN, CONTENT_W, frame_top - MARGIN, id=name, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0
    )
    doc.addPageTemplates(
        [
            PageTemplate("summary", [frame("summary")], onPage=_page_decorator(title, subtitle)),
            PageTemplate(
                "diagnostics",
                [frame("diagnostics")],
                onPage=_page_decorator("Simulation diagnostics", subtitle),
            ),
        ]
    )

    gap = 24
    narrow = (CONTENT_W - gap) * 0.32
    wide = CONTENT_W - gap - narrow
    doc.build(
        [
            _layout(
                [[_parameters(result, narrow), "", _results(result, wide)]],
                [narrow, gap, wide],
            ),
            NextPageTemplate("diagnostics"),
            PageBreak(),
            _diagnostics(result),
        ]
    )
    return buffer.getvalue()
