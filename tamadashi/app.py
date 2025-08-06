import dash
from dash import dcc, html, Input, State, Output, callback, no_update
import random

app = dash.Dash(
    name="Tamadashi",
    title="Tamadashi",
    update_title=None,
)


# Centered div + layered images with CSS classes
def make_tamadashi_box():
    tamadashi_body = html.Img(src="assets/Body.png", className="tamadashi-body")
    tamadashi_eyes = html.Img(src="assets/Eyes.png", className="tamadashi-eyes")
    tamadashi_mouth = html.Img(src="assets/Mouth.png", className="tamadashi-mouth")
    layout = html.Div(
        className="tamadashi-container",
        children=[
            html.Div(
                className="tamadashi-box",
                id="tamadashi-box",
                children=[tamadashi_body, tamadashi_eyes, tamadashi_mouth],
            )
        ],
    )
    return layout


def make_controls():
    return html.Div(
        className="controls-container",
        children=[
            html.Button(
                className="controls-button",
                children="🍔",
                id="feed-button",
                title="Feed!",
            ),
            html.Button(
                className="controls-button",
                children="🎾",
                id="play-button",
                title="Play!",
            ),
            html.Button(
                className="controls-button",
                children="🫳",
                id="pat-button",
                title="Pet!",
            ),
        ],
    )


def layout():
    return html.Div(
        className="main-container",
        children=[
            html.H1(
                className="tamadashi-title",
                children=[html.Span(x) for x in ("tama", "dash", "i")],
            ),
            make_tamadashi_box(),
            make_controls(),
            dcc.Interval(id="interval", interval=6000),
            dcc.Store(
                id="status",
                data={"food": 42, "happiness": 42, "energy": 42},
                storage_type="memory",
            ),
            html.Div(id="flying-text-container"),
        ],
    )


@callback(
    Output("status", "data", allow_duplicate=True),
    Output("feed-button", "disabled", allow_duplicate=True),
    Output("play-button", "disabled", allow_duplicate=True),
    Output("pat-button", "disabled", allow_duplicate=True),
    State("status", "data"),
    Input("interval", "n_intervals"),
    prevent_initial_call=True,
)
async def update_status(status, n_intervals):
    status["food"] -= 1
    status["happiness"] -= 1
    status["energy"] += 2
    return status, False, False, False


@callback(
    Output("tamadashi-box", "className"),
    Input("status", "data"),
)
async def update_tamadashi_box(status):
    classname = "tamadashi-box"
    if status["food"] <= 0 or status["happiness"] <= 0 or status["energy"] <= 0:
        classname += " dead"
    elif status["food"] < 40 or status["happiness"] < 40 or status["energy"] < 40:
        classname += " sad"
    elif status["food"] > 75 and status["happiness"] > 75 and status["energy"] > 75:
        classname += " happy"
    return classname


@callback(
    Output("status", "data", allow_duplicate=True),
    Output("feed-button", "disabled", allow_duplicate=True),
    Output("play-button", "disabled", allow_duplicate=True),
    Output("pat-button", "disabled", allow_duplicate=True),
    Output("flying-text-container", "children"),
    State("status", "data"),
    Input("feed-button", "n_clicks"),
    Input("play-button", "n_clicks"),
    Input("pat-button", "n_clicks"),
    prevent_initial_call=True,
)
async def interact(status, n_clicks_feed, n_clicks_play, n_clicks_pat):
    ctx = dash.callback_context
    minmax = lambda x: min(100, max(0, x))

    flying_text = None

    if ctx.triggered_id == "feed-button":
        status["food"] = minmax(status["food"] + 10)
        status["energy"] = minmax(status["energy"] + 5)
        feed_messages = [
            "Yum!",
            "Delicious!",
            "Nom nom!",
            "Tasty!",
            "Mmm!",
            "Yummy!",
            "Scrumptious!",
            "Yay food!",
        ]
        flying_text = html.Div(
            random.choice(feed_messages),
            className="flying-text feed",
            key=f"feed-{n_clicks_feed}",
        )
        feed_disabled = True
        play_disabled = no_update
        pat_disabled = no_update

    elif ctx.triggered_id == "play-button" and status["energy"] > 0:
        status["happiness"] = minmax(status["happiness"] + 10)
        status["energy"] = minmax(status["energy"] - 10)
        status["food"] = minmax(status["food"] - 5)
        play_messages = [
            "Whee!",
            "Fun!",
            "Yay!",
            "Playtime!",
            "Awesome!",
            "Exciting!",
            "Woo!",
            "Amazing!",
        ]
        flying_text = html.Div(
            random.choice(play_messages),
            className="flying-text play",
            key=f"play-{n_clicks_play}",
        )
        feed_disabled = no_update
        play_disabled = True
        pat_disabled = no_update

    elif ctx.triggered_id == "pat-button":
        status["happiness"] = minmax(status["happiness"] + 10)
        status["energy"] = minmax(status["energy"] - 5)
        status["food"] = minmax(status["food"] - 2)
        pat_messages = [
            "Aww!",
            "Cute!",
            "Love!",
            "Sweet!",
            "Gentle!",
            "Kind!",
            "Warm!",
            "Cozy!",
        ]
        flying_text = html.Div(
            random.choice(pat_messages),
            className="flying-text pat",
            key=f"pat-{n_clicks_pat}",
        )
        feed_disabled = no_update
        play_disabled = no_update
        pat_disabled = True

    print(status)

    return status, feed_disabled, play_disabled, pat_disabled, flying_text


app.layout = layout
server = app.server


if __name__ == "__main__":
    app.run(debug=True)
