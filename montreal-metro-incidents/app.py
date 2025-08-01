from datetime import datetime
import dash_ag_grid as dag
import dash_mantine_components as dmc
import pandas as pd
import plotly.express as px
from dash import Dash, Input, Output, callback, dcc, html

app = Dash(__name__)
server = app.server
symptomes_list = [
    "Clientèle",
    "Matériel roulant",
    "Équipements fixes",
    "Exploitation trains",
    "Feu, fumée, odeur, produit, etc…",
]

app.layout = dmc.MantineProvider(
    html.Div(
        [
            dcc.Interval(id="clock-interval", interval=1000, n_intervals=0),
            html.Div(
                [
                    html.Div(
                        [
                            html.Span("MÉTROPOLITAIN", className="header-title"),
                            html.Div(
                                [
                                    html.Span(
                                        "OPÉRATIONNEL", className="status-operational"
                                    ),
                                    html.Span("ACTIVE", className="status-active"),
                                    html.Span(id="live-clock", className="live-clock"),
                                ],
                                className="status-bar",
                            ),
                        ],
                        className="top-bar",
                    ),
                    html.Div(
                        "CENTRE DE CONTRÔLE DES INCIDENTS",
                        className="control-center-title",
                    ),
                    html.Hr(className="header-divider"),
                ],
                className="metro-header",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.H4(
                                        "🛠️ FILTRES & CONTRÔLE",
                                        className="filter-title",
                                    ),
                                    html.Label(
                                        "Année:",
                                        className="filter-label",
                                    ),
                                    dcc.Dropdown(
                                        id="year-dropdown",
                                        options=[
                                            {"label": str(year), "value": year}
                                            for year in range(2019, 2026)
                                        ],
                                        value=2023,
                                        className="dropdown-style",
                                    ),
                                    html.Label(
                                        "Ligne:",
                                        className="filter-label",
                                    ),
                                    dcc.Dropdown(
                                        id="line-dropdown",
                                        options=[
                                            {"label": "Ligne Verte", "value": 1},
                                            {"label": "Ligne Orange", "value": 2},
                                            {"label": "Ligne Jaune", "value": 4},
                                            {"label": "Ligne Bleue", "value": 5},
                                        ],
                                        value=2,
                                        className="dropdown-style",
                                    ),
                                    html.Label(
                                        "Types d'incidents:",
                                        className="filter-label-with-margin",
                                    ),
                                    dcc.Checklist(
                                        symptomes_list,
                                        symptomes_list,
                                        id="incident-checklist",
                                        className="checklist-style",
                                        inputClassName="checklist-input-style",
                                        labelClassName="checklist-label-style",
                                    ),
                                ],
                                className="card filters",
                            ),
                        ],
                        className="left-column",
                    ),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.H4(
                                                "🚨 INCIDENTS TOTAUX",
                                                className="data-card-header primary",
                                            ),
                                            html.H2(
                                                id="total-incidents",
                                                className="data-card-value",
                                            ),
                                        ],
                                        className="card small-card data-card",
                                    ),
                                    html.Div(
                                        [
                                            html.H4(
                                                "📅 CE MOIS-CI",
                                                className="data-card-header success",
                                            ),
                                            html.H2("89", className="data-card-value"),
                                        ],
                                        className="card small-card data-card",
                                    ),
                                    html.Div(
                                        [
                                            html.H4(
                                                "⏱️ RÉSOLUTION MOY.",
                                                className="data-card-header danger",
                                            ),
                                            html.H2(
                                                id="resolution-moyenne",
                                                className="data-card-value",
                                            ),
                                        ],
                                        className="card small-card data-card",
                                    ),
                                ],
                                className="row",
                            ),
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.H4("🗺️ CARTOGRAPHIE RÉSEAU MÉTRO"),
                                            dcc.Graph(id="map"),
                                        ],
                                        className="card medium-card",
                                    ),
                                ],
                                className="row",
                            ),
                        ],
                        className="flex-one",
                    ),
                ],
                className="flex-container",
            ),
        ],
        className="main-content",
    )
)


@callback(Output("live-clock", "children"), Input("clock-interval", "n_intervals"))
def update_clock(n_intervals):
    return datetime.now().strftime("%H:%M:%S")


@callback(
    Output("map", "figure"),
    Output("total-incidents", "children"),
    Output("resolution-moyenne", "children"),
    Input("year-dropdown", "value"),
    Input("line-dropdown", "value"),
    Input("incident-checklist", "value"),
)
def update_map(year, line, selected_incidents):
    df = pd.read_csv("incidents_metro.csv")
    df = df[df["Année civile"] == year]
    df = df[df["Ligne"].astype(str).str.contains(str(line), na=False)]

    if selected_incidents:
        df = df[df["Symptome"].isin(selected_incidents)]
    nombre_incidents = str(df["Numero d'incident"].nunique())
    try:
        df["Heure de l'incident"] = pd.to_datetime(
            df["Heure de l'incident"], format="%H:%M", errors="coerce"
        )
        df["Heure de reprise"] = pd.to_datetime(
            df["Heure de reprise"], format="%H:%M", errors="coerce"
        )
        df["resolution_time"] = (
            df["Heure de reprise"] - df["Heure de l'incident"]
        ).dt.total_seconds() / 60

        mean_resolution = df["resolution_time"].mean()
        if pd.notna(mean_resolution):
            resolution_moyenne = f"{int(mean_resolution)} min"
        else:
            resolution_moyenne = "N/A"
    except:
        resolution_moyenne = "N/A"
    grouped = df.groupby("Code de lieu").size().reset_index(name="Nombre d'incidents")
    grouped = grouped.sort_values(by="Nombre d'incidents", ascending=False)

    fig = px.bar(
        grouped,
        x="Code de lieu",
        y="Nombre d'incidents",
        labels={"Code de lieu": "Station", "Nombre d'incidents": "Nombre d'incidents"},
    )
    fig.update_traces(
        marker_color="#00b04f", marker_line_color="#00ffff", marker_line_width=1
    )
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(13, 20, 33, 0.1)",
        font=dict(family="Rajdhani, sans-serif", color="#ffffff", size=12),
        title=dict(
            font=dict(family="Orbitron, monospace", color="#ff8c00", size=16),
            x=0.5,
            xanchor="center",
        ),
        xaxis=dict(
            title_font=dict(color="#00ffff", family="Orbitron, monospace"),
            tickfont=dict(color="#ffffff", family="Rajdhani, sans-serif"),
            gridcolor="rgba(0, 158, 224, 0.2)",
            showgrid=True,
        ),
        yaxis=dict(
            title_font=dict(color="#00ffff", family="Orbitron, monospace"),
            tickfont=dict(color="#ffffff", family="Rajdhani, sans-serif"),
            gridcolor="rgba(0, 158, 224, 0.2)",
            showgrid=True,
        ),
        margin=dict(l=40, r=40, t=60, b=40),
        height=None,
    )
    fig.update_traces(
        marker=dict(line=dict(color="#00ffff", width=1), color="#00b04f", opacity=0.8),
        hovertemplate="<b>%{x}</b><br>Incidents: %{y}<extra></extra>",
        hoverlabel=dict(
            bgcolor="rgba(13, 20, 33, 0.9)",
            bordercolor="#00ffff",
            font=dict(color="#ffffff", family="Rajdhani"),
        ),
    )

    return fig, nombre_incidents, resolution_moyenne


if __name__ == "__main__":
    app.run(debug=True, port=8050)
