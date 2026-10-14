"""Hover panel that shows the Monte Carlo engine's code, for live demos.

Snippets are read from the source file at startup, so the panel always
matches the code that is actually running.
"""

import ast
from pathlib import Path

import dash_design_kit as ddk
from dash import dcc, html

# (heading, explanation, top-level name in the source file)
SNIPPETS = [
    (
        "1 · Risk-neutral dynamics",
        "Vectorized log-price increments for a whole block of paths: GBM, "
        "plus compound-Poisson jumps with the martingale compensator for Merton.",
        "log_increments",
    ),
    (
        "2 · Chunked simulation with antithetic pairs",
        "Paths are generated in 25k-path chunks to bound memory. Antithetic "
        "mode reuses each draw as (Z, -Z) and averages the pair.",
        "simulate",
    ),
    (
        "3 · Control variate",
        "The discounted terminal price has a known mean, S0·e^(-qT), so it "
        "absorbs variance from the payoff at no extra simulation cost.",
        "control_variate",
    ),
    (
        "4 · Greeks with common random numbers",
        "Central-difference bump-and-revalue, reusing one seed so each bump "
        "sees the same random draws and the noise largely cancels.",
        "mc_greeks",
    ),
]


def extract_source(path: Path, names: list[str]) -> dict[str, str]:
    """Source text of top-level functions or assignments, keyed by name."""
    source = path.read_text()
    found = {}
    for node in ast.parse(source).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name = node.name
            # Include decorators such as @callback(...) in the snippet.
            start = min([d.lineno for d in node.decorator_list] + [node.lineno])
        elif isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            start = node.lineno
        else:
            continue
        if name in names:
            lines = source.splitlines()[start - 1 : node.end_lineno]
            found[name] = "\n".join(lines)
    return found


def code_panel(source_file: str) -> html.Div:
    names = [name for _, _, name in SNIPPETS]
    sources = extract_source(Path(source_file), names)
    sections = []
    for heading, explanation, name in SNIPPETS:
        if name not in sources:
            continue
        sections += [
            html.Div(heading, className="code-peek-heading"),
            html.P(explanation, className="code-peek-caption"),
            dcc.Markdown(
                f"```python\n{sources[name]}\n```",
                className="code-peek-code",
                highlight_config={"theme": "light"},
            ),
        ]

    return html.Div(
        [
            html.Div(
                ddk.Icon(icon_name="code", className="code-peek-icon"),
                className="code-peek-trigger",
                title="How the simulation engine works",
            ),
            html.Div(
                html.Div(
                    [
                        html.Div(
                            [
                                html.Div(
                                    "How it works · Monte Carlo engine",
                                    className="code-peek-title",
                                ),
                                html.Div(
                                    f"Live source from {Path(source_file).name}",
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
