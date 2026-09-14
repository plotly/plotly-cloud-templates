import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

from utils import data_utils
from typing import Tuple

pio.templates["app_theme"] = go.layout.Template(
    layout=go.Layout(
        font=dict(family="Poppins, sans-serif", color="#514338"),
        paper_bgcolor="rgba(0, 0, 0, 0)",
        plot_bgcolor="rgba(0, 0, 0, 0)",
        margin=dict(t=40, l=20, r=20, b=20),
    )
)
pio.templates.default = "app_theme"


def add_spot_market_links_for_node(
    spot_market_node: str,
    link_mappings: dict,
    col: str,
    spod_data: pd.DataFrame,
    year: str,
    links: list,
):
    """
    This function is a helper function to add_spot_market_links. This loops through the
    spot data (either Spod or Lep data) to create each link.
    """
    color_dict = data_utils.get_color_dict()
    # check in case spod market is not a value in the currently selected nodes/filters
    if spot_market_node in link_mappings[col].keys():
        # looping through the spod-df
        for node_value, link_weight in zip(spod_data[col], spod_data[year]):
            # getting link color
            if not node_value in link_mappings[col].keys():
                link_color = color_dict.get("Other")
            else:
                link_color = color_dict.get(node_value)
            links.append(
                (
                    (
                        link_mappings[col].get(
                            node_value, link_mappings[col].get("Other")
                        ),
                        link_mappings[col][spot_market_node],
                    ),
                    link_weight,
                    link_color,
                )
            )
    return links


def add_spot_market_links(
    links: list,
    link_mappings: dict,
    columns: list,
    spot_df: pd.DataFrame,
    year: str,
):
    """
    This function handles the Spot Market links. It aggregates the data in the spot market df
    (seperating spod nodes from lep nodes) and creates a link from this aggregation to
    the appropriate Spot Node.
    """
    spod_str = "Spot Market Spod"
    lep_str = "Spot Market Lep"
    for col in columns:
        if col.startswith("Resource"):
            if "Offtake Owner" in spot_df.columns:
                spod_data = spot_df.loc[spot_df["Offtake Owner"] == spod_str]
                lep_data = spot_df.loc[spot_df["Offtake Owner"] == lep_str]
                # creating 2 dfs: one with spod data and one with lep data, grouped by each node type
                # to link to the spot market node
                spod_data = spod_data.groupby([col], as_index=False).sum()
                lep_data = lep_data.groupby([col], as_index=False).sum()

                add_spot_market_links_for_node(
                    spod_str,
                    link_mappings,
                    col,
                    spod_data,
                    year,
                    links,
                )
                add_spot_market_links_for_node(
                    lep_str,
                    link_mappings,
                    col,
                    lep_data,
                    year,
                    links,
                )


def get_top_values(
    columns: list,
    df: pd.DataFrame,
    year: str,
    spot_df: pd.DataFrame,
    view_top,
) -> list:
    """
    This function keeps the top_x nodes of each columns in the sankey diagram.
    The top_x value is selected from the dropdown in the app.
    The nodes not in the top_x are aggregated into one "Other" category.
    Params:
        columns: list of selected "nodes" in the app, they actally represent columns in the dataframe
        df: the supply dataframe
        year: the selected year from the year dropdown (as a string)
        spot_df: the the spot market dataframe
        view_top: number of nodes to be shown per columns (5,10, 15 or all)
    Returns:
        column_values: a list of lists, each of these is a list of nodes for each selected column
    """
    column_values = []
    spot_market_nodes = ["Spot Market Spod", "Spot Market Lep"]
    if view_top == "view_all":
        view_top = df.shape[0]
    for col in columns:
        # We need to add the resource cols from spod-market-df to the supply-df so we can create
        # the links (this is because some nodes from spot-market-df are not in the supply-df)
        if col.startswith("Resource"):
            # get all Resource nodes from the supply and spod dataframe
            all_resource_nodes = df[[col, year]].append(spot_df[[col, year]])
            # group by year and sort in descending order
            grouped_resource_nodes = (
                all_resource_nodes.groupby([col], as_index=False)
                .sum()
                .sort_values(by=year, ascending=False)
            )
            # remove spot market nodes from the dataframe so they don't get removed if they don't
            # appear in the top_x (as these should always be present)
            grouped_resource_nodes = grouped_resource_nodes[
                ~grouped_resource_nodes[col].isin(spot_market_nodes)
            ]
            # keep top_x values only and add back the spot market nodes
            top_x_resource_nodes = (
                list(grouped_resource_nodes.head(view_top)[col])
                + spot_market_nodes
            )
            # replacing all nodes NOT in the top_x with the "Other" keyword
            all_resource_nodes.loc[
                ~all_resource_nodes[col].isin(top_x_resource_nodes), col
            ] = "Other"
            column_values.append(all_resource_nodes[col])
        else:
            # Same logic as above but without the spod market nodes
            all_nodes = df[[col, year]]
            grouped_nodes = (
                all_nodes.groupby([col], as_index=False)
                .sum()
                .sort_values(by=year, ascending=False)
            )
            top_x_nodes = list(grouped_nodes.head(view_top)[col])
            all_nodes.loc[~all_nodes[col].isin(top_x_nodes), col] = "Other"
            column_values.append(all_nodes[col])
    return column_values


def generate_sankey_data(
    columns: list,
    df: pd.DataFrame,
    year: int,
    spot_df: pd.DataFrame,
    view_top,
) -> Tuple[list, list, list, list, list]:
    """
    This function creates the data required to generate the sankey diragram.
    Params:
        columns: list of selected "nodes" in the app, they actally represent columns in the dataframe
        df: the supply dataframe
        year: the selected year from the year dropdown
        spot_df: the the spot market dataframe

    Returns:
        labels: labels that get assigned to each node
        sources: a list of nubmers, each number represents a node in the sankey.
        targets: a list of nubmers, same as above. The link is created between the source and target by using the numbers placed as the same index in the list.
        values: the weight of each link.
        colors: a list of the color to be used for each link
    """
    color_dict = data_utils.get_color_dict()
    df = df.fillna("(No Value)")
    year = str(year)
    # list of dfs that contain a list of nodes for each selected column

    column_values = get_top_values(columns, df, year, spot_df, view_top)

    # list of all unique nodes in all of the columns
    labels = sum(
        [list(node_values.unique()) for node_values in column_values], []
    )
    # list of empty dicts (one per column) to create a numerical mapping
    link_mappings = {}
    for col in columns:
        link_mappings[col] = {}

    # assigning a number to each unique node, repeating for each column. Numbers must be
    # continuous from column to column
    i = 0
    for col, nodes in zip(columns, column_values):
        for node in nodes.unique():
            link_mappings[col][node] = i
            i = i + 1

    source_nodes = column_values[: len(columns) - 1]
    target_nodes = column_values[1:]
    source_cols = columns[: len(columns) - 1]
    target_cols = columns[1:]
    links = []
    # Create links (tuples) between source and target nodes, and their respective weight and color, by using the list of mappings
    # Note: resource columns will be longer than other columns becasue spot nodes were added. By default, the loop
    # will operate on the shortest column. This is what we want since the extra nodes from the resource colums come from the
    # spot-df and those links will be added afterwards.
    for source, target, source_col, target_col in zip(
        source_nodes, target_nodes, source_cols, target_cols
    ):
        for val1, val2, link_weight in zip(source, target, df[year]):
            links.append(
                (
                    (
                        link_mappings[source_col][val1],
                        link_mappings[target_col][val2],
                    ),
                    link_weight,
                    color_dict.get(val1),
                )
            )
    # adding spot market links to current links
    add_spot_market_links(links, link_mappings, columns, spot_df, year)
    df_links = pd.DataFrame(links, columns=["link", "weight", "color"])
    df_links = df_links.groupby(by=["link"], as_index=False).agg(
        {"weight": sum, "color": "first"}
    )
    sources = [val[0] for val in df_links["link"]]
    targets = [val[1] for val in df_links["link"]]
    values = df_links["weight"].tolist()
    link_hex_colors = df_links["color"]
    link_colors = [data_utils.hex2rgb(color) for color in link_hex_colors]
    node_colors = [color_dict.get(color, "#afa28e") for color in labels]
    return labels, sources, targets, values, link_colors, node_colors


def generate_sankey(nodes, df, year, spot_df, view_top):
    (
        labels,
        sources,
        targets,
        values,
        link_colors,
        node_colors,
    ) = generate_sankey_data(nodes, df, year, spot_df, view_top)
    fig = go.Figure(
        data=[
            go.Sankey(
                node=dict(
                    pad=15,
                    thickness=20,
                    line=dict(width=0),
                    label=labels if len(labels) < 50 else [],
                    customdata=labels,
                    hovertemplate="%{customdata}",
                    color=node_colors,
                ),
                link=dict(
                    source=sources,
                    target=targets,
                    value=values,
                    hovertemplate="%{source.customdata} to %{target.customdata}",
                    color=link_colors,
                ),
            )
        ],
    )
    # Add annotations for each node name
    for i, node in enumerate(nodes):
        if i == 0:
            xanchor = "left"
        elif i == len(nodes) - 1:
            xanchor = "right"
        else:
            xanchor = "center"

        fig.add_annotation(
            text=node,
            xref="paper",
            yref="paper",
            xanchor=xanchor,
            x=i / (len(nodes) - 1),
            y=1.1,
            font=dict(size=14),
            showarrow=False,
        )
    # Create space at top for annotations
    fig.update_layout(margin=dict(t=50, l=20, r=20))
    return fig

