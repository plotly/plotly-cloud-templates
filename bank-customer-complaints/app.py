"""
Bank Customer Complaints

Shows how Dash can be used for NLP based data analysis. The dataset contains
consumer complaints filed against US banks between 2015 and 2017.

Pick a bank (from the dropdown or by clicking a bar in the top 10 chart) to see
the words most used in its complaints, and the complaints grouped into topics by
an LDA model. Click a point in the topic map to read that complaint. The sample
size and time frame filters let you look at a subset of the data: for instance,
compare Equifax with and without 2017 (the year of its data breach), or notice
how often "Macy" shows up in complaints about Capital One.

The Bigrams view compares the most common two-word phrases between companies.

Originally written for Plotly by Vildly in 2019.
"""

from functools import lru_cache

import dash
import dash_mantine_components as dmc
from dash import Input, Output, State, ctx, dcc, html
from dash_iconify import DashIconify

import data
import figures
from theme import CATEGORICAL, FONT

THEME = {
    "fontFamily": FONT,
    "headings": {"fontFamily": FONT},
    "primaryColor": "blue",
    "defaultRadius": "md",
}
GRAPH_CONFIG = {"displayModeBar": False, "responsive": True}
DEFAULT_PERCENT = 20
ALL_MONTHS = [0, len(data.MONTHS) - 1]


def graph(graph_id):
    return html.Div(
        dcc.Loading(
            dcc.Graph(id=graph_id, config=GRAPH_CONFIG, style={"height": "100%"}),
            parent_style={"position": "absolute", "inset": 0},
            delay_show=300,
            overlay_style={"visibility": "visible", "opacity": 0.5},
        ),
        className="viz-body",
    )


def card(title, body, action=None, area=None, subtitle=None):
    header = dmc.Group(
        [
            dmc.Stack(
                [
                    dmc.Text(title, fw=600, size="sm"),
                    subtitle and dmc.Text(subtitle, size="xs", c="dimmed"),
                ],
                gap=0,
            ),
            action,
        ],
        justify="space-between",
        wrap="nowrap",
        gap="xs",
        mb="xs",
    )
    return dmc.Paper(
        [header, body],
        withBorder=True,
        p="sm",
        className="viz-card",
        style={"gridArea": area},
    )


def year_marks():
    return [
        {"value": i, "label": str(m.year)}
        for i, m in enumerate(data.MONTHS)
        if m.month == 1
    ]


header = dmc.AppShellHeader(
    dmc.Group(
        [
            dmc.Group(
                [
                    dmc.Burger(id="burger", size="sm", hiddenFrom="sm"),
                    dmc.ThemeIcon(
                        DashIconify(icon="tabler:message-report", width=22),
                        size="lg",
                        variant="light",
                        color="gray",
                        visibleFrom="sm",
                    ),
                    dmc.Stack(
                        [
                            dmc.Title("Bank Customer Complaints", order=4, className="app-title"),
                            dmc.Text(
                                "Natural language processing of US consumer complaints, 2015–2017",
                                size="xs",
                                c="dimmed",
                                visibleFrom="md",
                            ),
                        ],
                        gap=0,
                    ),
                ],
                gap="sm",
                wrap="nowrap",
                className="title-group",
            ),
            dmc.Group(
                [
                    dmc.SegmentedControl(
                        id="view",
                        data=[
                            {"value": "explorer", "label": "Explorer"},
                            {"value": "bigrams", "label": "Bigrams"},
                        ],
                        value="explorer",
                        size="sm",
                    ),
                    html.A(
                        html.Img(src="assets/dash-logo.png", height=32, alt="Dash"),
                        href="https://dash.plotly.com/",
                        className="dash-logo",
                    ),
                ],
                gap="md",
                wrap="nowrap",
            ),
        ],
        justify="space-between",
        h="100%",
        px="md",
        wrap="nowrap",
    )
)

navbar = dmc.AppShellNavbar(
    dmc.Stack(
        [
            dmc.Text("Filters", fw=600, size="sm"),
            dmc.Stack(
                [
                    dmc.Group(
                        [
                            dmc.Text("Sample size", size="sm", fw=500),
                            dmc.Text(id="percent-label", size="sm", c="dimmed"),
                        ],
                        justify="space-between",
                    ),
                    dmc.Slider(
                        id="percent",
                        min=1,
                        max=100,
                        value=DEFAULT_PERCENT,
                        marks=[{"value": v} for v in (25, 50, 75)],
                        label=None,
                        size="sm",
                        updatemode="mouseup",
                    ),
                    dmc.Text(
                        "Lower is faster, higher is more precise.",
                        size="xs",
                        c="dimmed",
                    ),
                ],
                gap=4,
            ),
            dmc.Select(
                id="bank",
                label="Bank",
                data=data.bank_options(),
                value=data.DEFAULT_BANK,
                searchable=True,
                allowDeselect=False,
                size="sm",
                comboboxProps={"width": 360, "position": "bottom-start"},
                description="Or click a bar in the top 10 chart.",
            ),
            dmc.Stack(
                [
                    dmc.Group(
                        [
                            dmc.Text("Time frame", size="sm", fw=500),
                            dmc.Text(id="months-label", size="xs", c="dimmed"),
                        ],
                        justify="space-between",
                    ),
                    dmc.RangeSlider(
                        id="months",
                        min=0,
                        max=len(data.MONTHS) - 1,
                        value=ALL_MONTHS,
                        minRange=0,
                        marks=year_marks(),
                        label=None,
                        size="sm",
                        updatemode="mouseup",
                    ),
                ],
                gap=4,
                mb="md",
            ),
            dmc.Divider(),
            dmc.Stack(
                [
                    dmc.Text("Complaints in selection", size="xs", c="dimmed"),
                    dmc.Text(id="complaint-count", className="hero-number"),
                    dmc.Text(id="complaint-count-bank", size="xs", c="dimmed"),
                ],
                gap=2,
            ),
            dmc.Text(
                [
                    "Source: ",
                    html.A(
                        "CFPB Consumer Complaint Database",
                        href="https://www.consumerfinance.gov/data-research/consumer-complaints/",
                        target="_blank",
                    ),
                    " (sample).",
                ],
                size="xs",
                c="dimmed",
                mt="auto",
                className="source",
            ),
        ],
        gap="lg",
        h="100%",
    ),
    p="md",
)

complaint_detail = dmc.Stack(
    id="complaint-detail", gap="xs", className="viz-body complaint-detail"
)

explorer = html.Div(
    [
        card(
            "Top 10 banks",
            graph("top-banks"),
            area="banks",
            subtitle="By number of complaints",
        ),
        card(
            "Most frequent words",
            graph("word-frequency"),
            area="words",
            subtitle="Top 15, excluding common words",
        ),
        card(
            "Top words",
            graph("word-cloud"),
            action=dmc.SegmentedControl(
                id="cloud-mode",
                data=[
                    {"value": "treemap", "label": "Treemap"},
                    {"value": "cloud", "label": "Word cloud"},
                ],
                value="treemap",
                size="xs",
            ),
            area="cloud",
        ),
        card(
            "Topics found by LDA",
            graph("lda-scatter"),
            area="topics",
            subtitle="Each point is a complaint. Click one to read it, click a legend entry to isolate a topic.",
        ),
        card("Complaint", complaint_detail, area="detail"),
    ],
    id="explorer-view",
    className="dashboard explorer-grid",
)


def company_select(select_id, value):
    return dmc.Select(
        id=select_id,
        data=data.BIGRAM_COMPANIES,
        value=value,
        allowDeselect=False,
        size="xs",
        w=240,
        comboboxProps={"width": 320},
    )


bigrams = html.Div(
    [
        card(
            "Bigram comparison",
            graph("bigram-comparison"),
            action=dmc.Group(
                [
                    company_select("company-1", "EQUIFAX, INC."),
                    dmc.Text("vs", size="xs", c="dimmed"),
                    company_select("company-2", "TRANSUNION INTERMEDIATE HOLDINGS, INC."),
                ],
                gap="xs",
                wrap="nowrap",
            ),
            subtitle="The 20 most frequent two-word phrases across both companies",
        ),
        card(
            "Bigram similarity",
            graph("bigram-scatter"),
            action=dmc.Group(
                [
                    dmc.Text("Perplexity", size="xs", c="dimmed", visibleFrom="lg"),
                    dmc.SegmentedControl(
                        id="perplexity",
                        data=[str(p) for p in data.PERPLEXITIES],
                        value=str(data.PERPLEXITIES[0]),
                        size="xs",
                    ),
                ],
                gap="xs",
                wrap="nowrap",
            ),
            subtitle="t-SNE of the top bigrams, sized by frequency",
        ),
    ],
    id="bigram-view",
    className="dashboard bigram-grid",
    style={"display": "none"},
)

app = dash.Dash(
    __name__,
    title="Bank Customer Complaints",
    external_stylesheets=[
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
    ],
)
server = app.server

app.layout = dmc.MantineProvider(
    dmc.AppShell(
        [header, navbar, dmc.AppShellMain([explorer, bigrams])],
        id="shell",
        header={"height": 60},
        navbar={
            "width": 290,
            "breakpoint": "sm",
            "collapsed": {"mobile": True, "desktop": False},
        },
        padding="md",
    ),
    theme=THEME,
    forceColorScheme="light",
)


@app.callback(
    Output("shell", "navbar"),
    Output("explorer-view", "style"),
    Output("bigram-view", "style"),
    Input("view", "value"),
    Input("burger", "opened"),
    State("shell", "navbar"),
)
def switch_view(view, burger_opened, navbar):
    """The filters only apply to the bank explorer, so hide them on the bigrams view."""
    explorer = view == "explorer"
    navbar["collapsed"] = {"mobile": not (explorer and burger_opened), "desktop": not explorer}
    hidden = {"display": "none"}
    return navbar, None if explorer else hidden, hidden if explorer else None


@app.callback(
    Output("percent-label", "children"),
    Output("months-label", "children"),
    Input("percent", "value"),
    Input("months", "value"),
)
def update_filter_labels(percent, months):
    return f"{percent}%", data.format_month_range(months)


@app.callback(
    Output("top-banks", "figure"),
    Output("complaint-count", "children"),
    Output("complaint-count-bank", "children"),
    Input("percent", "value"),
    Input("months", "value"),
    Input("bank", "value"),
)
def update_top_banks(percent, months, bank):
    df = data.filter_complaints(percent, months)
    bank_total = int((df["Company"] == bank).sum())
    return (
        figures.top_banks(df, bank),
        f"{len(df):,}",
        f"{bank_total:,} about {bank.title()}",
    )


@app.callback(
    Output("bank", "value"),
    Input("top-banks", "clickData"),
    prevent_initial_call=True,
)
def select_bank_from_chart(click):
    return click["points"][0]["customdata"]


@lru_cache(maxsize=16)
def word_counts(percent, months, bank):
    return figures.word_counts(data.filter_complaints(percent, months, bank), bank)


@app.callback(
    Output("word-frequency", "figure"),
    Output("word-cloud", "figure"),
    Input("percent", "value"),
    Input("months", "value"),
    Input("bank", "value"),
    Input("cloud-mode", "value"),
)
def update_words(percent, months, bank, mode):
    counts = word_counts(percent, tuple(months), bank)
    if not counts:
        message = "Not enough complaints, try widening the filters"
        return figures.empty(message), figures.empty(message)
    words_fig = figures.wordcloud(counts) if mode == "cloud" else figures.treemap(counts)
    return figures.word_frequency(counts), words_fig


@app.callback(
    Output("lda-scatter", "figure"),
    Output("complaint-detail", "children"),
    Input("bank", "value"),
    Input("months", "value"),
    Input("lda-scatter", "clickData"),
)
def update_topics(bank, months, click):
    docs, topic_words = data.lda_documents(bank, months)
    if docs is None or docs.empty:
        message = (
            "No topic model for this bank" if docs is None else "No complaints in this time frame"
        )
        return figures.empty(message), dmc.Text(message, size="sm", c="dimmed")

    selected = docs["Document_No"].iloc[0]
    if ctx.triggered_id == "lda-scatter" and click:
        clicked = click["points"][0].get("customdata")
        if clicked in set(docs["Document_No"]):
            selected = clicked

    doc = docs[docs["Document_No"] == selected].iloc[0]
    topic = int(doc["Dominant_Topic"])
    detail = [
        dmc.Group(
            [
                dmc.Text(
                    f"{doc['Date']:%b} {doc['Date'].day}, {doc['Date'].year}",
                    fw=600,
                    size="sm",
                ),
                dmc.Badge(
                    topic_words[topic],
                    color=CATEGORICAL[topic % len(CATEGORICAL)],
                    variant="dot",
                    size="sm",
                    tt="none",
                ),
                dmc.Text(
                    f"{doc['Topic_Perc_Contrib']:.0%} topic match", size="xs", c="dimmed"
                ),
            ],
            gap="xs",
        ),
        dmc.Group(
            [
                dmc.Badge(word.strip(), variant="default", size="xs", tt="none")
                for word in doc["Keywords"].split(",")
            ],
            gap=4,
        ),
        dmc.ScrollArea(
            dmc.Text(doc["Text"], size="sm", className="complaint-text"),
            type="auto",
            offsetScrollbars=True,
            className="viz-body",
        ),
    ]
    return figures.lda_scatter(docs, topic_words, selected), detail


@app.callback(
    Output("bigram-comparison", "figure"),
    Input("company-1", "value"),
    Input("company-2", "value"),
)
def update_bigram_comparison(first, second):
    if first == second:
        return figures.empty("Pick two different companies")
    return figures.bigram_comparison(first, second)


@app.callback(Output("bigram-scatter", "figure"), Input("perplexity", "value"))
def update_bigram_scatter(perplexity):
    return figures.bigram_scatter(data.BIGRAM_EMBEDDINGS[int(perplexity)])


if __name__ == "__main__":
    app.run(debug=True)
