"""
Downhole callbacks:
1. Hole selector → rebuild strip log figure
2. Clientside callback: hoverData → update depth cursor shape (zero Python round-trip)
3. Python callback: clickData → click-to-measure state machine
4. Clear button → reset measurement
"""

import json
import plotly.graph_objects as go
from dash import Input, Output, State, callback, clientside_callback, no_update, ctx
import dash

from pages.downhole_logs import _strip_log_figure
from utils import load_data


@callback(
    Output("strip-log-chart", "figure"),
    Input("hole-selector", "value"),
)
def update_strip_log(hole_id):
    collar, assay, lith, survey = load_data()
    return _strip_log_figure(hole_id, collar, assay, lith, survey)


@callback(
    [Output("kpi-hole-depth", "children"),
     Output("kpi-lith-count", "children")],
    Input("hole-selector", "value"),
)
def update_hole_kpis(hole_id):
    collar, _, lith, _ = load_data()
    row = collar.loc[collar["HOLEID"] == hole_id]
    depth = int(row["TOTDEPTH"].iloc[0]) if not row.empty else 0
    lith_count = int(lith[lith["HOLEID"] == hole_id].shape[0])
    return f"{depth} m", str(lith_count)


# ── Depth cursor — clientside for zero latency ──────────────────────────────
# Plot-wide hover events fire even over empty plot areas (not just data points).
# The transparent sentinel traces in each panel ensure hoverData is populated
# anywhere along the depth axis.
clientside_callback(
    """
    function(hoverData, figure) {
        if (!hoverData || !hoverData.points || hoverData.points.length === 0) {
            return window.dash_clientside.no_update;
        }
        var depth = hoverData.points[0].y;
        if (depth === undefined || depth === null) {
            return window.dash_clientside.no_update;
        }
        // Deep-copy so Dash detects the change
        var fig = JSON.parse(JSON.stringify(figure));
        if (!fig.layout.shapes) return window.dash_clientside.no_update;
        for (var i = 0; i < fig.layout.shapes.length; i++) {
            if (fig.layout.shapes[i].name === 'depth-cursor') {
                fig.layout.shapes[i].y0 = depth;
                fig.layout.shapes[i].y1 = depth;
                fig.layout.shapes[i].visible = true;
            }
        }
        return fig;
    }
    """,
    Output("strip-log-chart", "figure", allow_duplicate=True),
    Input("strip-log-chart", "hoverData"),
    State("strip-log-chart", "figure"),
    prevent_initial_call=True,
)


# ── Click-to-measure state machine ──────────────────────────────────────────
@callback(
    [Output("measure-readout", "children"),
     Output("measure-store",   "data"),
     Output("strip-log-chart", "figure", allow_duplicate=True)],
    [Input("strip-log-chart", "clickData"),
     Input("measure-clear-btn", "n_clicks")],
    [State("measure-store",   "data"),
     State("strip-log-chart", "figure")],
    prevent_initial_call=True,
)
def handle_click_measure(click_data, clear_clicks, store, current_fig):
    triggered = ctx.triggered_id

    # Clear button
    if triggered == "measure-clear-btn":
        fig = go.Figure(current_fig)
        for shape in fig.layout.shapes:
            if shape.name == "measure-span":
                shape.visible = False
        fig.layout.annotations = [
            a for a in fig.layout.annotations if "click again" not in (a.text or "")
        ]
        return "Click a depth to start measuring", None, fig

    # Click events
    if not click_data or not click_data.get("points"):
        return no_update, no_update, no_update

    depth = click_data["points"][0].get("y")
    if depth is None:
        return no_update, no_update, no_update

    fig = go.Figure(current_fig)

    # Strip any pending "click again" prompt before updating
    fig.layout.annotations = [
        a for a in fig.layout.annotations if "click again" not in (a.text or "")
    ]

    if store is None or store.get("first_depth") is None:
        # First click: store depth
        new_store = {"first_depth": float(depth)}
        readout   = f"From: {depth:.1f} m — click again to set end depth"

        # Show a thin line at the first click depth
        for shape in fig.layout.shapes:
            if shape.name == "measure-span":
                shape.y0      = float(depth)
                shape.y1      = float(depth) + 0.5
                shape.visible = True

        # On-chart prompt so user knows a second click is needed
        fig.add_annotation(
            x=0.5, y=float(depth) + 10,
            xref="paper", yref="y",
            text="↓ click again to set end depth",
            showarrow=True, arrowhead=2,
            arrowcolor="#e8a020", ax=0, ay=22,
            font=dict(size=10, color="#e8a020", family="monospace"),
            bgcolor="rgba(255,255,255,0.9)",
            bordercolor="#e8a020", borderwidth=1,
            xanchor="center",
        )

        return readout, new_store, fig

    else:
        # Second click: compute interval, draw span
        d1 = store["first_depth"]
        d2 = float(depth)
        lo, hi    = min(d1, d2), max(d1, d2)
        thickness = hi - lo

        for shape in fig.layout.shapes:
            if shape.name == "measure-span":
                shape.y0      = lo
                shape.y1      = hi
                shape.visible = True

        # Add annotation showing the thickness
        fig.add_annotation(
            x=0.98, y=(lo + hi) / 2,
            xref="paper", yref="y",
            text=f" {thickness:.1f} m ",
            showarrow=False,
            font=dict(size=11, color="#d48806", family="monospace"),
            bgcolor="rgba(255,255,255,0.9)",
            bordercolor="#e8a020",
            borderwidth=1,
            xanchor="right",
        )

        readout = f"{lo:.1f} m — {hi:.1f} m  =  {thickness:.1f} m interval"
        return readout, None, fig   # reset store for next measurement


@callback(
    Output("dl-tour", "isOpen"),
    Input("dl-tour-btn", "n_clicks"),
    prevent_initial_call=True,
)
def open_dl_tour(_):
    return True
