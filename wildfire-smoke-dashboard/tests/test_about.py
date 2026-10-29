"""About the Data — article content, URL routing and page rendering."""

import pytest
from dash import html

from callbacks.routing import page_title, path_for, resolve_route
from components.about_tab import about_page
from config import ABOUT_IMAGE_DIR, IMAGE_LICENSES
from utils.content import article_by_slug, load_articles, next_article


def _text(component) -> str:
    """All string content in a component tree, joined."""
    if isinstance(component, str):
        return component
    if isinstance(component, (list, tuple)):
        return " ".join(_text(c) for c in component)
    children = getattr(component, "children", None)
    return _text(children) if children is not None else ""


def test_articles_load_with_credited_images():
    articles = load_articles()
    assert len(articles) >= 4
    for a in articles:
        assert (ABOUT_IMAGE_DIR / a.image.file).is_file()
        assert a.image.license in IMAGE_LICENSES
        assert a.image.credit and a.image.source_url.startswith("https://")
        assert a.image.license == "Public domain" or a.image.license_url.startswith("https://")


def test_placeholders_are_resolved():
    for a in load_articles():
        fields = [a.title, a.dek, a.kicker, *(b.text for b in a.body), *(f.value for f in a.facts)]
        assert not any("{" in f or "}" in f for f in fields), a.slug


def test_next_article_cycles_through_every_story():
    articles = load_articles()
    seen, slug = [], articles[0].slug
    for _ in articles:
        slug = next_article(slug).slug
        seen.append(slug)
    assert sorted(seen) == sorted(a.slug for a in articles)


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/", ("map", None)),
        (None, ("map", None)),
        ("/timeseries", ("timeseries", None)),
        ("/about", ("about", None)),
        ("/about/", ("about", None)),
        ("/about/smoke", ("about", "smoke")),
        ("/health", ("map", None)),  # retired tab
        ("/nowhere", ("map", None)),
    ],
)
def test_resolve_route(path, expected):
    assert resolve_route(path) == expected


@pytest.mark.parametrize("tab", ["map", "timeseries", "about"])
def test_path_for_round_trips(tab):
    assert resolve_route(path_for(tab)) == (tab, None)


def test_page_titles_name_the_article():
    smoke = article_by_slug("smoke")
    assert page_title("about", "smoke").startswith(smoke.title)
    assert page_title("about", "missing").startswith("About the Data")


def test_about_page_renders_index_article_and_fallback():
    index = about_page(None)
    assert all(a.title in _text(index) for a in load_articles())

    article = about_page("fires")
    assert isinstance(article, html.Article)
    assert article_by_slug("fires").body[0].text in _text(article)

    missing = about_page("not-a-story")
    assert "couldn't be found" in _text(missing)
