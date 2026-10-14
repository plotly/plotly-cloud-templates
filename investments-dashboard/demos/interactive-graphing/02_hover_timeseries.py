from dash import Dash, html, dcc, Input, Output, callback
import pandas as pd
import plotly.express as px

BG = '#0f1117'
CARD = '#1a1d27'
BORDER = '#2d3148'
TEXT = '#e2e8f0'
MUTED = '#94a3b8'
TEMPLATE = 'plotly_dark'

app = Dash(__name__)

df = pd.read_csv('https://plotly.github.io/datasets/country_indicators.csv')

dropdown_style = {
    'backgroundColor': CARD,
    'color': TEXT,
}

label_style = {
    'color': MUTED,
    'fontSize': '11px',
    'fontWeight': '600',
    'letterSpacing': '0.08em',
    'textTransform': 'uppercase',
    'marginBottom': '6px',
}

radio_style = {
    'color': TEXT,
    'fontSize': '13px',
}

app.layout = html.Div(style={
    'backgroundColor': BG,
    'padding': '24px',
    'fontFamily': 'Inter, system-ui, sans-serif',
    'minHeight': '100vh',
}, children=[
    html.H2('World Indicators Explorer', style={'color': TEXT, 'marginBottom': '4px'}),
    html.P('Hover over a country in the scatter plot to see its historical trend.',
           style={'color': MUTED, 'marginBottom': '20px'}),

    # Controls row
    html.Div(style={'display': 'flex', 'gap': '24px', 'marginBottom': '16px'}, children=[
        html.Div(style={'flex': 1}, children=[
            html.Div('X Axis Indicator', style=label_style),
            dcc.Dropdown(
                df['Indicator Name'].unique(),
                'Fertility rate, total (births per woman)',
                id='crossfilter-xaxis-column',
                style=dropdown_style,
            ),
            dcc.RadioItems(
                ['Linear', 'Log'], 'Linear',
                id='crossfilter-xaxis-type',
                inline=True,
                style=radio_style,
                labelStyle={'marginRight': '12px', 'marginTop': '6px'},
            ),
        ]),
        html.Div(style={'flex': 1}, children=[
            html.Div('Y Axis Indicator', style=label_style),
            dcc.Dropdown(
                df['Indicator Name'].unique(),
                'Life expectancy at birth, total (years)',
                id='crossfilter-yaxis-column',
                style=dropdown_style,
            ),
            dcc.RadioItems(
                ['Linear', 'Log'], 'Linear',
                id='crossfilter-yaxis-type',
                inline=True,
                style=radio_style,
                labelStyle={'marginRight': '12px', 'marginTop': '6px'},
            ),
        ]),
    ]),

    # Charts row
    html.Div(style={'display': 'flex', 'gap': '16px'}, children=[
        html.Div(style={'flex': '0 0 55%'}, children=[
            dcc.Graph(
                id='crossfilter-indicator-scatter',
                hoverData={'points': [{'customdata': 'Japan'}]},
            ),
        ]),
        html.Div(style={'flex': 1}, children=[
            dcc.Graph(id='x-time-series'),
            dcc.Graph(id='y-time-series'),
        ]),
    ]),

    # Year slider
    html.Div(style={'marginTop': '8px', 'paddingRight': '24px', 'width': '55%'}, children=[
        html.Div('Year', style=label_style),
        dcc.Slider(
            df['Year'].min(),
            df['Year'].max(),
            step=None,
            id='crossfilter-year--slider',
            value=df['Year'].max(),
            marks={str(year): {'label': str(year), 'style': {'color': MUTED, 'fontSize': '11px'}}
                   for year in df['Year'].unique()},
        ),
    ]),
])


@callback(
    Output('crossfilter-indicator-scatter', 'figure'),
    Input('crossfilter-xaxis-column', 'value'),
    Input('crossfilter-yaxis-column', 'value'),
    Input('crossfilter-xaxis-type', 'value'),
    Input('crossfilter-yaxis-type', 'value'),
    Input('crossfilter-year--slider', 'value'))
def update_scatter(xaxis_col, yaxis_col, xaxis_type, yaxis_type, year):
    dff = df[df['Year'] == year]
    fig = px.scatter(
        x=dff[dff['Indicator Name'] == xaxis_col]['Value'],
        y=dff[dff['Indicator Name'] == yaxis_col]['Value'],
        hover_name=dff[dff['Indicator Name'] == yaxis_col]['Country Name'],
        template=TEMPLATE,
    )
    fig.update_traces(
        customdata=dff[dff['Indicator Name'] == yaxis_col]['Country Name'],
        marker=dict(size=8, opacity=0.8),
    )
    fig.update_xaxes(title=xaxis_col, type='linear' if xaxis_type == 'Linear' else 'log')
    fig.update_yaxes(title=yaxis_col, type='linear' if yaxis_type == 'Linear' else 'log')
    fig.update_layout(
        plot_bgcolor=CARD,
        paper_bgcolor=CARD,
        margin=dict(l=40, b=40, t=20, r=20),
        hovermode='closest',
    )
    return fig


def create_time_series(dff, axis_type, title):
    fig = px.scatter(dff, x='Year', y='Value', template=TEMPLATE)
    fig.update_traces(mode='lines+markers', marker=dict(size=5), line=dict(color='#7c3aed'))
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(type='linear' if axis_type == 'Linear' else 'log')
    fig.add_annotation(
        x=0, y=0.85, xanchor='left', yanchor='bottom',
        xref='paper', yref='paper', showarrow=False, align='left',
        text=title, font=dict(size=11, color=MUTED),
    )
    fig.update_layout(
        height=225,
        plot_bgcolor=CARD,
        paper_bgcolor=CARD,
        margin=dict(l=20, b=30, r=10, t=10),
    )
    return fig


@callback(
    Output('x-time-series', 'figure'),
    Input('crossfilter-indicator-scatter', 'hoverData'),
    Input('crossfilter-xaxis-column', 'value'),
    Input('crossfilter-xaxis-type', 'value'))
def update_x_timeseries(hoverData, xaxis_col, axis_type):
    country = hoverData['points'][0]['customdata']
    dff = df[(df['Country Name'] == country) & (df['Indicator Name'] == xaxis_col)]
    return create_time_series(dff, axis_type, f'<b>{country}</b><br>{xaxis_col}')


@callback(
    Output('y-time-series', 'figure'),
    Input('crossfilter-indicator-scatter', 'hoverData'),
    Input('crossfilter-yaxis-column', 'value'),
    Input('crossfilter-yaxis-type', 'value'))
def update_y_timeseries(hoverData, yaxis_col, axis_type):
    country = hoverData['points'][0]['customdata']
    dff = df[(df['Country Name'] == country) & (df['Indicator Name'] == yaxis_col)]
    return create_time_series(dff, axis_type, yaxis_col)


if __name__ == '__main__':
    app.run(debug=True)
