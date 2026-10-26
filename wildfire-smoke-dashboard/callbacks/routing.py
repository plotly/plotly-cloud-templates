"""URL routing — shareable paths for every tab and About article.

    /                    Map View
    /timeseries          Time Series
    /about               About the Data index
    /about/<slug>        About article

`route` is the single owner of url.pathname ↔ main-tabs.value (a circular dependency
inside one callback is allowed). dcc.Location uses refresh="callback-nav", so
navigation never reloads the page and Back/Forward work. Unknown paths, including the
retired /health, fall back to the map.
"""

from dash import Input, Output, callback, clientside_callback, ctx, get_relative_path, no_update, strip_relative_path

from components.about_tab import about_page, article_path
from config import APP_TITLE
from utils.content import article_by_slug

TAB_SEGMENTS = {"map": "", "timeseries": "timeseries", "about": "about"}


def resolve_route(pathname: str | None) -> tuple[str, str | None]:
    """URL path → (tab, article slug or None)."""
    path = strip_relative_path(pathname or "/") or ""
    parts = [p for p in path.split("/") if p]
    if not parts or parts[0] == "map":
        return "map", None
    if parts[0] == "timeseries":
        return "timeseries", None
    if parts[0] == "about":
        return "about", parts[1] if len(parts) > 1 else None
    return "map", None


def path_for(tab: str, slug: str | None = None) -> str:
    if tab == "about":
        return article_path(slug)
    return get_relative_path(f"/{TAB_SEGMENTS[tab]}")


def page_title(tab: str, slug: str | None = None) -> str:
    if tab == "timeseries":
        return f"Time Series · {APP_TITLE}"
    if tab == "about":
        article = article_by_slug(slug)
        return f"{article.title} · About the Data · {APP_TITLE}" if article else f"About the Data · {APP_TITLE}"
    return APP_TITLE


@callback(
    output=dict(
        pathname=Output("url", "pathname"),
        tab=Output("main-tabs", "value"),
        about=Output("about-content", "children"),
        title=Output("page-title", "data"),
    ),
    inputs=dict(
        pathname=Input("url", "pathname"),
        tab=Input("main-tabs", "value"),
    ),
)
def route(pathname: str, tab: str) -> dict:
    """Keep the URL and the active tab in sync and render the About page for the URL."""
    url_tab, slug = resolve_route(pathname)

    if ctx.triggered_id == "main-tabs":
        # Tab click → push that tab's path. Clicking About from an article returns to the index.
        target = path_for(tab)
        return {
            "pathname": target if target != pathname else no_update,
            "tab": no_update,
            "about": about_page(None) if tab == "about" and slug else no_update,
            "title": page_title(tab),
        }

    # Initial load, link click, or Back/Forward → follow the URL.
    return {
        "pathname": no_update,
        "tab": url_tab if url_tab != tab else no_update,
        "about": about_page(slug) if url_tab == "about" else no_update,
        "title": page_title(url_tab, slug),
    }


# Browser-only side effects on navigation: tab title + scroll to top.
clientside_callback(
    """
    function (title) {
        if (title) { document.title = title; }
        window.scrollTo({ top: 0 });
        return window.dash_clientside.no_update;
    }
    """,
    Output("page-title", "id"),
    Input("page-title", "data"),
)
