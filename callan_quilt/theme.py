"""Brand constants and the quilt's asset-class palette.

Keep brand colors in sync with assets/theme.js (DDK theme) and assets/style.css.
"""

# Editorial "almanac" look: warm paper, ink-black type, one petrol accent.
BRAND_DARK = "#1C1917"
BRAND_ACCENT = "#1F5F6B"

INK = "#1C1917"
MUTED = "#78716C"
GRID_LINE = "#E4DDD0"
SURFACE = "#FBF8F2"
NEGATIVE = "#B3261E"

FONT_BODY = "IBM Plex Sans, sans-serif"
FONT_MONO = "IBM Plex Mono, monospace"

# Asset-class colors from Paul Tol's colorblind-safe "muted" set. Every quilt
# cell also prints its ticker, so color is never the only cue. Colors follow
# the asset, never its rank, so filtering never repaints the survivors.
ASSET_COLORS = {
    "SPY": "#332288",  # indigo
    "IWM": "#88CCEE",  # cyan
    "EFA": "#44AA99",  # teal
    "EEM": "#AA4499",  # purple
    "AGG": "#117733",  # green
    "VNQ": "#CC6677",  # rose
    "GLD": "#DDCC77",  # sand
}

# The balanced portfolio is a solid ink cell, so it reads as "the blend"
# without spending another hue.
PORTFOLIO_FILL = INK
PORTFOLIO_LINE = INK
