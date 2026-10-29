from dash import Dash, html, dcc
import plotly.express as px
import pandas as pd

BG = '#0f1117'
CARD = '#1a1d27'
BORDER = '#2d3148'
TEXT = '#e2e8f0'
MUTED = '#94a3b8'
TEMPLATE = 'plotly_dark'

app = Dash(__name__)

df = pd.DataFrame({
    "Fruit": ["Apples", "Oranges", "Bananas", "Apples", "Oranges", "Bananas"],
    "Amount": [4, 1, 2, 2, 4, 5],
    "City": ["SF", "SF", "SF", "Montreal", "Montreal", "Montreal"],
})

fig = px.bar(df, x="Fruit", y="Amount", color="City", barmode="group", template=TEMPLATE)
fig.update_layout(plot_bgcolor=CARD, paper_bgcolor=CARD, margin=dict(l=40, r=40, t=40, b=40))

app.layout = html.Div(style={
    'backgroundColor': BG,
    'padding': '32px',
    'fontFamily': 'Inter, system-ui, sans-serif',
    'minHeight': '100vh',
}, children=[
    html.H1('Hello Dash', style={'color': TEXT, 'marginBottom': '4px'}),

    html.Div('Dash: A web application framework for your data.', style={
        'color': MUTED,
        'fontSize': '15px',
        'marginBottom': '24px',
    }),

    dcc.Graph(id='example-graph', figure=fig),

    html.P(
        '✏️  Try editing the H1 title above in the code, save the file, and watch the browser update automatically.',
        style={
            'color': MUTED,
            'fontSize': '12px',
            'marginTop': '16px',
            'border': f'1px solid {BORDER}',
            'borderRadius': '6px',
            'padding': '10px 14px',
            'backgroundColor': CARD,
        },
    ),
])

if __name__ == '__main__':
    app.run(debug=True)
