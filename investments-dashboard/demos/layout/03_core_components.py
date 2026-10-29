from dash import Dash, html, dcc

BG = '#0f1117'
CARD = '#1a1d27'
BORDER = '#2d3148'
TEXT = '#e2e8f0'
MUTED = '#94a3b8'
ACCENT = '#7c3aed'

app = Dash(__name__)

label_style = {
    'color': MUTED,
    'fontSize': '11px',
    'fontWeight': '700',
    'letterSpacing': '0.08em',
    'textTransform': 'uppercase',
    'marginBottom': '8px',
    'marginTop': '20px',
    'display': 'block',
}

section_style = {
    'backgroundColor': CARD,
    'border': f'1px solid {BORDER}',
    'borderRadius': '10px',
    'padding': '20px 24px',
    'flex': 1,
    'minWidth': 0,
}

app.layout = html.Div(style={
    'backgroundColor': BG,
    'padding': '32px',
    'fontFamily': 'Inter, system-ui, sans-serif',
    'minHeight': '100vh',
}, children=[
    html.H2('Core Components', style={'color': TEXT, 'marginBottom': '4px'}),
    html.P('Every dcc component is declared entirely through keyword arguments — fully declarative.',
           style={'color': MUTED, 'marginBottom': '24px'}),

    html.Div(style={'display': 'flex', 'gap': '16px'}, children=[

        # Left column
        html.Div(style=section_style, children=[
            html.Span('Dropdown', style=label_style),
            dcc.Dropdown(
                ['New York City', 'Montréal', 'San Francisco'],
                'Montréal',
            ),

            html.Span('Multi-Select Dropdown', style=label_style),
            dcc.Dropdown(
                ['New York City', 'Montréal', 'San Francisco'],
                ['Montréal', 'San Francisco'],
                multi=True,
            ),

            html.Span('Radio Items', style=label_style),
            dcc.RadioItems(
                ['New York City', 'Montréal', 'San Francisco'],
                'Montréal',
                labelStyle={'color': TEXT, 'marginRight': '12px', 'fontSize': '14px'},
            ),
        ]),

        # Right column
        html.Div(style=section_style, children=[
            html.Span('Checkboxes', style=label_style),
            dcc.Checklist(
                ['New York City', 'Montréal', 'San Francisco'],
                ['Montréal', 'San Francisco'],
                labelStyle={'color': TEXT, 'marginRight': '12px', 'fontSize': '14px'},
            ),

            html.Span('Text Input', style=label_style),
            dcc.Input(
                value='MTL',
                type='text',
                style={
                    'backgroundColor': BG,
                    'border': f'1px solid {BORDER}',
                    'borderRadius': '6px',
                    'color': TEXT,
                    'padding': '8px 12px',
                    'fontSize': '14px',
                    'outline': 'none',
                },
            ),

            html.Span('Slider', style=label_style),
            dcc.Slider(
                min=0,
                max=9,
                marks={
                    i: {
                        'label': f'Label {i}' if i == 1 else str(i),
                        'style': {'color': MUTED, 'fontSize': '11px'},
                    }
                    for i in range(1, 6)
                },
                value=5,
            ),
        ]),
    ]),
])

if __name__ == '__main__':
    app.run(debug=True)
