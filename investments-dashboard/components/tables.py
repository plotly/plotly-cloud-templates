import dash_mantine_components as dmc
from dash import html
import pandas as pd

def create_data_table(df, title=None, striped=True):
    """Create a styled Mantine table from DataFrame"""
    
    columns = df.columns.tolist()
    
    header = dmc.TableThead(
        dmc.TableTr([
            dmc.TableTh(col, style={'fontWeight': 600}) for col in columns
        ])
    )
    
    rows = []
    for _, row in df.iterrows():
        cells = []
        for i, val in enumerate(row):
            style = {}
            if isinstance(val, str):
                if '%' in val:
                    try:
                        num = float(val.replace('%', ''))
                        style['color'] = '#40c057' if num > 0 else '#fa5252' if num < 0 else None
                        style['fontWeight'] = 500
                    except:
                        pass
            cells.append(dmc.TableTd(val, style=style))
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

def create_returns_table(df):
    """Create formatted returns comparison table"""
    return create_data_table(df, title="Average Annual Returns")

def create_fund_facts_table(df):
    """Create fund facts key-value table"""
    
    rows = []
    for _, row in df.iterrows():
        rows.append(
            dmc.TableTr([
                dmc.TableTd(row['label'], style={'fontWeight': 500, 'color': 'dimmed'}),
                dmc.TableTd(str(row['value']).replace('"', ''), style={'fontWeight': 600}),
            ])
        )
    
    return dmc.Table(
        dmc.TableTbody(rows),
        withTableBorder=True,
        highlightOnHover=True,
    )

def create_dividend_table(df):
    """Create dividend history table"""
    return create_data_table(df, title="Distribution History")

def create_comparison_table(data, columns, title=None):
    """Create a generic comparison table"""
    
    header = dmc.TableThead(
        dmc.TableTr([dmc.TableTh(col, style={'fontWeight': 600}) for col in columns])
    )
    
    rows = []
    for row_data in data:
        cells = [dmc.TableTd(cell) for cell in row_data]
        rows.append(dmc.TableTr(cells))
    
    body = dmc.TableTbody(rows)
    
    table = dmc.Table(
        [header, body],
        striped=True,
        highlightOnHover=True,
        withTableBorder=True,
    )
    
    if title:
        return dmc.Stack([
            dmc.Text(title, fw=600, size="lg"),
            table
        ], gap="sm")
    
    return table
