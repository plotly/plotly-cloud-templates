import dash_mantine_components as dmc
from dash import (
    ALL,
    MATCH,
    Input,
    Output,
    State,
    callback,
    ctx,
    dash,
    dcc,
    html,
)

from constants import DEFAULT_SANKEY_NODES
from utils import chart_utils, data_utils, ui_utils

DEFAULT_FORECAST_VERSION = data_utils.get_forecast_version_values()[0][
    "value"
]


def layout():
    return html.Div(
        [
            html.Div(
                ui_utils.sidebar_controls_supply_sankey(
                    data_utils.get_supply_data(DEFAULT_FORECAST_VERSION),
                    data_utils.supply_filter_values(),
                ),
                id="controls-filters-sankey",
                className="flex-row",
                style={
                    "flexGrow": "1",
                    "height": "100%",
                    "minHeight": "0px",
                },
            ),
            html.Div(
                [
                    dmc.Card(
                        html.Div(
                            [
                                html.Div(
                                    [
                                        *ui_utils.get_default_nodes(),
                                    ],
                                    id="node-row",
                                    className="node-container flex-row",
                                    style={
                                        "alignItems": "flex-start",
                                        "minWidth": "0px",
                                        "flex": "1 1 0%",
                                    },
                                ),
                                dmc.Space(w=10),
                                html.Div(
                                    dmc.Button(
                                        "+ Node",
                                        radius="md",
                                        variant="outline",
                                        id="add-node-btn",
                                    ),
                                    style={
                                        "margin-left": "auto",
                                        "marginTop": "16px",
                                        "flexShrink": "0",
                                    },
                                ),
                                dmc.Space(w=20),
                            ],
                            className="flex-row",
                            style={
                                "height": "inherit",
                                "alignItems": "flex-start",
                                "minWidth": "0px",
                            },
                        ),
                        shadow="sm",
                        radius="md",
                        withBorder=True,
                        style={
                            "marginBottom": "20px",
                            "minWidth": "0px",
                            "overflow": "visible",
                            "position": "relative",
                            "zIndex": 2,
                        },
                    ),
                    dmc.Card(
                        dcc.Graph(
                            id="sankey-diagram-div",
                            config={
                                "displaylogo": False,
                                "responsive": True,
                            },
                            style={"flexGrow": "1", "width": "100%"},
                        ),
                        shadow="sm",
                        radius="md",
                        withBorder=True,
                        style={
                            "flexGrow": "1",
                            "display": "flex",
                            "flexDirection": "column",
                            "minWidth": "0px",
                        },
                    ),
                ],
                className="flex-column",
                style={
                    "width": "calc(100vw - 300px)",
                    "height": "100%",
                    "minHeight": "0px",
                    "minWidth": "0px",
                },
            ),
        ],
        className="page-div flex-row",
        style={"height": "calc(100vh - 68px)"},
    )


@callback(
    Output("node-row", "children"),
    Output("add-node-btn", "disabled"),
    Input("add-node-btn", "n_clicks"),
    Input({"type": "delete-single-node", "index": ALL}, "n_clicks"),
    State("node-row", "children"),
    prevent_initial_call=True,
)
def add_remove_node_selector_cards(add_node, delete_single_node, node_div):
    if ctx.triggered_id == "add-node-btn":
        node_div.append(
            # get id number of last node in the node_div to make the next node with that id + 1
            ui_utils.get_node_card(
                int(node_div[-1]["props"]["id"]["index"]) + 1, None
            )
        )
        if len(node_div) == 8:
            return node_div, True
        return node_div, False
    if ctx.triggered_id["type"] == "delete-single-node":
        # Adding a node registers a new delete button matching this ALL
        # pattern, which re-fires this callback with that button's n_clicks
        # still None (nobody clicked it) - ignore that phantom trigger
        # instead of treating it as a real delete.
        if not ctx.triggered[0]["value"]:
            return dash.no_update, dash.no_update
        node_to_remove = str(ctx.triggered_id["index"])
        current_nodes = [
            node_div[i]["props"]["id"]["index"]
            for i in range(0, len(node_div))
        ]
        # get index of node to delete and remove it from node_div
        node_div.pop(current_nodes.index(node_to_remove))
        return node_div, False
    return dash.no_update, False


@callback(
    Output("sankey-diagram-div", "figure"),
    Input({"type": "node-selector", "index": ALL}, "value"),
    Input({"type": "global-filters", "index": ALL}, "value"),
    Input("year-filter-selection", "value"),
    Input("view-top-data", "value"),
)
def update_sankey_diagram(nodes, filters, year, view_top):
    df = data_utils.get_supply_data(DEFAULT_FORECAST_VERSION)
    spot_df = data_utils.get_spot_data(DEFAULT_FORECAST_VERSION)
    # case: same node selected twice
    if len(set(nodes)) != len(nodes):
        return dash.no_update
    # case: a node has been added, but no selection has been made yet
    if not all(nodes):
        nodes = [node for node in nodes if node]
    for column, filter in zip(
        data_utils.supply_filter_values().values(), filters
    ):
        if not filter:
            # no filter selected means use all the data
            continue
        df = df[df[column].isin(filter)]
    df = df[[str(year)] + nodes]
    if view_top != "view_all":
        view_top = int(view_top)
    return chart_utils.generate_sankey(nodes, df, year, spot_df, view_top)


@callback(
    Output({"type": "node-selector", "index": MATCH}, "error"),
    Input({"type": "node-selector", "index": MATCH}, "value"),
    State({"type": "node-selector", "index": ALL}, "value"),
)
def select_value(new_node, nodes):
    node_already_selected = new_node is not None and nodes.count(new_node) >= 2
    return (
        "This node has already been selected!" if node_already_selected else ""
    )
