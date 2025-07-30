from dash import dcc, html, Dash
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc

app = Dash(__name__)
server = app.server
df = pd.read_csv("data.csv")

# Custom color mapping for each category
color_discrete_map = {
    "Fruity": "#C94A45",
    "Roasted": "#C94930",
    "Sour/Fermented": "#EAB40A",
    "Green/Vegetative": "#5E9B7F",
    "Spices": "#764552",
    "Floral": "#E1719B",
    "Sweet": "#F27778",
    "Nutty/Cocoa": "#BB764B",
    "Other": "#76C0CB",
}

sunburst_fig = px.sunburst(
    df,
    path=["Level_1", "Level_2", "Level_3"],
    color="Level_1",
    color_discrete_map=color_discrete_map,
)
sunburst_fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))


treemap_fig = px.treemap(
    df,
    path=["Level_1", "Level_2", "Level_3"],
    color="Level_1",
    color_discrete_map=color_discrete_map,
)

treemap_fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))

treemap_fig.update_traces(
    textinfo="label",
    hovertemplate="<b>%{label}</b><br>%{percentParent}<extra></extra>",
)


def create_datacard(title, value, color):
    return html.Div(
        [
            html.Div(
                [
                    html.H4(value, className="datacard-number"),
                    html.P(title, className="datacard-label"),
                ],
                className=f"datacard {color}",
            )
        ],
    )


app.layout = dmc.MantineProvider(
    html.Div(
        [
            dmc.Grid(
                [
                    dmc.GridCol(
                        [
                            dmc.Card(
                                [
                                    dcc.Markdown(
                                        f"""
                                            ## Coffee Flavor Analysis Dashboard
                                            This dashboard explores the complex world of coffee flavor profiles using a hierarchical taxonomy.
                                         """,
                                    ),
                                    html.Div(
                                        [
                                            html.Div(
                                                [
                                                    dcc.Markdown(
                                                        """
                                                            **Data Structure**
                                                            - **Level 1:** Main categories (Fruity, Floral, etc.)
                                                            - **Level 2:** Sub-categories (Berry, Citrus, etc.)  
                                                            - **Level 3:** Specific flavors (Blackberry, Orange, etc.)
                                                         """
                                                    )
                                                ]
                                            ),
                                            html.Div(
                                                [
                                                    dcc.Markdown(
                                                        """
                                                            **Key Features**
                                                            - Interactive sunburst chart for exploration
                                                            - Treemap visualization for analysis  
                                                            - Consistent color coding across charts
                                                         """
                                                    )
                                                ]
                                            ),
                                        ],
                                        className="intro-content-flex",
                                    ),
                                ],
                                className="intro-card",
                            )
                        ],
                        span=9,
                    ),
                    dmc.GridCol(
                        dmc.Stack(
                            [
                                create_datacard(
                                    "Total Categories",
                                    df["Level_1"].nunique(),
                                    "burgundy",
                                ),
                                create_datacard(
                                    "Sub-Categories", df["Level_2"].nunique(), "pink"
                                ),
                                create_datacard(
                                    "Flavor Profiles", len(df.dropna()), "coral"
                                ),
                            ],
                            className="datacard-stack",
                        ),
                        span=3,
                    ),
                ],
            ),
            dmc.Grid(
                [
                    dmc.GridCol(
                        [
                            dmc.Card(
                                [
                                    dmc.CardSection(
                                        dmc.Group(
                                            children=[
                                                dmc.Text(
                                                    "Coffee Flavor Profile Distribution",
                                                    fw=500,
                                                ),
                                            ],
                                        ),
                                        withBorder=True,
                                        inheritPadding=True,
                                        py="xs",
                                    ),
                                    dcc.Graph(figure=sunburst_fig),
                                ],
                                className="chart-card",
                            )
                        ],
                        span=4,
                    ),
                    dmc.GridCol(
                        [
                            dmc.Card(
                                [
                                    dmc.CardSection(
                                        dmc.Group(
                                            children=[
                                                dmc.Text(
                                                    "Coffee Flavor Treemap", fw=500
                                                )
                                            ],
                                        ),
                                        withBorder=True,
                                        inheritPadding=True,
                                        py="xs",
                                    ),
                                    dcc.Graph(figure=treemap_fig),
                                ],
                                radius="md",
                                className="chart-card",
                            )
                        ],
                        span=8,
                    ),
                ],
            ),
        ],
        className="main-container",
    )
)

if __name__ == "__main__":
    app.run(debug=True, port=8050)
