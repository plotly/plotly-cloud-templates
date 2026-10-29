from dash import Input, Output, State, callback, clientside_callback

from pages.cross_section import _build_figure
from utils import load_data


@callback(
    Output("cross-section-chart", "figure"),
    Input("section-orientation", "value"),
)
def update_cross_section(orientation):
    collar, _, _, survey = load_data()
    return _build_figure(collar, survey, orientation)


@callback(
    Output("cs-tour", "isOpen"),
    Input("cs-tour-btn", "n_clicks"),
    prevent_initial_call=True,
)
def open_cs_tour(_):
    return True


# Hide the Y-axis hint on first meaningful chart interaction (pan, zoom).
clientside_callback(
    """
    function(relayoutData, currentStyle) {
        if (!relayoutData) return currentStyle || {"display": "flex"};
        var ignored = {"autosize": 1, "width": 1, "height": 1};
        var keys = Object.keys(relayoutData).filter(function(k) {
            return !ignored[k];
        });
        if (keys.length > 0) {
            return {"display": "none"};
        }
        return currentStyle || {"display": "flex"};
    }
    """,
    Output("cs-yaxis-hint", "style"),
    Input("cross-section-chart", "relayoutData"),
    State("cs-yaxis-hint", "style"),
    prevent_initial_call=True,
)


# Elevation cursor — tracks mouse elevation across all three panels.
clientside_callback(
    """
    function(hoverData, figure) {
        if (!hoverData || !hoverData.points || !hoverData.points.length) {
            return window.dash_clientside.no_update;
        }
        var elev = hoverData.points[0].y;
        if (elev == null) return window.dash_clientside.no_update;
        var fig = JSON.parse(JSON.stringify(figure));
        if (!fig.layout.shapes) return window.dash_clientside.no_update;
        for (var i = 0; i < fig.layout.shapes.length; i++) {
            var n = fig.layout.shapes[i].name || "";
            if (n === "elev-cursor-1" || n === "elev-cursor-2" || n === "elev-cursor-3") {
                fig.layout.shapes[i].y0 = elev;
                fig.layout.shapes[i].y1 = elev;
                fig.layout.shapes[i].visible = true;
            }
        }
        return fig;
    }
    """,
    Output("cross-section-chart", "figure", allow_duplicate=True),
    Input("cross-section-chart", "hoverData"),
    State("cross-section-chart", "figure"),
    prevent_initial_call=True,
)


# Click to pin a marker line at the clicked elevation across all three panels.
clientside_callback(
    """
    function(clickData, figure) {
        if (!clickData || !clickData.points || !clickData.points.length) {
            return window.dash_clientside.no_update;
        }
        var elev = clickData.points[0].y;
        if (elev == null) return window.dash_clientside.no_update;
        var fig = JSON.parse(JSON.stringify(figure));
        if (!fig.layout.shapes) return window.dash_clientside.no_update;
        for (var i = 0; i < fig.layout.shapes.length; i++) {
            var n = fig.layout.shapes[i].name || "";
            if (n.indexOf("measure-span-") === 0) {
                fig.layout.shapes[i].y0 = elev - 0.5;
                fig.layout.shapes[i].y1 = elev + 0.5;
                fig.layout.shapes[i].visible = true;
            }
        }
        return fig;
    }
    """,
    Output("cross-section-chart", "figure", allow_duplicate=True),
    Input("cross-section-chart", "clickData"),
    State("cross-section-chart", "figure"),
    prevent_initial_call=True,
)
