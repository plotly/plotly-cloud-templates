"""About the Data — an editorial index of data-source stories, and a page per story.

URLs: /about is the index and /about/<slug> an article. callbacks/routing.py renders
about_page(slug) into #about-content. Content comes from content/articles.json
(utils.content). Styling is the `.editorial` block in assets/styles.css: text sits on
the canvas with hairline rules, and there are no card boxes, badges or icon tiles.
"""

from dash import dcc, get_asset_url, get_relative_path, html

from utils.content import Article, Block, ImageInfo, article_by_slug, load_articles, next_article

MASTHEAD_TITLE = "Behind the numbers"
MASTHEAD_DEK = "Where this dashboard's data comes from, how it is processed, and what it can and cannot tell you."


def article_path(slug: str | None = None) -> str:
    return get_relative_path(f"/about/{slug}" if slug else "/about")


def _external(label: str, url: str) -> html.A:
    return html.A(label, href=url, target="_blank", rel="noopener noreferrer")


def credit_line(image: ImageInfo) -> list:
    """"Photo: <credit> · <license>", each linked to its source."""
    license_ = _external(image.license, image.license_url) if image.license_url else image.license
    return ["Photo: ", _external(image.credit, image.source_url), " · ", license_]


def _img(image: ImageInfo) -> html.Img:
    return html.Img(src=get_asset_url(f"about/{image.file}"), alt=image.alt, className="ed-img")


def figure(image: ImageInfo) -> html.Figure:
    return html.Figure(
        [
            html.Div(_img(image), className="ed-frame"),
            html.Figcaption([image.caption, " ", html.Span(credit_line(image), className="ed-credit")]),
        ],
        className="ed-figure",
    )


# ── Index ─────────────────────────────────────────────────────────────────────
def story(article: Article, size: str) -> dcc.Link:
    """A story teaser; `size` is "lead", "half" or "third" (see .ed-story-* rules)."""
    return dcc.Link(
        html.Article(
            [
                html.Div(_img(article.image), className="ed-frame"),
                html.Div(
                    [
                        html.P(article.kicker, className="ed-kicker"),
                        html.H2(article.title, className="ed-headline"),
                        html.P(article.dek, className="ed-dek"),
                    ],
                    className="ed-story-text",
                ),
            ],
            className=f"ed-story ed-story-{size}",
        ),
        href=article_path(article.slug),
        className="ed-story-link",
    )


def _photo_credits(articles: tuple[Article, ...]) -> html.Section:
    return html.Section(
        [
            html.H2("Photographs", className="ed-credits-title"),
            html.Ul([html.Li([html.Span(f"{a.title}.", className="ed-credits-story"), " ", *credit_line(a.image)]) for a in articles]),
        ],
        className="ed-credits",
    )


def article_index(note: str | None = None) -> html.Div:
    articles = load_articles()
    lead, *rest = articles
    return html.Div(
        [
            html.Header(
                [html.H1(MASTHEAD_TITLE, className="ed-masthead-title"), html.P(MASTHEAD_DEK, className="ed-masthead-dek")],
                className="ed-masthead",
            ),
            *([html.P(note, className="ed-note")] if note else []),
            story(lead, "lead"),
            html.Div([story(a, "half") for a in rest[:2]], className="ed-row ed-row-2"),
            html.Div([story(a, "third") for a in rest[2:]], className="ed-row ed-row-3"),
            _photo_credits(articles),
        ],
        className="editorial ed-index",
    )


# ── Article ───────────────────────────────────────────────────────────────────
def _block(block: Block):
    if block.type == "h":
        return html.H2(block.text, className="ed-subhead")
    if block.type == "quote":
        return html.Blockquote(block.text, className="ed-quote")
    return html.P(block.text)


def article_view(article: Article) -> html.Article:
    nxt = next_article(article.slug)
    facts = html.Section(
        [
            html.H2("At a glance", className="ed-facts-title"),
            html.Dl([el for f in article.facts for el in (html.Dt(f.label), html.Dd(f.value))]),
        ],
        className="ed-facts",
    )
    source = [html.P(["Source: ", _external(article.source.label, article.source.url)], className="ed-source")] if article.source else []
    return html.Article(
        [
            dcc.Link("← All articles", href=article_path(), className="ed-back"),
            html.Header(
                [
                    html.P(article.kicker, className="ed-kicker"),
                    html.H1(article.title, className="ed-title"),
                    html.P(article.dek, className="ed-dek ed-dek-lg"),
                ],
                className="ed-article-head",
            ),
            figure(article.image),
            html.Div([*(_block(b) for b in article.body), facts, *source], className="ed-body"),
            html.Footer(
                dcc.Link(
                    [html.Span("Next", className="ed-next-label"), html.Span(nxt.title, className="ed-next-title")],
                    href=article_path(nxt.slug),
                    className="ed-next",
                ),
                className="ed-article-foot",
            ),
        ],
        className="editorial ed-article",
    )


def about_page(slug: str | None) -> html.Div | html.Article:
    """Index for /about, the article for /about/<slug>; unknown slugs fall back to the index."""
    if slug is None:
        return article_index()
    article = article_by_slug(slug)
    if article is None:
        return article_index(note="That article couldn't be found, so here is the full list.")
    return article_view(article)
