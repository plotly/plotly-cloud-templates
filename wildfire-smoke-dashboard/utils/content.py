"""About the Data articles — loaded from content/articles.json and validated once.

Text fields may use placeholders filled from the data snapshot, so prose never goes
stale when the data is refreshed: {monitors}, {counties}, {seasons}, {health_last_year},
{smoke_cover}, and per season {window_<key>} / {note_<key>} (keys from config.SEASONS).
Validation runs at first load: a broken article stops the app at startup, not in a callback.
"""

import json
from dataclasses import dataclass
from datetime import date
from functools import lru_cache

from config import ABOUT_IMAGE_DIR, ARTICLES_JSON, IMAGE_LICENSES, SEASONS, SMOKE_COVER_FRAC
from utils.data import AQ, COUNTY_FIPS, HEALTH_LAST_YEAR

BLOCK_TYPES = {"p", "h", "quote"}


@dataclass(frozen=True)
class ImageInfo:
    file: str
    alt: str
    caption: str
    credit: str
    license: str
    license_url: str
    source_url: str


@dataclass(frozen=True)
class Block:
    type: str  # "p" paragraph, "h" subhead, "quote" pull quote
    text: str


@dataclass(frozen=True)
class Fact:
    label: str
    value: str


@dataclass(frozen=True)
class Source:
    label: str
    url: str


@dataclass(frozen=True)
class Article:
    slug: str
    kicker: str
    title: str
    dek: str
    image: ImageInfo
    body: tuple[Block, ...]
    facts: tuple[Fact, ...]
    source: Source | None


class ContentError(ValueError):
    """Raised when content/articles.json is inconsistent."""


def _window(start: str, end: str) -> str:
    """"2020-08-01", "2020-10-31" → "Aug 1 – Oct 31, 2020"."""
    a, b = date.fromisoformat(start), date.fromisoformat(end)
    return f"{a:%b} {a.day} – {b:%b} {b.day}, {b.year}"


def placeholders() -> dict[str, str]:
    values = {
        "monitors": f"{AQ['site_id'].nunique():,}",
        "counties": str(len(COUNTY_FIPS)),
        "seasons": {1: "one", 2: "two", 3: "three", 4: "four"}.get(len(SEASONS), str(len(SEASONS))),
        "health_last_year": str(HEALTH_LAST_YEAR),
        "smoke_cover": f"{SMOKE_COVER_FRAC:.0%}",
    }
    for key, meta in SEASONS.items():
        values[f"window_{key}"] = _window(meta["start"], meta["end"])
        values[f"note_{key}"] = meta["note"]
    return values


def _fill(text: str, values: dict[str, str], slug: str) -> str:
    try:
        return text.format_map(values)
    except (KeyError, ValueError) as exc:
        raise ContentError(f"{slug}: bad placeholder in {text[:60]!r}: {exc}") from exc


def _parse(entry: dict, values: dict[str, str]) -> Article:
    slug = entry["slug"]
    fill = lambda text: _fill(text, values, slug)  # noqa: E731
    source = entry.get("source")
    return Article(
        slug=slug,
        kicker=fill(entry["kicker"]),
        title=fill(entry["title"]),
        dek=fill(entry["dek"]),
        image=ImageInfo(**{k: fill(v) for k, v in entry["image"].items()}),
        body=tuple(Block(b["type"], fill(b["text"])) for b in entry["body"]),
        facts=tuple(Fact(fill(f["label"]), fill(f["value"])) for f in entry["facts"]),
        source=Source(source["label"], source["url"]) if source else None,
    )


def _validate(articles: tuple[Article, ...]) -> None:
    slugs = [a.slug for a in articles]
    if len(set(slugs)) != len(slugs):
        raise ContentError(f"duplicate slugs: {slugs}")
    for a in articles:
        img = a.image
        if not (ABOUT_IMAGE_DIR / img.file).is_file():
            raise ContentError(f"{a.slug}: missing image assets/about/{img.file}")
        if img.license not in IMAGE_LICENSES:
            raise ContentError(f"{a.slug}: license {img.license!r} not in {sorted(IMAGE_LICENSES)}")
        if not (img.alt and img.caption and img.credit and img.source_url):
            raise ContentError(f"{a.slug}: image needs alt, caption, credit and source_url")
        if img.license != "Public domain" and not img.license_url:
            raise ContentError(f"{a.slug}: {img.license} image needs a license_url")
        bad = {b.type for b in a.body} - BLOCK_TYPES
        if bad:
            raise ContentError(f"{a.slug}: unknown body block types {sorted(bad)}")


@lru_cache(maxsize=1)
def load_articles() -> tuple[Article, ...]:
    """All articles in display order (the first is the lead story)."""
    with open(ARTICLES_JSON, encoding="utf-8") as fh:
        entries = json.load(fh)
    values = placeholders()
    articles = tuple(_parse(e, values) for e in entries)
    _validate(articles)
    return articles


def article_by_slug(slug: str | None) -> Article | None:
    return next((a for a in load_articles() if a.slug == slug), None)


def next_article(slug: str) -> Article:
    """The story after `slug`, wrapping around to the lead."""
    articles = load_articles()
    i = [a.slug for a in articles].index(slug)
    return articles[(i + 1) % len(articles)]
