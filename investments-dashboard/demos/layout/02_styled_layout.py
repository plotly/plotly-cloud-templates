from dash import Dash, dcc, html
import plotly.express as px
import pandas as pd

# style dict — the pattern from the docs, upgraded to our palette
colors = {
    'background': '#0f1117',
    'card': '#1a1d27',
    'text': '#e2e8f0',
    'muted': '#94a3b8',
    'accent': '#7c3aed',
}

app = Dash(__name__)

df = pd.DataFrame({
    "Fruit": ["Apples", "Oranges", "Bananas", "Apples", "Oranges", "Bananas"],
    "Amount": [4, 1, 2, 2, 4, 5],
    "City": ["SF", "SF", "SF", "Montreal", "Montreal", "Montreal"],
})

fig = px.bar(df, x="Fruit", y="Amount", color="City", barmode="group", template='plotly_dark')
fig.update_layout(
    plot_bgcolor=colors['card'],
    paper_bgcolor=colors['card'],
    font_color=colors['text'],
    margin=dict(l=40, r=40, t=40, b=40),
)

app.layout = html.Div(
    style={'backgroundColor': colors['background'], 'padding': '32px',
           'fontFamily': 'Inter, system-ui, sans-serif', 'minHeight': '100vh'},
    children=[
        html.H1(
            'Hello Dash',
            style={'textAlign': 'center', 'color': colors['accent']},
        ),
        html.Div(
            'Dash: A web application framework for your data.',
            style={'textAlign': 'center', 'color': colors['muted'], 'marginBottom': '24px'},
        ),
        dcc.Graph(id='example-graph-2', figure=fig),
    ],
)

if __name__ == '__main__':
    app.run(debug=True)
