var dagcomponentfuncs = (window.dashAgGridComponentFunctions = window.dashAgGridComponentFunctions || {});

// Keep in sync with WELL_STATUS and FORMATION_COLOR in app.py
const STATUS_COLOR = {
  Producing: "#0ca30c",
  "Ramping up": "#0ca30c",
  Underperforming: "#ec835a",
  "Shut in": "#d03b3b",
};
const FORMATION_COLOR = {
  "Kestrel Shale": "#6250d6",
  "Marlow Lime": "#eda100",
  "Dunmore Sand": "#1baf7a",
};

dagcomponentfuncs.StatusCell = (props) =>
  React.createElement(
    "span",
    { className: "cell-status" },
    React.createElement("span", { className: "dot", style: { background: STATUS_COLOR[props.value] } }),
    props.value
  );

dagcomponentfuncs.FormationCell = (props) =>
  React.createElement(
    "span",
    { className: "cell-status" },
    React.createElement("span", { className: "swatch", style: { background: FORMATION_COLOR[props.value] } }),
    props.value
  );
