"""Halcyon Capital brand constants and chart colors.

The module-level colors are the light print palette used by the PDF report;
DARK holds the on-screen (dark mode) chart colors used by figures.py.

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


# On-screen dark mode. Same roles as above, lifted for a dark surface.
DARK = {
    "PRIMARY": "#7FC8BE",
    "INK": "#E3ECEB",
    "MUTED": "#8FA2A3",
    "GRID_LINE": "#24383B",
    "SURFACE": "#132326",
    "BAND_OUTER": "rgba(127, 200, 190, 0.10)",
    "BAND_INNER": "rgba(127, 200, 190, 0.22)",
    "SAMPLE_PATH": "rgba(127, 200, 190, 0.16)",
    "SELECTED": "#3DB8A8",
    "SELECTED_FILL": "rgba(61, 184, 168, 0.22)",
    "BASELINE": "#5E7274",
    "BASELINE_FILL": "rgba(143, 162, 163, 0.18)",
    "KNOCKED": BRAND_ACCENT,
    "REFERENCE": "#C9D4D3",
}
