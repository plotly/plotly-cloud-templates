from dash import Dash, dcc, html, Input, Output, callback
import plotly.express as px
import pandas as pd

BG = '#0f1117'
CARD = '#1a1d27'
BORDER = '#2d3148'
TEXT = '#e2e8f0'
MUTED = '#94a3b8'
TEMPLATE = 'plotly_dark'

app = Dash(__name__)

df = pd.read_csv('https://raw.githubusercontent.com/plotly/datasets/master/gapminderDataFiveYear.csv')

app.layout = html.Div(style={
    'backgroundColor': BG,
    'padding': '24px',
    'fontFamily': 'Inter, system-ui, sans-serif',
    'minHeight': '100vh',
}, children=[
    html.H2('GDP vs Life Expectancy', style={'color': TEXT, 'marginBottom': '4px'}),
    html.P('Drag the year slider — the chart animates smoothly between years.',
           style={'color': MUTED, 'marginBottom': '16px'}),

    dcc.Graph(id='graph-with-slider'),

    html.Div(style={'padding': '8px 40px 0 40px'}, children=[
        html.Div('Year', style={
            'color': MUTED, 'fontSize': '11px', 'fontWeight': '600',
            'letterSpacing': '0.08em', 'textTransform': 'uppercase', 'marginBottom': '8px',
        }),
        dcc.Slider(
            df['year'].min(),
            df['year'].max(),
            step=None,
            value=df['year'].min(),
            marks={
                str(year): {
                    'label': str(year),
                    'style': {'color': MUTED, 'fontSize': '11px'},
                }
                for year in df['year'].unique()
            },
            id='year-slider',
        ),
    ]),
])


@callback(
    Output('graph-with-slider', 'figure'),
    Input('year-slider', 'value'))
def update_figure(selected_year):
    filtered_df = df[df.year == selected_year]

    fig = px.scatter(
        filtered_df,
        x='gdpPercap', y='lifeExp',
        size='pop', color='continent',
        hover_name='country',
        log_x=True, size_max=55,
        template=TEMPLATE,
    )
    fig.update_layout(
        transition_duration=500,
        plot_bgcolor=CARD,
        paper_bgcolor=CARD,
        margin=dict(l=40, r=40, t=20, b=20),
    )
    return fig


if __name__ == '__main__':
    app.run(debug=True)
