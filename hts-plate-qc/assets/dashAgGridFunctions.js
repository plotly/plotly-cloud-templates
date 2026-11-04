var dagfuncs = (window.dashAgGridFunctions = window.dashAgGridFunctions || {});

// Grid theme, kept in sync with style.css
dagfuncs.qcTheme = (theme) =>
  theme.withParams({
    backgroundColor: "#ffffff",
    foregroundColor: "#0b0b0b",
    accentColor: "#0f766e",
    borderColor: "rgba(15, 35, 30, 0.09)",
    headerBackgroundColor: "#f4f6f5",
    headerTextColor: "#4f5551",
    headerFontSize: 12,
    headerFontWeight: 600,
    fontFamily: "'Public Sans', system-ui, sans-serif",
    fontSize: 13,
    selectedRowBackgroundColor: "#dff3ef",
    rowHoverColor: "#f4f6f5",
    wrapperBorderRadius: 8,
  });
