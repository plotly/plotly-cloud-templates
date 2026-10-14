from dash import Dash, dcc, html, Input, Output, callback
import plotly.express as px
import pandas as pd
import json

BG = '#0f1117'
CARD = '#1a1d27'
BORDER = '#2d3148'
TEXT = '#e2e8f0'
MUTED = '#94a3b8'
TEMPLATE = 'plotly_dark'

app = Dash(__name__)

df = pd.DataFrame({
    "x": [1, 2, 1, 2],
    "y": [1, 2, 3, 4],
    "customdata": [1, 2, 3, 4],
    "fruit": ["apple", "apple", "orange", "orange"]
})

fig = px.scatter(df, x="x", y="y", color="fruit", custom_data=["customdata"],
                 template=TEMPLATE, color_discrete_map={"apple": "#7c3aed", "orange": "#f97316"})
fig.update_layout(
    plot_bgcolor=CARD,
    paper_bgcolor=CARD,
    clickmode='event+select',
    margin=dict(l=40, r=40, t=40, b=40),
)
fig.update_traces(marker_size=20)

pre_style = {
    'backgroundColor': CARD,
    'border': f'1px solid {BORDER}',
    'color': TEXT,
    'borderRadius': '8px',
    'padding': '12px',
    'overflowX': 'auto',
    'fontSize': '12px',
    'minHeight': '180px',
}

label_style = {
    'color': MUTED,
    'fontSize': '11px',
    'fontWeight': '600',
    'letterSpacing': '0.08em',
    'textTransform': 'uppercase',
    'marginBottom': '8px',
}

panel_style = {
    'flex': 1,
    'minWidth': 0,
}

app.layout = html.Div(style={
    'backgroundColor': BG,
    'padding': '24px',
    'fontFamily': 'Inter, system-ui, sans-serif',
    'minHeight': '100vh',
}, children=[
    html.H2('Graph Interaction Data', style={'color': TEXT, 'marginBottom': '4px'}),
    html.P('Hover, click, select, or zoom the chart to see the interaction data.',
           style={'color': MUTED, 'marginBottom': '24px'}),

    dcc.Graph(
        id='basic-interactions',
        figure=fig,
        style={'marginBottom': '24px'},
    ),

    html.Div(style={'display': 'flex', 'gap': '16px'}, children=[
        html.Div(style=panel_style, children=[
            html.Div('Hover Data', style=label_style),
            html.Pre(id='hover-data', style=pre_style),
        ]),
        html.Div(style=panel_style, children=[
            html.Div('Click Data', style=label_style),
            html.Pre(id='click-data', style=pre_style),
        ]),
        html.Div(style=panel_style, children=[
            html.Div('Selection Data', style=label_style),
            html.Pre(id='selected-data', style=pre_style),
        ]),
        html.Div(style=panel_style, children=[
            html.Div('Zoom / Relayout Data', style=label_style),
            html.Pre(id='relayout-data', style=pre_style),
        ]),
    ]),
])


@callback(Output('hover-data', 'children'), Input('basic-interactions', 'hoverData'))
def display_hover(hoverData):
    return json.dumps(hoverData, indent=2)


@callback(Output('click-data', 'children'), Input('basic-interactions', 'clickData'))
def display_click(clickData):
    return json.dumps(clickData, indent=2)


@callback(Output('selected-data', 'children'), Input('basic-interactions', 'selectedData'))
def display_selected(selectedData):
    return json.dumps(selectedData, indent=2)


@callback(Output('relayout-data', 'children'), Input('basic-interactions', 'relayoutData'))
def display_relayout(relayoutData):
    return json.dumps(relayoutData, indent=2)


if __name__ == '__main__':
    app.run(debug=True)
