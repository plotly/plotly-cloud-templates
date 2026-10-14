import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np

COLORS = {
    "primary":   "#0d9488",   # teal
    "secondary": "#2563eb",   # blue
    "danger":    "#ef4444",
    "warning":   "#f59e0b",
    "success":   "#22c55e",
    "gray":      "#94a3b8",
    "purple":    "#8b5cf6",
}

NAVY = "#1e3a8a"   # deep navy accent (matches app theme highlight)

VITAL_COLORS = {
    "HR":    "#ef4444",
    "SpO2":  "#2563eb",
    "Temp":  "#f59e0b",
    "SysBP": "#8b5cf6",
    "DiaBP": "#a78bfa",
    "RR":    "#22c55e",
}

VITAL_RANGES = {
    "HR":    (60,  100),
    "SpO2":  (95,  100),
    "Temp":  (36.1, 37.8),
    "SysBP": (90,  130),
    "DiaBP": (60,  90),
    "RR":    (12,  20),
}

BASE_LAYOUT = {
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor":  "rgba(0,0,0,0)",
    "font":          {"family": "Inter, sans-serif"},
    "margin":        {"l": 48, "r": 24, "t": 48, "b": 40},
    "hovermode":     "x unified",
    "hoverlabel":    {
        "bgcolor": "white",
        "bordercolor": "#e2e8f0",
        "font": {"family": "Inter, sans-serif", "size": 12},
    },
}


# ── Admissions area chart ─────────────────────────────────────────────────────
def create_admissions_chart(df: pd.DataFrame, department: str = "All") -> go.Figure:
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])

    if department == "All":
        agg = df.groupby("date")["admissions"].sum().reset_index()
        fig = go.Figure(go.Scatter(
            x=agg["date"], y=agg["admissions"],
            fill="tozeroy",
            line={"color": COLORS["primary"], "width": 2},
            fillcolor="rgba(13,148,136,0.15)",
            name="Total Admissions",
            hovertemplate="%{y} admissions<extra></extra>",
        ))
    else:
        sub = df[df["department"] == department]
        fig = go.Figure(go.Scatter(
            x=sub["date"], y=sub["admissions"],
            fill="tozeroy",
            line={"color": COLORS["secondary"], "width": 2},
            fillcolor="rgba(37,99,235,0.12)",
            name=department,
            hovertemplate="%{y} admissions<extra></extra>",
        ))

    fig.update_layout(
        **BASE_LAYOUT,
        title={"text": "Daily Admissions", "x": 0, "font": {"size": 15, "weight": 600}},
        xaxis={"showgrid": False},
        yaxis={"showgrid": True, "gridcolor": "rgba(0,0,0,0.05)", "title": "Patients"},
        showlegend=False,
    )
    return fig


# ── Vitals time-series with reference bands ───────────────────────────────────
def create_vitals_chart(df: pd.DataFrame, vitals: list,
                        show_reference: bool = True,
                        ma_days: str = "none") -> go.Figure:
    fig = go.Figure()
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    ma_window = {"20": 20, "50": 50, "none": None}.get(ma_days)

    for v in vitals:
        if v not in df.columns:
            continue
        color = VITAL_COLORS.get(v, COLORS["primary"])
        series = df[v]
        if ma_window:
            series = series.rolling(ma_window, min_periods=1).mean()

        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=series,
            name=v, line={"color": color, "width": 1.8},
            hovertemplate=f"{v}: %{{y}}<extra></extra>",
        ))

        if show_reference and v in VITAL_RANGES:
            lo, hi = VITAL_RANGES[v]
            fig.add_hrect(y0=lo, y1=hi, fillcolor=color,
                          opacity=0.06, layer="below", line_width=0)

    fig.update_layout(
        **{**BASE_LAYOUT, "margin": {"l": 48, "r": 24, "t": 16, "b": 40}},
        legend={"orientation": "h", "y": -0.18},
        xaxis={
            "showgrid": True, "gridcolor": "rgba(0,0,0,0.04)",
            "rangeslider": {"visible": False},
        },
        yaxis={"showgrid": True, "gridcolor": "rgba(0,0,0,0.04)"},
    )
    return fig


# ── Vitals variability (box plot per vital) ───────────────────────────────────
def create_vitals_variability(df: pd.DataFrame, vitals: list) -> go.Figure:
    fig = go.Figure()
    for v in vitals:
        if v not in df.columns:
            continue
        fig.add_trace(go.Box(
            y=df[v], name=v,
            marker_color=VITAL_COLORS.get(v, COLORS["primary"]),
            boxmean="sd",
        ))
    fig.update_layout(
        **BASE_LAYOUT,
        title={"text": "Vital Sign Distribution", "x": 0,
               "font": {"size": 15, "weight": 600}},
        yaxis={"showgrid": True, "gridcolor": "rgba(0,0,0,0.04)"},
        showlegend=False,
    )
    return fig


# ── ECG-style HR sparkline ────────────────────────────────────────────────────
def create_ecg_sparkline(hr_history: list, patient_id: str = "") -> go.Figure:
    fig = go.Figure(go.Scatter(
        y=hr_history,
        mode="lines",
        line={"color": COLORS["success"], "width": 2},
        hovertemplate="%{y} bpm<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter, sans-serif"},
        margin={"l": 0, "r": 0, "t": 12, "b": 0},
        xaxis={"visible": False},
        yaxis={"visible": False, "range": [35, 165]},
        showlegend=False,
        title={"text": patient_id, "x": 0, "font": {"size": 12, "weight": 600}},
    )
    return fig


# ── Diagnosis donut (cohort demographics) ─────────────────────────────────────
def create_diagnosis_donut(df: pd.DataFrame) -> go.Figure:
    counts = df["diagnosis"].value_counts().reset_index()
    counts.columns = ["diagnosis", "count"]
    fig = go.Figure(go.Pie(
        labels=counts["diagnosis"],
        values=counts["count"],
        hole=0.58,
        textinfo="percent",
        textposition="outside",
        marker={"colors": px.colors.qualitative.Pastel[:len(counts)]},
        hovertemplate="%{label}<br>%{value} patients (%{percent})<extra></extra>",
    ))
    fig.update_layout(
        **BASE_LAYOUT,
        title={"text": "Diagnosis Distribution", "x": 0,
               "font": {"size": 15, "weight": 600}},
        legend={"orientation": "v", "x": 1.02, "y": 0.5},
        annotations=[{"text": "Cohort", "x": 0.5, "y": 0.5,
                       "font": {"size": 13, "weight": 600}, "showarrow": False}],
    )
    return fig


# ── Age-sex bar chart (cohort demographics) ───────────────────────────────────
def create_age_sex_chart(df: pd.DataFrame) -> go.Figure:
    bins = [20, 30, 40, 50, 60, 70, 80, 90]
    labels = ["20-29","30-39","40-49","50-59","60-69","70-79","80+"]
    df = df.copy()
    df["age_group"] = pd.cut(df["age"], bins=bins, labels=labels, right=False)
    grp = df.groupby(["age_group", "gender"], observed=True).size().reset_index(name="count")
    fig = go.Figure()
    for gender, color in [("M", COLORS["secondary"]), ("F", COLORS["primary"])]:
        sub = grp[grp["gender"] == gender]
        fig.add_trace(go.Bar(
            x=sub["age_group"].astype(str), y=sub["count"],
            name="Male" if gender == "M" else "Female",
            marker_color=color,
        ))
    fig.update_layout(
        **BASE_LAYOUT,
        title={"text": "Age & Sex Distribution", "x": 0,
               "font": {"size": 15, "weight": 600}},
        barmode="group",
        xaxis={"title": "Age Group"},
        yaxis={"title": "Patients", "showgrid": True, "gridcolor": "rgba(0,0,0,0.04)"},
        legend={"orientation": "h", "y": -0.18},
    )
    return fig


# ── Risk stratification bar chart ─────────────────────────────────────────────
def create_risk_strat_chart(df: pd.DataFrame) -> go.Figure:
    risk_diag = df.groupby(["diagnosis", "risk_level"]).size().reset_index(name="count")
    color_map = {"High": COLORS["danger"], "Medium": COLORS["warning"], "Low": COLORS["success"]}
    fig = go.Figure()
    for level in ["High", "Medium", "Low"]:
        sub = risk_diag[risk_diag["risk_level"] == level]
        fig.add_trace(go.Bar(
            x=sub["diagnosis"], y=sub["count"],
            name=level, marker_color=color_map[level],
        ))
    fig.update_layout(
        **BASE_LAYOUT,
        title={"text": "Risk Stratification by Diagnosis", "x": 0,
               "font": {"size": 15, "weight": 600}},
        barmode="stack",
        xaxis={"tickangle": -30},
        yaxis={"title": "Patients"},
        legend={"orientation": "h", "y": -0.22},
    )
    return fig


# ── Crossfilter scatter ───────────────────────────────────────────────────────
SCATTER_LIGHT = {
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor":  "rgba(0,0,0,0)",
    "font":          {"family": "Inter, sans-serif", "color": "#1e2433"},
    "margin":        {"l": 40, "r": 16, "t": 40, "b": 36},
    "hovermode":     False,
    "newselection_mode": "gradual",
}

def create_crossfilter_scatter(df: pd.DataFrame, x_col: str, y_col: str,
                               selected_ids=None) -> go.Figure:
    all_ids = df.index.tolist()
    if selected_ids is None:
        selected_ids = all_ids

    risk_colors = {"High": "#ef4444", "Medium": "#f59e0b", "Low": "#22c55e"}
    marker_colors = [risk_colors.get(r, "#94a3b8") for r in df["risk_level"]]

    fig = px.scatter(df, x=x_col, y=y_col, template="plotly_white")
    fig.update_traces(
        selectedpoints=selected_ids,
        customdata=df.index,
        mode="markers",
        marker={
            "color": marker_colors,
            "size": 8,
            "opacity": 0.9,
            "line": {"width": 0.6, "color": "#ffffff"},
        },
        unselected={"marker": {"opacity": 0.15, "color": "#cbd5e1"}},
        selected={"marker": {"opacity": 1.0, "size": 9}},
    )
    grid = {"showgrid": True, "gridcolor": "rgba(0,0,0,0.06)",
            "zeroline": False, "linecolor": "rgba(0,0,0,0.12)"}
    fig.update_layout(
        **SCATTER_LIGHT,
        dragmode="select",
        activeselection={"fillcolor": "rgba(30,58,138,0.08)"},
        xaxis={**grid, "title": x_col},
        yaxis={**grid, "title": y_col},
        title={"text": f"{x_col} vs {y_col}",
               "font": {"size": 13, "color": NAVY, "weight": 600}},
    )
    return fig
