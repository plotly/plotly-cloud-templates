// Custom cell renderers, referenced by name in columnDefs
var dagcomponentfuncs = (window.dashAgGridComponentFunctions = window.dashAgGridComponentFunctions || {});
const e = React.createElement;

// 30 day value path as a tiny line, colored by direction
dagcomponentfuncs.Sparkline = (props) => {
  const v = props.value;
  if (!v || !v.length) return null;
  const w = 96, h = 24, pad = 2;
  const lo = Math.min(...v), hi = Math.max(...v);
  const span = hi - lo || 1;
  const pts = v.map((y, i) => [pad + (i / (v.length - 1)) * (w - pad * 2), h - pad - ((y - lo) / span) * (h - pad * 2)]);
  const up = v[v.length - 1] >= v[0];
  const color = up ? "#38e1b0" : "#ff7b72";
  const line = pts.map((p) => p.join(",")).join(" ");
  const area = `${pad},${h} ${line} ${w - pad},${h}`;
  const last = pts[pts.length - 1];
  return e("svg", { width: w, height: h, className: "spark", viewBox: `0 0 ${w} ${h}` },
    e("polygon", { points: area, fill: color, opacity: 0.08 }),
    e("polyline", { points: line, fill: "none", stroke: color, strokeWidth: 1.4, strokeLinejoin: "round" }),
    e("circle", { cx: last[0], cy: last[1], r: 2, fill: color })
  );
};

// Diverging drift bar centered on target, with the tolerance band shaded
dagcomponentfuncs.DriftBar = (props) => {
  const d = props.value;
  if (d == null) return null;
  const band = (props.data && props.data.band) || props.band || 0.03;
  const scale = props.scale || 0.12; // drift that fills half the track
  const half = 50;
  const len = Math.min(Math.abs(d) / scale, 1) * half;
  const out = Math.abs(d) > band;
  const bandW = Math.min(band / scale, 1) * half;
  return e("div", { className: "drift" },
    e("div", { className: "drift-track" },
      e("div", { className: "drift-band", style: { left: `${half - bandW}%`, width: `${bandW * 2}%` } }),
      e("div", { className: "drift-mid" }),
      e("div", {
        className: "drift-fill " + (out ? "out" : "in"),
        style: d >= 0 ? { left: "50%", width: `${len}%` } : { left: `${half - len}%`, width: `${len}%` },
      })
    ),
    e("span", { className: "drift-num " + (out ? "out" : "") }, (d > 0 ? "+" : "") + (d * 100).toFixed(2) + "%")
  );
};

const STATUS_CLASS = {
  "Out of band": "bad", Watch: "warn", "In band": "ok",
  pass: "ok", warn: "warn", fail: "bad",
  Routed: "idle", Working: "info", Partial: "warn", Filled: "ok",
  Short: "warn", Long: "ok",
};

dagcomponentfuncs.Pill = (props) => {
  if (props.value == null) return null;
  const label = props.labels ? props.labels[props.value] || props.value : props.value;
  return e("span", { className: "pill " + (STATUS_CLASS[props.value] || "idle") }, e("i"), label);
};

dagcomponentfuncs.Side = (props) =>
  props.value ? e("span", { className: "side " + props.value.toLowerCase() }, props.value.toUpperCase()) : null;

dagcomponentfuncs.ModelTag = (props) => {
  if (!props.value) return null;
  const key = props.value.split(" ")[0].toLowerCase().replace(/[^a-z]/g, "");
  return e("span", { className: "model m-" + key }, props.value);
};

const AC_COLORS = {
  "US Equity": "#5aa9ff", "Intl Equity": "#a78bfa", "EM Equity": "#f472b6",
  "Fixed Income": "#f5c451", "Real Assets": "#fb923c", Cash: "#8892a2",
};
dagcomponentfuncs.AssetClass = (props) =>
  props.value
    ? e("span", { className: "ac" }, e("i", { style: { background: AC_COLORS[props.value] } }), props.value)
    : null;

// Security cell: ticker over name, with a drill affordance
dagcomponentfuncs.Security = (props) => {
  if (!props.data || !props.data.ticker) return props.value || null;
  return e("div", { className: "sec" + (props.drill ? " drillable" : "") },
    e("b", null, props.data.ticker),
    e("span", null, props.data.name)
  );
};

// Household cell with a drill button that reports back through cellRendererData
dagcomponentfuncs.Drill = (props) => {
  if (!props.data) return null;
  return e("div", { className: "drill-cell" },
    e("div", { className: "drill-text" }, e("b", null, props.value), e("span", null, props.data.id + " · " + props.data.registration)),
    e("button", {
      className: "drill-btn",
      title: "Open holdings",
      onClick: (ev) => {
        ev.stopPropagation();
        props.setData({ action: "drill", id: props.data.id });
      },
    }, "→")
  );
};

// One compliance rule: tick, warning or cross
dagcomponentfuncs.Check = (props) => {
  const glyph = { pass: "✓", warn: "!", fail: "×" }[props.value];
  return glyph ? e("span", { className: "chk " + props.value, title: props.value }, glyph) : null;
};

// Fill progress for the blotter
dagcomponentfuncs.FillBar = (props) => {
  if (!props.data) return null;
  const pct = props.data.pct || 0;
  return e("div", { className: "fill" },
    e("div", { className: "fill-track" },
      e("div", { className: "fill-bar " + (pct >= 1 ? "done" : ""), style: { width: `${pct * 100}%` } })),
    e("span", null, `${props.data.filled.toLocaleString()} / ${props.data.qty.toLocaleString()}`)
  );
};

// Allocation strip: weight versus target on one bar
dagcomponentfuncs.WeightBar = (props) => {
  if (!props.data || props.data.weight == null) return null;
  const max = props.max || 0.3;
  const w = Math.min(props.data.weight / max, 1) * 100;
  const t = Math.min(props.data.target / max, 1) * 100;
  return e("div", { className: "wbar" },
    e("div", { className: "wbar-track" },
      e("div", { className: "wbar-fill", style: { width: `${w}%` } }),
      props.data.target > 0 ? e("div", { className: "wbar-target", style: { left: `${t}%` } }) : null),
    e("span", null, (props.data.weight * 100).toFixed(2) + "%")
  );
};

// Drag handle header for the priority column
dagcomponentfuncs.Rank = (props) => e("span", { className: "rank" }, props.node.rowIndex + 1);
