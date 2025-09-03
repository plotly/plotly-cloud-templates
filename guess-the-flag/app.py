import dash
import dash_mantine_components as dmc
from dash import Input, Output, State, callback_context, dcc, html
from utils.utils import create_flag_display, get_countries_data

# Initialize the Dash app
app = dash.Dash(__name__)

server = app.server
app.title = "Guess the Flag"
app.index_string = """
<!DOCTYPE html>
<html>
  <head>
    {%metas%}
    <title>Guess the Flag</title>
    <meta name="title" content="Guess the Flag" />
    <meta name="description" content="Do you know your flags? Test your knowledge with this fun game built in Dash!" />

    <meta property="og:type" content="website" />
    <meta property="og:url" content="https://guess-the-flag.plotly.app/" />
    <meta property="og:title" content="Guess the Flag" />
    <meta property="og:description" content="Do you know your flags? Test your knowledge with this fun game built in Dash!" />
    <meta property="og:image" content="https://guess-the-flag.plotly.app/assets/thumbnail.png" />

    <meta name="twitter:card" content="summary_large_image" />
    <meta name="twitter:url" content="https://guess-the-flag.plotly.app/" />
    <meta name="twitter:title" content="Guess the Flag" />
    <meta name="twitter:description" content="Do you know your flags? Test your knowledge with this fun game built in Dash!" />
    <meta name="twitter:image" content="https://guess-the-flag.plotly.app/assets/thumbnail.png" />

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

# Load the countries data
df = get_countries_data()
print(f"Loaded {len(df)} countries using countryflag package")

# Get list of country names for dropdown
country_names = df["name"].tolist()

# Initialize game state
current_flag = None
current_country = None
score = 0


def get_random_flag():
    """Get a random flag and country from the dataset"""
    global current_flag, current_country
    random_row = df.sample(n=1).iloc[0]
    current_country = random_row["name"]
    current_flag = random_row["flag"]
    return current_flag, current_country


# Get initial flag
get_random_flag()

# App layout
app.layout = dmc.MantineProvider(
    html.Div(
        [
            # Background container with world map theme
            html.Div(
                [
                    html.H1("🌍 Guess the Flag! 🌍", className="app-title"),
                    # Score display with globe icon
                    html.Div(
                        [
                            html.H2(
                                f"🏆 Score: {score} 🏆",
                                id="score-display",
                                className="score-display",
                            )
                        ]
                    ),
                    # Flag image with fallback - centered with world theme
                    html.Div(
                        [
                            html.Div(
                                create_flag_display(current_flag, current_country),
                                id="flag-container",
                                className="flag-container-wrapper",
                            ),
                        ],
                        className="flag-container-wrapper",
                    ),
                    # Country dropdown with international styling
                    html.Div(
                        [
                            html.Label(
                                "🗺️ Select the country:", className="dropdown-label"
                            ),
                            dcc.Dropdown(
                                id="country-dropdown",
                                options=[
                                    {"label": country, "value": country}
                                    for country in country_names
                                ],
                                placeholder="Choose a country...",
                                style={
                                    "marginTop": "3px",
                                    "marginBottom": "8px",
                                    "fontSize": "clamp(11px, 2.2vw, 14px)",
                                },
                            ),
                        ],
                        className="dropdown-section",
                    ),
                    # Submit button with international styling
                    html.Div(
                        [
                            html.Button(
                                "🚀 Submit Guess 🚀",
                                id="submit-button",
                                n_clicks=0,
                                className="submit-button",
                            )
                        ],
                        className="button-container",
                    ),
                    # Result message with better styling
                    html.Div(
                        id="result-message",
                        className="result-message",
                    ),
                    # New game button with international styling
                    html.Div(
                        [
                            html.Button(
                                "🌎 Next Flag 🌎",
                                id="next-flag-button",
                                n_clicks=0,
                                className="next-flag-button",
                            )
                        ],
                        id="next-flag-container",
                        className="button-container",
                    ),
                ],
                className="world-theme-container",
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
        className="app-container",
    )
)


@app.callback(
    [
        Output("result-message", "children"),
        Output("score-display", "children"),
        Output("next-flag-container", "style"),
        Output("flag-container", "children"),
        Output("submit-button", "disabled"),
    ],
    [Input("submit-button", "n_clicks"), Input("next-flag-button", "n_clicks")],
    [State("country-dropdown", "value")],
    prevent_initial_call=True,
)
def handle_submission(submit_clicks, next_clicks, selected_country):
    global score, current_flag, current_country

    # Determine which button was clicked
    ctx = callback_context
    if not ctx.triggered:
        return (
            "",
            f"Score: {score}",
            {"display": "none"},
            create_flag_display(current_flag, current_country),
            False,
        )

    button_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if button_id == "submit-button":
        if selected_country is None:
            return (
                "Please select a country first!",
                f"Score: {score}",
                {"display": "none"},
                create_flag_display(current_flag, current_country),
                False,
            )

        if selected_country == current_country:
            score += 1
            message = f"Correct! That's {current_country}. Score: {score}"
            return (
                message,
                f"Score: {score}",
                {"display": "block"},
                create_flag_display(current_flag, current_country),
                True,
            )
        else:
            score = 0
            message = (
                f"Wrong! The correct answer was {current_country}. Score reset to 0."
            )
            return (
                message,
                f"Score: {score}",
                {"display": "block"},
                create_flag_display(current_flag, current_country),
                False,
            )

    elif button_id == "next-flag-button":
        # Generate new flag
        new_flag, new_country = get_random_flag()
        return (
            "",
            f"Score: {score}",
            {"display": "none"},
            create_flag_display(new_flag, new_country),
            False,
        )

    return (
        "",
        f"Score: {score}",
        {"display": "none"},
        create_flag_display(current_flag, current_country),
        False,
    )


@app.callback(
    Output("country-dropdown", "value"),
    [Input("next-flag-button", "n_clicks")],
    prevent_initial_call=True,
)
def reset_dropdown(next_clicks):
    """Reset dropdown selection when moving to next flag"""
    return None


# Flag display is now initialized directly in the layout above

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)
