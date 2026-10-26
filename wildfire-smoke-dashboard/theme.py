"""Mantine theme — prussian / charcoal-blue chrome on a papaya canvas, peach accents.

Built from the brand palette: prussian-blue #001b2e, charcoal-blue #294c60, pale-slate
#adb6c4, papaya-whip #ffefd3, peach-glow #ffc49b. Each is the anchor of a 10-shade scale
(★ below). Mantine's own `gray` is replaced by the slate scale, so every gray.*, `dimmed`
and default-border token follows it. Map data colours live in config.py and never read
this theme.
"""

# 10 shades each, light → dark. charcoal.6 holds ≥4.5:1 against white text, papaya.2 and
# peach.3 against prussian; slate.6 (Mantine's `dimmed`) holds ≥4.5:1 on white and the canvas.
# charcoal: ★6 charcoal-blue, ★9 prussian-blue (9 sidebar, 8 section panel, 6 controls, 5 hover)
CHARCOAL = ["#eef3f6", "#d9e4ea", "#b5c9d5", "#8eabbd", "#6a8ea4", "#4b7389", "#294c60", "#1d3b4e", "#0d2a3d", "#001b2e"]
# slate: ★4 pale-slate
SLATE = ["#f7f8fa", "#eef0f4", "#e1e5eb", "#cdd3dc", "#adb6c4", "#8692a3", "#5f6d80", "#475668", "#2f3f50", "#001b2e"]
# papaya: ★2 papaya-whip (1 is the page canvas)
PAPAYA = ["#fffbf4", "#fff7e9", "#ffefd3", "#f9e2bb", "#f0d09e", "#e3b97d", "#c99a5c", "#a77b42", "#835e30", "#5f4220"]
# peach: ★3 peach-glow
PEACH = ["#fff6ef", "#ffead9", "#ffd8bb", "#ffc49b", "#f0a878", "#d48552", "#a85a32", "#874729", "#683620", "#4a2617"]

FONT_FAMILY = "'IBM Plex Sans', sans-serif"

THEME = {
    "primaryColor": "charcoal",
    "colors": {"charcoal": CHARCOAL, "gray": SLATE, "papaya": PAPAYA, "peach": PEACH},
    "black": CHARCOAL[9],
    "autoContrast": True,  # light fills (papaya.2, peach.3) get prussian text
    "fontFamily": FONT_FAMILY,
    "headings": {"fontFamily": FONT_FAMILY},
    "defaultRadius": "md",
    "shadows": {
        "xs": "0 1px 2px rgba(0, 27, 46, 0.06)",
        "sm": "0 1px 3px rgba(0, 27, 46, 0.08), 0 1px 2px rgba(0, 27, 46, 0.04)",
    },
    "components": {
        "Card": {"defaultProps": {"withBorder": False, "radius": "lg", "padding": "md", "shadow": "xs"}},
        "Select": {"defaultProps": {"size": "sm", "allowDeselect": False, "checkIconPosition": "right"}},
        "SegmentedControl": {"defaultProps": {"size": "xs", "withItemsBorders": False}},
        "Tooltip": {"defaultProps": {"withArrow": True, "openDelay": 200}},
    },
}
