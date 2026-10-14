from dash import dcc, html
import dash_ag_grid as dag
import dash_mantine_components as dmc
from dash_iconify import DashIconify

from utils import load_data

COLUMN_DEFS = [
    {
        "field": "HOLEID",
        "headerName": "Hole ID",
        "pinned": "left",
        "lockPinned": True,
        "filter": "agTextColumnFilter",
        "minWidth": 110,
    },
    {"field": "FROM", "headerName": "From (m)", "filter": "agNumberColumnFilter", "minWidth": 110},
    {"field": "TO",   "headerName": "To (m)",   "filter": "agNumberColumnFilter", "minWidth": 110},
    {
        "field": "Au_ppm",
        "headerName": "Au (g/t)",
        "filter": "agNumberColumnFilter",
        "minWidth": 110,
        "cellStyle": {
            "styleConditions": [
                {"condition": "params.value >= 1.0",                          "style": {"backgroundColor": "#c6efce", "color": "#276221", "fontWeight": "600"}},
                {"condition": "params.value >= 0.3 && params.value < 1.0",   "style": {"backgroundColor": "#ffeb9c", "color": "#9c6500"}},
            ],
            "defaultStyle": {"backgroundColor": "white", "color": "#495057"},
        },
    },
    {
        "field": "Cu_pct",
        "headerName": "Cu (%)",
        "filter": "agNumberColumnFilter",
        "minWidth": 110,
        "cellStyle": {
            "styleConditions": [
                {"condition": "params.value >= 0.5",                          "style": {"backgroundColor": "#c6efce", "color": "#276221", "fontWeight": "600"}},
                {"condition": "params.value >= 0.2 && params.value < 0.5",   "style": {"backgroundColor": "#ffeb9c", "color": "#9c6500"}},
            ],
            "defaultStyle": {"backgroundColor": "white", "color": "#495057"},
        },
    },
    {
        "field": "Ag_ppm",
        "headerName": "Ag (ppm)",
        "filter": "agNumberColumnFilter",
        "minWidth": 110,
        "cellStyle": {
            "styleConditions": [
                {"condition": "params.value >= 5.0",                          "style": {"backgroundColor": "#c6efce", "color": "#276221", "fontWeight": "600"}},
                {"condition": "params.value >= 1.0 && params.value < 5.0",   "style": {"backgroundColor": "#ffeb9c", "color": "#9c6500"}},
            ],
            "defaultStyle": {"backgroundColor": "white", "color": "#495057"},
        },
    },
]


def layout():
    _, assay, _, _ = load_data()

    return dmc.Stack([
        dmc.Group([
            DashIconify(icon="tabler:cube", width=22, color="#868e96"),
            dmc.Title("Block Model", order=3, c="dark"),
        ], gap="sm"),

        dmc.Group([
            dcc.Input(
                id="bm-quick-filter",
                placeholder="Search all columns...",
                debounce=True,
                style={"width": 280, "padding": "6px 10px", "border": "1px solid #dee2e6", "borderRadius": 6, "fontSize": 13},
            ),
            dmc.Text(id="bm-row-count", size="sm", c="dimmed"),
            dmc.Button(
                "Export CSV",
                id="bm-export-btn",
                leftSection=DashIconify(icon="tabler:download", width=16),
                variant="light",
                color="gray",
                size="sm",
            ),
        ], gap="sm", align="center"),

        dag.AgGrid(
            id="bm-grid",
            columnDefs=COLUMN_DEFS,
            rowData=assay.to_dict("records"),
            columnSize="autoSize",
            dashGridOptions={
                "theme": "themeAlpine",
                "pagination": True,
                "paginationPageSize": 20,
                "paginationPageSizeSelector": [20, 50, 100],
            },
            defaultColDef={
                "filter": True,
                "floatingFilter": True,
                "sortable": True,
                "resizable": True,
                "minWidth": 100,
            },
            style={"height": "600px"},
        ),
    ], gap="md", p="md")
