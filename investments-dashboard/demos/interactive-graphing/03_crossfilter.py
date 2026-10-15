from dash import Dash, dcc, html, Input, Output, callback
import numpy as np
import pandas as pd
import plotly.express as px

BG = '#0f1117'
CARD = '#1a1d27'
BORDER = '#2d3148'
TEXT = '#e2e8f0'
MUTED = '#94a3b8'
ACCENT = '#7c3aed'
TEMPLATE = 'plotly_dark'

app = Dash(__name__)

np.random.seed(0)
df = pd.DataFrame({"Col " + str(i + 1): np.random.rand(30) for i in range(6)})


def get_figure(df, x_col, y_col, selectedpoints, selectedpoints_local):
    if selectedpoints_local and selectedpoints_local.get("range"):
        ranges = selectedpoints_local["range"]
        selection_bounds = {
            "x0": ranges["x"][0], "x1": ranges["x"][1],
            "y0": ranges["y"][0], "y1": ranges["y"][1],
        }
    else:
        selection_bounds = {
            "x0": np.min(df[x_col]), "x1": np.max(df[x_col]),
            "y0": np.min(df[y_col]), "y1": np.max(df[y_col]),
        }

    fig = px.scatter(df, x=df[x_col], y=df[y_col], text=df.index, template=TEMPLATE)
    fig.update_traces(
        selectedpoints=selectedpoints,
        customdata=df.index,
        mode="markers+text",
        marker={"color": ACCENT, "size": 16, "opacity": 0.9},
        unselected={
            "marker": {"opacity": 0.15, "color": MUTED},
            "textfont": {"color": "rgba(0,0,0,0)"},
        },
        selected={
            "marker": {"color": ACCENT, "opacity": 1.0},
        },
        textfont={"size": 9, "color": MUTED},
    )
    fig.update_layout(
        plot_bgcolor=CARD,
        paper_bgcolor=CARD,
        margin={"l": 20, "r": 10, "b": 20, "t": 30},
        dragmode="select",
        hovermode=False,
        newselection_mode="gradual",
        xaxis_title=x_col,
        yaxis_title=y_col,
    )
    fig.add_shape(dict(
        type="rect",
        line={"width": 1, "dash": "dot", "color": MUTED},
        **selection_bounds,
    ))
    return fig


app.layout = html.Div(style={
    'backgroundColor': BG,
    'padding': '24px',
    'fontFamily': 'Inter, system-ui, sans-serif',
    'minHeight': '100vh',
}, children=[
    html.H2('Crossfilter', style={'color': TEXT, 'marginBottom': '4px'}),
    html.P('Lasso or box-select points in any chart — the selection filters across all three.',
           style={'color': MUTED, 'marginBottom': '24px'}),

    html.Div(style={'display': 'flex', 'gap': '16px'}, children=[
        dcc.Graph(id='g1', config={'displayModeBar': True, 'modeBarButtonsToKeep': ['select2d', 'lasso2d']},
                  style={'flex': 1}),
        dcc.Graph(id='g2', config={'displayModeBar': True, 'modeBarButtonsToKeep': ['select2d', 'lasso2d']},
                  style={'flex': 1}),
        dcc.Graph(id='g3', config={'displayModeBar': True, 'modeBarButtonsToKeep': ['select2d', 'lasso2d']},
                  style={'flex': 1}),
    ]),
])


@callback(
    Output('g1', 'figure'),
    Output('g2', 'figure'),
    Output('g3', 'figure'),
    Input('g1', 'selectedData'),
    Input('g2', 'selectedData'),
    Input('g3', 'selectedData'),
)
def update_charts(sel1, sel2, sel3):
    selectedpoints = df.index
    for sel in [sel1, sel2, sel3]:
        if sel and sel['points']:
            selectedpoints = np.intersect1d(
                selectedpoints,
                [p['customdata'] for p in sel['points']]
            )
    return [
        get_figure(df, 'Col 1', 'Col 2', selectedpoints, sel1),
        get_figure(df, 'Col 3', 'Col 4', selectedpoints, sel2),
        get_figure(df, 'Col 5', 'Col 6', selectedpoints, sel3),
    ]


if __name__ == '__main__':
    app.run(debug=True)
