"""Brand constants and the quilt's asset-class palette.

Keep brand colors in sync with assets/theme.js (DDK theme) and assets/style.css.
"""

BRAND_DARK = "#0F172A"
BRAND_ACCENT = "#0D9488"

INK = "#1E293B"
MUTED = "#64748B"
GRID_LINE = "#E2E8F0"
SURFACE = "#FFFFFF"
NEGATIVE = "#B91C1C"

# Asset-class colors from the Okabe-Ito colorblind-safe set. Every quilt cell
# also prints its ticker, so color is never the only cue. Colors follow the
# asset, never its rank, so filtering never repaints the survivors.
ASSET_COLORS = {
    "SPY": "#0072B2",  # blue
    "IWM": "#56B4E9",  # sky blue
    "EFA": "#009E73",  # bluish green
    "EEM": "#CC79A7",  # reddish purple
    "AGG": "#E69F00",  # orange
    "VNQ": "#D55E00",  # vermillion
    "GLD": "#F0E442",  # yellow
}

# The balanced portfolio is drawn as a white cell with a dark outline, the
# classic Callan treatment for a diversified blend, so it needs no extra hue.
PORTFOLIO_FILL = SURFACE
PORTFOLIO_LINE = BRAND_DARK
