import dash_mantine_components as dmc
from dash import ALL, Input, Output, State, callback, ctx, html
from dash_iconify import DashIconify

from constants import DEFAULT_SANKEY_NODES, NAVY
from utils import data_utils


def panel_header(title):
    return dmc.CardSection(
        dmc.Text(title, c="white", fw=600, size="sm", ta="center"),
        style={
            "backgroundColor": NAVY,
            "padding": "10px 14px",
        },
    )


def sidebar_controls_supply_sankey(df, filter_values):
    years = data_utils.get_year_dropdown_vals(df)
    return dmc.Card(
        [
            panel_header("Basic Controls & Filters"),
            html.Div(
                [
                    dmc.Space(h=10),
                    html.Div(
                        [
                            dmc.Select(
                                label="Year",
                                value=years[0],
                                data=[
                                    {"value": year, "label": year}
                                    for year in years
                                ],
                                radius="md",
                                id="year-filter-selection",
                            ),
                            dmc.Space(h=10),
                            dmc.Select(
                                label="View Top",
                                placeholder="Select...",
                                value=data_utils.get_top_x_values()[0][
                                    "value"
                                ],
                                data=data_utils.get_top_x_values(),
                                radius="md",
                                id="view-top-data",
                            ),
                        ],
                        style={"padding": "0px 12px"},
                    ),
                    dmc.Space(h=10),
                    dmc.Divider(variant="dashed", mx=12),
                    dmc.Space(h=8),
                    html.Div(
                        generate_filter_controls(df, filter_values),
                        style={"padding": "0px 12px"},
                    ),
                    dmc.Space(h=8),
                    html.Div(
                        dmc.Button(
                            "Clear Filters",
                            radius="md",
                            variant="outline",
                            id="clear-node-filters-btn",
                        ),
                        className="flex-row justify-center",
                        style={"padding": "0px 12px 12px 12px"},
                    ),
                ],
                style={
                    "flexGrow": "1",
                    "overflowY": "auto",
                    "minHeight": "0px",
                },
            ),
        ],
        shadow="sm",
        radius="md",
        withBorder=True,
        style={
            "width": "280px",
            "height": "100%",
            "display": "flex",
            "flexDirection": "column",
        },
    )


def generate_filter_controls(df, filter_values):
    controls = []
    for label, column in filter_values.items():
        controls.extend(
            [
                dmc.MultiSelect(
                    label=label,
                    placeholder="Select value(s)...",
                    data=data_utils.get_filter_dropdown_vals(df, column),
                    searchable=True,
                    clearable=True,
                    id={"type": "global-filters", "index": column},
                ),
                dmc.Space(h=8),
            ]
        )
    return controls


def get_node_card(node_nb, value):
    # Cant delete first 2 nodes, only add "X" on third node and up.
    delete_icon = (
        []
        if node_nb == 1 or node_nb == 2
        else [
            dmc.ActionIcon(
                DashIconify(icon="humbleicons:times", width=16, color="white"),
                variant="transparent",
                size="sm",
                id={
                    "type": "delete-single-node",
                    "index": f"{node_nb}",
                },
            )
        ]
    )
    # Wrapped in a plain html.Div (rather than putting id/className directly
    # on the dmc.Card) because Dash's Card wrapper doesn't accept a `key`
    # prop, and html.Div does. Without a stable `key` here, React reconciles
    # this list by position instead of identity: deleting a middle card then
    # recycles a DOM node (and any stuck focus/CSS state) onto the wrong
    # card instead of actually removing it.
    return html.Div(
        dmc.Card(
            [
                dmc.CardSection(
                    dmc.Group(
                        [dmc.Text("Node", c="white", fw=600, size="sm")]
                        + delete_icon,
                        justify="space-between",
                        style={"height": "100%"},
                    ),
                    style={
                        "backgroundColor": NAVY,
                        "padding": "0px 14px",
                        "height": "44px",
                    },
                ),
                dmc.CardSection(
                    dmc.Select(
                        placeholder="Select Node...",
                        data=data_utils.get_node_dropdown_vals(node_nb == 1),
                        value=value,
                        radius="md",
                        comboboxProps={"position": "bottom", "zIndex": 1000},
                        maxDropdownHeight=160,
                        id={
                            "type": "node-selector",
                            "index": f"{node_nb}",
                        },
                    ),
                    style={"padding": "12px"},
                ),
            ],
            shadow="sm",
            radius="md",
            withBorder=True,
        ),
        className="node-card",
        key=f"node-card-{node_nb}",
        id={
            "type": "node-card",
            "index": f"{node_nb}",
        },
    )


def get_default_nodes():
    return [
        get_node_card(i + 1, value)
        for i, value in enumerate(DEFAULT_SANKEY_NODES)
    ]


@callback(
    Output({"type": "global-filters", "index": ALL}, "value"),
    Input("clear-node-filters-btn", "n_clicks"),
    State({"type": "global-filters", "index": ALL}, "value"),
    prevent_initial_call=True,
)
def clear_node_and_filter_selctions(n_clicks_filter, filters):
    return [[]] * len(ctx.args_grouping[1])
