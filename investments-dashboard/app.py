import dash
from dash import html, dcc, Input, Output, callback
import dash_mantine_components as dmc
from dash_iconify import DashIconify

from pages import dashboard, performance, portfolio, fees
from callbacks import dashboard as dashboard_callbacks
from callbacks import performance as performance_callbacks
from callbacks import portfolio as portfolio_callbacks
from callbacks import fees as fees_callbacks
from callbacks import export_all as export_all_callbacks

app = dash.Dash(
    __name__,
    backend="fastapi",
    websocket_callbacks=True,
    suppress_callback_exceptions=True,
    external_stylesheets=dmc.styles.ALL,
    title="Investment Insights"
)
server = app.server

def create_nav_link(icon, label, href):
    return dmc.NavLink(
        label=label,
        leftSection=DashIconify(icon=icon, width=20),
        href=href,
        variant="subtle",
        active=True,
    )

def create_header():
    return dmc.Paper(
        dmc.Group([
            dmc.Group([
                dmc.Title("Investment Insights", order=3),
                dmc.Divider(orientation="vertical", size="sm"),
                html.Img(src="/assets/DE-logo.png", height=40),
            ], gap="sm", align="center", wrap="nowrap"),
            dmc.Group([
                dmc.Group([
                    DashIconify(icon="tabler:circle-filled", width=10, color="#40c057"),
                    dmc.Text("Market Open", size="xs", c="dimmed"),
                ], gap=4),
                dmc.Text("NYSE", size="xs", fw=500),
                dmc.Divider(orientation="vertical", size="sm"),
                dmc.Text("Last Updated", size="xs", c="dimmed"),
                dmc.Text("Apr 8, 2026 3:45 PM", size="xs", fw=500),
                dmc.Divider(orientation="vertical", size="sm"),
                dmc.Button(
                    "Download PDF",
                    id="generate-pdf-all-btn",
                    size="xs",
                    variant="light",
                    color="blue",
                    leftSection=DashIconify(icon="tabler:file-type-pdf", width=14),
                ),
                dmc.ActionIcon(
                    DashIconify(icon="tabler:bell", width=20),
                    variant="subtle",
                    size="lg",
                ),
            ], gap="sm", align="center", wrap="nowrap"),
        ], justify="space-between", align="center", wrap="nowrap"),
        p="md",
        withBorder=True,
        radius=0,
    )

def create_navbar():
    return dmc.Paper(
        dmc.Stack([
            dmc.Stack([
                dmc.Text("Navigation", size="xs", c="dimmed", fw=600, tt="uppercase", mb="xs"),
                dmc.NavLink(
                    label="Dashboard",
                    leftSection=DashIconify(icon="tabler:dashboard", width=20),
                    href="/",
                    id="nav-dashboard",
                ),
                dmc.NavLink(
                    label="Price Performance",
                    leftSection=DashIconify(icon="tabler:chart-line", width=20),
                    href="/performance",
                    id="nav-performance",
                ),
                dmc.NavLink(
                    label="Portfolio Analysis",
                    leftSection=DashIconify(icon="tabler:chart-donut", width=20),
                    href="/portfolio",
                    id="nav-portfolio",
                ),
                dmc.NavLink(
                    label="Fees & Distributions",
                    leftSection=DashIconify(icon="tabler:receipt", width=20),
                    href="/fees",
                    id="nav-fees",
                ),
                dmc.Divider(my="md"),
                dmc.Text("Fund Info", size="xs", c="dimmed", fw=600, tt="uppercase", mb="xs"),
                dmc.Stack([
                    dmc.Group([
                        dmc.Text("Fund:", size="sm", c="dimmed"),
                        dmc.Text("500 Index Fund", size="sm", fw=500),
                    ], justify="space-between"),
                    dmc.Group([
                        dmc.Text("Category:", size="sm", c="dimmed"),
                        dmc.Text("Large Blend", size="sm", fw=500),
                    ], justify="space-between"),
                    dmc.Group([
                        dmc.Text("Expense:", size="sm", c="dimmed"),
                        dmc.Badge("0.14%", color="green", size="sm"),
                    ], justify="space-between"),
                ], gap="xs"),
                dmc.Divider(my="md"),
                dmc.Text("Resources", size="xs", c="dimmed", fw=600, tt="uppercase", mb="xs"),
                dmc.Anchor(
                    dmc.NavLink(
                        label="Prospectus",
                        leftSection=DashIconify(icon="tabler:file-text", width=18),
                        rightSection=DashIconify(icon="tabler:external-link", width=14, color="gray"),
                        variant="subtle",
                        py=6,
                    ),
                    href="https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000036405&type=485&dateb=&owner=include&count=40",
                    target="_blank",
                    underline=False,
                ),
                dmc.Anchor(
                    dmc.NavLink(
                        label="Fact Sheet",
                        leftSection=DashIconify(icon="tabler:file-description", width=18),
                        rightSection=DashIconify(icon="tabler:external-link", width=14, color="gray"),
                        variant="subtle",
                        py=6,
                    ),
                    href="https://investor.vanguard.com/investment-products/mutual-funds/profile/vfiax",
                    target="_blank",
                    underline=False,
                ),
                dmc.Anchor(
                    dmc.NavLink(
                        label="Annual Report",
                        leftSection=DashIconify(icon="tabler:report", width=18),
                        rightSection=DashIconify(icon="tabler:external-link", width=14, color="gray"),
                        variant="subtle",
                        py=6,
                    ),
                    href="https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000036405&type=N-CSR&dateb=&owner=include&count=40",
                    target="_blank",
                    underline=False,
                ),
                dmc.Anchor(
                    dmc.NavLink(
                        label="Tax Documents",
                        leftSection=DashIconify(icon="tabler:file-invoice", width=18),
                        rightSection=DashIconify(icon="tabler:external-link", width=14, color="gray"),
                        variant="subtle",
                        py=6,
                    ),
                    href="https://investor.vanguard.com/client-benefits/tax-center",
                    target="_blank",
                    underline=False,
                ),
            ], gap=4, style={"flex": 1}),
        ], gap="md", justify="space-between", h="100%"),
        p="md",
        h="100%",
        withBorder=True,
        radius=0,
        style={"minWidth": "250px"}
    )

app.layout = dmc.MantineProvider(
    id="mantine-provider",
    forceColorScheme="light",
    children=[
        dcc.Location(id="url", refresh=False),
        dcc.Download(id="download-pdf-all"),
        html.Div(id="pdf-status-all", style={"display": "none"}),
        dmc.AppShell(
            [
                dmc.AppShellHeader(create_header()),
                dmc.AppShellNavbar(create_navbar()),
                dmc.AppShellMain(
                    dmc.Container(
                        id="page-content",
                        fluid=True,
                        p="md",
                    )
                ),
            ],
            header={"height": 73},
            navbar={"width": 280, "breakpoint": "sm", "collapsed": {"mobile": True}},
            padding="md",
        ),
    ]
)

@callback(
    Output("page-content", "children"),
    Input("url", "pathname")
)
def display_page(pathname):
    if pathname == "/performance":
        return performance.layout
    elif pathname == "/portfolio":
        return portfolio.layout
    elif pathname == "/fees":
        return fees.layout
    else:
        return dashboard.layout

@callback(
    [Output("nav-dashboard", "active"),
     Output("nav-performance", "active"),
     Output("nav-portfolio", "active"),
     Output("nav-fees", "active")],
    Input("url", "pathname")
)
def update_nav_active(pathname):
    return [
        pathname == "/" or pathname is None,
        pathname == "/performance",
        pathname == "/portfolio",
        pathname == "/fees",
    ]

if __name__ == "__main__":
    app.run(debug=True)
