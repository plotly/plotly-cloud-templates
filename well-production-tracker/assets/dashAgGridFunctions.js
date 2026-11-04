var dagfuncs = (window.dashAgGridFunctions = window.dashAgGridFunctions || {});

// Grid theme, kept in sync with style.css
dagfuncs.prodTheme = (theme) =>
  theme.withParams({
    backgroundColor: "#fcfcfb",
    foregroundColor: "#0b0b0b",
    accentColor: "#2b2a27",
    borderColor: "rgba(11, 11, 11, 0.08)",
    headerBackgroundColor: "#f3f2ee",
    headerTextColor: "#52514e",
    headerFontSize: 12,
    headerFontWeight: 600,
    fontFamily: "'IBM Plex Sans', system-ui, sans-serif",
    fontSize: 13,
    selectedRowBackgroundColor: "#fdf3c4",
    rowHoverColor: "#f3f2ee",
    wrapperBorderRadius: 8,
  });
