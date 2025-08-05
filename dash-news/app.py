import math
from datetime import datetime

import dash
from dash import Input, Output, State, dcc, html
from newsapi import NewsApiClient

app = dash.Dash(__name__, external_stylesheets=["./custom.css"])
newsapi = NewsApiClient(api_key="9902e19f61b54149854b2955e060312c")

CATEGORIES = [
    {"label": "General", "value": "general"},
    {"label": "Business", "value": "business"},
    {"label": "Technology", "value": "technology"},
    {"label": "Sports", "value": "sports"},
    {"label": "Entertainment", "value": "entertainment"},
    {"label": "Health", "value": "health"},
    {"label": "Science", "value": "science"},
]


def format_date(date_string):
    try:
        date_obj = datetime.fromisoformat(date_string.replace("Z", "+00:00"))
        return date_obj.strftime("%B %d, %Y at %I:%M %p")
    except:
        return date_string


def create_news_card(article):
    image_url = (
        article.get("urlToImage")
        or "https://via.placeholder.com/300x200/667eea/ffffff?text=No+Image"
    )
    title = article.get("title", "No Title")
    source = article.get("source", {}).get("name", "Unknown Source")
    author = article.get("author", "Unknown Author")
    published_at = article.get("publishedAt", "")
    description = article.get("description", "No description available")
    formatted_date = format_date(published_at) if published_at else "Date not available"

    return html.A(
        [
            html.Div(
                [
                    html.Img(src=image_url, className="news-image"),
                    html.Div(
                        [
                            html.H3(title, className="news-title"),
                            html.Div(
                                [html.P(description, className="news-description")],
                                className="news-description-container",
                            ),
                            html.Div(
                                [
                                    html.Span(author, className="news-author"),
                                    html.Span(formatted_date, className="news-date"),
                                ],
                                className="news-meta",
                            ),
                            html.P(source, className="news-source"),
                        ],
                        className="news-content",
                    ),
                ],
                className="news-card",
            )
        ],
        href=article.get("url", "#"),
        target="_blank",
        className="news-link",
    )


def process_news_data(news_articles, current_page, articles_per_page=15):
    if news_articles["status"] == "ok" and news_articles["articles"]:
        total_articles = len(news_articles["articles"])
        start_idx = (current_page - 1) * articles_per_page
        end_idx = start_idx + articles_per_page
        page_articles = news_articles["articles"][start_idx:end_idx]
        news_cards = [create_news_card(article) for article in page_articles]
        total_pages = math.ceil(total_articles / articles_per_page)
        page_info = f"Page {current_page} of {total_pages} ({total_articles} articles)"
        return news_cards, current_page, total_articles, page_info
    else:
        error_card = html.Div(
            [html.H3("No articles found for this category", className="error-message")],
            className="error-container",
        )
        return [error_card], current_page, 0, "No articles found"


server = app.server

app.layout = html.Div(
    [
        html.Div(
            [
                html.Div(
                    [
                        html.H1("Dash News Network", className="header-title"),
                        html.Span("Source: newsapi.org", className="source-label"),
                    ],
                    className="title-section",
                ),
                html.Div(
                    [
                        html.Label("Select Category:", className="dropdown-label"),
                        dcc.Dropdown(
                            id="category-dropdown",
                            options=CATEGORIES,
                            value="general",
                            className="category-dropdown",
                            clearable=False,
                        ),
                    ],
                    className="dropdown-container",
                ),
            ],
            className="header",
        ),
        html.Div(
            [
                html.Div(id="news-content", className="news-grid"),
                html.Div(
                    [
                        html.Button(
                            "Previous", id="prev-button", className="pagination-btn"
                        ),
                        html.Span(id="page-info", className="page-info"),
                        html.Button(
                            "Next", id="next-button", className="pagination-btn"
                        ),
                    ],
                    className="pagination-container",
                ),
            ],
            className="content-wrapper",
        ),
        dcc.Store(id="current-page", data=1),
        dcc.Store(id="total-articles", data=0),
    ],
    className="app-container",
)


@app.callback(
    Output("news-content", "children"),
    Output("current-page", "data"),
    Output("total-articles", "data"),
    Output("page-info", "children"),
    Input("category-dropdown", "value"),
    Input("prev-button", "n_clicks"),
    Input("next-button", "n_clicks"),
    State("current-page", "data"),
    State("total-articles", "data"),
)
def update_news_content(
    selected_category, prev_clicks, next_clicks, current_page, total_articles
):
    ctx = dash.callback_context
    if not ctx.triggered:
        button_id = None
    else:
        button_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if button_id == "prev-button" and current_page > 1:
        current_page = current_page - 1
    elif button_id == "next-button":
        current_page = current_page + 1
    elif button_id == "category-dropdown":
        current_page = 1

    try:
        news_articles = newsapi.get_everything(
            q=selected_category, language="en", sort_by="popularity", page_size=100
        )
        return process_news_data(news_articles, current_page)
    except Exception as e:
        error_card = html.Div(
            [html.H3(f"Error loading news: {str(e)}", className="error-message")],
            className="error-container",
        )
        return [error_card], current_page, 0, "Error loading articles"


@app.callback(
    [Output("prev-button", "disabled"), Output("next-button", "disabled")],
    [Input("current-page", "data"), Input("total-articles", "data")],
)
def update_pagination_buttons(current_page, total_articles):
    articles_per_page = 15
    total_pages = math.ceil(total_articles / articles_per_page)
    prev_disabled = current_page <= 1
    next_disabled = current_page >= total_pages
    return prev_disabled, next_disabled


if __name__ == "__main__":
    app.run(debug=True)
