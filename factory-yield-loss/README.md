# Yield Loss Finder

A dashboard that finds where a wafer fab is losing yield, and why, in a few clicks.
It's built with [Dash](https://dash.plotly.com/) and
[Dash Mantine Components](https://www.dash-mantine-components.com/).

The fab is Northbridge Fab 2, a made-up 300 mm fab running three products. Its probe
results cover 60 days of lots, with four problems hidden in the data. The app doesn't
know about them. It finds them with a **commonality analysis**: for each fail bin, it
checks which tool, chamber, slurry lot, probe card, shift or product the losing wafers
have in common.

## How to use it

The page follows the steps an engineer takes to explain a yield loss:

1. **Where is yield lost?** Die lost by fail bin, split into typical loss and loss
   above typical. Click a bin to investigate it.
2. **What do the losing wafers share?** Route steps ranked by how much more of that
   bin their wafers lose. *Explains* is the share of the bin's above-typical loss on
   those wafers. Click a row to follow that suspect.
3. **Follow the wafers through the line.** A Sankey of every wafer's path through
   litho, etch chamber, deposition, CMP and implant. Bands heat up where the selected
   bin runs above typical, and the suspect lights up.
4. **When did it start?** Daily loss for wafers through the suspect against all
   other wafers, with the estimated start date.
5. **Watch it appear on the wafer.** Fail rate at each die position, stacked
   across wafers, with the closest matching pattern (edge ring, arc scratch, center
   cluster, mid-radius ring). Press **Replay** to watch the pattern build day by day.
6. **Which lots to review.** The lots through the suspect with the most loss. Click
   one to open it.
7. **Open the lot.** All 25 wafers of the lot, die by die. Wafers that ran through
   the suspect are ringed. For ETC-03 · B, only the even slots fail (chamber B).

A **finding** at the top sums it up in plain words, with a suggested next step and a
button that copies it to the clipboard to paste into a chat or a shift report.
Filter by product and by how many days of lots to include.

## The hidden problems

| Fail bin | Cause | Start |
|---|---|---|
| Edge leakage | Etch chamber ETC-03 · B | Oct 22 |
| Metal short | One slurry lot on CMP-02 | Early October, for about a week |
| Via open | DEP-04 film drifting thicker | Gets worse from Oct 19 |
| Vt shift | Implanter IMP-02, on product PM-12 only, after maintenance | Oct 28 |

Some decoys are built in too. LTH-02 feeds most ETC-03 lots, so it shows up as a
weaker suspect for edge leakage. Slurry lots change every few days, so they always
overlap in time with any new problem.

## How suspects are ranked

- Wafers through a step are compared with wafers **run on the same days**. That keeps
  something that only changed at the same time, like a new slurry lot, from taking
  the blame.
- Wafers in one lot tend to rise and fall together, so each lot counts as **one
  sample**, not 25. Without that, the app would be overconfident.
- The score combines the strength of the difference with the share of the loss it
  explains. *Strong*, *Likely*, *Possible* and *Weak* are bands of that statistic.
- For problems that need two conditions at once, pairs of the leading suspects are
  also tested (for example, IMP-02 + PM-12).
- **Typical loss** is a bin's 20th-percentile daily rate over the 60 days.

## Project structure

```
app.py              # Layout, charts and callbacks
fab.py              # Synthetic fab data and the commonality analysis
assets/style.css    # Page layout and styling (dark theme)
```

## Publish to Plotly Cloud

Upload all of the files in this folder to [Plotly Cloud](https://cloud.plotly.com).
Plotly Cloud installs the dependencies from `requirements.txt`.

## Run locally

Requires Python 3.13.

```bash
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:8057.
