# Portfolio Stress Test & VaR

A comparison workbench for the market risk of a made-up $1.6B multi-asset
fund. The app opens on an empty canvas. You drag the things you want to
compare from the sidebar onto it.

## How it works

The sidebar has two tabs.

**Compare** lists everything you can compare, in three groups:

- **VaR models**: historical, parametric (delta-normal), Monte Carlo
  (Student-t, full revaluation) and Monte Carlo in a crisis regime (2×
  volatility, crisis correlations)
- **Stress scenarios**: five historical-style replays (2008, Covid, 2022,
  1994, the 2013 taper tantrum), three hypothetical scenarios, the book's worst
  10 days in the data, and **Custom scenario**, a snapshot of the shocks you set
  in the Controls tab
- **Positions**: all 21 positions in the book

Drag an item anywhere onto the canvas, or click it, or press Enter on it. It
joins the comparison for its kind. Each kind has its own tab above the
canvas, labelled with how many items it holds. A tab appears once you add
something of that kind, and adding an item opens its tab. You can
compare up to four items of each kind. Remove an item with × on its tile, or
clear a whole section with × in its header.

- **Compare VaR models**: overlaid P&L distributions with each model's VaR, a
  250-day backtest of every model's VaR line against the book's daily P&L, and a
  table of VaR, limit use, expected shortfall, tail weight, diversification
  benefit, backtest exceptions, Basel traffic light and Kupiec test
- **Compare stress scenarios**: P&L by asset class or by risk factor, and a
  table of total loss, stress-limit status, biggest loss driver, hardest-hit
  position, best offset and the severity that would hit the limit
- **Compare positions**: P&L in every stress scenario, and a table of market
  value, weight, standalone VaR, contribution to expected shortfall, and worst
  and best scenario

**Controls** sets the confidence level, horizon, lookback window, the method
used for position risk, and two model stresses: a volatility multiplier and a
correlation stress. These apply to every comparison on the canvas. The tab also
holds the custom scenario builder: start from a preset and adjust the ten
factor shocks.

## The data

Everything is synthetic and generated at startup in `risk.py`:

- **10 risk factors**: US, developed and emerging equities, the US 10y yield,
  IG and HY credit spreads, crude oil, gold, the dollar index and VIX
- **21 positions**, each mapped to the factors as $ exposures (betas for
  equities and commodities, durations for bonds). The S&P 500 put spread overlay
  is non-linear: it has convexity, can lose at most its premium and can pay at
  most its width. This is why the three VaR methods give different answers
- **1,300 business days of factor history** drawn from a Student-t copula with
  GARCH volatility clustering. It includes a made-up liquidity shock in spring
  2025 (triple volatility, crisis correlations) and a smaller wobble in August
  2026, which falls inside the backtest window

The historical scenario shocks are rough, made-up approximations for
illustration. They are not calibrated to real market data.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:8050.

## Publish

Drag the folder's files into a new app on [Plotly Cloud](https://cloud.plotly.com).
The `Procfile` runs it with gunicorn.

## Built with

Dash, Dash Mantine Components, Plotly and NumPy.
