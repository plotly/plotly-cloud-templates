"""Halcyon Capital brand constants and chart colors.

Keep brand colors in sync with assets/theme.js (DDK theme) and assets/style.css.
"""

BRAND_PRIMARY = "#0E3B43"
BRAND_ACCENT = "#D97B29"

INK = "#1C2B2D"
MUTED = "#6B7B7D"
GRID_LINE = "#E2E8E7"
SURFACE = "#FFFFFF"
NEGATIVE = "#B42318"

# Single-hue sequential steps (teal family) for the fan chart's percentile
# bands: darker = closer to the median.
BAND_OUTER = "rgba(14, 59, 67, 0.10)"
BAND_INNER = "rgba(14, 59, 67, 0.22)"
SAMPLE_PATH = "rgba(14, 59, 67, 0.18)"

# Categorical roles, drawn from the brand palette. "Plain" and
# "worthless" are deliberately de-emphasized grays, not extra hues.
SELECTED = "#2A9D8F"  # headline estimator / paths that pay off
BASELINE = "#A9B8B6"  # plain Monte Carlo / paths that expire worthless
KNOCKED = BRAND_ACCENT  # paths knocked out by the barrier
REFERENCE = INK  # strike, barrier and benchmark reference lines
