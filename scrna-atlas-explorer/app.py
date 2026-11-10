"""
Single-Cell Atlas Explorer

Explore a single-cell RNA-seq atlas of melanoma biopsies taken before and during
anti-PD-1 therapy: a UMAP of every cell colored by annotation, sample or any
gene, a marker dot plot, differential expression between patients, timepoints
or a lasso selection, how cell-type composition shifts with response, the CD8
T cell path from memory to exhaustion, and the quality-control filters that
decide which cells are kept.

The data is synthetic, see atlas.py.
"""

import os
import socket

import dash
import dash_mantine_components as dmc
import numpy as np
import plotly.graph_objects as go
from dash import ALL, Input, Output, State, ctx, dcc, html
from dash._hooks import HooksManager
from dash_iconify import DashIconify

import atlas as at

C = at.CELLS

# ---------------------------------------------------------------- colors
# Dark theme. Kept in sync with assets/style.css.
SURFACE = "#1a1a19"
INK = "#f0efec"
INK_2 = "#c3c2b7"
MUTED = "#898781"
GRID = "#2c2c2a"
AXIS = "#383835"
UNEXPRESSED = "#3a3a37"

# Cell types: one hue family per compartment, a shade per type, plus a text
# label on the UMAP so identity never rests on color alone
TYPE_COLOR = {
    "CD4 naive/memory": "#5fd3a5", "Treg": "#199e70",
    "CD8 TCF7+ memory": "#b7d3f6", "CD8 effector": "#6da7ec", "CD8 exhausted": "#3987e5",
    "Proliferating T": "#2563b8",
    "NK": "#9085e9",
    "B cells": "#e3bc4f", "Plasma cells": "#b07a00",
    "Classical monocytes": "#f2a77e", "TAM C1QC+": "#d95926", "TAM SPP1+": "#e66767", "cDC1": "#f6cfb3",
    "pDC": "#b8452b",
    "CAFs": "#52bf52", "Endothelial": "#2f8c2f",
    "Melanoma MITF-high": "#d55181", "Melanoma AXL-high": "#f09bc0",
    at.LOW_QUALITY: "#6b6a65",
}
COMPARTMENT_COLOR = {
    "CD4 T": "#5fd3a5", "CD8 T": "#6da7ec", "NK": "#9085e9", "B lineage": "#e3bc4f", "Myeloid": "#d95926",
    "Stromal": "#52bf52", "Tumor": "#d55181", at.LOW_QUALITY: "#6b6a65",
}
RESPONSE_COLOR = {"Responder": "#3987e5", "Non-responder": "#d95926"}
TIMEPOINT_COLOR = {"Pre": "#9085e9", "On": "#199e70"}
PATIENT_COLOR = dict(zip(at.PATIENTS, ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300",
                                       "#9085e9", "#e66767"]))
# Sequential: dark (near the surface) to bright, one hue
SEQ_BLUE = [[0, "#184f95"], [0.35, "#2a78d6"], [0.7, "#6da7ec"], [1, "#cde2fb"]]
SEQ_ORANGE = [[0, "#6b2a10"], [0.4, "#b8461b"], [0.75, "#eb6834"], [1, "#fbd3bd"]]
UP, DOWN, NS = "#e66767", "#3987e5", "#5c5b56"

FONT = "system-ui, -apple-system, 'Segoe UI', sans-serif"
MONO = "ui-monospace, 'SF Mono', Menlo, monospace"

THEME = {
    "fontFamily": FONT,
    "headings": {"fontFamily": FONT},
    "primaryColor": "blue",
    "defaultRadius": "md",
    "colors": {
        "dark": ["#f0efec", "#c3c2b7", "#a3a29a", "#898781", "#5c5b56", "#383835", "#1a1a19", "#111110",
                 "#0b0b0a", "#050505"],
    },
}

# Skip installed Dash plugins (such as the Plotly Studio Embedded chat) so the
# explorer renders on its own. Dash loads them once per process, on first app init
HooksManager._registered = True

app = dash.Dash(__name__, title="Single-Cell Atlas Explorer")
server = app.server

HEALTHY_TYPES = [c.name for c in at.CELL_TYPES]
ALL_TYPES = at.CELL_TYPE_NAMES
DEFAULT_GENE = "CXCL13"
DEFAULT_MIN_GENES, DEFAULT_MAX_MITO = 500, 15

COMPARISONS = {
    "r_vs_nr_on": "Responders vs non-responders, on treatment",
    "r_vs_nr_pre": "Responders vs non-responders, pre-treatment",
    "on_vs_pre_r": "On vs pre-treatment, responders (paired)",
    "on_vs_pre_nr": "On vs pre-treatment, non-responders (paired)",
    "type_vs_rest": "Cell type vs all other cells",
    "selection_vs_rest": "Lasso selection vs all other cells",
}


# ---------------------------------------------------------------- helpers


def qc_mask(min_genes, max_mito):
    return (C["n_genes"] >= (min_genes or 0)) & (C["pct_mito"] <= (max_mito or 100))


def view_mask(min_genes, max_mito, responses, timepoints):
    return qc_mask(min_genes, max_mito) & np.isin(C["response"], responses or []) & np.isin(
        C["timepoint"], timepoints or [])


def style(fig, margin=None):
    fig.update_xaxes(gridcolor=GRID, linecolor=AXIS, zeroline=False, tickfont={"color": MUTED, "size": 11},
                     title_font={"color": MUTED, "size": 12})
    fig.update_yaxes(gridcolor=GRID, linecolor=AXIS, zeroline=False, tickfont={"color": MUTED, "size": 11},
                     title_font={"color": MUTED, "size": 12})
    fig.update_layout(
        paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
        font={"family": FONT, "color": INK_2, "size": 12},
        margin=margin or {"l": 56, "r": 16, "t": 12, "b": 40},
        hoverlabel={"bgcolor": "#262624", "bordercolor": AXIS, "font": {"color": INK, "size": 12, "family": FONT}},
        legend={"font": {"color": INK_2, "size": 11}, "bgcolor": "rgba(0,0,0,0)"},
        dragmode=False,
    )
    return fig


def empty_fig(message, height=None):
    fig = go.Figure()
    fig.add_annotation(text=message, showarrow=False, font={"color": MUTED, "size": 13}, x=0.5, y=0.5,
                       xref="paper", yref="paper")
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    style(fig)
    if height:
        fig.update_layout(height=height)
    return fig


def umap_axes(fig):
    fig.update_xaxes(visible=False, scaleanchor="y", scaleratio=1)
    fig.update_yaxes(visible=False)
    return fig


def card(title, body, extra=None, hint=None, className=""):
    head = dmc.Group(
        [dmc.Stack([dmc.Text(title, className="card-title"),
                    dmc.Text(hint, className="card-hint") if hint is not None else None], gap=0), extra],
        justify="space-between", align="flex-start", wrap="nowrap", className="card-head",
    )
    return dmc.Paper([head, body], className=f"card {className}")


def graph(id_, className="graph", **kw):
    return dcc.Graph(id=id_, className=className, config={"displaylogo": False, "displayModeBar": False}, **kw)


def fmt_int(n):
    return f"{n:,}"


def gene_options():
    return [{"group": s, "items": [{"value": g, "label": g} for g in genes]} for s, genes in at.GENE_SETS.items()]


def group_names(comparison, cell_type):
    """Display names for the two sides of a comparison, lower-case except cell-type names."""
    if comparison.startswith("r_vs_nr"):
        return "responders", "non-responders"
    if comparison.startswith("on_vs_pre"):
        return "on treatment", "pre-treatment"
    if comparison == "type_vs_rest":
        return cell_type, "other cells"
    return "selection", "other cells"


def cap(s):
    return s[:1].upper() + s[1:]


def comparison_samples(key):
    """The two sample groups for a between-sample comparison, ordered so paired comparisons line up."""
    r = [p for p in at.PATIENTS if at.RESPONSE[p] == "Responder"]
    nr = [p for p in at.PATIENTS if at.RESPONSE[p] == "Non-responder"]
    if key == "r_vs_nr_on":
        return [f"{p}-On" for p in r], [f"{p}-On" for p in nr], False
    if key == "r_vs_nr_pre":
        return [f"{p}-Pre" for p in r], [f"{p}-Pre" for p in nr], False
    pats = r if key == "on_vs_pre_r" else nr
    return [f"{p}-On" for p in pats], [f"{p}-Pre" for p in pats], True


# ---------------------------------------------------------------- atlas view

COLOR_BY = [
    {"group": "Annotation", "items": [{"value": "cell_type", "label": "Cell type"},
                                      {"value": "compartment", "label": "Compartment"}]},
    {"group": "Sample", "items": [{"value": "response", "label": "Response"},
                                  {"value": "timepoint", "label": "Timepoint"},
                                  {"value": "patient", "label": "Patient"}]},
    {"group": "Continuous", "items": [{"value": "gene", "label": "Selected gene"},
                                      {"value": "pseudotime", "label": "CD8 pseudotime"},
                                      {"value": "n_genes", "label": "Genes detected"},
                                      {"value": "pct_mito", "label": "% mitochondrial"}]},
]
CATEGORY_COLORS = {"cell_type": TYPE_COLOR, "compartment": COMPARTMENT_COLOR, "response": RESPONSE_COLOR,
                   "timepoint": TIMEPOINT_COLOR, "patient": PATIENT_COLOR}


def umap_figure(mask, color_by, gene_name):
    idx = np.where(mask)[0]
    xy = at.CELLS["umap"]
    fig = go.Figure()
    size = 3.2 if len(idx) > 6000 else 4.5
    hover = ("<b>%{customdata[1]}</b><br>%{customdata[2]} · %{customdata[3]}<extra></extra>")

    def cd(sel):
        return np.column_stack([sel, C["cell_type"][sel], C["sample"][sel], C["response"][sel]])

    if color_by in CATEGORY_COLORS:
        colors = CATEGORY_COLORS[color_by]
        for name, color in colors.items():
            sel = idx[C[color_by][idx] == name]
            if not len(sel):
                continue
            kw = {}
            if color_by == "cell_type":
                comp = at.CELLS["compartment"][sel[0]]
                kw = {"legendgroup": comp, "legendgrouptitle": {"text": comp, "font": {"color": MUTED, "size": 11}}}
            fig.add_trace(go.Scattergl(
                x=xy[sel, 0], y=xy[sel, 1], mode="markers", name=f"{name}", customdata=cd(sel),
                marker={"size": size, "color": color, "opacity": 0.85, "line": {"width": 0}},
                hovertemplate=hover, **kw,
            ))
        if color_by in ("cell_type", "compartment"):
            for name in colors:
                sel = idx[C[color_by][idx] == name]
                if len(sel) < 25 or name == at.LOW_QUALITY:
                    continue
                cx, cy = np.median(xy[sel, 0]), np.median(xy[sel, 1])
                fig.add_annotation(x=cx, y=cy, text=name, showarrow=False,
                                   font={"color": INK, "size": 11}, bgcolor="rgba(17,17,16,0.72)", borderpad=2)
        fig.update_layout(legend={"itemsizing": "constant", "groupclick": "toggleitem", "tracegroupgap": 6})
    else:
        if color_by == "gene":
            vals, title, scale = at.gene(gene_name)[idx], f"{gene_name}<br>log-norm", SEQ_BLUE
        elif color_by == "pseudotime":
            vals, title, scale = C["pseudotime"][idx], "Pseudo-<br>time", SEQ_ORANGE
        elif color_by == "n_genes":
            vals, title, scale = np.log10(C["n_genes"][idx]), "Genes<br>(log10)", SEQ_BLUE
        else:
            vals, title, scale = C["pct_mito"][idx], "% mito", SEQ_ORANGE
        zero = ~(vals > 0) if color_by in ("gene", "pseudotime") else np.zeros(len(idx), bool)
        z = idx[zero]
        fig.add_trace(go.Scattergl(
            x=xy[z, 0], y=xy[z, 1], mode="markers", name="Not expressed" if color_by == "gene" else "Not CD8",
            marker={"size": size, "color": UNEXPRESSED, "line": {"width": 0}}, customdata=cd(z),
            hovertemplate=hover, showlegend=False,
        ))
        nz = idx[~zero]
        v = vals[~zero]
        order = np.argsort(v)
        nz, v = nz[order], v[order]
        fig.add_trace(go.Scattergl(
            x=xy[nz, 0], y=xy[nz, 1], mode="markers", showlegend=False,
            customdata=np.column_stack([cd(nz), np.round(v, 2)]),
            marker={"size": size + 0.6, "color": v, "colorscale": scale, "line": {"width": 0},
                    "colorbar": {"title": {"text": title, "font": {"color": MUTED, "size": 11}}, "thickness": 10,
                                 "len": 0.5, "outlinewidth": 0, "tickfont": {"color": MUTED, "size": 10}, "x": 1.0}},
            hovertemplate="<b>%{customdata[1]}</b><br>%{customdata[2]} · %{customdata[3]}"
                          "<br>Value %{customdata[4]}<extra></extra>",
        ))
    style(fig, {"l": 8, "r": 8, "t": 8, "b": 8})
    fig.update_layout(dragmode="lasso", uirevision="umap", hovermode="closest",
                      selectionrevision="umap", newselection={"line": {"color": INK, "width": 1}})
    return umap_axes(fig)


def gene_violin(mask, gene_name):
    vals = at.gene(gene_name)
    rows = []
    for t in HEALTHY_TYPES:
        sel = mask & (C["cell_type"] == t)
        if sel.sum() >= 5:
            v = vals[sel]
            rows.append((t, v, (v > 0).mean(), v.mean()))
    if not rows:
        return empty_fig("No cells pass the current filters")
    rows.sort(key=lambda r: r[3])
    fig = go.Figure()
    for t, v, pct, mean in rows:
        fig.add_trace(go.Violin(
            x=v, y=[t] * len(v), name=t, orientation="h", side="positive", width=1.6, points=False,
            line={"width": 1, "color": TYPE_COLOR[t]}, fillcolor=TYPE_COLOR[t], opacity=0.75,
            spanmode="hard", meanline={"visible": False}, showlegend=False,
            hoveron="violins", text=f"{t}<br>{pct:.0%} of cells express · mean {mean:.2f}",
            hoverinfo="text",
        ))
    for t, v, pct, mean in rows:
        fig.add_annotation(x=1.0, xref="paper", y=t, text=f"{pct:.0%}", showarrow=False, xanchor="left",
                           font={"color": MUTED, "size": 10, "family": MONO}, xshift=4)
    style(fig, {"l": 140, "r": 40, "t": 8, "b": 40})
    fig.update_xaxes(title=f"{gene_name}, log-normalized expression", rangemode="tozero")
    fig.update_yaxes(gridcolor=SURFACE, tickfont={"color": INK_2, "size": 11})
    fig.update_layout(height=max(320, 26 * len(rows) + 60), violingap=0, violinmode="overlay")
    return fig


# ---------------------------------------------------------------- markers view


def dot_plot(mask, mode, gene_name):
    if mode == "curated":
        genes = at.CURATED_MARKERS
    else:
        genes = []
        for t in HEALTHY_TYPES:
            genes += [g for g in at.top_markers(t, 2) if g not in genes]
    types = [t for t in HEALTHY_TYPES if (mask & (C["cell_type"] == t)).sum() >= 5]
    if not types:
        return empty_fig("No cells pass the current filters")
    gi = [at.GENE_INDEX[g] for g in genes]
    mean = np.zeros((len(types), len(genes)))
    pct = np.zeros_like(mean)
    for i, t in enumerate(types):
        e = at.EXPR[mask & (C["cell_type"] == t)][:, gi]
        mean[i], pct[i] = e.mean(0), (e > 0).mean(0)
    scaled = mean / (mean.max(0, keepdims=True) + 1e-9)
    xs, ys = np.meshgrid(np.arange(len(genes)), np.arange(len(types)))
    fig = go.Figure(go.Scatter(
        x=np.array(genes)[xs.ravel()], y=np.array(types)[ys.ravel()], mode="markers",
        marker={"size": 4 + 16 * np.sqrt(pct.ravel()), "color": scaled.ravel(), "colorscale": SEQ_BLUE,
                "cmin": 0, "cmax": 1, "line": {"width": 0},
                "colorbar": {"title": {"text": "Mean, scaled<br>per gene", "font": {"color": MUTED, "size": 11}},
                             "thickness": 10, "len": 0.4, "y": 0.8, "outlinewidth": 0,
                             "tickfont": {"color": MUTED, "size": 10}}},
        customdata=np.column_stack([pct.ravel() * 100, mean.ravel()]),
        hovertemplate="<b>%{x}</b> in %{y}<br>%{customdata[0]:.0f}% of cells express"
                      "<br>Mean %{customdata[1]:.2f}<extra></extra>",
        showlegend=False,
    ))
    # Size key
    for p in (0.25, 0.5, 0.75, 1.0):
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", name=f"{p:.0%}",
                                 marker={"size": 4 + 16 * np.sqrt(p), "color": MUTED},
                                 legendgroup="size", legendgrouptitle={"text": "% expressing"}))
    if gene_name in genes:
        fig.add_vrect(x0=genes.index(gene_name) - 0.5, x1=genes.index(gene_name) + 0.5,
                      fillcolor="rgba(240,239,236,0.06)", line_width=0, layer="below")
    style(fig, {"l": 150, "r": 24, "t": 8, "b": 72})
    fig.update_xaxes(tickangle=-50, tickfont={"color": INK_2, "size": 11}, showgrid=False)
    fig.update_yaxes(autorange="reversed", tickfont={"color": INK_2, "size": 11})
    fig.update_layout(height=34 * len(types) + 120, legend={"x": 1.02, "y": 0.35, "itemsizing": "trace"})
    return fig


# ---------------------------------------------------------------- differential expression


def run_de(comparison, cell_type, min_genes, max_mito, selection):
    healthy = qc_mask(min_genes, max_mito) & (C["cell_type"] != at.LOW_QUALITY)
    if comparison == "selection_vs_rest":
        if not selection:
            return None, "Draw a lasso around cells on the Atlas UMAP to compare them with everything else."
        in_mask = np.zeros(at.N_CELLS, bool)
        in_mask[selection] = True
        in_mask &= healthy
        if in_mask.sum() < 10:
            return None, "Fewer than 10 selected cells pass QC. Select a larger group."
        return at.cells_vs_rest(in_mask, healthy & ~in_mask), None
    if comparison == "type_vs_rest":
        if cell_type == "All":
            return None, "Pick a cell type to compare against all other cells."
        in_mask = healthy & (C["cell_type"] == cell_type)
        return at.cells_vs_rest(in_mask, healthy & ~in_mask), None
    mask = healthy if cell_type == "All" else healthy & (C["cell_type"] == cell_type)
    a, b, paired = comparison_samples(comparison)
    res = at.samples_test(mask, a, b, paired)
    if res is None:
        return None, f"Too few samples with at least 10 {cell_type} cells for this comparison."
    return res, None


def volcano(res, comparison, cell_type, gene_name):
    """Volcano for sample-level tests. Cell-level tests saturate p, so they plot detection difference instead."""
    lfc, q = np.asarray(res["log2fc"], float), np.asarray(res["q"], float)
    by_cells = res["unit"] == "cells"
    y = -np.log10(q)
    y_plot = (res["pct_in"] - res["pct_out"]) * 100 if by_cells else y
    sig_up = (q < 0.05) & (lfc >= 1)
    sig_dn = (q < 0.05) & (lfc <= -1)
    a_name, b_name = group_names(comparison, cell_type)
    fig = go.Figure()
    genes = np.array(at.GENES)
    cd = np.column_stack([genes, np.round(lfc, 2), [f"{v:.1e}" for v in q], np.round(res["pct_in"] * 100),
                          np.round(res["pct_out"] * 100)])
    for m, color, name in [(~sig_up & ~sig_dn, NS, "Not significant"), (sig_up, UP, f"Higher in {a_name}"),
                           (sig_dn, DOWN, f"Higher in {b_name}")]:
        fig.add_trace(go.Scatter(
            x=lfc[m], y=y_plot[m], mode="markers", name=f"{name} ({m.sum()})", customdata=cd[m],
            marker={"size": 8, "color": color, "opacity": 0.9, "line": {"width": 1, "color": SURFACE}},
            hovertemplate="<b>%{customdata[0]}</b><br>log2 FC %{customdata[1]}<br>adj. p %{customdata[2]}"
                          f"<br>Expressed in %{{customdata[3]}}% of cells in {a_name}, "
                          f"%{{customdata[4]}}% in {b_name}<extra></extra>",
        ))
    # Label the strongest hits on each side, skipping any that would collide with a placed label
    score = np.abs(y_plot) * np.abs(lfc)
    lim = max(2.5, float(np.nanmax(np.abs(lfc))) * 1.1)
    yspan = 210 if by_cells else max(float(y_plot.max()), 1) * 1.05
    placed = []
    for m in (sig_up, sig_dn):
        for i in np.argsort(-np.where(m, score, -1))[:12]:
            if not m[i]:
                continue
            nx, ny = lfc[i] / (2 * lim), y_plot[i] / yspan
            if any(abs(nx - px) < 0.07 and abs(ny - py) < 0.05 for px, py in placed):
                continue
            placed.append((nx, ny))
            fig.add_annotation(x=lfc[i], y=y_plot[i], text=at.GENES[i], showarrow=False, yshift=11,
                               font={"color": INK_2, "size": 11})
    if gene_name in at.GENE_INDEX:
        i = at.GENE_INDEX[gene_name]
        fig.add_trace(go.Scatter(x=[lfc[i]], y=[y_plot[i]], mode="markers", showlegend=False, hoverinfo="skip",
                                 marker={"size": 16, "color": "rgba(0,0,0,0)", "line": {"width": 2, "color": INK}}))
    for x in (-1, 1):
        fig.add_vline(x=x, line={"color": AXIS, "width": 1})
    fig.add_hline(y=0 if by_cells else -np.log10(0.05), line={"color": AXIS, "width": 1})
    style(fig, {"l": 56, "r": 16, "t": 8, "b": 48})
    fig.update_xaxes(title=f"log2 fold change, {a_name} vs {b_name}", range=[-lim, lim])
    if by_cells:
        fig.update_yaxes(title=f"% expressing, {a_name} minus {b_name}", range=[-105, 105])
    else:
        fig.update_yaxes(title="−log10 adjusted p", rangemode="tozero")
    fig.update_layout(legend={"orientation": "h", "x": 0, "y": 1.02, "yanchor": "bottom"}, hovermode="closest")
    return fig


def de_gene_detail(comparison, cell_type, gene_name, min_genes, max_mito, selection):
    """Per-sample values for sample comparisons, a split violin for cell comparisons."""
    healthy = qc_mask(min_genes, max_mito) & (C["cell_type"] != at.LOW_QUALITY)
    g = at.GENE_INDEX[gene_name]
    fig = go.Figure()
    if comparison in ("type_vs_rest", "selection_vs_rest"):
        if comparison == "type_vs_rest":
            in_mask = healthy & (C["cell_type"] == cell_type)
        else:
            in_mask = np.zeros(at.N_CELLS, bool)
            in_mask[selection or []] = True
            in_mask &= healthy
        a_name, b_name = group_names(comparison, cell_type)
        for m, name, color in [(in_mask, cap(a_name), UP), (healthy & ~in_mask, cap(b_name), DOWN)]:
            v = at.EXPR[m, g]
            fig.add_trace(go.Violin(y=v, name=name, line={"color": color, "width": 1}, fillcolor=color,
                                    opacity=0.6, points=False, spanmode="hard", width=0.8,
                                    meanline={"visible": True, "color": INK}, showlegend=False,
                                    hoverinfo="name+y"))
        fig.update_yaxes(title=f"{gene_name}, log-normalized")
        style(fig, {"l": 56, "r": 16, "t": 8, "b": 40})
        fig.update_xaxes(tickfont={"color": INK_2, "size": 12})
        return fig
    mask = healthy if cell_type == "All" else healthy & (C["cell_type"] == cell_type)
    pb = at.pseudobulk(mask)
    a, b, paired = comparison_samples(comparison)
    a_name, b_name = map(cap, group_names(comparison, cell_type))
    if paired:
        for sa, sb in zip(a, b):
            if sa in pb and sb in pb:
                p = sa.split("-")[0]
                fig.add_trace(go.Scatter(
                    x=[b_name, a_name], y=[pb[sb][g], pb[sa][g]], mode="lines+markers", name=p,
                    line={"color": MUTED, "width": 1.5}, marker={"size": 9, "color": [DOWN, UP]},
                    hovertemplate=f"{p} %{{x}}: %{{y:.2f}}<extra></extra>", showlegend=False,
                ))
                fig.add_annotation(x=a_name, y=pb[sa][g], text=p, showarrow=False, xanchor="left", xshift=8,
                                   font={"color": MUTED, "size": 10})
    else:
        for grp, name, color in [(b, b_name, DOWN), (a, a_name, UP)]:
            vals = [(s, pb[s][g]) for s in grp if s in pb]
            fig.add_trace(go.Box(
                y=[v for _, v in vals], name=name, boxpoints="all", jitter=0.4, pointpos=0,
                text=[s for s, _ in vals], hovertemplate="%{text}: %{y:.2f}<extra></extra>",
                marker={"size": 9, "color": color}, line={"color": color, "width": 1},
                fillcolor="rgba(0,0,0,0)", showlegend=False,
            ))
    style(fig, {"l": 56, "r": 40, "t": 8, "b": 40})
    fig.update_yaxes(title=f"{gene_name}, log2 mean per sample")
    fig.update_xaxes(tickfont={"color": INK_2, "size": 12})
    return fig


def de_table(res, comparison, cell_type):
    lfc, q = np.asarray(res["log2fc"], float), np.asarray(res["q"], float)
    ok = (q < 0.05) & (np.abs(lfc) >= 1)
    if res["unit"] == "cells":
        ok &= np.maximum(res["pct_in"], res["pct_out"]) >= 0.1
    a_name, b_name = group_names(comparison, cell_type)

    def rows(sign):
        score = np.where(ok & (np.sign(lfc) == sign), np.abs(lfc), -1)
        top = [i for i in np.argsort(-score)[:8] if score[i] > 0]
        if not top:
            return [html.Tr(html.Td("None at adjusted p < 0.05 and 2-fold", colSpan=3, className="muted"))]
        return [
            html.Tr([html.Td(at.GENES[i], className="gene"),
                     html.Td(f"{lfc[i]:+.2f}", className="num"),
                     html.Td("<1e-300" if q[i] <= 1e-300 else f"{q[i]:.0e}" if q[i] < 0.001 else f"{q[i]:.3f}",
                             className="num muted")],
                    id={"type": "de-gene", "gene": at.GENES[i]}, n_clicks=0, className="clickable")
            for i in top
        ]

    head = html.Tr([html.Th("Gene"), html.Th("log2 FC", className="num"), html.Th("adj. p", className="num")])
    return html.Div([
        dmc.Text(f"Higher in {a_name}", className="table-title up"),
        html.Table([html.Thead(head), html.Tbody(rows(1))], className="gene-table"),
        dmc.Text(f"Higher in {b_name}", className="table-title down"),
        html.Table([html.Thead(head), html.Tbody(rows(-1))], className="gene-table"),
    ])


# ---------------------------------------------------------------- composition view

SAMPLE_ORDER = [s for r in at.RESPONSES for t in at.TIMEPOINTS for s in at.SAMPLES
                if at.RESPONSE[s.split("-")[0]] == r and s.endswith(t)]


def composition_table(min_genes, max_mito):
    healthy = qc_mask(min_genes, max_mito) & (C["cell_type"] != at.LOW_QUALITY)
    out = np.zeros((len(SAMPLE_ORDER), len(HEALTHY_TYPES)))
    for i, s in enumerate(SAMPLE_ORDER):
        sel = healthy & (C["sample"] == s)
        n = sel.sum()
        if n:
            for j, t in enumerate(HEALTHY_TYPES):
                out[i, j] = (C["cell_type"][sel] == t).sum() / n * 100
    return out


def composition_heatmap(comp, selected_type):
    labels = [f"{s.split('-')[0]} · {s.split('-')[1]}" for s in SAMPLE_ORDER]
    groups = [f"{at.RESPONSE[s.split('-')[0]]}" for s in SAMPLE_ORDER]
    fig = go.Figure(go.Heatmap(
        z=comp, x=HEALTHY_TYPES, y=labels, colorscale=SEQ_BLUE, xgap=2, ygap=2,
        customdata=np.array(groups)[:, None].repeat(len(HEALTHY_TYPES), 1),
        hovertemplate="<b>%{x}</b><br>%{y} (%{customdata})<br>%{z:.1f}% of cells<extra></extra>",
        colorbar={"title": {"text": "% of<br>sample", "font": {"color": MUTED, "size": 11}}, "thickness": 10,
                  "len": 0.6, "outlinewidth": 0, "tickfont": {"color": MUTED, "size": 10}},
    ))
    # Group brackets on the left
    for k, (r, t) in enumerate([(r, t) for r in at.RESPONSES for t in at.TIMEPOINTS]):
        fig.add_shape(type="rect", y0=4 * k - 0.4, y1=4 * k + 3.4, x0=-0.115, x1=-0.105, xref="paper", yref="y",
                      fillcolor=RESPONSE_COLOR[r], line_width=0, opacity=1 if t == "On" else 0.45)
    if selected_type in HEALTHY_TYPES:
        j = HEALTHY_TYPES.index(selected_type)
        fig.add_shape(type="rect", x0=j - 0.5, x1=j + 0.5, y0=-0.5, y1=len(labels) - 0.5,
                      line={"color": INK, "width": 1.5})
    style(fig, {"l": 100, "r": 16, "t": 8, "b": 120})
    fig.update_xaxes(tickangle=-45, tickfont={"color": INK_2, "size": 11}, showgrid=False)
    fig.update_yaxes(autorange="reversed", tickfont={"color": INK_2, "size": 11, "family": MONO}, showgrid=False)
    fig.update_layout(height=560)
    return fig


def composition_pairs(comp, cell_type):
    j = HEALTHY_TYPES.index(cell_type)
    val = {s: comp[i, j] for i, s in enumerate(SAMPLE_ORDER)}
    fig = go.Figure()
    for r in at.RESPONSES:
        pats = [p for p in at.PATIENTS if at.RESPONSE[p] == r]
        for p in pats:
            fig.add_trace(go.Scatter(
                x=["Pre", "On"], y=[val[f"{p}-Pre"], val[f"{p}-On"]], mode="lines+markers",
                line={"color": RESPONSE_COLOR[r], "width": 1}, opacity=0.45, marker={"size": 6},
                name=p, legendgroup=r, showlegend=False,
                hovertemplate=f"{p} ({r.lower()}) %{{x}}: %{{y:.1f}}%<extra></extra>",
            ))
        means = [np.mean([val[f"{p}-{t}"] for p in pats]) for t in at.TIMEPOINTS]
        fig.add_trace(go.Scatter(
            x=at.TIMEPOINTS, y=means, mode="lines+markers", name=f"{r}s, mean",
            line={"color": RESPONSE_COLOR[r], "width": 3}, marker={"size": 10},
            hovertemplate=f"{r}s mean %{{x}}: %{{y:.1f}}%<extra></extra>",
        ))
        fig.add_annotation(x="On", y=means[1], text=f"{r}s", showarrow=False, xanchor="left", xshift=12,
                           font={"color": INK_2, "size": 11})
    style(fig, {"l": 56, "r": 110, "t": 8, "b": 40})
    fig.update_yaxes(title=f"{cell_type}, % of sample", rangemode="tozero")
    fig.update_xaxes(tickfont={"color": INK_2, "size": 12}, range=[-0.3, 1.3])
    fig.update_layout(showlegend=False, height=330)
    return fig


def composition_summary(comp, cell_type):
    j = HEALTHY_TYPES.index(cell_type)
    val = {s: comp[i, j] for i, s in enumerate(SAMPLE_ORDER)}
    items = []
    for r in at.RESPONSES:
        pats = [p for p in at.PATIENTS if at.RESPONSE[p] == r]
        ratios = [np.log2((val[f"{p}-On"] + 0.1) / (val[f"{p}-Pre"] + 0.1)) for p in pats]
        fold = 2 ** np.mean(ratios)
        up = sum(x > 0 for x in ratios)
        items.append(dmc.Stack([
            dmc.Text(f"{r}s", className="stat-label"),
            dmc.Text(f"{fold:.1f}×" if fold >= 1 else f"{fold:.2f}×", className="stat-value"),
            dmc.Text(f"Geometric mean change on treatment · up in {up} of {len(pats)}", className="stat-sub"),
        ], gap=0))
    return dmc.SimpleGrid(items, cols=2, spacing="lg")


# ---------------------------------------------------------------- trajectory view

PT_BINS = np.linspace(0, 1, 21)
PT_MID = (PT_BINS[:-1] + PT_BINS[1:]) / 2


def trajectory_umap(mask):
    cd8 = mask & np.isin(C["cell_type"], at.CD8_LINEAGE)
    other = mask & ~cd8
    xy = C["umap"]
    fig = go.Figure()
    fig.add_trace(go.Scattergl(x=xy[other, 0], y=xy[other, 1], mode="markers", hoverinfo="skip",
                               marker={"size": 2.5, "color": UNEXPRESSED, "line": {"width": 0}}, showlegend=False))
    i = np.where(cd8)[0]
    i = i[np.argsort(C["pseudotime"][i])]
    fig.add_trace(go.Scattergl(
        x=xy[i, 0], y=xy[i, 1], mode="markers", showlegend=False,
        marker={"size": 4.5, "color": C["pseudotime"][i], "colorscale": SEQ_ORANGE, "cmin": 0, "cmax": 1,
                "line": {"width": 0},
                "colorbar": {"title": {"text": "Pseudo-<br>time", "font": {"color": MUTED, "size": 11}},
                             "thickness": 10, "len": 0.5, "outlinewidth": 0, "tickfont": {"color": MUTED, "size": 10}}},
        customdata=np.column_stack([C["cell_type"][i], C["sample"][i], np.round(C["pseudotime"][i], 2)]),
        hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}<br>Pseudotime %{customdata[2]}<extra></extra>",
    ))
    for name, (lo, hi) in at.CD8_PT_RANGE.items():
        sel = i[(C["pseudotime"][i] >= lo) & (C["pseudotime"][i] < hi)]
        if len(sel):
            fig.add_annotation(x=np.median(xy[sel, 0]), y=np.median(xy[sel, 1]), text=name.replace("CD8 ", ""),
                               showarrow=False, font={"color": INK, "size": 11}, bgcolor="rgba(17,17,16,0.72)")
    style(fig, {"l": 8, "r": 8, "t": 8, "b": 8})
    fig.update_xaxes(range=[-13, 2.5])
    fig.update_yaxes(range=[-5, 8])
    fig.update_layout(height=380)
    return umap_axes(fig)


def trajectory_density(min_genes, max_mito):
    healthy = qc_mask(min_genes, max_mito)
    cd8 = healthy & np.isin(C["cell_type"], at.CD8_LINEAGE)
    fig = go.Figure()
    for k, t in enumerate(at.TIMEPOINTS):
        for r in at.RESPONSES:
            sel = cd8 & (C["response"] == r) & (C["timepoint"] == t)
            h, _ = np.histogram(C["pseudotime"][sel], PT_BINS)
            h = np.convolve(np.pad(h, 2, mode="edge"), [1, 2, 3, 2, 1], "valid") / 9
            h = h / max(h.sum(), 1) * 100
            fig.add_trace(go.Scatter(
                x=PT_MID, y=h, mode="lines", line={"color": RESPONSE_COLOR[r], "width": 2, "shape": "spline"},
                fill="tozeroy", fillcolor=RESPONSE_COLOR[r] + "26", name=f"{r}s", legendgroup=r,
                showlegend=k == 0, xaxis=f"x{k + 1}" if k else "x", yaxis=f"y{k + 1}" if k else "y",
                hovertemplate=f"{r}s, {t}: %{{y:.1f}}% of CD8 cells<extra></extra>",
            ))
    style(fig, {"l": 48, "r": 16, "t": 28, "b": 40})
    fig.update_layout(
        xaxis={"domain": [0, 0.47], "title": "Pseudotime"}, xaxis2={"domain": [0.53, 1], "title": "Pseudotime"},
        yaxis={"title": "% of CD8 T cells", "rangemode": "tozero"},
        yaxis2={"anchor": "x2", "matches": "y", "showticklabels": False},
        legend={"orientation": "h", "x": 0, "y": -0.28}, height=300, hovermode="x unified",
    )
    for k, t in enumerate(["Pre-treatment", "On treatment"]):
        fig.add_annotation(x=0.235 + 0.53 * k, y=1.0, xref="paper", yref="paper", text=t, showarrow=False,
                           yanchor="bottom", font={"color": INK_2, "size": 12})
    fig.update_xaxes(gridcolor=GRID, linecolor=AXIS, tickfont={"color": MUTED, "size": 11},
                     title_font={"color": MUTED, "size": 12})
    fig.update_yaxes(gridcolor=GRID, tickfont={"color": MUTED, "size": 11})
    return fig


def trajectory_trends(min_genes, max_mito, genes):
    if not genes:
        return empty_fig("Pick genes to plot along pseudotime", 300)
    healthy = qc_mask(min_genes, max_mito)
    cd8 = healthy & np.isin(C["cell_type"], at.CD8_LINEAGE)
    pt = C["pseudotime"]
    genes = genes[:8]
    cols = min(4, len(genes))
    nrows = (len(genes) + cols - 1) // cols
    fig = go.Figure()
    gap = 0.06
    w = (1 - gap * (cols - 1)) / cols
    hgap = 0.18 if nrows > 1 else 0
    h = (1 - hgap * (nrows - 1)) / nrows
    for k, g in enumerate(genes):
        r_, c_ = divmod(k, cols)
        ax = "" if k == 0 else str(k + 1)
        x0 = c_ * (w + gap)
        y1 = 1 - r_ * (h + hgap)
        fig.update_layout({
            f"xaxis{ax}": {"domain": [x0, min(1.0, x0 + w)], "anchor": f"y{ax}", "range": [0, 1],
                           "title": "Pseudotime" if r_ == nrows - 1 else None},
            f"yaxis{ax}": {"domain": [max(0.0, y1 - h), y1], "anchor": f"x{ax}", "rangemode": "tozero"},
        })
        v = at.gene(g)
        for resp in at.RESPONSES:
            sel = cd8 & (C["response"] == resp)
            b = np.digitize(pt[sel], PT_BINS[1:-1])
            means = [v[sel][b == i].mean() if (b == i).sum() >= 5 else None for i in range(len(PT_MID))]
            fig.add_trace(go.Scatter(
                x=PT_MID, y=means, mode="lines", line={"color": RESPONSE_COLOR[resp], "width": 2, "shape": "spline"},
                name=f"{resp}s", legendgroup=resp, showlegend=k == 0, xaxis=f"x{ax}", yaxis=f"y{ax}",
                hovertemplate=f"{g}, {resp.lower()}s<br>pseudotime %{{x:.2f}}: %{{y:.2f}}<extra></extra>",
            ))
        fig.add_annotation(x=x0, y=y1, xref="paper", yref="paper", text=f"<b>{g}</b>", showarrow=False,
                           xanchor="left", yanchor="bottom", font={"color": INK, "size": 12})
    style(fig, {"l": 40, "r": 16, "t": 28, "b": 48})
    fig.update_xaxes(gridcolor=GRID, linecolor=AXIS, zeroline=False, tickfont={"color": MUTED, "size": 10},
                     title_font={"color": MUTED, "size": 11}, tickvals=[0, 0.5, 1])
    fig.update_yaxes(gridcolor=GRID, linecolor=AXIS, zeroline=False, tickfont={"color": MUTED, "size": 10})
    fig.update_layout(height=230 * nrows + 70, hovermode="x unified",
                      legend={"orientation": "h", "x": 1, "xanchor": "right", "y": 1.0, "yanchor": "bottom"})
    return fig


# ---------------------------------------------------------------- QC view


def qc_histograms(min_genes, max_mito):
    keep = qc_mask(min_genes, max_mito)
    fig = go.Figure()
    specs = [
        ("x", "y", np.log10(C["n_genes"]), "Genes detected (log scale)", np.log10(max(min_genes, 1)), "min"),
        ("x2", "y2", np.log10(C["n_counts"]), "UMIs per cell (log scale)", None, None),
        ("x3", "y3", C["pct_mito"], "% mitochondrial reads", max_mito, "max"),
    ]
    for k, (xa, ya, v, title, thresh, side) in enumerate(specs):
        bins = {"start": float(v.min()), "end": float(v.max()), "size": float((v.max() - v.min()) / 60)}
        for m, name, color in [(keep, "Kept", "#6da7ec"), (~keep, "Removed", "#d03b3b")]:
            fig.add_trace(go.Histogram(x=v[m], xbins=bins, name=name, marker={"color": color, "line": {"width": 0}},
                                       legendgroup=name, showlegend=k == 0, xaxis=xa, yaxis=ya, opacity=0.9,
                                       hovertemplate=f"{name}: %{{y}} cells<extra></extra>"))
        if thresh is not None:
            fig.add_shape(type="line", x0=thresh, x1=thresh, y0=0, y1=1, xref=xa, yref=f"{ya} domain",
                          line={"color": INK, "width": 1.5})
            fig.add_annotation(x=thresh, y=1, xref=xa, yref=f"{ya} domain", showarrow=False, yanchor="bottom",
                               xanchor="left" if side == "min" else "right", xshift=4 if side == "min" else -4,
                               text=f"{side} {min_genes if side == 'min' else max_mito}{'' if side == 'min' else '%'}",
                               font={"color": INK, "size": 11})
    style(fig, {"l": 48, "r": 16, "t": 24, "b": 48})
    for k, (xa, ya, _, title, _, _) in enumerate(specs):
        n = "" if k == 0 else str(k + 1)
        x0 = k * 0.35
        fig.update_layout({
            f"xaxis{n}": {"domain": [x0, x0 + 0.3], "anchor": f"y{n}", "title": title},
            f"yaxis{n}": {"anchor": f"x{n}", "title": "Cells" if k == 0 else None},
        })
        if k < 2:
            ticks = [2, 2.5, 3, 3.5, 4, 4.5]
            fig.update_layout({f"xaxis{n}": {"tickvals": ticks, "ticktext": [f"{10 ** t:,.0f}" for t in ticks]}})
    fig.update_xaxes(gridcolor=GRID, linecolor=AXIS, tickfont={"color": MUTED, "size": 10},
                     title_font={"color": MUTED, "size": 12})
    fig.update_yaxes(gridcolor=GRID, linecolor=AXIS, tickfont={"color": MUTED, "size": 10},
                     title_font={"color": MUTED, "size": 12})
    fig.update_layout(barmode="stack", height=280, bargap=0.05,
                      legend={"orientation": "h", "x": 1, "xanchor": "right", "y": 1.08})
    return fig


def qc_per_sample(min_genes, max_mito):
    keep = qc_mask(min_genes, max_mito)
    kept = [int((keep & (C["sample"] == s)).sum()) for s in SAMPLE_ORDER]
    total = [int((C["sample"] == s).sum()) for s in SAMPLE_ORDER]
    removed = [t - k for t, k in zip(total, kept)]
    labels = [s.replace("-", " · ") for s in SAMPLE_ORDER]
    pct = [r / t * 100 for r, t in zip(removed, total)]
    fig = go.Figure([
        go.Bar(x=labels, y=kept, name="Kept", marker={"color": "#6da7ec", "line": {"width": 0}},
               hovertemplate="%{x}: %{y} kept<extra></extra>"),
        go.Bar(x=labels, y=removed, name="Removed", marker={"color": "#d03b3b", "line": {"width": 0}},
               customdata=pct, hovertemplate="%{x}: %{y} removed (%{customdata:.0f}%)<extra></extra>"),
    ])
    for k, (r, t) in enumerate([(r, t) for r in at.RESPONSES for t in at.TIMEPOINTS]):
        fig.add_annotation(x=4 * k + 1.5, y=1.0, yref="paper", yanchor="bottom", showarrow=False,
                           text=f"{r}s · {'pre' if t == 'Pre' else 'on'}", font={"color": MUTED, "size": 11})
        if k:
            fig.add_vline(x=4 * k - 0.5, line={"color": AXIS, "width": 1})
    worst = int(np.argmax(pct))
    fig.add_annotation(x=labels[worst], y=total[worst], text=f"{pct[worst]:.0f}% removed", showarrow=False,
                       yanchor="bottom", yshift=4, font={"color": INK, "size": 11})
    style(fig, {"l": 48, "r": 16, "t": 64, "b": 72})
    fig.update_layout(barmode="stack", height=340, bargap=0.25,
                      legend={"orientation": "h", "x": 1, "xanchor": "right", "y": 0.98, "yanchor": "top",
                              "yref": "container", "traceorder": "normal"})
    fig.update_xaxes(tickangle=-45, tickfont={"color": INK_2, "size": 10, "family": MONO})
    fig.update_yaxes(title="Cells")
    return fig


def qc_scatter(min_genes, max_mito):
    keep = qc_mask(min_genes, max_mito)
    fig = go.Figure()
    cd = np.column_stack([C["cell_type"], C["sample"], np.round(C["pct_mito"], 1)])
    hover = ("%{customdata[0]} · %{customdata[1]}<br>%{x:,} UMIs, %{y:,} genes"
             "<br>%{customdata[2]}% mito<extra></extra>")
    fig.add_trace(go.Scattergl(
        x=C["n_counts"][keep], y=C["n_genes"][keep], mode="markers", name="Kept", customdata=cd[keep],
        marker={"size": 3.5, "color": "#6da7ec", "opacity": 0.6, "line": {"width": 0}}, hovertemplate=hover,
    ))
    fig.add_trace(go.Scattergl(
        x=C["n_counts"][~keep], y=C["n_genes"][~keep], mode="markers", name="Removed", customdata=cd[~keep],
        marker={"size": 5, "color": "#d03b3b", "symbol": "x-thin", "line": {"width": 1.2, "color": "#d03b3b"}},
        hovertemplate=hover,
    ))
    fig.add_hline(y=min_genes, line={"color": INK, "width": 1})
    style(fig, {"l": 56, "r": 16, "t": 24, "b": 48})
    fig.update_xaxes(type="log", title="UMIs per cell")
    fig.update_yaxes(type="log", title="Genes detected")
    fig.update_layout(height=300, legend={"orientation": "h", "x": 0, "y": 1.1})
    return fig


# ---------------------------------------------------------------- layout

total_patients = len(at.PATIENTS)

header = dmc.AppShellHeader(
    html.Div([
        dmc.Group([
            html.Div(DashIconify(icon="tabler:dna-2", width=20), className="brand-mark"),
            dmc.Stack([
                dmc.Text("Single-Cell Atlas Explorer", className="brand-name"),
                dmc.Text(f"Melanoma on anti-PD-1 · {total_patients} patients · {len(at.SAMPLES)} biopsies · "
                         f"{at.N_CELLS:,} cells · {len(at.GENES)} genes", className="brand-sub"),
            ], gap=0),
        ], gap="sm", wrap="nowrap"),
        dmc.SegmentedControl(
            id="view", value="atlas", size="sm", radius="md", className="view-switch",
            data=[{"value": "atlas", "label": "Atlas"}, {"value": "markers", "label": "Markers"},
                  {"value": "de", "label": "Differential expression"},
                  {"value": "composition", "label": "Composition"},
                  {"value": "trajectory", "label": "CD8 trajectory"}, {"value": "qc", "label": "Quality control"}],
        ),
    ], className="header-inner"),
    className="header",
)

filter_bar = dmc.Paper(
    dmc.Group([
        dmc.Group([
            DashIconify(icon="tabler:search", width=16, color=MUTED),
            dmc.Select(id="gene", data=gene_options(), value=DEFAULT_GENE, searchable=True, size="sm", w=170,
                       maxDropdownHeight=360, allowDeselect=False, comboboxProps={"withinPortal": True},
                       label="Gene"),
        ], gap=6, align="flex-end", wrap="nowrap"),
        html.Div(className="divider"),
        dmc.Stack([
            dmc.Text("Response", className="filter-label"),
            dmc.ChipGroup(dmc.Group([dmc.Chip(r, value=r, size="xs", radius="xl", color="blue")
                                     for r in at.RESPONSES], gap=6),
                          id="responses", value=list(at.RESPONSES), multiple=True),
        ], gap=6),
        dmc.Stack([
            dmc.Text("Timepoint", className="filter-label"),
            dmc.ChipGroup(dmc.Group([dmc.Chip({"Pre": "Pre-treatment", "On": "On treatment"}[t], value=t, size="xs",
                                              radius="xl", color="blue") for t in at.TIMEPOINTS], gap=6),
                          id="timepoints", value=list(at.TIMEPOINTS), multiple=True),
        ], gap=6),
        html.Div(className="divider"),
        dmc.Stack([
            dmc.Text("QC · min genes detected", className="filter-label"),
            dmc.Slider(id="min-genes", min=0, max=1500, step=50, value=DEFAULT_MIN_GENES, size="sm", w=170,
                       marks=[{"value": v, "label": str(v)} for v in (0, 500, 1000, 1500)]),
        ], gap=6, className="slider-block"),
        dmc.Stack([
            dmc.Text("QC · max % mitochondrial", className="filter-label"),
            dmc.Slider(id="max-mito", min=5, max=60, step=1, value=DEFAULT_MAX_MITO, size="sm", w=170,
                       marks=[{"value": v, "label": f"{v}%"} for v in (5, 20, 40, 60)]),
        ], gap=6, className="slider-block"),
        html.Div(id="cell-count", className="cell-count"),
    ], gap="lg", align="flex-end", className="filter-row"),
    className="filter-bar",
)

atlas_view = dmc.Grid([
    dmc.GridCol(card(
        "UMAP",
        graph("umap", "graph-umap"),
        hint="Lasso cells to compare them · click a legend item to hide it",
        extra=dmc.Select(id="color-by", data=COLOR_BY, value="cell_type", size="xs", w=170,
                         allowDeselect=False, leftSection=DashIconify(icon="tabler:palette", width=14)),
    ), span={"base": 12, "lg": 8}),
    dmc.GridCol(dmc.Stack([
        card("Expression by cell type", graph("gene-violin", "graph-auto"), extra=html.Div(id="gene-badge"),
             hint="Sorted by mean · right column: % of cells expressing"),
        card("Lasso selection", html.Div(id="selection-info"),
             extra=dmc.Button("Compare in DE", id="selection-to-de", size="compact-xs", variant="light",
                              radius="xl", disabled=True,
                              leftSection=DashIconify(icon="tabler:arrows-diff", width=14))),
    ], gap="md"), span={"base": 12, "lg": 4}),
], gutter="md")

markers_view = card(
    "Marker genes",
    graph("dot-plot", "graph-auto"),
    hint="Dot size: % of cells expressing · color: mean expression scaled to each gene's maximum · "
         "click a dot to select that gene",
    extra=dmc.SegmentedControl(id="marker-mode", value="curated", size="xs",
                               data=[{"value": "curated", "label": "Canonical markers"},
                                     {"value": "computed", "label": "Top 2 per type, computed"}]),
)

de_view = dmc.Stack([
    dmc.Paper(dmc.Group([
        dmc.Select(id="de-type", label="Cells", data=["All"] + HEALTHY_TYPES, value="TAM C1QC+", size="sm",
                   w=220, allowDeselect=False),
        dmc.Select(id="de-comparison", label="Comparison",
                   data=[{"value": k, "label": v} for k, v in COMPARISONS.items()], value="on_vs_pre_r",
                   size="sm", w=360, allowDeselect=False),
        dmc.Text(id="de-method", className="method-note"),
    ], align="flex-end", gap="lg"), className="card control-strip"),
    dmc.Grid([
        dmc.GridCol(card("Volcano", graph("volcano", "graph-volcano"), hint=html.Span(id="volcano-hint")),
                    span={"base": 12, "lg": 6}),
        dmc.GridCol(dmc.Stack([
            card("Top genes", html.Div(id="de-table"), hint="Adjusted p < 0.05 and 2-fold, ranked by fold change · click a row"),
        ]), span={"base": 12, "md": 6, "lg": 3}),
        dmc.GridCol(card("Selected gene", graph("de-detail", "graph-detail"), extra=html.Div(id="de-gene-badge")),
                    span={"base": 12, "md": 6, "lg": 3}),
    ], gutter="md"),
], gap="md")

composition_view = dmc.Grid([
    dmc.GridCol(card("Cell-type composition per biopsy", graph("comp-heatmap", "graph-auto"),
                     hint="Share of each biopsy's cells after QC · click a column · left bars: responders (blue), "
                          "non-responders (orange), faint = pre-treatment"),
                span={"base": 12, "lg": 7}),
    dmc.GridCol(card("Change on treatment", dmc.Stack([
        dmc.Select(id="comp-type", data=HEALTHY_TYPES, value="CD8 effector", size="sm", allowDeselect=False,
                   searchable=True),
        html.Div(id="comp-summary"),
        graph("comp-pairs", "graph-auto"),
    ], gap="md"), hint="Each thin line is one patient; thick lines are group means"),
        span={"base": 12, "lg": 5}),
], gutter="md")

trajectory_view = dmc.Stack([
    dmc.Grid([
        dmc.GridCol(card("CD8 T cell path", graph("traj-umap", "graph-auto"),
                         hint="Memory (TCF7+) → effector (GZMK+) → exhausted (HAVCR2+, CXCL13+)"),
                    span={"base": 12, "lg": 5}),
        dmc.GridCol(card("Where CD8 T cells sit along the path", graph("traj-density", "graph-auto"),
                         hint="Share of each group's CD8 T cells at each point of pseudotime"),
                    span={"base": 12, "lg": 7}),
    ], gutter="md"),
    card("Gene trends along pseudotime", graph("traj-trends", "graph-auto"),
         hint="Mean log-normalized expression in 20 pseudotime bins",
         extra=dmc.MultiSelect(id="traj-genes", data=gene_options(), searchable=True, size="xs", w=420,
                               maxValues=8, value=["TCF7", "GZMK", "GZMB", "IFNG", "PDCD1", "HAVCR2", "TOX",
                                                   "CXCL13"],
                               comboboxProps={"withinPortal": True})),
], gap="md")

qc_view = dmc.Stack([
    dmc.SimpleGrid(id="qc-stats", cols={"base": 2, "md": 4}, spacing="md"),
    card("Per-cell metrics", graph("qc-hist", "graph-auto"),
         hint="Move the QC sliders above; every view uses the cells kept here"),
    dmc.Grid([
        dmc.GridCol(card("Cells kept per biopsy", graph("qc-samples", "graph-auto")), span={"base": 12, "lg": 7}),
        dmc.GridCol(card("UMIs vs genes", graph("qc-scatter", "graph-auto"),
                         hint="Hover a cell for its type, biopsy and % mitochondrial reads"),
                    span={"base": 12, "lg": 5}),
    ], gutter="md"),
], gap="md")

VIEWS = {"atlas": atlas_view, "markers": markers_view, "de": de_view, "composition": composition_view,
         "trajectory": trajectory_view, "qc": qc_view}

app.layout = dmc.MantineProvider(
    dmc.AppShell([
        header,
        dmc.AppShellMain(html.Div([
            filter_bar,
            *[html.Div(v, id=f"panel-{k}", style={"display": "block" if k == "atlas" else "none"})
              for k, v in VIEWS.items()],
            dmc.Text("Synthetic data generated for demonstration. Patients, samples and expression values are "
                     "made up; the biology is loosely modeled on published melanoma immunotherapy atlases.",
                     className="foot"),
        ], className="main-inner")),
        dcc.Store(id="selection", data=[]),
        dcc.Store(id="umap-narrow"),
    ], header={"height": 64}, padding=0),
    theme=THEME, forceColorScheme="dark",
)


# ---------------------------------------------------------------- callbacks


@dash.callback([Output(f"panel-{k}", "style") for k in VIEWS], Input("view", "value"))
def switch_view(view):
    return [{"display": "block" if k == view else "none"} for k in VIEWS]


@dash.callback(
    Output("cell-count", "children"),
    Input("min-genes", "value"), Input("max-mito", "value"), Input("responses", "value"), Input("timepoints", "value"),
)
def cell_count(min_genes, max_mito, responses, timepoints):
    n = int(view_mask(min_genes, max_mito, responses, timepoints).sum())
    return [html.Span(f"{n:,}", className="count-num"), html.Span(f" of {at.N_CELLS:,} cells shown",
                                                                  className="count-of")]


@dash.callback(
    Output("umap", "figure"),
    Input("color-by", "value"), Input("gene", "value"), Input("min-genes", "value"), Input("max-mito", "value"),
    Input("responses", "value"), Input("timepoints", "value"),
)
def update_umap(color_by, gene_name, min_genes, max_mito, responses, timepoints):
    # The lasso selection is not an input: redrawing would fire an empty selection and clear it
    mask = view_mask(min_genes, max_mito, responses, timepoints)
    if not mask.any():
        return empty_fig("No cells match the filters")
    return umap_figure(mask, color_by, gene_name)


# On phones the side legend would squash the UMAP; the on-plot labels carry identity instead
dash.clientside_callback(
    """
    function(fig) {
        if (window.innerWidth < 700) {
            setTimeout(() => {
                const gd = document.querySelector('#umap .js-plotly-plot');
                if (gd) { window.Plotly.relayout(gd, {showlegend: false}); }
            }, 50);
        }
        return window.innerWidth;
    }
    """,
    Output("umap-narrow", "data"),
    Input("umap", "figure"),
)


@dash.callback(
    Output("gene-violin", "figure"), Output("gene-badge", "children"),
    Input("gene", "value"), Input("min-genes", "value"), Input("max-mito", "value"),
    Input("responses", "value"), Input("timepoints", "value"),
)
def update_violin(gene_name, min_genes, max_mito, responses, timepoints):
    mask = view_mask(min_genes, max_mito, responses, timepoints)
    badge = dmc.Badge(f"{gene_name} · {at.GENE_SET_OF[gene_name]}", variant="light", radius="sm", size="md")
    return gene_violin(mask, gene_name), badge


@dash.callback(
    Output("selection", "data"),
    Input("umap", "selectedData"),
    prevent_initial_call=True,
)
def store_selection(selected):
    if not selected or not selected.get("points"):
        return []
    return sorted({int(p["customdata"][0]) for p in selected["points"] if "customdata" in p})


@dash.callback(
    Output("selection-info", "children"), Output("selection-to-de", "disabled"),
    Input("selection", "data"), Input("min-genes", "value"), Input("max-mito", "value"),
)
def selection_info(selection, min_genes, max_mito):
    if not selection:
        return dmc.Text("Use the lasso on the UMAP (drag around cells) to describe a group of cells and find "
                        "the genes that set it apart.", className="empty-note"), True
    sel = np.zeros(at.N_CELLS, bool)
    sel[selection] = True
    healthy = qc_mask(min_genes, max_mito) & (C["cell_type"] != at.LOW_QUALITY)
    sel &= healthy
    n = int(sel.sum())
    if n < 10:
        return dmc.Text(f"{n} cells selected after QC. Select at least 10.", className="empty-note"), True
    types, counts = np.unique(C["cell_type"][sel], return_counts=True)
    order = np.argsort(-counts)[:4]
    res = at.cells_vs_rest(sel, healthy & ~sel)
    ok = (res["pct_in"] >= 0.3) & ~at.MITO
    top = [at.GENES[i] for i in np.argsort(-np.where(ok, res["log2fc"], -np.inf))[:6]]
    resp = (C["response"][sel] == "Responder").mean()
    on = (C["timepoint"][sel] == "On").mean()
    bars = [
        html.Div([
            html.Div([html.Span(className="swatch", style={"background": TYPE_COLOR[types[i]]}),
                      html.Span(types[i])], className="comp-name"),
            html.Div(html.Div(style={"width": f"{counts[i] / n * 100:.0f}%",
                                     "background": TYPE_COLOR[types[i]]}), className="comp-bar"),
            html.Span(f"{counts[i] / n:.0%}", className="comp-pct"),
        ], className="comp-row") for i in order
    ]
    return dmc.Stack([
        dmc.Group([
            dmc.Stack([dmc.Text(f"{n:,}", className="stat-value"), dmc.Text("cells", className="stat-sub")], gap=0),
            dmc.Stack([dmc.Text(f"{resp:.0%}", className="stat-value"), dmc.Text("from responders",
                                                                                  className="stat-sub")], gap=0),
            dmc.Stack([dmc.Text(f"{on:.0%}", className="stat-value"), dmc.Text("on treatment",
                                                                               className="stat-sub")], gap=0),
        ], gap="xl"),
        html.Div(bars),
        dmc.Text("Top genes vs other cells", className="filter-label"),
        dmc.Group([html.Span(g, id={"type": "sel-gene", "gene": g}, className="gene-chip", n_clicks=0)
                   for g in top], gap=6),
    ], gap="sm"), False


@dash.callback(
    Output("view", "value"), Output("de-comparison", "value"),
    Input("selection-to-de", "n_clicks"),
    prevent_initial_call=True,
)
def selection_to_de(_):
    return "de", "selection_vs_rest"


@dash.callback(
    Output("gene", "value"),
    Input("dot-plot", "clickData"), Input("volcano", "clickData"),
    Input({"type": "de-gene", "gene": ALL}, "n_clicks"), Input({"type": "sel-gene", "gene": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def pick_gene(dot, volc, _rows, _badges):
    trig = ctx.triggered_id
    if trig == "dot-plot" and dot:
        return dot["points"][0]["x"]
    if trig == "volcano" and volc:
        p = volc["points"][0]
        if "customdata" in p:
            return p["customdata"][0]
    if isinstance(trig, dict) and ctx.triggered[0]["value"]:
        return trig["gene"]
    return dash.no_update


@dash.callback(
    Output("dot-plot", "figure"),
    Input("marker-mode", "value"), Input("gene", "value"), Input("min-genes", "value"), Input("max-mito", "value"),
    Input("responses", "value"), Input("timepoints", "value"),
)
def update_dot_plot(mode, gene_name, min_genes, max_mito, responses, timepoints):
    return dot_plot(view_mask(min_genes, max_mito, responses, timepoints), mode, gene_name)


@dash.callback(
    Output("volcano", "figure"), Output("de-table", "children"), Output("de-method", "children"),
    Input("de-type", "value"), Input("de-comparison", "value"), Input("gene", "value"),
    Input("min-genes", "value"), Input("max-mito", "value"), Input("selection", "data"),
)
def update_de(cell_type, comparison, gene_name, min_genes, max_mito, selection):
    res, err = run_de(comparison, cell_type, min_genes, max_mito, selection)
    if err:
        return empty_fig(err), dmc.Text("—", className="empty-note"), ""
    if res["unit"] == "cells":
        method = (f"Cell-level Welch t-test · {res['n_in']:,} vs {res['n_out']:,} cells. With this many cells "
                  "almost every p-value is tiny, so the plot shows fold change against the difference in "
                  "% of cells expressing.")
    else:
        kind = "paired t-test across patients" if comparison.startswith("on_vs_pre") else "Welch t-test"
        method = (f"Pseudobulk {kind} · {res['n_in']} vs {res['n_out']} biopsies "
                  f"({res['n_cells']:,} cells). Each biopsy counts once.")
    return volcano(res, comparison, cell_type, gene_name), de_table(res, comparison, cell_type), method


@dash.callback(
    Output("de-type", "disabled"), Output("volcano-hint", "children"),
    Input("de-comparison", "value"),
)
def de_controls(comparison):
    cells = comparison in ("type_vs_rest", "selection_vs_rest")
    hint = ("Colored: adjusted p < 0.05 and at least 2-fold · y: difference in % of cells expressing"
            if cells else "Colored: adjusted p < 0.05 and at least 2-fold")
    return comparison == "selection_vs_rest", hint + " · click a gene for detail"


@dash.callback(
    Output("de-detail", "figure"), Output("de-gene-badge", "children"),
    Input("de-type", "value"), Input("de-comparison", "value"), Input("gene", "value"),
    Input("min-genes", "value"), Input("max-mito", "value"), Input("selection", "data"),
)
def update_de_detail(cell_type, comparison, gene_name, min_genes, max_mito, selection):
    badge = dmc.Badge(gene_name, variant="light", radius="sm")
    if comparison == "type_vs_rest" and cell_type == "All":
        return empty_fig("Pick a cell type"), badge
    if comparison == "selection_vs_rest" and not selection:
        return empty_fig("No lasso selection"), badge
    return de_gene_detail(comparison, cell_type, gene_name, min_genes, max_mito, selection), badge


@dash.callback(
    Output("comp-type", "value"),
    Input("comp-heatmap", "clickData"),
    prevent_initial_call=True,
)
def pick_comp_type(click):
    return click["points"][0]["x"] if click else dash.no_update


@dash.callback(
    Output("comp-heatmap", "figure"), Output("comp-pairs", "figure"), Output("comp-summary", "children"),
    Input("comp-type", "value"), Input("min-genes", "value"), Input("max-mito", "value"),
)
def update_composition(cell_type, min_genes, max_mito):
    comp = composition_table(min_genes, max_mito)
    return composition_heatmap(comp, cell_type), composition_pairs(comp, cell_type), composition_summary(comp,
                                                                                                         cell_type)


@dash.callback(
    Output("traj-umap", "figure"), Output("traj-density", "figure"), Output("traj-trends", "figure"),
    Input("min-genes", "value"), Input("max-mito", "value"), Input("responses", "value"),
    Input("timepoints", "value"), Input("traj-genes", "value"),
)
def update_trajectory(min_genes, max_mito, responses, timepoints, genes):
    mask = view_mask(min_genes, max_mito, responses, timepoints)
    return (trajectory_umap(mask), trajectory_density(min_genes, max_mito),
            trajectory_trends(min_genes, max_mito, genes))


@dash.callback(
    Output("qc-stats", "children"), Output("qc-hist", "figure"), Output("qc-samples", "figure"),
    Output("qc-scatter", "figure"),
    Input("min-genes", "value"), Input("max-mito", "value"),
)
def update_qc(min_genes, max_mito):
    keep = qc_mask(min_genes, max_mito)
    lq = C["cell_type"] == at.LOW_QUALITY
    caught = (lq & ~keep).sum() / lq.sum()
    lost_good = (~lq & ~keep).sum()
    stats = [
        ("Cells kept", f"{keep.sum():,}", f"of {at.N_CELLS:,}"),
        ("Removed", f"{(~keep).sum():,}", f"{(~keep).mean():.1%} of all cells"),
        ("Low-quality cells caught", f"{caught:.0%}", f"{(lq & keep).sum():,} still pass"),
        ("Good cells lost", f"{lost_good:,}", "annotated cells below a threshold"),
    ]
    tiles = [dmc.Paper(dmc.Stack([dmc.Text(a, className="stat-label"), dmc.Text(b, className="stat-value"),
                                  dmc.Text(c, className="stat-sub")], gap=0), className="card stat-tile")
             for a, b, c in stats]
    return tiles, qc_histograms(min_genes, max_mito), qc_per_sample(min_genes, max_mito), qc_scatter(min_genes,
                                                                                                      max_mito)


def free_port(start=8050):
    """First port from `start` upward that nothing is listening on."""
    for port in range(start, start + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError("no free port found")


if __name__ == "__main__":
    # Store the choice in the environment so the debug reloader's child process reuses it.
    os.environ.setdefault("PORT", str(free_port()))
    app.run(debug=True, port=int(os.environ["PORT"]))
