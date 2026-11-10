# Rebalance Desk

A portfolio rebalancing workflow, built to show how far Dash AG Grid goes. Every screen is an AG Grid, and the controls around each one drive the grid API.

Each of 12 clients has a target mix of five funds (US Stocks, International Stocks, Bonds, Real Estate and a Cash Fund), for example 55% / 25% / 10% / 5% / 5% for Growth. As prices move, the real mix drifts away from the target. An account is **off target** once any fund is more than 5 points away.

1. **Screen.** See which accounts are off target and tick the ones to fix. Click **→** on a client to see the funds they own, then click a fund to see each purchase. The breadcrumbs take you back up.
2. **Propose.** The buys and sells that bring each fund back to its target. Edit shares, order type and limit price in place, with undo and redo. Amount, the new share of the account and the gain on each sale recompute as you type. Drag rows to change the order they are sent in.
3. **Check.** Three house rules: orders must be at least $2,000, buys must be paid for by sales plus cash, and sales that lock in more than $2,000 of gain in a taxable account are flagged for review. Blocked orders can't be selected, and orders to review stay unticked until you approve them.
4. **Release.** The orders fill live. Changed cells flash, and the numbers at the top track shares filled and amount traded.

The data is made up and seeded, see `desk.py`.

## AG Grid features used

| Area | Features |
| --- | --- |
| Selection | `rowSelection` multi-row with header checkbox, `isRowSelectable`, `selectedRows`, `setNodesSelected()`, `deselectAll` |
| Columns | column groups, pinned left and right, `responsiveSizeToFit` |
| Cells | custom React cell renderers (sparkline, drift bar, weight bar, fill bar, pills), `cellRendererData` for the drill button, `valueGetter`, `valueFormatter`, `cellClassRules`, `rowClassRules`, tooltips |
| Editing | `agNumberCellEditor`, `agSelectCellEditor`, conditional `editable`, `valueParser`, `cellValueChanged`, `undoRedoCellEditing` |
| Rows | `pinnedBottomRowData` totals, `rowDragManaged` with `rowDragMultiRow`, `enableCellSpan` and `spanRows`, `wrapText` with `autoHeight` |
| Updates | `getRowId`, `rowTransaction` updates, `enableCellChangeFlash` |
| Export | `exportDataAsCsv` with `csvExportParams`, including selected rows only |
| Theming | Theming API: `themeQuartz` with the dark color scheme part and custom params (`assets/dashAgGridFunctions.js`) |

## Run locally

```bash
pip install -r requirements.txt
python app.py
```
