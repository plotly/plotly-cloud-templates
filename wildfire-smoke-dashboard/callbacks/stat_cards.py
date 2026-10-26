"""Stat-card callbacks — thin wrappers: memoised stats → view dict → outputs.

Patterns (Dash docs):
- Flexible signatures: output=dict(...) / inputs=dict(...) keep many outputs readable.
- Pattern-matching ALL outputs must follow layout order; `to_outputs` maps each
  slot by its id `key` via ctx.outputs_grouping instead of trusting list position.
- prevent_initial_call=True: stats_column() already seeds the layout with the
  same view builders, so nothing needs to run on page load.
"""

from dash import ALL, Input, Output, callback, ctx

from components.stat_cards import air_view, exposure_view
from utils.stats import air_stats, exposure_stats


def to_outputs(view: dict, grouping: dict) -> dict:
    """Shape a view dict to the callback's output grouping.

    Pattern-matching (ALL) outputs arrive as a list of {"id": {...}, "property": ...}
    in layout order; each is filled from `view[name][id["key"]]`. Scalar outputs
    are passed through unchanged.
    """
    return {
        name: [view[name][o["id"]["key"]] for o in spec] if isinstance(spec, list) else view[name]
        for name, spec in grouping.items()
    }


def _trend_outputs(prefix: str) -> dict:
    return {
        "trend_icon": Output({"type": f"{prefix}-icon", "key": ALL}, "icon"),
        "trend_icon_color": Output({"type": f"{prefix}-icon", "key": ALL}, "color"),
        "trend_text": Output({"type": f"{prefix}-value", "key": ALL}, "children"),
        "trend_text_color": Output({"type": f"{prefix}-value", "key": ALL}, "c"),
    }


@callback(
    output=dict(
        subtitle=Output("aq-subtitle", "children"),
        kpis=Output({"type": "aq-kpi", "key": ALL}, "children"),
        units=Output({"type": "aq-unit", "key": ALL}, "children"),
        peak_site=Output("aq-peak-site", "children"),
        levels=Output({"type": "aq-level", "key": ALL}, "children"),
        **_trend_outputs("aq-trend"),
        compare=Output("aq-compare", "children"),
        empty=Output("aq-empty", "display"),
    ),
    inputs=dict(
        selection=Input("selection", "data"),
        pollutant=Input("pollutant", "value"),
    ),
    prevent_initial_call=True,
)
def update_air_card(selection: dict, pollutant: str) -> dict:
    """Monitor KPIs for one day: reporting count, AQI>150 count, mean, peak, AQI mix, day-over-day."""
    view = air_view(air_stats(selection["season"], selection["day"], pollutant))
    return to_outputs(view, ctx.outputs_grouping)


@callback(
    output=dict(
        kpis=Output({"type": "ex-kpi", "key": ALL}, "children"),
        popmean_caption=Output("ex-popmean-caption", "children"),
        days_caption=Output("ex-days-caption", "children"),
        smoke_levels=Output({"type": "smoke-level", "key": ALL}, "children"),
        smoke_empty=Output("smoke-empty", "display"),
    ),
    inputs=dict(
        selection=Input("selection", "data"),
        pollutant=Input("pollutant", "value"),
    ),
    prevent_initial_call=True,
)
def update_exposure_card(selection: dict, pollutant: str) -> dict:
    """Population-weighted exposure, residents in AQI>100 / smoke-covered counties, Unhealthy+ days to date."""
    view = exposure_view(exposure_stats(selection["season"], selection["day"], pollutant))
    return to_outputs(view, ctx.outputs_grouping)
