"""Loading and filtering the complaint data.

The LDA topic models were fitted offline and saved to data/precomputed.json,
so the app only needs pandas, scikit-learn (for the bigram t-SNE) and wordcloud
at runtime.
"""

import io
import json
import re
from functools import lru_cache
from pathlib import Path

import pandas as pd
from sklearn.manifold import TSNE
from wordcloud import STOPWORDS

DATA_DIR = Path(__file__).parent / "data"

COMPLAINTS = pd.read_csv(
    DATA_DIR / "customer_complaints_narrative_sample.csv",
    usecols=["Date received", "Consumer complaint narrative", "Company"],
)
COMPLAINTS["Date received"] = pd.to_datetime(
    COMPLAINTS["Date received"], format="%m/%d/%Y"
)

with open(DATA_DIR / "precomputed.json") as f:
    _PRECOMPUTED_LDA = json.load(f)

BIGRAM_COUNTS = pd.read_csv(DATA_DIR / "bigram_counts_data.csv", index_col=0)
_BIGRAM_EMBED = pd.read_csv(DATA_DIR / "tsne_bigram_data.csv", index_col=0)
# Simple averages of GloVe 50d vectors, one row per bigram
_BIGRAM_VECTORS = pd.read_csv(DATA_DIR / "bigram_vectors.csv", index_col=0)

DEFAULT_BANK = "EQUIFAX, INC."
BIGRAM_COMPANIES = [c for c in BIGRAM_COUNTS["company"].unique() if c != "Total"]
PERPLEXITIES = [3, 4, 5, 6]

# Redacted names (XXXX) and words that appear in nearly every complaint
STOPWORDS = set(STOPWORDS) | {
    "XXXX",
    "XX",
    "xx",
    "xxxx",
    "n't",
    "Trans Union",
    "BOA",
    "Citi",
    "account",
    "please",
    "will",
    "s",
}

# The time slider works on whole months, indexed from the first month in the data
MONTHS = pd.period_range(
    COMPLAINTS["Date received"].min(), COMPLAINTS["Date received"].max(), freq="M"
)


def bank_options():
    """Banks with more than 10 complaints, largest first."""
    counts = COMPLAINTS["Company"].value_counts()
    return counts[counts > 10].index.tolist()


def month_range(month_values):
    """Turn a [start, end] pair of month indexes into an inclusive date range."""
    start, end = month_values or (0, len(MONTHS) - 1)
    return MONTHS[start].start_time, MONTHS[end].end_time


def format_month_range(month_values):
    start, end = month_values
    return f"{MONTHS[start].strftime('%b %Y')} – {MONTHS[end].strftime('%b %Y')}"


@lru_cache(maxsize=8)
def _sample(percent):
    """An evenly distributed, reproducible sample of the complaints."""
    return COMPLAINTS.sample(frac=percent / 100, random_state=1)


def filter_complaints(percent, month_values, bank=None):
    df = _sample(percent)
    start, end = month_range(month_values)
    df = df[df["Date received"].between(start, end)]
    if bank:
        df = df[df["Company"] == bank]
    return df


def stopwords_for(bank):
    """The default stopwords plus the words in the bank's own name."""
    return STOPWORDS | {w.lower() for w in re.findall(r"[\w']+", bank or "")}


@lru_cache(maxsize=32)
def _lda(bank):
    entry = _PRECOMPUTED_LDA[bank]
    docs = pd.read_json(io.StringIO(entry["df_dominant_topic"]))
    points = pd.read_json(io.StringIO(entry["tsne_df"]))
    topics = pd.read_json(io.StringIO(entry["df_top3words"]))
    docs = docs.join(points[["tsne_x", "tsne_y"]])
    docs["Date"] = pd.to_datetime(docs["Date"])
    topic_words = {
        row.topic_id: " · ".join(w.strip() for w in row.words.split(","))
        for row in topics.itertuples()
    }
    return docs, topic_words


def lda_documents(bank, month_values):
    """Precomputed LDA documents for a bank within the time frame, or None."""
    if bank not in _PRECOMPUTED_LDA:
        return None, {}
    docs, topic_words = _lda(bank)
    start, end = month_range(month_values)
    return docs[docs["Date"].between(start, end)], topic_words


def _embed(perplexity):
    coords = TSNE(
        n_components=2, perplexity=perplexity, init="pca", random_state=0
    ).fit_transform(_BIGRAM_VECTORS.to_numpy())
    return _BIGRAM_EMBED.assign(tsne_1=coords[:, 0], tsne_2=coords[:, 1])


# Only 20 bigrams, so every perplexity is computed once at startup
BIGRAM_EMBEDDINGS = {p: _embed(p) for p in PERPLEXITIES}
