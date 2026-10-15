from dash import Input, Output, callback
from pages.comparison import build_comparison_figure
from utils import load_data, GRADE_LABELS


@callback(
    Output("comparison-chart", "figure"),
    [Input("hole-checklist",  "value"),
     Input("grade-selector",  "value")],
)
def update_comparison(selected_holes, grade_col):
    holes = (selected_holes or [])[:10]
    return build_comparison_figure(holes, grade_col)


@callback(
    [Output("badge-hole-count",    "children"),
     Output("badge-total-meters",  "children"),
     Output("badge-grade",         "children")],
    [Input("hole-checklist", "value"),
     Input("grade-selector", "value")],
)
def update_comparison_badges(selected_holes, grade_col):
    holes = (selected_holes or [])[:10]
    collar, _, _, _ = load_data()
    total_m = int(collar.loc[collar["HOLEID"].isin(holes), "TOTDEPTH"].sum())
    return (
        f"Holes selected: {len(holes)}",
        f"Combined meters: {total_m:,} m",
        f"Grade: {GRADE_LABELS.get(grade_col, grade_col)}",
    )
