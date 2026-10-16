# Bank Customer Complaints

## About this app

An example of how Dash can be used for Natural Language Processing (NLP), using a
sample of consumer complaints filed against US banks between 2015 and 2017.

The **Explorer** view fits on one screen:

- **Top 10 banks** by number of complaints. Click a bar to select that bank.
- **Most frequent words** and **Top words** (treemap or word cloud) in the selected
  bank's complaints, excluding common words and the bank's own name.
- **Topics found by LDA**: each complaint placed on a t-SNE map and colored by its
  dominant topic. Click a point to read the complaint.

The sidebar filters by sample size, bank, and time frame.

The **Bigrams** view compares the most frequent two-word phrases of two companies,
and maps the top bigrams by meaning with t-SNE.

The LDA topic models were fitted offline and are stored in `data/precomputed.json`,
so the app does not need any NLP model libraries at runtime.

## How to run this app

Requires Python 3.13.

```
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:8050.

## Publishing to Plotly Cloud

Upload all the files in this folder to [Plotly Cloud](https://cloud.plotly.com).
It installs `requirements.txt` and serves `app:server`.

## Resources

- [Dash documentation](https://dash.plotly.com/)
- [Dash Mantine Components](https://www.dash-mantine-components.com/)
- [CFPB Consumer Complaint Database](https://www.consumerfinance.gov/data-research/consumer-complaints/)
