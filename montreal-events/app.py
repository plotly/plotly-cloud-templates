from datetime import datetime

import dash_ag_grid as dag
import dash_mantine_components as dmc
import pandas as pd
import plotly.express as px
from dash import Dash, Input, Output, callback, dcc, html

app = Dash(__name__)
server = app.server
app.title = "Montreal Events"
app.index_string = """
<!DOCTYPE html>
<html>
  <head>
    {%metas%}
    <title>Montreal Events</title>
    <meta name="title" content="Montreal Events" />
    <meta name="description" content="Discover and explore public events happening in Montreal with interactive maps and filtering." />

    <meta property="og:type" content="website" />
    <meta property="og:url" content="https://evenements-de-montreal.plotly.app/" />
    <meta property="og:title" content="Montreal Events" />
    <meta property="og:description" content="Discover and explore public events happening in Montreal with interactive maps and filtering." />
    <meta property="og:image" content="https://evenements-de-montreal.plotly.app/assets/thumbnail.png" />

    <meta name="twitter:card" content="summary_large_image" />
    <meta name="twitter:url" content="https://evenements-de-montreal.plotly.app/" />
    <meta name="twitter:title" content="Montreal Events" />
    <meta name="twitter:description" content="Discover and explore public events happening in Montreal with interactive maps and filtering." />
    <meta name="twitter:image" content="https://evenements-de-montreal.plotly.app/assets/thumbnail.png" />

    {%favicon%}
    {%css%}
  </head>
  <body>
    {%app_entry%}
    <footer>
      {%config%}
      {%scripts%}
      {%renderer%}
    </footer>
  </body>
</html>
"""
df = pd.read_csv("evenements.csv")


def generate_map(df):
    scatter_map = px.scatter_map(
        df,
        lat="lat",
        lon="long",
        color="type_evenement",
        color_discrete_sequence=px.colors.qualitative.Prism,
        zoom=10,
        hover_data=["titre"],
    )
    scatter_map.update_layout(
        margin={"l": 0, "r": 0, "t": 0, "b": 50},
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.2,
            xanchor="center",
            x=0.5,
            title=None,
        ),
    )
    return scatter_map


def generate_dropdown(col, label, value=[]):
    data = pd.read_csv("evenements.csv")
    return dmc.MultiSelect(
        data=[{"label": i, "value": i} for i in data[col].dropna().unique()],
        label=label,
        placeholder="Choisir...",
        value=value,
        id=col,
    )


app.layout = dmc.MantineProvider(
    html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            dcc.Markdown(
                                """
                                **Événements de Montréal**

                                Filtrez les événements ci dessous et consultez la carte et cliquez sur une ligne pour voir les détails.
                                """
                            ),
                            dmc.Divider(),
                            generate_dropdown("type_evenement", "Événement(s)"),
                            generate_dropdown("emplacement", "Emplacement(s)"),
                            generate_dropdown("arrondissement", "Arrondissement(s)"),
                            dmc.DatePickerInput(
                                id="date_debut",
                                label="Date de Début",
                                value=datetime.now(),
                            ),
                            dmc.DatePickerInput(
                                id="date_fin",
                                label="Date de Fin",
                                placeholder="Choisir...",
                            ),
                        ],
                        className="card sidebar",
                    ),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Div(
                                        id="search-results", className="card small-card"
                                    ),
                                    html.Div(
                                        id="event-info", className="card small-card"
                                    ),
                                    html.Div(
                                        id="event-date", className="card small-card"
                                    ),
                                    html.Div(
                                        id="event-description",
                                        className="card small-card",
                                    ),
                                ],
                                className="row",
                            ),
                            html.Div(
                                [
                                    html.Div(
                                        [dcc.Graph(id="map")],
                                        className="card medium-card",
                                    ),
                                    html.Div(
                                        [
                                            dag.AgGrid(
                                                id="grid",
                                                columnDefs=[
                                                    {
                                                        "field": "titre",
                                                        "checkboxSelection": True,
                                                        "minWidth": 300,
                                                    },
                                                    {
                                                        "field": "date_debut",
                                                        "headerName": "Date de début",
                                                        "width": 120,
                                                        "valueFormatter": {
                                                            "function": "d3.timeFormat('%d %b %Y')(d3.timeParse('%Y-%m-%d')(params.value))"
                                                        },
                                                    },
                                                    {
                                                        "field": "date_fin",
                                                        "headerName": "Date de fin",
                                                        "width": 120,
                                                        "valueFormatter": {
                                                            "function": "d3.timeFormat('%d %b %Y')(d3.timeParse('%Y-%m-%d')(params.value))"
                                                        },
                                                    },
                                                    {
                                                        "field": "type_evenement",
                                                        "headerName": "Type d'événement",
                                                        "width": 150,
                                                    },
                                                    {
                                                        "field": "arrondissement",
                                                        "headerName": "Arrondissement",
                                                        "width": 200,
                                                    },
                                                ],
                                                rowData=[],
                                                dashGridOptions={
                                                    "pagination": True,
                                                    "paginationPageSize": 30,
                                                    "rowSelection": "single",
                                                },
                                                defaultColDef={
                                                    "wrapText": True,
                                                    "autoHeight": True,
                                                },
                                                className="ag-theme-balham",
                                                style={"height": "calc(73vh - 60px)"},
                                            )
                                        ],
                                        className="card medium-card",
                                    ),
                                ],
                                className="row",
                            ),
                        ],
                        style={"flex": "1"},
                    ),
                ],
                style={"display": "flex"},
            ),
            dmc.Affix(
                dcc.Link(
                    dmc.Button("Try Plotly Cloud", className="cloud-button"),
                    href="https://cloud.plotly.com/",
                    target="_blank",
                ),
                position={"bottom": 20, "right": 20},
            ),
        ],
        className="main-content",
    )
)


@callback(
    Output("grid", "rowData"),
    Output("map", "figure"),
    Output("search-results", "children"),
    Input("type_evenement", "value"),
    Input("emplacement", "value"),
    Input("arrondissement", "value"),
    Input("date_debut", "value"),
    Input("date_fin", "value"),
)
def update_grid(type_evenement, emplacement, arrondissement, date_debut, date_fin):
    df = pd.read_csv("evenements.csv")
    if len(type_evenement) > 0:
        df = df[df["type_evenement"].isin(type_evenement)]
    if len(emplacement) > 0:
        df = df[df["emplacement"].isin(emplacement)]
    if len(arrondissement) > 0:
        df = df[df["arrondissement"].isin(arrondissement)]
    if date_debut:
        df = df[df["date_debut"] >= date_debut]
    if date_fin:
        df = df[df["date_fin"] <= date_fin]
    row_data = df.to_dict("records")
    scatter_map = generate_map(df)
    search_results = dcc.Markdown(
        f"""
            **{len(row_data)} événements trouvés**
            
            📅 {df["type_evenement"].nunique()} types d'événements
            
            📍 {df["arrondissement"].nunique()} arrondissements

            📊 Source: [Données de la Ville de Montréal](https://donnees.montreal.ca/dataset/evenements-publics)
        """
    )
    return row_data, scatter_map, search_results


@callback(
    Output("event-info", "children"),
    Output("event-date", "children"),
    Output("event-description", "children"),
    Input("grid", "selectedRows"),
)
def update_event_description(selected_rows):
    df = pd.read_csv("evenements.csv")
    if selected_rows:
        cout = selected_rows[0]["cout"]
        inscription = selected_rows[0]["inscription"]
        emplacement = selected_rows[0]["emplacement"]
        link = selected_rows[0]["url_fiche"]
        event_info = html.Div(
            [
                dcc.Markdown(
                    f"**Coût :** {cout}\n\n**Inscription :** {inscription}\n\n**Emplacement :** {emplacement}"
                ),
                html.A(
                    "Voir l'événement",
                    href=link,
                    className="event-btn",
                    target="_blank",
                ),
            ]
        )
        date_debut_raw = selected_rows[0]["date_debut"]
        date_fin_raw = selected_rows[0]["date_fin"]
        try:
            date_debut = datetime.strptime(date_debut_raw, "%Y-%m-%d").strftime(
                "%b %d, %Y"
            )
            date_fin = datetime.strptime(date_fin_raw, "%Y-%m-%d").strftime("%b %d, %Y")
        except:
            date_debut = date_debut_raw
            date_fin = date_fin_raw
        event_date = dcc.Markdown(
            f"**Date de début :** {date_debut}\n\n**Date de fin :** {date_fin}"
        )

        titre = selected_rows[0]["titre"]
        description = selected_rows[0]["description"]
        event_description = dcc.Markdown(f"**{titre}**\n\n{description}")
        return event_info, event_date, event_description
    no_data = dcc.Markdown(
        "Selectionnez un événement dans la grille pour voir les détails"
    )
    return no_data, no_data, no_data


if __name__ == "__main__":
    app.run(debug=True, port=8050)
