# Rebalance Desk

A portfolio rebalancing workflow for a private wealth desk, built to show how far Dash AG Grid goes. Every screen is an AG Grid, and the controls around each one drive the grid API.

1. **Screen.** Scan 24 accounts for drift against their model portfolio. Filter by status, quick-filter, show or hide columns, and tick the accounts to rebalance. Click **→** on a household to drill into its holdings, then click a ticker to see its tax lots.
2. **Propose.** Trades that take each position back to target. Edit shares, order type, limit price and time in force in place, with undo and redo. Notional, post-trade weight, residual drift and estimated tax recompute in the browser on every keystroke. Drag rows to set execution priority, or bulk-apply an order type to the selected rows.
3. **Check.** Pre-trade compliance: restricted list, wash sale, concentration, short-term gains, liquidity and ticket size. Blocked orders can't be selected, and orders flagged for review need an explicit acknowledgement.
4. **Release.** Orders stream fills as row transactions. Changed cells flash, and the KPIs track filled share count, executed notional and slippage.

The book is synthetic and seeded, see `desk.py`.

## AG Grid features used

| Area | Features |
| --- | --- |
| Selection | `rowSelection` multi-row with header checkbox and `selectAll: 'filtered'`, `isRowSelectable`, `selectedRows`, `setNodesSelected()`, `deselectAll` |
| Filtering | `filterModel` driven from Python, `floatingFilter`, `quickFilterText`, number, text and date filters with a custom date comparator |
| Columns | column groups with `columnGroupShow`, pinned left and right, `setColumnsVisible()`, `resetColumnState`, `persistence` on `columnState`, `responsiveSizeToFit` |
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
