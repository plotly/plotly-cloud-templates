from dash import Dash, dcc, html, Input, Output, callback

BG = '#0f1117'
CARD = '#1a1d27'
BORDER = '#2d3148'
TEXT = '#e2e8f0'
MUTED = '#94a3b8'
ACCENT = '#7c3aed'

app = Dash(__name__)

app.layout = html.Div(style={
    'backgroundColor': BG,
    'padding': '48px',
    'fontFamily': 'Inter, system-ui, sans-serif',
    'minHeight': '100vh',
    'maxWidth': '640px',
    'margin': '0 auto',
}, children=[
    html.H2('Callback Anatomy', style={'color': TEXT, 'marginBottom': '4px'}),
    html.P('The output reacts automatically whenever the input changes.',
           style={'color': MUTED, 'marginBottom': '40px'}),

    # Input section
    html.Div(style={
        'backgroundColor': CARD,
        'border': f'1px solid {BORDER}',
        'borderRadius': '10px',
        'padding': '20px',
        'marginBottom': '12px',
    }, children=[
        html.Div('INPUT', style={
            'color': MUTED, 'fontSize': '11px', 'fontWeight': '700',
            'letterSpacing': '0.1em', 'marginBottom': '10px',
        }),
        dcc.Input(
            id='my-input',
            value='initial value',
            type='text',
            debounce=False,
            style={
                'backgroundColor': BG,
                'border': f'1px solid {ACCENT}',
                'borderRadius': '6px',
                'color': TEXT,
                'padding': '10px 14px',
                'fontSize': '15px',
                'width': '100%',
                'outline': 'none',
                'boxSizing': 'border-box',
            },
        ),
        html.P('Try changing this value — the output below updates instantly.',
               style={'color': MUTED, 'fontSize': '12px', 'marginTop': '8px', 'marginBottom': 0}),
    ]),

    # Arrow indicator
    html.Div('↓', style={
        'color': ACCENT, 'fontSize': '24px', 'textAlign': 'center',
        'margin': '4px 0', 'lineHeight': 1,
    }),

    # Output section
    html.Div(style={
        'backgroundColor': CARD,
        'border': f'1px solid {BORDER}',
        'borderRadius': '10px',
        'padding': '20px',
    }, children=[
        html.Div('OUTPUT', style={
            'color': MUTED, 'fontSize': '11px', 'fontWeight': '700',
            'letterSpacing': '0.1em', 'marginBottom': '10px',
        }),
        html.Div(id='my-output', style={
            'color': ACCENT,
            'fontSize': '22px',
            'fontWeight': '600',
            'minHeight': '32px',
        }),
    ]),
])


@callback(
    Output('my-output', 'children'),
    Input('my-input', 'value'),
)
def update_output(input_value):
    return f'Output: {input_value}'


if __name__ == '__main__':
    app.run(debug=True)
