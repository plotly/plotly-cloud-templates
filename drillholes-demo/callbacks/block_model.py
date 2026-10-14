from dash import callback, Input, Output, Patch, no_update


@callback(
    Output("bm-grid", "dashGridOptions"),
    Input("bm-quick-filter", "value"),
)
def update_quick_filter(search_value):
    patch = Patch()
    patch["quickFilterText"] = search_value or ""
    return patch


@callback(
    Output("bm-row-count", "children"),
    Input("bm-grid", "virtualRowData"),
)
def update_row_count(virtual_rows):
    if virtual_rows is None:
        return no_update
    return f"{len(virtual_rows):,} rows"


@callback(
    Output("bm-grid", "exportDataAsCsv"),
    Input("bm-export-btn", "n_clicks"),
    prevent_initial_call=True,
)
def export_csv(n_clicks):
    return True
