import random

import dash
import dash_mantine_components as dmc
import humanize
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import ALL, Input, Output, State, callback, ctx, dcc, html
from dash_iconify import DashIconify

dash._dash_renderer._set_react_version("18.2.0")

# Initialize the Dash app
app = dash.Dash(__name__)
server = app.server

# Load data once at startup
df = pd.read_csv("data/data.csv")


def get_google_link(search):
    return dcc.Link(
        search,
        href=f"https://google.com/search?q={search}",
        target="_blank",
        className="text-btn",
    )


def create_movie_card(movie, index, metric):
    return dmc.Card(
        [
            dmc.Group(
                [
                    html.Div(
                        [
                            dmc.Group(
                                [
                                    dmc.Badge(
                                        f"#{index + 1}",
                                        variant="filled",
                                        size="xl",
                                        className="rank-badge",
                                    ),
                                    dmc.Text(
                                        f"{movie['title']} ({movie['year']})",
                                        className="movie-title",
                                        fw=800,
                                        size="xl",
                                    ),
                                    html.A(
                                        dmc.ActionIcon(
                                            DashIconify(
                                                icon="mdi:open-in-new", width=22
                                            ),
                                            className="link-btn",
                                            size="xl",
                                            style={"margin-bottom": "12px"},
                                        ),
                                        href=movie["link"],
                                        target="_blank",
                                        style={
                                            "text-decoration": "none",
                                            "margin-left": "auto",
                                        },
                                    ),
                                ],
                                gap="md",
                                align="center",
                                style={"margin-bottom": "12px"},
                            ),
                            html.Div(
                                dmc.Text(
                                    f"${humanize.intword(movie[metric])}",
                                    className="movie-metric",
                                    ml=10,
                                    fw=800,
                                    size="lg",
                                ),
                                className="value-badge",
                            ),
                            html.Div(
                                [
                                    dmc.Badge(
                                        movie.get("genre_1", "Unknown"),
                                        variant="filled",
                                        c="white",
                                        size="lg",
                                        mr=8,
                                        style={
                                            "background": "linear-gradient(135deg, #ff6b35, #d43425)",
                                            "box-shadow": "0 4px 15px rgba(255, 107, 53, 0.3)",
                                        },
                                    ),
                                    (
                                        dmc.Badge(
                                            movie.get(
                                                "genre_2", movie.get("genre_1", "Drama")
                                            ),
                                            variant="outline",
                                            c="gray",
                                            size="md",
                                            style={
                                                "border-color": "rgba(255, 255, 255, 0.3)",
                                                "color": "rgba(255, 255, 255, 0.8)",
                                            },
                                        )
                                        if movie.get("genre_2")
                                        else None
                                    ),
                                ],
                                style={"margin": "15px 0"},
                            ),
                            dmc.Group(
                                [
                                    DashIconify(
                                        icon="mdi:movie-open",
                                        width=18,
                                        color="#ff6b35",
                                        style={
                                            "filter": "drop-shadow(0 0 3px rgba(255, 107, 53, 0.5))"
                                        },
                                    ),
                                    dmc.Text(
                                        "Directed by", size="sm", c="dimmed", fw=500
                                    ),
                                    get_google_link(movie["director"]),
                                ],
                                gap=8,
                                align="center",
                                style={"margin": "8px 0"},
                            ),
                            dmc.Group(
                                [
                                    DashIconify(
                                        icon="mdi:account-star",
                                        width=18,
                                        color="#ff6b35",
                                        style={
                                            "filter": "drop-shadow(0 0 3px rgba(255, 107, 53, 0.5))"
                                        },
                                    ),
                                    dmc.Text("Starring", size="sm", c="dimmed", fw=500),
                                    get_google_link(movie["main_actor_1"]),
                                    dmc.Text("&", size="sm", c="dimmed"),
                                    get_google_link(movie["main_actor_2"]),
                                ],
                                gap=8,
                                align="center",
                                style={"margin": "8px 0"},
                            ),
                        ],
                        style={"flex": 1},
                    ),
                ],
                wrap="nowrap",
                align="flex-start",
            ),
        ],
        className="movie-card",
        p=30,
        style={"position": "relative"},
    )


def create_graph(df, metric):
    """Create stunning graph with streamlined code"""
    df_aggregated = df.groupby(["year", "genre_1"]).agg({metric: "sum"}).reset_index()

    fig = go.Figure()
    genres = sorted(df_aggregated["genre_1"].unique())

    for i, genre in enumerate(genres):
        genre_data = df_aggregated[df_aggregated["genre_1"] == genre]

        fig.add_trace(
            go.Scatter(
                x=genre_data["year"],
                y=genre_data[metric],
                name=genre,
                mode="lines+markers",
                line=dict(width=5, shape="spline", smoothing=1.3),
                marker=dict(size=8),
                hovertemplate=f"<b>{genre}</b><br>Year: %{{x}}<br>{metric.title()}: $%{{y:,.0f}}<extra></extra>",
            )
        )

    # Enhanced layout
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        title=dict(
            text=f"Movie {metric.title()} by Genre",
            x=0.5,
            font=dict(size=20, color="white"),
        ),
        xaxis=dict(title=dict(text="Year", font=dict(size=18))),
        yaxis=dict(title=dict(text=f"{metric.title()}", font=dict(size=18))),
        legend=dict(
            bgcolor="rgba(15, 15, 20, 0.9)",
            bordercolor="rgba(255, 107, 53, 0.3)",
        ),
    )

    return fig


app.layout = dmc.MantineProvider(
    [
        html.Link(
            href="https://fonts.googleapis.com/css2?family=Outfit:wght@100..900&display=swap",
            rel="stylesheet",
        ),
        dmc.Group(
            [
                DashIconify(icon="fluent-emoji-flat:popcorn", width=45),
                dmc.Text("Movie Genre Trends", ml=10, size="xl", fw=900),
            ],
            align="center",
            className="header",
        ),
        dmc.Group(
            [
                dmc.Card(
                    [
                        dmc.Group(
                            [
                                dmc.Text("Metric Selection", size="lg", fw=700, mb=10),
                                dmc.SegmentedControl(
                                    id="segmented",
                                    value="revenue",
                                    data=[
                                        {"value": i, "label": i.capitalize()}
                                        for i in ["revenue", "budget"]
                                    ],
                                ),
                            ],
                            justify="space-between",
                            align="flex-end",
                            style={"margin-bottom": "25px"},
                        ),
                        dmc.Alert(
                            html.Div(
                                [
                                    "Click on any genre line to explore the ",
                                    html.Strong("top 10 movies"),
                                    " in that category.",
                                ]
                            ),
                            icon=DashIconify(icon="mdi:sparkles", width=20),
                            variant="light",
                            className="instruction-alert",
                        ),
                        dcc.Graph(id="graph", className="graph"),
                        dmc.Group(
                            [
                                dmc.Text(
                                    "Data powered by",
                                    size="sm",
                                    c="dimmed",
                                    fw=500,
                                ),
                                dcc.Link(
                                    "Box Office Mojo",
                                    href="https://www.boxofficemojo.com/",
                                    target="_blank",
                                    className="text-link",
                                ),
                            ],
                            className="footer",
                        ),
                    ],
                    p=20,
                    flex=3,
                    className="main-card",
                    h="calc(100vh - 100px)",
                ),
            ],
            id="content",
            p=10,
            gap=0,
            align="flex-start",
        ),
    ],
    forceColorScheme="dark",
    theme={"colorScheme": "dark"},
)


@callback(
    Output("graph", "figure"),
    Input("segmented", "value"),
)
def update_graph(metric):
    return create_graph(df, metric)


@callback(
    Output("content", "children"),
    Input("graph", "clickData"),
    Input("segmented", "value"),
    State("content", "children"),
    prevent_initial_call=True,
)
def show_enhanced_movie_details(clickData, metric, content):

    if not clickData:
        dash.no_update

    genres = sorted(df["genre_1"].unique())
    selected_genre = genres[clickData["points"][0]["curveNumber"]]

    # Filter and sort movies
    genre_movies = (
        df[df["genre_1"] == selected_genre]
        .dropna(subset=[metric])
        .sort_values(by=metric, ascending=False)
        .head(10)
        .reset_index(drop=True)
    )

    # Create stunning movie cards
    movie_cards = [
        create_movie_card(movie, i, metric)
        for i, (_, movie) in enumerate(genre_movies.iterrows())
    ]

    details_content = content + [
        dmc.Card(
            [
                dmc.Text(
                    f"Top {selected_genre} Movies",
                    className="section-title",
                ),
                # Movie cards in enhanced scrollable container
                html.Div(movie_cards, className="movie-cards-div"),
            ],
            p=10,
            flex=2,
            className="main-card",
            h="calc(100vh - 100px)",
        )
    ]

    return details_content


if __name__ == "__main__":
    app.run(debug=True)
