// Functions referenced by name from the grid definitions in app.py
var dagfuncs = (window.dashAgGridFunctions = window.dashAgGridFunctions || {});

// Theming API: Quartz with a dark scheme and the desk's colors. Keep in sync with style.css
dagfuncs.deskTheme = (theme, agGrid) =>
  theme
    .withPart(agGrid.createPart(agGrid.colorSchemeDark))
    .withPart(agGrid.createPart(agGrid.iconSetQuartzLight))
    .withParams({
      backgroundColor: "#11151c",
      foregroundColor: "#dfe4ec",
      accentColor: "#38e1b0",
      borderColor: "rgba(255,255,255,0.06)",
      headerBackgroundColor: "#0d1117",
      headerTextColor: "#8892a2",
      headerFontSize: 11,
      headerFontWeight: 600,
      headerColumnResizeHandleColor: "rgba(255,255,255,0.18)",
      oddRowBackgroundColor: "rgba(255,255,255,0.012)",
      rowHoverColor: "rgba(56,225,176,0.05)",
      selectedRowBackgroundColor: "rgba(56,225,176,0.09)",
      chromeBackgroundColor: "#0d1117",
      fontFamily: "Geist, system-ui, sans-serif",
      fontSize: 13,
      spacing: 6,
      rowHeight: 40,
      headerHeight: 38,
      wrapperBorderRadius: 0,
      wrapperBorder: false,
      rowBorder: { color: "rgba(255,255,255,0.045)" },
      columnBorder: false,
      checkboxCheckedBackgroundColor: "#38e1b0",
      checkboxCheckedShapeColor: "#06120e",
      inputFocusBorder: { color: "#38e1b0" },
      menuBackgroundColor: "#171c25",
      tooltipBackgroundColor: "#1b2130",
      cellEditingBorder: { color: "#38e1b0", width: 1.5 },
      rangeSelectionBorderColor: "#38e1b0",
      valueChangeValueHighlightBackgroundColor: "rgba(56,225,176,0.22)",
    });

const usd0 = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
const usd2 = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 });

dagfuncs.money = (v) => (v == null || isNaN(v) ? "" : usd0.format(v));
dagfuncs.price = (v) => (v == null || isNaN(v) ? "" : usd2.format(v));

// $1.24M / $812k for big headline values
dagfuncs.compact = (v) => {
  if (v == null) return "";
  const a = Math.abs(v);
  if (a >= 1e6) return "$" + (v / 1e6).toFixed(2) + "M";
  if (a >= 1e3) return "$" + (v / 1e3).toFixed(0) + "k";
  return usd0.format(v);
};

dagfuncs.pct = (v, digits) => (v == null ? "" : (v * 100).toFixed(digits == null ? 1 : digits) + "%");
dagfuncs.signedPct = (v) => (v == null ? "" : (v > 0 ? "+" : "") + (v * 100).toFixed(2) + "%");

// Value getters for the editable trade ticket. They recompute on every edit, which
// keeps the undo stack intact (no round trip to Python to refresh the row)
dagfuncs.notional = (d) => (d ? d.qty * (d.order_type === "Limit" && d.limit ? d.limit : d.price) : null);
dagfuncs.signedNotional = (d) => (d ? dagfuncs.notional(d) * (d.side === "Buy" ? 1 : -1) : null);
dagfuncs.postWeight = (d) => (d ? (d.market_value + dagfuncs.signedNotional(d)) / d.account_value : null);
dagfuncs.estTax = (d) => (d && d.side === "Sell" ? d.qty * d.tax_per_share : 0);
dagfuncs.residualDrift = (d) => (d ? dagfuncs.postWeight(d) - d.target : null);

// Wider drift is worse. Used for the default sort on holdings
dagfuncs.absComparator = (a, b) => Math.abs(a) - Math.abs(b);

dagfuncs.tradeTooltip = (p) => {
  if (!p.data || p.node.rowPinned) return "";
  const d = p.data;
  return `${d.side} ${d.qty.toLocaleString()} ${d.ticker} moves weight ${(d.weight * 100).toFixed(2)}% → ${(
    dagfuncs.postWeight(d) * 100
  ).toFixed(2)}% (target ${(d.target * 100).toFixed(2)}%)`;
};

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const parseIso = (v) => {
  const [y, m, d] = v.split("-").map(Number);
  return new Date(y, m - 1, d);
};

dagfuncs.dateFmt = (v) => {
  if (!v) return "";
  const d = parseIso(v);
  return `${MONTHS[d.getMonth()]} ${String(d.getDate()).padStart(2, "0")}, ${d.getFullYear()}`;
};

// Date filter on ISO strings
dagfuncs.isoDateComparator = (filterDate, cellValue) => {
  if (!cellValue) return -1;
  const d = parseIso(cellValue);
  return d < filterDate ? -1 : d > filterDate ? 1 : 0;
};
