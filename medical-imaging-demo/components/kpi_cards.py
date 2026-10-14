import dash_mantine_components as dmc
from dash_iconify import DashIconify


def create_kpi_card(id_prefix, title, value, trend=None,
                    trend_positive=True, subtitle=None, icon=None,
                    alert_color=None):
    """Clinical KPI card, optionally coloured for alert state."""
    trend_color = "teal" if trend_positive else "red"
    border_color = {"red": "#ef4444", "yellow": "#f59e0b", "green": "#22c55e"}.get(alert_color)
    style = {"minWidth": "200px"}
    if border_color:
        style["borderLeft"] = f"4px solid {border_color}"

    return dmc.Paper(
        dmc.Stack([
            dmc.Group([
                dmc.Text(title, size="sm", c="dimmed", fw=500, id=f"{id_prefix}-title"),
                DashIconify(icon=icon, width=20, color="gray") if icon else None,
            ], justify="space-between"),
            dmc.Group([
                dmc.Text(value, size="xl", fw=700, id=f"{id_prefix}-value"),
                dmc.Text(
                    trend or "",
                    size="sm",
                    c=trend_color,
                    fw=500,
                    id=f"{id_prefix}-trend",
                    style={"display": "block" if trend else "none"},
                ),
            ], justify="space-between", mt="xs"),
            dmc.Text(subtitle, size="xs", c="dimmed", mt=4,
                     id=f"{id_prefix}-subtitle") if subtitle else None,
        ], gap="xs"),
        p="md",
        radius="md",
        withBorder=True,
        style=style,
    )


def create_stat_card(label, value, description=None, value_color=None):
    return dmc.Paper(
        dmc.Stack([
            dmc.Text(label, size="xs", c="dimmed", tt="uppercase", fw=600),
            dmc.Text(value, size="lg", fw=600, c=value_color or "default"),
            dmc.Text(description, size="xs", c="dimmed") if description else None,
        ], gap=4),
        p="sm",
        radius="sm",
        withBorder=True,
    )


def create_risk_row(id_prefix, label, value, progress_value, color):
    return dmc.Group([
        dmc.Text(label, size="sm", w=120),
        dmc.Progress(value=progress_value, color=color, size="lg",
                     style={"flex": 1}, id=f"{id_prefix}-bar"),
        dmc.Text(value, size="sm", fw=500, w=55, id=f"{id_prefix}-value"),
    ], gap="sm")
