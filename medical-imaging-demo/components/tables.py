import dash_mantine_components as dmc
import pandas as pd


def create_data_table(df: pd.DataFrame, title: str = None,
                      striped: bool = True, highlight_flags: bool = False):
    """Generic Mantine table from a DataFrame."""
    cols = df.columns.tolist()
    header = dmc.TableThead(
        dmc.TableTr([dmc.TableTh(c, style={"fontWeight": 600}) for c in cols])
    )
    rows = []
    for _, row in df.iterrows():
        cells = []
        for col, val in zip(cols, row):
            style = {}
            val_str = str(val) if not pd.isna(val) else "—"
            if highlight_flags and col == "flag":
                color = {"H": "#ef4444", "L": "#3b82f6"}.get(val_str, "#22c55e")
                style["color"] = color
                style["fontWeight"] = 600
            cells.append(dmc.TableTd(val_str, style=style))
        rows.append(dmc.TableTr(cells))
    body = dmc.TableTbody(rows)
    table = dmc.Table(
        [header, body],
        striped=striped,
        highlightOnHover=True,
        withTableBorder=True,
        withColumnBorders=True,
    )
    if title:
        return dmc.Stack([
            dmc.Text(title, fw=600, size="lg"),
            dmc.ScrollArea(table, type="auto"),
        ], gap="sm")
    return dmc.ScrollArea(table, type="auto")


def create_findings_table(annotations: list):
    """Build a findings table from a list of annotation dicts."""
    if not annotations:
        return dmc.Text("No annotations yet. Draw on the X-ray to add findings.",
                        size="sm", c="dimmed", ta="center", py="md")

    headers = ["#", "Finding", "Severity", "Location (px)", "Size (px²)", "Note"]
    header = dmc.TableThead(
        dmc.TableTr([dmc.TableTh(h, style={"fontWeight": 600, "fontSize": "12px"})
                     for h in headers])
    )

    sev_color = {"High": "#ef4444", "Medium": "#f59e0b", "Low": "#22c55e"}
    rows = []
    for i, ann in enumerate(annotations, 1):
        x0 = ann.get("x0", 0)
        y0 = ann.get("y0", 0)
        x1 = ann.get("x1", 0)
        y1 = ann.get("y1", 0)
        area = abs((x1 - x0) * (y1 - y0))
        sev = ann.get("_severity", "—")
        rows.append(dmc.TableTr([
            dmc.TableTd(str(i), style={"fontSize": "12px"}),
            dmc.TableTd(ann.get("_label", "Unspecified"),
                        style={"fontWeight": 500, "fontSize": "12px"}),
            dmc.TableTd(
                dmc.Badge(sev, color={"High":"red","Medium":"yellow","Low":"teal"}.get(sev,"gray"),
                          size="sm"),
            ),
            dmc.TableTd(f"({int(x0)},{int(y0)})→({int(x1)},{int(y1)})",
                        style={"fontFamily": "monospace", "fontSize": "11px"}),
            dmc.TableTd(f"{int(area):,}", style={"fontSize": "12px"}),
            dmc.TableTd(ann.get("_note", ""), style={"fontSize": "12px"}),
        ]))

    return dmc.ScrollArea(
        dmc.Table([header, dmc.TableTbody(rows)],
                  striped=True, highlightOnHover=True,
                  withTableBorder=True, withColumnBorders=False,
                  verticalSpacing="xs"),
        type="auto",
    )


def create_patient_table(df: pd.DataFrame, cols=None):
    """Patient roster table with coloured risk badges."""
    if cols is None:
        cols = ["patient_id", "name", "age", "gender", "diagnosis", "ward", "risk_score"]
    df = df[cols].copy()
    header = dmc.TableThead(
        dmc.TableTr([dmc.TableTh(c.replace("_"," ").title(),
                                  style={"fontWeight": 600, "fontSize": "12px"})
                     for c in cols])
    )
    rows = []
    for _, row in df.iterrows():
        cells = []
        for col in cols:
            val = row[col]
            if col == "risk_score":
                color = "red" if val > 70 else "yellow" if val > 40 else "teal"
                cells.append(dmc.TableTd(
                    dmc.Badge(f"{val:.0f}", color=color, size="sm")))
            else:
                cells.append(dmc.TableTd(str(val), style={"fontSize": "12px"}))
        rows.append(dmc.TableTr(cells))
    return dmc.ScrollArea(
        dmc.Table([header, dmc.TableTbody(rows)],
                  striped=True, highlightOnHover=True, withTableBorder=True),
        type="auto", h=280,
    )
