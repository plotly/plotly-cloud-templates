"""Plotly figures for the dashboard."""

import plotly.graph_objects as go
from wordcloud import WordCloud

from data import BIGRAM_COUNTS, stopwords_for
from theme import (
    ACCENT,
    BASE_LAYOUT,
    BLUE_RAMP,
    CATEGORICAL,
    GRID,
    MUTED,
    NEUTRAL,
    TEXT,
    TOPIC_SYMBOLS,
)

TOP_WORDS = 25
FREQUENCY_WORDS = 15
# Canvas the word cloud is laid out on; roughly the size of its card
CLOUD_WIDTH, CLOUD_HEIGHT = 640, 300


def _layout(**kwargs):
    fig = go.Figure(layout=BASE_LAYOUT)
    fig.update_layout(**kwargs)
    return fig


def _short(name, width=26):
    name = name.title()
    return name if len(name) <= width else name[: width - 1].rstrip(" ,.") + "…"


def empty(message):
    fig = _layout(xaxis_visible=False, yaxis_visible=False)
    fig.add_annotation(
        text=message, showarrow=False, font=dict(color=MUTED, size=13)
    )
    return fig


def top_banks(df, selected_bank, n=10):
    counts = df["Company"].value_counts().head(n).iloc[::-1]
    if counts.empty:
        return empty("No complaints in this selection")
    fig = _layout(
        xaxis=dict(gridcolor=GRID, zeroline=False, tickformat=","),
        yaxis=dict(ticks="", automargin=True),
        bargap=0.25,
        showlegend=False,
    )
    fig.add_bar(
        x=counts.values,
        y=[_short(name) for name in counts.index],
        customdata=counts.index,
        orientation="h",
        marker_color=[ACCENT if b == selected_bank else BLUE_RAMP[0] for b in counts.index],
        hovertemplate="%{customdata}<br>%{x:,} complaints<extra></extra>",
    )
    return fig


def word_counts(df, bank):
    """Word counts for the complaints, most frequent first."""
    text = " ".join(df["Consumer complaint narrative"].dropna())
    if not text:
        return {}
    cloud = WordCloud(stopwords=stopwords_for(bank), collocations=False)
    counts = cloud.process_text(text)
    return dict(sorted(counts.items(), key=lambda kv: kv[1], reverse=True))


def word_frequency(counts):
    words = list(counts)[:FREQUENCY_WORDS][::-1]
    fig = _layout(
        xaxis=dict(gridcolor=GRID, zeroline=False, tickformat="~s"),
        yaxis=dict(ticks="", automargin=True, tickfont_size=10, dtick=1),
        bargap=0.2,
        showlegend=False,
    )
    fig.add_bar(
        x=[counts[w] for w in words],
        y=words,
        orientation="h",
        marker_color=ACCENT,
        hovertemplate="%{y}: %{x:,}<extra></extra>",
    )
    return fig


def treemap(counts):
    words = list(counts)[:TOP_WORDS]
    values = [counts[w] for w in words]
    fig = _layout()
    fig.add_treemap(
        labels=words,
        parents=[""] * len(words),
        values=values,
        marker=dict(
            colors=values,
            colorscale=[[i / (len(BLUE_RAMP) - 1), c] for i, c in enumerate(BLUE_RAMP)],
            line=dict(color="#FFFFFF", width=2),
            pad=dict(t=0, l=0, r=0, b=0),
        ),
        texttemplate="%{label}<br>%{value:,}",
        hovertemplate="%{label}: %{value:,}<extra></extra>",
        tiling_pad=2,
    )
    return fig


def wordcloud(counts):
    """The word cloud as an image, with invisible points on each word for hover."""
    cloud = WordCloud(
        width=CLOUD_WIDTH,
        height=CLOUD_HEIGHT,
        scale=2,
        max_words=80,
        prefer_horizontal=1.0,
        margin=4,
        background_color=None,
        mode="RGBA",
        random_state=1,
        color_func=lambda word, **_: _cloud_color(counts, word),
    ).generate_from_frequencies(counts)

    fig = _layout(
        xaxis=dict(visible=False, range=[0, CLOUD_WIDTH], constrain="domain"),
        yaxis=dict(
            visible=False,
            range=[CLOUD_HEIGHT, 0],
            scaleanchor="x",
            constrain="domain",
        ),
        showlegend=False,
    )
    fig.add_layout_image(
        source=cloud.to_image(),
        xref="x",
        yref="y",
        x=0,
        y=0,
        sizex=CLOUD_WIDTH,
        sizey=CLOUD_HEIGHT,
        sizing="stretch",
        layer="below",
    )
    xs, ys, hover = [], [], []
    for (word, _freq), size, (row, col), _orientation, _color in cloud.layout_:
        # layout_ is in scaled-down canvas pixels; estimate each word's center
        xs.append(col + 0.3 * size * len(word))
        ys.append(row + 0.5 * size)
        hover.append(f"{word}: {counts[word]:,}")
    fig.add_scatter(
        x=xs,
        y=ys,
        mode="markers",
        marker=dict(size=12, opacity=0),
        hovertext=hover,
        hoverinfo="text",
    )
    return fig


def _cloud_color(counts, word):
    """Darker blue for more frequent words."""
    share = counts[word] / max(counts.values())
    return BLUE_RAMP[min(1 + int(share * (len(BLUE_RAMP) - 1)), len(BLUE_RAMP) - 1)]


def lda_scatter(docs, topic_words, selected_doc):
    fig = _layout(
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        legend=dict(
            orientation="h",
            x=0,
            y=1,
            yanchor="bottom",
            font_size=11,
            itemclick="toggleothers",
        ),
        margin=dict(l=8, r=8, t=36, b=8),
        clickmode="event",
    )
    for topic, words in topic_words.items():
        points = docs[docs["Dominant_Topic"] == topic]
        fig.add_scattergl(
            name=words,
            x=points["tsne_x"],
            y=points["tsne_y"],
            # A list, not an array: scattergl drops binary-encoded customdata from clickData
            customdata=points["Document_No"].tolist(),
            mode="markers",
            marker=dict(
                size=7,
                color=CATEGORICAL[topic % len(CATEGORICAL)],
                symbol=TOPIC_SYMBOLS[topic % len(TOPIC_SYMBOLS)],
                opacity=0.75,
                line=dict(width=0),
            ),
            hovertemplate=f"Complaint #%{{customdata}}<br>{words}<extra></extra>",
        )
    selected = docs[docs["Document_No"] == selected_doc]
    if not selected.empty:
        fig.add_scatter(
            x=selected["tsne_x"],
            y=selected["tsne_y"],
            mode="markers",
            marker=dict(size=16, color="rgba(0,0,0,0)", line=dict(width=2, color=TEXT)),
            hoverinfo="skip",
            showlegend=False,
        )
    return fig


def bigram_comparison(first, second, top=20):
    df = BIGRAM_COUNTS[BIGRAM_COUNTS["company"].isin([first, second])]
    wide = df.pivot_table(index="ngram", columns="company", values="value", fill_value=0)
    for company in (first, second):
        if company not in wide:
            wide[company] = 0
    wide = wide.assign(total=wide[first] + wide[second]).nlargest(top, "total")
    wide = wide.iloc[::-1]
    labels = [n.replace("_", " ") for n in wide.index]

    fig = _layout(
        barmode="relative",
        bargap=0.2,
        xaxis=dict(
            gridcolor=GRID,
            zeroline=True,
            zerolinecolor=NEUTRAL,
            tickformat="~s",
        ),
        yaxis=dict(ticks="", automargin=True),
        legend=dict(orientation="h", x=0, y=1, yanchor="bottom"),
        margin=dict(l=8, r=8, t=32, b=8),
    )
    for company, sign, color in ((first, -1, CATEGORICAL[0]), (second, 1, CATEGORICAL[1])):
        fig.add_bar(
            name=_short(company, 36),
            y=labels,
            x=sign * wide[company],
            customdata=wide[company],
            orientation="h",
            marker_color=color,
            hovertemplate=f"{company}<br>%{{y}}: %{{customdata:,}}<extra></extra>",
        )
    # Counts on both sides of the axis are positive
    limit = wide[[first, second]].to_numpy().max() * 1.05
    ticks = _nice_ticks(limit)
    fig.update_xaxes(
        range=[-limit, limit],
        tickvals=[-t for t in ticks[:0:-1]] + ticks,
        ticktext=[f"{t:,.0f}" for t in ticks[:0:-1]] + [f"{t:,.0f}" for t in ticks],
    )
    return fig


def _nice_ticks(limit, count=3):
    """0 plus up to `count` round tick values below `limit`."""
    raw = limit / count
    magnitude = 10 ** (len(str(int(raw))) - 1)
    step = next(m * magnitude for m in (1, 2, 2.5, 5, 10) if m * magnitude >= raw)
    ticks, value = [0], step
    while value < limit:
        ticks.append(value)
        value += step
    return ticks


def bigram_scatter(embedding):
    fig = _layout(
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        showlegend=False,
    )
    fig.add_scatter(
        x=embedding["tsne_1"],
        y=embedding["tsne_2"],
        mode="markers+text",
        text=[b.replace("_", " ") for b in embedding["bigram"]],
        textposition="top center",
        textfont=dict(size=11, color=TEXT),
        customdata=embedding["count"],
        marker=dict(
            size=embedding["count"],
            sizemode="area",
            sizeref=2.0 * embedding["count"].max() / 50**2,
            sizemin=4,
            color=ACCENT,
            opacity=0.55,
            line=dict(width=1, color="#FFFFFF"),
        ),
        hovertemplate="%{text}<br>%{customdata:,} occurrences<extra></extra>",
        cliponaxis=False,
    )
    return fig
