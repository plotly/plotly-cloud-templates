"""Dash Cytoscape + Leaflet + Context Menu demo for designing a BT (low-voltage)
distribution network. UI chrome is built entirely with Dash Mantine Components.

Left panel   : search a transformer, toggle labels, pick a tree layout.
Center map   : the network overlaid on a real OpenStreetMap basemap (CyLeaflet),
               right-click a node/edge to edit the topology (context menu).
Right panel  : the same network as a clean dagre tree.
Bottom-left  : selection info (updates the chart as soon as a node/edge is clicked).
Bottom-right : time-series of the aggregated downstream load (kVA).
"""
import copy
import math
import time

import dash
import dash_cytoscape as cyto
import dash_mantine_components as dmc
import plotly.graph_objects as go
from dash import Input, Output, State, callback_context, dcc, no_update
from dash.exceptions import PreventUpdate

import data as netdata

cyto.load_extra_layouts()
dmc.add_figure_templates()

NETWORK = netdata.build_network()
PR_IDS = netdata.all_pr_ids(NETWORK)
LOAD_DF = netdata.build_load_curves(PR_IDS)

DEFAULT_TRANSFO = next(iter(NETWORK))

MAP_ID = "network-map"
MAP_CY_ID = {"id": MAP_ID, "component": "cyleaflet", "sub": "cy"}

CONTEXT_MENU_ITEMS = [
    {
        "id": "add-node",
        "label": "Add Node",
        "tooltipText": "Add a new node here",
        "availableOn": ["canvas"],
    },
    {
        "id": "remove-edge",
        "label": "Remove Edge",
        "tooltipText": "Remove this edge",
        "availableOn": ["edge"],
    },
    {
        "id": "revert-edge",
        "label": "Revert Edge",
        "tooltipText": "Reverse the direction of this edge",
        "availableOn": ["edge"],
    },
    {
        "id": "split-edge",
        "label": "Split Edge",
        "tooltipText": "Insert a node in the middle of this edge",
        "availableOn": ["edge"],
    },
    {
        "id": "link-nodes",
        "label": "Link to selected node",
        "tooltipText": "Draw an edge between the last selected node and this node",
        "availableOn": ["node"],
    },
]

CONVERSION_FACTOR = 20037508.34


def xy_to_lonlat(x, y):
    lon = x * 180.0 / CONVERSION_FACTOR
    lat = math.atan(math.exp(-y * math.pi / CONVERSION_FACTOR)) * 360.0 / math.pi - 90.0
    return lon, lat


def build_stylesheet(show_labels):
    label_style = {"label": "data(label)", "font-size": 8, "text-wrap": "wrap"} if show_labels else {"label": ""}
    return [
        {
            "selector": "node",
            "style": {
                **label_style,
                "text-valign": "top",
                "text-margin-y": -6,
            },
        },
        {
            "selector": 'node[kind = "transfo"]',
            "style": {
                "shape": "triangle",
                "background-color": "#e03131",
                "width": 22,
                "height": 22,
            },
        },
        {
            "selector": 'node[kind = "pole"]',
            "style": {
                "shape": "ellipse",
                "background-color": "#868e96",
                "width": 14,
                "height": 14,
            },
        },
        {
            "selector": 'node[kind = "pr"]',
            "style": {
                "shape": "rectangle",
                "background-color": "#ffffff",
                "border-color": "#495057",
                "border-width": 2,
                "width": 14,
                "height": 14,
            },
        },
        {
            "selector": "node:selected",
            "style": {"border-color": "#4263eb", "border-width": 3},
        },
        {
            "selector": 'node[kind = "boundary"]',
            "style": {"opacity": 0, "width": 1, "height": 1, "events": "no"},
        },
        {
            "selector": "edge",
            "style": {
                "width": 3,
                "line-color": "#f59f00",
                "target-arrow-color": "#f59f00",
                "target-arrow-shape": "triangle",
                "curve-style": "straight",
            },
        },
        {
            "selector": "edge:selected",
            "style": {"line-color": "#4263eb", "target-arrow-color": "#4263eb"},
        },
    ]


def elements_index(elements):
    nodes, edges = {}, {}
    for el in elements:
        d = el["data"]
        if "source" in d:
            edges[d["id"]] = el
        else:
            nodes[d["id"]] = el
    return nodes, edges


def downstream_pr_ids(elements, start_id):
    if not start_id:
        return []
    nodes, edges = elements_index(elements)
    adjacency = {}
    for e in edges.values():
        adjacency.setdefault(e["data"]["source"], []).append(e["data"]["target"])

    result, seen, stack = [], set(), [start_id]
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        node = nodes.get(cur)
        if node is not None:
            d = node["data"]
            if d.get("kind") == "pr" or d.get("also_pr"):
                result.append(cur)
        for nxt in adjacency.get(cur, []):
            stack.append(nxt)
    return sorted(set(result))


def apply_context_menu_action(menu_item_id, ctx, elements, last_node_id):
    """Return updated elements, or None if nothing changed."""
    elements = copy.deepcopy(elements)
    nodes, edges = elements_index(elements)

    if menu_item_id == "add-node":
        lon, lat = xy_to_lonlat(ctx["x"], ctx["y"])
        new_id = "N" + str(int(time.time() * 1000))[-8:]
        elements.append(
            {"data": {"id": new_id, "label": new_id, "kind": "pole", "lat": lat, "lon": lon}}
        )
        return elements

    if menu_item_id == "remove-edge":
        eid = ctx["elementId"]
        return [e for e in elements if e["data"]["id"] != eid]

    if menu_item_id == "revert-edge":
        eid = ctx["elementId"]
        for e in elements:
            if e["data"]["id"] == eid:
                e["data"]["source"], e["data"]["target"] = (
                    e["data"]["target"],
                    e["data"]["source"],
                )
        return elements

    if menu_item_id == "split-edge":
        eid, src, tgt = ctx["elementId"], ctx["edgeSource"], ctx["edgeTarget"]
        src_node, tgt_node = nodes.get(src), nodes.get(tgt)
        if src_node is None or tgt_node is None:
            return None
        mid_lat = (src_node["data"]["lat"] + tgt_node["data"]["lat"]) / 2
        mid_lon = (src_node["data"]["lon"] + tgt_node["data"]["lon"]) / 2
        new_id = "N" + str(int(time.time() * 1000))[-8:]
        elements = [e for e in elements if e["data"]["id"] != eid]
        elements.append(
            {"data": {"id": new_id, "label": new_id, "kind": "pole", "lat": mid_lat, "lon": mid_lon}}
        )
        elements.append(
            {"data": {"id": f"e-{src}-{new_id}", "source": src, "target": new_id, "kind": "conductor"}}
        )
        elements.append(
            {"data": {"id": f"e-{new_id}-{tgt}", "source": new_id, "target": tgt, "kind": "conductor"}}
        )
        return elements

    if menu_item_id == "connect-node-edge":
        src = ctx["edgeSource"]
        if not last_node_id or last_node_id not in nodes or last_node_id == src:
            return None
        new_edge_id = f"e-{last_node_id}-{src}-link"
        if new_edge_id in edges:
            return None
        elements.append(
            {"data": {"id": new_edge_id, "source": last_node_id, "target": src, "kind": "conductor"}}
        )
        return elements

    if menu_item_id == "link-nodes":
        tgt = ctx["elementId"]
        if not last_node_id or last_node_id not in nodes or last_node_id == tgt or tgt not in nodes:
            return None
        new_edge_id = f"e-{last_node_id}-{tgt}-link"
        if new_edge_id in edges:
            return None
        elements.append(
            {"data": {"id": new_edge_id, "source": last_node_id, "target": tgt, "kind": "conductor"}}
        )
        return elements

    return None


MAP_ZOOM_OUT_PAD = 0.6  # fraction of the network's own lat/lon span added as margin
MIN_PAD_DEG = 0.0008  # floor so a tiny/single-node network still gets some margin


def with_map_padding(elements):
    """Append two invisible nodes that widen the auto-fit bounding box, so the
    CyLeaflet map shows some margin around the network instead of a tight crop."""
    lats = [e["data"]["lat"] for e in elements if "source" not in e["data"] and "lat" in e["data"]]
    lons = [e["data"]["lon"] for e in elements if "source" not in e["data"] and "lon" in e["data"]]
    if not lats:
        return elements
    pad_lat = max((max(lats) - min(lats)) * MAP_ZOOM_OUT_PAD, MIN_PAD_DEG)
    pad_lon = max((max(lons) - min(lons)) * MAP_ZOOM_OUT_PAD, MIN_PAD_DEG)
    padding_nodes = [
        {
            "data": {
                "id": "__pad_nw",
                "kind": "boundary",
                "lat": max(lats) + pad_lat,
                "lon": min(lons) - pad_lon,
            }
        },
        {
            "data": {
                "id": "__pad_se",
                "kind": "boundary",
                "lat": min(lats) - pad_lat,
                "lon": max(lons) + pad_lon,
            }
        },
    ]
    return elements + padding_nodes


def make_cy_leaflet(elements, show_labels):
    return cyto.CyLeaflet(
        id=MAP_ID,
        cytoscape_props={
            "elements": with_map_padding(elements),
            "stylesheet": build_stylesheet(show_labels),
            "contextMenu": CONTEXT_MENU_ITEMS,
            "boxSelectionEnabled": False,
        },
        tiles=cyto.CyLeaflet.OSM,
        width="100%",
        height="100%",
    )


LAYOUT_OPTIONS = [
    {"label": "Dagre (tree)", "value": "dagre"},
    {"label": "Breadthfirst", "value": "breadthfirst"},
    {"label": "Cose (force)", "value": "cose"},
    {"label": "Circle", "value": "circle"},
]

PAPER_PROPS = dict(shadow="sm", radius="lg", withBorder=True)
PAPER_BG = {"backgroundColor": "white"}

app = dash.Dash(__name__)
app.title = "LV Network - Cytoscape / Leaflet"
server = app.server


def section_label(text):
    return dmc.Text(text, size="xs", fw=700, tt="uppercase", c="dimmed", lts="0.03em")


control_panel = dmc.Paper(
    **PAPER_PROPS,
    p="md",
    style={**PAPER_BG, "height": "100%", "flex": "0 0 300px", "overflowY": "auto"},
    children=dmc.Stack(
        gap="sm",
        children=[
            section_label("Control panel"),
            dmc.Select(
                id="transfo-search",
                data=[
                    {
                        "label": tid
                        if not netdata.TRANSFO_META[tid].get("note")
                        else f"{tid} -> {netdata.TRANSFO_META[tid]['note']}",
                        "value": tid,
                    }
                    for tid in NETWORK
                ],
                value=DEFAULT_TRANSFO,
                placeholder="Search transformer...",
                leftSection=dmc.Text("🔍", size="sm"),
                searchable=True,
                allowDeselect=False,
                radius="md",
            ),
            dmc.Divider(),
            dmc.Stack(
                gap=6,
                children=[
                    section_label("Selected transformer"),
                    dmc.Badge(
                        DEFAULT_TRANSFO,
                        id="selected-transfo-display",
                        variant="light",
                        color="indigo",
                        size="lg",
                        radius="sm",
                    ),
                ],
            ),
            dmc.Divider(),
            dmc.Switch(id="show-labels", label="Show node labels", checked=True, color="indigo"),
            dmc.Divider(),
            dmc.Stack(
                gap=6,
                children=[
                    section_label("Tree layout"),
                    dmc.Select(
                        id="layout-dropdown",
                        data=LAYOUT_OPTIONS,
                        value="dagre",
                        allowDeselect=False,
                        radius="md",
                    ),
                ],
            ),
            dmc.Paper(
                id="edit-edge-panel",
                withBorder=True,
                radius="md",
                p="sm",
                style={"display": "none", "backgroundColor": "#f8f9fc"},
                children=dmc.Stack(
                    gap="xs",
                    children=[
                        dmc.Text("Edit edge", fw=700, size="sm"),
                        dmc.NumberInput(id="edit-edge-length", label="Length (m)", min=0, radius="md"),
                        dmc.Select(
                            id="edit-edge-conductor",
                            label="Conductor type",
                            data=netdata.CONDUCTOR_TYPES,
                            radius="md",
                        ),
                        dmc.Group(
                            grow=True,
                            gap="xs",
                            children=[
                                dmc.Button("Apply", id="edit-edge-apply", n_clicks=0, color="indigo", size="xs"),
                                dmc.Button("Cancel", id="edit-edge-cancel", n_clicks=0, variant="default", size="xs"),
                            ],
                        ),
                    ],
                ),
            ),
        ],
    ),
)

map_panel = dmc.Paper(
    **PAPER_PROPS,
    style={**PAPER_BG, "height": "100%", "flex": "1 1 0%", "position": "relative", "overflow": "hidden"},
    children=[
        dmc.Box(id="map-container", style={"height": "100%", "width": "100%"}, children=[
            make_cy_leaflet(NETWORK[DEFAULT_TRANSFO], False)
        ]),
    ],
)

tree_panel = dmc.Paper(
    **PAPER_PROPS,
    style={**PAPER_BG, "height": "100%", "flex": "1 1 0%", "position": "relative", "overflow": "hidden"},
    children=[
        cyto.Cytoscape(
            id="tree-view",
            elements=NETWORK[DEFAULT_TRANSFO],
            layout={"name": "dagre"},
            stylesheet=build_stylesheet(False),
            style={"width": "100%", "height": "100%"},
        ),
    ],
)

info_panel = dmc.Paper(
    **PAPER_PROPS,
    p="md",
    style={**PAPER_BG, "height": "100%", "flex": "0 0 320px", "overflowY": "auto"},
    children=dmc.Stack(
        gap="sm",
        children=[
            section_label("Downstream load lookup"),
            dmc.Text(
                "Select a node or a conductor on the map or the tree view to see the "
                "downstream load.",
                size="sm",
                c="dimmed",
            ),
            dmc.Divider(),
            dmc.Group(
                justify="space-between",
                children=[
                    dmc.Text("Current selection", size="sm", fw=600),
                    dmc.Badge("-", id="current-selection", variant="light", color="gray"),
                ],
            ),
            dmc.Stack(
                gap=6,
                children=[
                    dmc.Text("Downstream connection points (PR)", size="sm", fw=600),
                    dmc.Group(id="downstream-pr-display", gap=6),
                ],
            ),
            dmc.Divider(),
            dmc.Stack(
                gap=0,
                children=[
                    dmc.Text("Peak load", size="xs", c="dimmed", tt="uppercase", fw=700),
                    dmc.Text("-", id="peak-display", fz=28, fw=800, c="indigo"),
                ],
            ),
        ],
    ),
)

chart_panel = dmc.Paper(
    **PAPER_PROPS,
    p="md",
    style={**PAPER_BG, "height": "100%", "flex": "1 1 0%"},
    children=dmc.Stack(
        gap="xs",
        style={"height": "100%"},
        children=[
            section_label("Downstream load (kVA)"),
            dcc.Graph(
                id="load-chart",
                style={"flex": "1 1 auto", "minHeight": 0},
                config={"displayModeBar": False},
            ),
        ],
    ),
)

app.layout = dmc.MantineProvider(
    theme={
        "primaryColor": "indigo",
        "defaultRadius": "md",
        "fontFamily": "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif",
    },
    children=dmc.Box(
        style={
            "height": "100vh",
            "backgroundColor": "#eef1f8",
            "display": "flex",
            "flexDirection": "column",
            "overflow": "hidden",
        },
        children=[
            dmc.Box(
                style={
                    "background": "linear-gradient(135deg, #1e1b4b 0%, #4338ca 100%)",
                    "padding": "12px 28px",
                    "flex": "0 0 auto",
                },
                children=dmc.Stack(
                    gap=0,
                    children=[
                        dmc.Title("LV Network Studio", order=3, c="white"),
                        dmc.Text(
                            "Cytoscape + Leaflet context-menu network editor",
                            size="xs",
                            c="indigo.1",
                        ),
                    ],
                ),
            ),
            dmc.Box(
                style={
                    "flex": "1 1 auto",
                    "display": "flex",
                    "flexDirection": "column",
                    "gap": "12px",
                    "padding": "12px 20px",
                    "minHeight": 0,
                },
                children=[
                    dmc.Box(
                        style={"flex": "3 1 0%", "display": "flex", "gap": "12px", "minHeight": 0},
                        children=[control_panel, map_panel, tree_panel],
                    ),
                    dmc.Box(
                        style={"flex": "2 1 0%", "display": "flex", "gap": "12px", "minHeight": 0},
                        children=[info_panel, chart_panel],
                    ),
                ],
            ),
            dcc.Store(id="network-elements", data=NETWORK[DEFAULT_TRANSFO]),
            dcc.Store(id="selected-transfo", data=DEFAULT_TRANSFO),
            dcc.Store(id="last-tapped-node", data=DEFAULT_TRANSFO),
            dcc.Store(id="current-selection-store", data={"id": DEFAULT_TRANSFO, "kind": "node"}),
            dcc.Store(id="downstream-pr-store", data=[]),
            dcc.Store(id="edit-edge-target"),
        ],
    ),
)


# ---------------------------------------------------------------------------
# Transformer search
# ---------------------------------------------------------------------------
@app.callback(
    Output("selected-transfo", "data"),
    Output("network-elements", "data", allow_duplicate=True),
    Output("selected-transfo-display", "children"),
    Output("current-selection-store", "data", allow_duplicate=True),
    Input("transfo-search", "value"),
    prevent_initial_call=True,
)
def pick_transfo(tid):
    if not tid or tid not in NETWORK:
        raise PreventUpdate
    return tid, NETWORK[tid], tid, {"id": tid, "kind": "node"}


# ---------------------------------------------------------------------------
# Render the map (CyLeaflet) and the tree view whenever the data changes
# ---------------------------------------------------------------------------
@app.callback(
    Output("map-container", "children"),
    Input("network-elements", "data"),
    Input("show-labels", "checked"),
)
def render_map(elements, show_labels):
    return make_cy_leaflet(elements or [], bool(show_labels))


@app.callback(
    Output("tree-view", "elements"),
    Output("tree-view", "stylesheet"),
    Output("tree-view", "layout"),
    Input("network-elements", "data"),
    Input("show-labels", "checked"),
    Input("layout-dropdown", "value"),
)
def render_tree(elements, show_labels, layout_name):
    layout = {"name": layout_name or "dagre", "animate": True}
    if layout_name == "dagre":
        layout["rankDir"] = "TB"
    return elements or [], build_stylesheet(bool(show_labels)), layout


# ---------------------------------------------------------------------------
# Context menu (add/remove/revert/edit/split/connect/link)
# ---------------------------------------------------------------------------
@app.callback(
    Output("network-elements", "data", allow_duplicate=True),
    Output("edit-edge-panel", "style"),
    Output("edit-edge-target", "data"),
    Output("edit-edge-length", "value"),
    Output("edit-edge-conductor", "value"),
    Input(MAP_CY_ID, "contextMenuData"),
    State("network-elements", "data"),
    State("last-tapped-node", "data"),
    prevent_initial_call=True,
)
def handle_context_menu(ctx, elements, last_node_id):
    if not ctx:
        raise PreventUpdate

    if ctx["menuItemId"] == "edit-edge":
        nodes, edges = elements_index(elements or [])
        edge = edges.get(ctx["elementId"])
        length = edge["data"].get("length_m") if edge else None
        conductor = edge["data"].get("conductor_type") if edge else None
        return no_update, {"display": "block", "backgroundColor": "#f8f9fc"}, ctx["elementId"], length, conductor

    new_elements = apply_context_menu_action(ctx["menuItemId"], ctx, elements or [], last_node_id)
    if new_elements is None:
        raise PreventUpdate
    return new_elements, {"display": "none"}, None, no_update, no_update


@app.callback(
    Output("network-elements", "data", allow_duplicate=True),
    Output("edit-edge-panel", "style", allow_duplicate=True),
    Input("edit-edge-apply", "n_clicks"),
    State("edit-edge-target", "data"),
    State("edit-edge-length", "value"),
    State("edit-edge-conductor", "value"),
    State("network-elements", "data"),
    prevent_initial_call=True,
)
def apply_edit_edge(n_clicks, edge_id, length, conductor, elements):
    if not n_clicks or not edge_id:
        raise PreventUpdate
    elements = copy.deepcopy(elements)
    for e in elements:
        if e["data"].get("id") == edge_id:
            if length is not None:
                e["data"]["length_m"] = length
            if conductor is not None:
                e["data"]["conductor_type"] = conductor
    return elements, {"display": "none"}


@app.callback(
    Output("edit-edge-panel", "style", allow_duplicate=True),
    Input("edit-edge-cancel", "n_clicks"),
    prevent_initial_call=True,
)
def cancel_edit_edge(n_clicks):
    if not n_clicks:
        raise PreventUpdate
    return {"display": "none"}


# ---------------------------------------------------------------------------
# Selection tracking (map + tree) -> downstream PR computation
# ---------------------------------------------------------------------------
@app.callback(
    Output("last-tapped-node", "data"),
    Output("current-selection-store", "data", allow_duplicate=True),
    Input(MAP_CY_ID, "tapNodeData"),
    Input(MAP_CY_ID, "tapEdgeData"),
    Input("tree-view", "tapNodeData"),
    Input("tree-view", "tapEdgeData"),
    prevent_initial_call=True,
)
def track_selection(map_node, map_edge, tree_node, tree_edge):
    # prop_id looks like "tree-view.tapNodeData" or '{"component":...}.tapEdgeData'
    prop_id = callback_context.triggered[0]["prop_id"]
    _, _, prop_name = prop_id.rpartition(".")

    if prop_id.startswith("tree-view."):
        data = tree_node if prop_name == "tapNodeData" else tree_edge
        kind = "node" if prop_name == "tapNodeData" else "edge"
    else:
        data = map_node if prop_name == "tapNodeData" else map_edge
        kind = "node" if prop_name == "tapNodeData" else "edge"

    if not data:
        raise PreventUpdate

    selection = {"id": data.get("id"), "kind": kind}
    last_node = data.get("id") if kind == "node" else no_update
    return last_node, selection


EMPTY_FIGURE = go.Figure(go.Scatter(x=[], y=[], mode="lines"))
EMPTY_FIGURE.update_layout(
    margin={"l": 50, "r": 20, "t": 10, "b": 30},
    yaxis_title="Load (kVA)",
    template="mantine_light",
)


def make_chart(series):
    fig = go.Figure(
        go.Scatter(x=series.index, y=series.values, mode="lines", line={"width": 1, "color": "#4263eb"})
    )
    fig.update_layout(
        margin={"l": 50, "r": 20, "t": 10, "b": 30},
        yaxis_title="Load (kVA)",
        template="mantine_light",
    )
    return fig


@app.callback(
    Output("current-selection", "children"),
    Output("current-selection", "color"),
    Output("downstream-pr-display", "children"),
    Output("downstream-pr-store", "data"),
    Output("load-chart", "figure"),
    Output("peak-display", "children"),
    Input("current-selection-store", "data"),
    State("network-elements", "data"),
)
def update_selection_display(selection, elements):
    empty_pr = [dmc.Text("-", size="sm", c="dimmed")]
    if not selection:
        return "-", "gray", empty_pr, [], EMPTY_FIGURE, "-"
    start_id = selection["id"]
    if selection["kind"] == "edge":
        nodes, edges = elements_index(elements or [])
        edge = edges.get(start_id)
        start_id = edge["data"]["target"] if edge else None
    pr_ids = downstream_pr_ids(elements or [], start_id)
    label = selection["id"]
    badge_color = "blue" if selection["kind"] == "node" else "orange"
    pr_badges = (
        [dmc.Badge(pr, variant="dot", color="gray", size="sm") for pr in pr_ids]
        if pr_ids
        else [dmc.Text("-", size="sm", c="dimmed")]
    )

    cols = [c for c in pr_ids if c in LOAD_DF.columns]
    if not cols:
        return label, badge_color, pr_badges, pr_ids, EMPTY_FIGURE, "-"

    series = LOAD_DF[cols].sum(axis=1)
    peak = series.max()
    fig = make_chart(series)
    return label, badge_color, pr_badges, pr_ids, fig, f"{peak:.1f} kVA"


if __name__ == "__main__":
    app.run(debug=True, port=8080)
