from dash import Dash, dcc, html, Input, Output, State, callback

BG = '#0f1117'
CARD = '#1a1d27'
BORDER = '#2d3148'
TEXT = '#e2e8f0'
MUTED = '#94a3b8'
ACCENT = '#7c3aed'

app = Dash(__name__)

input_style = {
    'backgroundColor': CARD,
    'border': f'1px solid {BORDER}',
    'borderRadius': '6px',
    'color': TEXT,
    'padding': '10px 14px',
    'fontSize': '15px',
    'width': '100%',
    'outline': 'none',
    'boxSizing': 'border-box',
    'marginBottom': '12px',
}

label_style = {
    'color': MUTED,
    'fontSize': '11px',
    'fontWeight': '600',
    'letterSpacing': '0.08em',
    'textTransform': 'uppercase',
    'marginBottom': '6px',
    'display': 'block',
}

app.layout = html.Div(style={
    'backgroundColor': BG,
    'padding': '48px',
    'fontFamily': 'Inter, system-ui, sans-serif',
    'minHeight': '100vh',
    'maxWidth': '560px',
    'margin': '0 auto',
}, children=[
    html.H2('State vs Input', style={'color': TEXT, 'marginBottom': '4px'}),
    html.P(
        'Typing in the fields does nothing. Only clicking Submit fires the callback.',
        style={'color': MUTED, 'marginBottom': '32px'},
    ),

    html.Div(style={
        'backgroundColor': CARD,
        'border': f'1px solid {BORDER}',
        'borderRadius': '10px',
        'padding': '24px',
        'marginBottom': '16px',
    }, children=[
        html.Span('City', style=label_style),
        dcc.Input(
            id='input-1-state',
            type='text',
            value='Montréal',
            placeholder='Enter a city',
            style=input_style,
        ),

        html.Span('Country', style=label_style),
        dcc.Input(
            id='input-2-state',
            type='text',
            value='Canada',
            placeholder='Enter a country',
            style=input_style,
        ),

        html.Button(
            'Submit',
            id='submit-button-state',
            n_clicks=0,
            style={
                'backgroundColor': ACCENT,
                'color': '#fff',
                'border': 'none',
                'borderRadius': '6px',
                'padding': '10px 24px',
                'fontSize': '14px',
                'fontWeight': '600',
                'cursor': 'pointer',
                'width': '100%',
                'marginTop': '4px',
            },
        ),
    ]),

    html.Div(id='output-state', style={
        'color': TEXT,
        'fontSize': '15px',
        'padding': '16px 20px',
        'backgroundColor': CARD,
        'border': f'1px solid {BORDER}',
        'borderRadius': '10px',
        'minHeight': '56px',
    }),
])


@callback(
    Output('output-state', 'children'),
    Input('submit-button-state', 'n_clicks'),
    State('input-1-state', 'value'),
    State('input-2-state', 'value'),
)
def update_output(n_clicks, city, country):
    if n_clicks == 0:
        return html.Span('Waiting for submission…', style={'color': MUTED})
    return f'Submitted {n_clicks} time{"s" if n_clicks != 1 else ""}. City: {city}, Country: {country}.'


if __name__ == '__main__':
    app.run(debug=True)
