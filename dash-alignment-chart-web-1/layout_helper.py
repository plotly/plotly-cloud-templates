import base64
import os

import dash
from dash import dcc, html

ASSETS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets')


def _encode_image(filename):
    with open(os.path.join(ASSETS_PATH, filename), 'rb') as image_file:
        return 'data:image/png;base64,{}'.format(
            base64.b64encode(image_file.read()).decode()
        )


def run_standalone_app(
        layout,
        callbacks,
        header_colors,
        filename
):
    """Create the Dash app with the Dash Bio page header."""
    app = dash.Dash(__name__, suppress_callback_exceptions=True)

    app_name = 'alignment-chart'

    app_title = "{}".format(app_name.replace('-', ' ').title())
    app.title = app_title

    # Assign layout
    app.layout = app_page_layout(
        page_layout=layout(),
        app_title=app_title,
        app_name=app_name,
        standalone=True,
        **header_colors()
    )

    # Register all callbacks
    callbacks(app)

    # return app object
    return app


def app_page_layout(page_layout,
                    app_title="Dash Bio App",
                    app_name="",
                    light_logo=True,
                    standalone=False,
                    bg_color="#506784",
                    font_color="#F3F6FA"):
    return html.Div(
        id='main_page',
        children=[
            dcc.Location(id='url', refresh=False),
            html.Div(
                id='app-page-header',
                children=[
                    html.A(
                        id='dashbio-logo', children=[
                            html.Img(src=_encode_image('plotly-dash-bio-logo.png'))
                        ],
                        href="https://dash.plotly.com/dash-bio"
                    ),
                    html.H2(
                        app_title
                    ),

                    html.A(
                        id='gh-link',
                        children=[
                            'View on GitHub'
                        ],
                        href="https://github.com/plotly/dash-bio",
                        style={'color': 'white' if light_logo else 'black',
                               'border': 'solid 1px white' if light_logo else 'solid 1px black'}
                    ),

                    html.Img(
                        src=_encode_image('GitHub-Mark-{}64px.png'.format(
                            'Light-' if light_logo else ''
                        ))
                    )
                ],
                style={
                    'background': bg_color,
                    'color': font_color,
                }
            ),
            html.Div(
                id='app-page-content',
                children=page_layout
            )
        ],
    )
