"""Hover panel that shows the app's own websocket code, for live demos.

Snippets are read from the source file at startup, so the panel always
matches the code that is actually running.
"""

import ast
from pathlib import Path

import dash_design_kit as ddk
from dash import dcc, html

# (heading, explanation, source file, name). The name is a top-level
# function or assignment, or "Class.method".
SNIPPETS = [
    (
        "1 · Turn on websocket callbacks",
        "One flag moves every callback onto a persistent websocket "
        "instead of an HTTP request per update.",
        "app.py",
        "app",
    ),
    (
        "2 · One long-lived stream per browser session",
        "No Inputs and no Outputs makes this a persistent callback: Dash runs "
        "it on page load and restarts it if the websocket reconnects. "
        "set_props pushes each update to the browser immediately.",
        "app.py",
        "stream_watchlist",
    ),
    (
        "3 · One shared Finnhub feed for every viewer",
        "Finnhub allows one socket per API key, so a single background "
        "connection subscribes to everyone's symbols and fans trades out.",
        "feed.py",
        "MarketFeed._stream",
    ),
]


def _node_source(source: str, node) -> str:
    # Include decorators such as @callback(...) in the snippet.
    start = min([d.lineno for d in node.decorator_list] + [node.lineno])
    lines = source.splitlines()[start - 1 : node.end_lineno]
    indent = min(len(l) - len(l.lstrip()) for l in lines if l.strip())
    return "\n".join(l[indent:] for l in lines)


def extract_source(path: Path, name: str) -> str | None:
    """Source text of a top-level function/assignment or a Class.method."""
    source = path.read_text()
    class_name, _, member = name.rpartition(".")
    body = ast.parse(source).body
    if class_name:
        classes = [
            n for n in body if isinstance(n, ast.ClassDef) and n.name == class_name
        ]
        body = classes[0].body if classes else []
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == member:
                return _node_source(source, node)
        elif isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id == member:
                lines = source.splitlines()[node.lineno - 1 : node.end_lineno]
                return "\n".join(lines)
    return None


def code_panel(source_file: str) -> html.Div:
    folder = Path(source_file).parent
    sections = []
    files = []
    for heading, explanation, file_name, name in SNIPPETS:
        code = extract_source(folder / file_name, name)
        if code is None:
            continue
        if file_name not in files:
            files.append(file_name)
        sections += [
            html.Div(heading, className="code-peek-heading"),
            html.P(explanation, className="code-peek-caption"),
            dcc.Markdown(
                f"```python\n{code}\n```",
                className="code-peek-code",
                highlight_config={"theme": "light"},
            ),
        ]

    return html.Div(
        [
            html.Div(
                ddk.Icon(icon_name="code", className="code-peek-icon"),
                className="code-peek-trigger",
                title="How the websockets work",
            ),
            html.Div(
                html.Div(
                    [
                        html.Div(
                            [
                                html.Div(
                                    "How it works · Dash websocket callbacks",
                                    className="code-peek-title",
                                ),
                                html.Div(
                                    f"Live source from {' and '.join(files)}",
                                    className="code-peek-subtitle",
                                ),
                            ],
                            className="code-peek-header",
                        ),
                        *sections,
                    ],
                    className="code-peek-body",
                ),
                className="code-peek-panel",
            ),
        ],
        className="code-peek",
        # Focusable so the panel also opens from the keyboard (Tab).
        tabIndex="0",
    )
