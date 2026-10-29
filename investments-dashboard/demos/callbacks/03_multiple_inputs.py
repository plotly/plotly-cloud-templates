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

df = pd.read_csv('https://plotly.github.io/datasets/country_indicators.csv')

label_style = {
    'color': MUTED,
    'fontSize': '11px',
    'fontWeight': '600',
    'letterSpacing': '0.08em',
    'textTransform': 'uppercase',
    'marginBottom': '6px',
}

radio_label_style = {'marginRight': '12px', 'marginTop': '6px', 'color': TEXT, 'fontSize': '13px'}

app.layout = html.Div(style={
    'backgroundColor': BG,
    'padding': '24px',
    'fontFamily': 'Inter, system-ui, sans-serif',
    'minHeight': '100vh',
}, children=[
    html.H2('Multiple Inputs → One Output', style={'color': TEXT, 'marginBottom': '4px'}),
    html.P('Any of the 5 controls below triggers the callback and updates the chart.',
           style={'color': MUTED, 'marginBottom': '20px'}),

    # Controls row
    html.Div(style={'display': 'flex', 'gap': '24px', 'marginBottom': '16px'}, children=[
        html.Div(style={'flex': 1}, children=[
            html.Div('X Axis Indicator', style=label_style),
            dcc.Dropdown(
                df['Indicator Name'].unique(),
                'Fertility rate, total (births per woman)',
                id='xaxis-column',
                style={'backgroundColor': CARD, 'color': TEXT},
            ),
            dcc.RadioItems(
                ['Linear', 'Log'], 'Linear',
                id='xaxis-type',
                inline=True,
                labelStyle=radio_label_style,
            ),
        ]),
        html.Div(style={'flex': 1}, children=[
            html.Div('Y Axis Indicator', style=label_style),
            dcc.Dropdown(
                df['Indicator Name'].unique(),
                'Life expectancy at birth, total (years)',
                id='yaxis-column',
                style={'backgroundColor': CARD, 'color': TEXT},
            ),
            dcc.RadioItems(
                ['Linear', 'Log'], 'Linear',
                id='yaxis-type',
                inline=True,
                labelStyle=radio_label_style,
            ),
        ]),
    ]),

    dcc.Graph(id='indicator-graphic'),

    html.Div(style={'padding': '8px 40px 0 40px'}, children=[
        html.Div('Year', style=label_style),
        dcc.Slider(
            df['Year'].min(),
            df['Year'].max(),
            step=None,
            id='year--slider',
            value=df['Year'].max(),
            marks={
                str(year): {
                    'label': str(year),
                    'style': {'color': MUTED, 'fontSize': '11px'},
                }
                for year in df['Year'].unique()
            },
        ),
    ]),
])


@callback(
    Output('indicator-graphic', 'figure'),
    Input('xaxis-column', 'value'),
    Input('yaxis-column', 'value'),
    Input('xaxis-type', 'value'),
    Input('yaxis-type', 'value'),
    Input('year--slider', 'value'))
def update_graph(xaxis_col, yaxis_col, xaxis_type, yaxis_type, year_value):
    dff = df[df['Year'] == year_value]

    fig = px.scatter(
        x=dff[dff['Indicator Name'] == xaxis_col]['Value'],
        y=dff[dff['Indicator Name'] == yaxis_col]['Value'],
        hover_name=dff[dff['Indicator Name'] == yaxis_col]['Country Name'],
        template=TEMPLATE,
    )
    fig.update_layout(
        plot_bgcolor=CARD,
        paper_bgcolor=CARD,
        margin=dict(l=40, b=40, t=20, r=20),
        hovermode='closest',
    )
    fig.update_xaxes(title=xaxis_col, type='linear' if xaxis_type == 'Linear' else 'log')
    fig.update_yaxes(title=yaxis_col, type='linear' if yaxis_type == 'Linear' else 'log')
    return fig


if __name__ == '__main__':
    app.run(debug=True)
