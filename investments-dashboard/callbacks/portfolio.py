from dash import callback, Input, Output, State, dcc, html
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

from utils.data_loader import get_sector_allocation
from components.charts import CHART_COLORS, CHART_LAYOUT

sector_data = get_sector_allocation()

def create_sector_bar_with_highlight(highlighted_sector=None):
    """Create sector bar chart with optional highlight"""
    fig = go.Figure()
    
    colors = [CHART_COLORS['primary'] if (highlighted_sector is None or s == highlighted_sector) 
              else 'rgba(34, 139, 230, 0.3)' 
              for s in sector_data['Sector']]
    
    fig.add_trace(go.Bar(
        y=sector_data['Sector'],
        x=sector_data['Fund'],
        name='Fund',
        orientation='h',
        marker_color=colors,
    ))
    
    benchmark_colors = [CHART_COLORS['gray'] if (highlighted_sector is None or s == highlighted_sector) 
                        else 'rgba(134, 142, 150, 0.3)' 
                        for s in sector_data['Sector']]
    
    fig.add_trace(go.Bar(
        y=sector_data['Sector'],
        x=sector_data['Benchmark'],
        name='Benchmark',
        orientation='h',
        marker_color=benchmark_colors,
    ))
    
    title = 'Sector Allocation vs Benchmark'
    if highlighted_sector:
        title = f'Sector Allocation - {highlighted_sector} Highlighted'
    
    fig.update_layout(
        **CHART_LAYOUT,
        title={'text': title, 'x': 0, 'font': {'size': 16, 'weight': 600}},
        barmode='group',
        bargap=0.3,
        legend={'orientation': 'h', 'y': -0.15},
        xaxis={'title': 'Allocation %', 'ticksuffix': '%'},
        yaxis={'title': ''},
        height=450,
    )
    
    return fig

@callback(
    [Output("allocation-view", "style"),
     Output("characteristics-view", "style"),
     Output("risk-view", "style")],
    Input("portfolio-view", "value")
)
def switch_portfolio_view(view):
    """Switch between allocation, characteristics, and risk views"""
    hidden = {"display": "none"}
    visible = {"display": "block"}
    
    if view == "allocation":
        return visible, hidden, hidden
    elif view == "characteristics":
        return hidden, visible, hidden
    else:
        return hidden, hidden, visible

@callback(
    Output("sector-bar-chart", "figure"),
    Input("sector-donut", "clickData"),
    State("sector-donut", "figure"),
    prevent_initial_call=True
)
def highlight_sector(click_data, current_figure):
    """Highlight selected sector in bar chart (synced with donut toggle)"""
    if click_data and 'points' in click_data:
        selected_idx = click_data['points'][0].get('pointNumber', None)
        sector_name = click_data['points'][0].get('label', None)
        
        current_pull = current_figure.get('data', [{}])[0].get('pull', [])
        already_selected = (
            current_pull and 
            selected_idx is not None and
            len(current_pull) > selected_idx and 
            current_pull[selected_idx] > 0
        )
        
        if not already_selected:
            return create_sector_bar_with_highlight(sector_name)
    return create_sector_bar_with_highlight(None)

@callback(
    Output("sector-detail-text", "children"),
    Input("sector-donut", "clickData"),
    State("sector-donut", "figure")
)
def update_sector_detail(click_data, current_figure):
    """Show sector details when clicked (synced with donut toggle)"""
    if click_data and 'points' in click_data:
        point = click_data['points'][0]
        selected_idx = point.get('pointNumber', None)
        sector = point.get('label', 'Unknown')
        value = point.get('value', 0)
        
        current_pull = current_figure.get('data', [{}])[0].get('pull', []) if current_figure else []
        already_selected = (
            current_pull and 
            selected_idx is not None and
            len(current_pull) > selected_idx and 
            current_pull[selected_idx] > 0
        )
        
        if not already_selected:
            return f"Selected: {sector} ({value:.1f}% allocation)"
    return "Click on a sector to see details"

@callback(
    Output("sector-donut", "figure"),
    Input("sector-donut", "clickData"),
    State("sector-donut", "figure"),
    prevent_initial_call=True
)
def highlight_donut_sector(click_data, current_figure):
    """Highlight selected sector in donut chart (click again to reset)"""
    import re
    colors = px.colors.qualitative.Set3[:len(sector_data)]
    
    pull_values = [0] * len(sector_data)
    opacities = [1] * len(sector_data)
    
    if click_data and 'points' in click_data:
        selected_idx = click_data['points'][0].get('pointNumber', None)
        if selected_idx is not None:
            current_pull = current_figure.get('data', [{}])[0].get('pull', [])
            already_selected = (
                current_pull and 
                len(current_pull) > selected_idx and 
                current_pull[selected_idx] > 0
            )
            
            if not already_selected:
                pull_values = [0.15 if i == selected_idx else 0 for i in range(len(sector_data))]
                opacities = [1 if i == selected_idx else 0.4 for i in range(len(sector_data))]
    
    adjusted_colors = []
    for i, c in enumerate(colors):
        if c.startswith('rgb('):
            rgb_match = re.match(r'rgb\((\d+),\s*(\d+),\s*(\d+)\)', c)
            if rgb_match:
                r, g, b = rgb_match.groups()
                adjusted_colors.append(f'rgba({r}, {g}, {b}, {opacities[i]})')
            else:
                adjusted_colors.append(c)
        elif c.startswith('#'):
            rgb = px.colors.hex_to_rgb(c)
            adjusted_colors.append(f'rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, {opacities[i]})')
        else:
            adjusted_colors.append(c)
    
    fig = go.Figure(go.Pie(
        labels=sector_data['Sector'],
        values=sector_data['Fund'],
        hole=0.6,
        marker={'colors': adjusted_colors, 'line': {'color': 'white', 'width': 2}},
        textinfo='percent',
        textposition='outside',
        pull=pull_values,
        hovertemplate='%{label}<br>%{value:.1f}%<extra></extra>'
    ))
    
    fig.update_layout(
        **CHART_LAYOUT,
        title={'text': 'Sector Allocation (Click to highlight)', 'x': 0, 'font': {'size': 16, 'weight': 600}},
        showlegend=True,
        legend={'orientation': 'v', 'x': 1.05, 'y': 0.5},
        annotations=[{
            'text': 'Sectors',
            'x': 0.5, 'y': 0.5,
            'font': {'size': 14, 'weight': 600},
            'showarrow': False
        }]
    )

    return fig


