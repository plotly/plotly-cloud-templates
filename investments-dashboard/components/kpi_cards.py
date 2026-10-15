import dash_mantine_components as dmc
from dash import html
from dash_iconify import DashIconify

def create_kpi_card(title, value, subtitle=None, trend=None, trend_positive=True, icon=None):
    """Create a KPI card with optional trend indicator"""
    
    trend_color = "teal" if trend_positive else "red"
    trend_icon = "tabler:trending-up" if trend_positive else "tabler:trending-down"
    
    content = [
        dmc.Group([
            dmc.Text(title, size="sm", c="dimmed", fw=500),
            DashIconify(icon=icon, width=20, color="gray") if icon else None,
        ], justify="space-between"),
        dmc.Group([
            dmc.Text(value, size="xl", fw=700),
            dmc.Group([
                DashIconify(icon=trend_icon, width=16, color=trend_color) if trend else None,
                dmc.Text(trend, size="sm", c=trend_color, fw=500) if trend else None,
            ], gap=4) if trend else None,
        ], justify="space-between", mt="xs"),
    ]
    
    if subtitle:
        content.append(dmc.Text(subtitle, size="xs", c="dimmed", mt=4))
    
    return dmc.Paper(
        dmc.Stack(content, gap="xs"),
        p="md",
        radius="md",
        withBorder=True,
        style={"minWidth": "200px"}
    )

def create_kpi_grid(metrics):
    """Create a grid of KPI cards from metrics dict"""
    
    cards = [
        create_kpi_card(
            title="Net Asset Value",
            value=f"${metrics['nav']:.2f}",
            trend=f"{metrics['ytd_return']:.1f}% YTD",
            trend_positive=metrics['ytd_return'] > 0,
            icon="tabler:currency-dollar"
        ),
        create_kpi_card(
            title="1 Year Return",
            value=f"{metrics['1y_return']:.2f}%",
            subtitle="vs S&P 500",
            trend_positive=True,
            icon="tabler:chart-line"
        ),
        create_kpi_card(
            title="Expense Ratio",
            value=metrics['expense_ratio'],
            subtitle="vs 0.99% category avg",
            trend="85% lower",
            trend_positive=True,
            icon="tabler:percentage"
        ),
        create_kpi_card(
            title="Category",
            value=metrics['category'],
            subtitle=metrics['asset_class'],
            icon="tabler:category"
        ),
    ]
    
    return dmc.SimpleGrid(
        cards,
        cols={"base": 1, "sm": 2, "lg": 4},
        spacing="md"
    )

def create_stat_card(label, value, description=None):
    """Simple stat card for fund facts"""
    return dmc.Paper(
        dmc.Stack([
            dmc.Text(label, size="xs", c="dimmed", tt="uppercase", fw=600),
            dmc.Text(value, size="lg", fw=600),
            dmc.Text(description, size="xs", c="dimmed") if description else None,
        ], gap=4),
        p="sm",
        radius="sm",
        withBorder=True,
    )
