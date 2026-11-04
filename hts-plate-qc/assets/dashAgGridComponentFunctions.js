var dagcomponentfuncs = (window.dashAgGridComponentFunctions = window.dashAgGridComponentFunctions || {});

// Keep in sync with PLATE_STATUS and DECISIONS in app.py
const STATUS_COLOR = { Pass: "#0ca30c", Review: "#fab219", Fail: "#d03b3b" };
const STATUS_ICON = { Pass: "✓", Review: "!", Fail: "✕" };
const DECISION_CLASS = { Pending: "pending", Accepted: "accepted", "Re-run": "rerun", Rejected: "rejected" };

dagcomponentfuncs.StatusCell = (props) =>
  React.createElement(
    "span",
    { className: "cell-status" },
    React.createElement(
      "span",
      { className: "status-icon", style: { background: STATUS_COLOR[props.value] } },
      STATUS_ICON[props.value]
    ),
    props.value
  );

dagcomponentfuncs.DecisionCell = (props) =>
  React.createElement("span", { className: "decision " + DECISION_CLASS[props.value] }, props.value);
