import dash_ag_grid as dag
import dash_design_kit as ddk
from dash import Dash, Input, Output, State, callback, ctx, dcc, html

import figures
from data import OPERATORS, wells

app = Dash(__name__, title="Ternary Map Explorer")
server = app.server

GRAPH_CONFIG = {"displaylogo": False, "responsive": True}
LAYERS = ["Wells", "Rock types"]

GRID_COLUMNS = [
    {"field": "well_id", "headerName": "Well", "width": 100, "pinned": "left"},
    {"field": "operator", "headerName": "Operator", "flex": 2, "minWidth": 200},
    {"field": "formation", "headerName": "Formation", "flex": 1, "minWidth": 150},
    {"field": "completed", "headerName": "Completed", "width": 120},
    {"field": "Quartz", "headerName": "Quartz %", "width": 110},
    {"field": "Carbonate", "headerName": "Carbonate %", "width": 125},
    {"field": "Clay", "headerName": "Clay %", "width": 100},
    {
        "field": "cum_mmcf",
        "headerName": "Cum. gas (MMcf)",
        "width": 150,
        "valueFormatter": {"function": "d3.format(',.1f')(params.value)"},
    },
]


def card(title, child, hint=None, class_name=""):
    return ddk.Card(
        className=f"chart-card {class_name}",
        children=[
            html.Div(
                [html.Div(title, className="card-title"), html.Span(hint) if hint else None],
                className="card-head",
            ),
            child,
        ],
    )


def graph(graph_id, **config):
    return dcc.Graph(
        id=graph_id, config={**GRAPH_CONFIG, **config}, style={"height": "320px"}
    )


def stat(label, value, sub):
    return html.Div(
        className="stat",
        children=[
            html.Div(label, className="stat-label"),
            html.Div(value, className="stat-value"),
            html.Div(sub, className="stat-sub"),
        ],
    )


app.layout = ddk.App(
    className="app-shell",
    use_mobile_viewport=True,
    children=[
        ddk.Header(
            [
                html.Div(
                    [
                        ddk.Title("Ternary Map Explorer"),
                        html.Div(
                            "Mineralogy and production of Devonian shale gas wells, "
                            "eastern Kentucky",
                            className="subtitle",
                        ),
                    ]
                ),
                html.Img(
                    src=app.get_asset_url("dash-logo.png"),
                    alt="Plotly",
                    height=32,
                    className="dash-logo",
                ),
            ]
        ),
        html.Main(
            className="explorer-page",
            children=[
                html.Div(
                    className="toolbar",
                    children=[
                        html.Div(
                            className="toolbar-item operators",
                            children=[
                                html.Label("Operators", htmlFor="operator-select"),
                                dcc.Dropdown(
                                    id="operator-select",
                                    options=OPERATORS,
                                    multi=True,
                                    placeholder="All operators",
                                ),
                            ],
                        ),
                        html.Div(
                            className="toolbar-item",
                            children=[
                                html.Label("Ternary layers"),
                                dcc.Checklist(
                                    id="layer-select",
                                    options=LAYERS,
                                    value=LAYERS,
                                    inline=True,
                                    className="pill-checklist",
                                ),
                            ],
                        ),
                        html.Div(id="selection-status", className="selection-status"),
                        html.Button(
                            "Clear selection",
                            id="clear-selection",
                            className="clear-button",
                        ),
                    ],
                ),
                html.Div(id="stats", className="stat-row"),
                html.Div(
                    className="chart-grid",
                    children=[
                        card(
                            "Well locations",
                            graph("well-map"),
                            "Lasso or click wells to select them",
                        ),
                        card(
                            "Shale mineralogy",
                            graph("ternary-map"),
                            "Composition by well; shaded regions are lithofacies",
                        ),
                        card(
                            "Wells by formation",
                            graph("form-by-bar", displayModeBar=False),
                            "Click a bar to select its wells",
                        ),
                        card(
                            "Annual gas production",
                            graph("production-fig", displayModeBar=False),
                            "Thin lines are individual wells; bold lines are the "
                            "median by formation",
                        ),
                    ],
                ),
                card(
                    "Wells",
                    dag.AgGrid(
                        id="well-table",
                        columnDefs=GRID_COLUMNS,
                        defaultColDef={"sortable": True, "resizable": True},
                        dashGridOptions={"animateRows": False, "rowHeight": 32, "headerHeight": 36},
                        style={"height": "300px"},
                    ),
                    class_name="table-card",
                ),
                html.Footer(
                    [
                        "Data: ",
                        html.A(
                            "Kentucky Geological Survey",
                            href="http://www.uky.edu/KGS/emsweb/kyogfaq/kyogfaq10.html",
                            target="_blank",
                        ),
                        " — historical production of selected Devonian Ohio Shale wells.",
                    ],
                    className="footer",
                ),
            ],
        ),
        dcc.Store(id="selected-wells"),
    ],
)


def wells_in_view(operators):
    if not operators:
        return wells
    return wells[wells["operator"].isin(operators)]


def well_ids_from_points(selection):
    """Well IDs from a map or ternary selectedData payload. Rock-type traces
    carry no customdata, so they drop out."""
    ids = []
    for point in (selection or {}).get("points", []):
        customdata = point.get("customdata")
        if customdata is None:
            continue
        well_id = customdata[0] if isinstance(customdata, list) else customdata
        ids.append(int(well_id))
    return sorted(set(ids)) or None


@callback(
    Output("selected-wells", "data"),
    Input("well-map", "selectedData"),
    Input("ternary-map", "selectedData"),
    Input("form-by-bar", "clickData"),
    Input("clear-selection", "n_clicks"),
    Input("operator-select", "value"),
    State("selected-wells", "data"),
    prevent_initial_call=True,
)
def update_selection(map_selection, ternary_selection, bar_click, _, operators, current):
    source = ctx.triggered_id
    if source == "well-map":
        return well_ids_from_points(map_selection)
    if source == "ternary-map":
        return well_ids_from_points(ternary_selection)
    if source == "form-by-bar" and bar_click:
        dff = wells_in_view(operators)
        formation = bar_click["points"][0]["y"]
        ids = sorted(dff.loc[dff["formation"] == formation, "well_id"].tolist())
        # Clicking the bar that is already selected clears it
        return None if ids == current else ids
    return None


@callback(
    Output("well-map", "figure"),
    Output("ternary-map", "figure"),
    Output("form-by-bar", "figure"),
    Output("production-fig", "figure"),
    Output("stats", "children"),
    Output("well-table", "rowData"),
    Output("selection-status", "children"),
    Output("clear-selection", "disabled"),
    Input("operator-select", "value"),
    Input("layer-select", "value"),
    Input("selected-wells", "data"),
)
def render(operators, layers, selected_ids):
    dff = wells_in_view(operators)
    selected = None
    if selected_ids is not None:
        selected = set(selected_ids) & set(dff["well_id"])
    focus = dff if selected is None else dff[dff["well_id"].isin(selected)]

    if selected is None:
        status = f"All {len(dff)} wells in view"
    else:
        status = [html.B(len(focus)), f" of {len(dff)} wells selected"]

    composition = focus[["Quartz", "Carbonate", "Clay"]].mean()
    stats = [
        stat(
            "Wells",
            f"{len(focus):,}",
            "selected" if selected is not None else "in view",
        ),
        stat(
            "Formations",
            f"{focus['formation'].nunique()}",
            f"top: {focus['formation'].mode().iat[0]}" if len(focus) else "—",
        ),
        stat(
            "Mean composition",
            " / ".join(f"{v:.0f}" for v in composition) if len(focus) else "—",
            "quartz / carbonate / clay, %",
        ),
        stat(
            "Cumulative gas",
            f"{focus['cum_mmcf'].sum() / 1_000:,.1f} Bcf",
            "lifetime production",
        ),
    ]

    return (
        figures.well_map(dff, selected),
        figures.ternary(
            dff,
            selected,
            show_wells="Wells" in layers,
            show_rock_types="Rock types" in layers,
        ),
        figures.formation_bar(dff, selected),
        figures.production_lines(dff, selected),
        stats,
        focus.to_dict("records"),
        status,
        selected is None,
    )


if __name__ == "__main__":
    app.run(debug=True)
