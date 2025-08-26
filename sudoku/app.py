from datetime import datetime

import dash
import dash_mantine_components as dmc
import numpy as np
from dash import Input, Output, State, callback, ctx, dcc, html
from dash_iconify import DashIconify

from game_loader import game_loader
from utils import (
    BOX_SIZE,
    GRID_SIZE,
    NUMBERS_RANGE,
    create_new_game_state,
    is_number_completed,
    update_highlighting,
)

dash._dash_renderer._set_react_version("18.2.0")

# Initialize the Dash app
app = dash.Dash(__name__, suppress_callback_exceptions=True)
server = app.server
app.title = "Dash Sudoku"
app.index_string = """
<!DOCTYPE html>
<html>
  <head>
    {%metas%}
    <title>Dash Sudoku - The best way to play Sudoku</title>
    <meta name="title" content="Dash Sudoku - The best way to play Sudoku" />
    <meta name="description" content="Classic sudoku in a Dash app — clean and simple." />

    <meta property="og:type" content="website" />
    <meta property="og:url" content="https://sudoku.plotly.app/" />
    <meta property="og:title" content="Dash Sudoku - The best way to play Sudoku" />
    <meta property="og:description" content="Classic sudoku in a Dash app — clean and simple." />
    <meta property="og:image" content="https://sudoku.plotly.app/assets/thumbnail.png" />

    <meta name="twitter:card" content="summary_large_image" />
    <meta name="twitter:url" content="https://sudoku.plotly.app/" />
    <meta name="twitter:title" content="Dash Sudoku - The best way to play Sudoku" />
    <meta name="twitter:description" content="Classic sudoku in a Dash app — clean and simple." />
    <meta name="twitter:image" content="https://sudoku.plotly.app/assets/thumbnail.png" />

    {%favicon%}
    {%css%}
  </head>
  <body>
    {%app_entry%}
    <footer>
      {%config%}
      {%scripts%}
      {%renderer%}
    </footer>
  </body>
</html>
"""

# Initialize game state with pre-generated games
puzzle, solution, given_cells = game_loader.load_game("medium")


def create_sudoku_grid(
    grid,
    given_cells,
    selected_cell=None,
    highlighted_cells=None,
    completed_highlighted_cells=None,
    conflict_cells=None,
):
    """Create the Sudoku grid component"""
    if highlighted_cells is None:
        highlighted_cells = set()
    if completed_highlighted_cells is None:
        completed_highlighted_cells = set()
    if conflict_cells is None:
        conflict_cells = set()

    cells = []
    for i in range(GRID_SIZE):
        for j in range(GRID_SIZE):
            cell_value = int(grid[i, j]) if grid[i, j] != 0 else ""

            # Determine cell classes
            cell_classes = ["sudoku-cell"]
            if (i, j) in given_cells:
                cell_classes.append("given")
            if selected_cell == (i, j):
                cell_classes.append("selected")
            if (i, j) in conflict_cells:
                cell_classes.append("conflict")
            elif (i, j) in completed_highlighted_cells:
                cell_classes.append("highlight-completed")
            elif (i, j) in highlighted_cells:
                cell_classes.append("highlight-same")

            cell_content = str(cell_value) if cell_value else ""

            cell = html.Div(
                cell_content,
                id={"type": "cell", "row": i, "col": j},
                className=" ".join(cell_classes),
                n_clicks=0,
            )
            cells.append(cell)

    # Arrange cells in a grid
    rows = []
    for i in range(GRID_SIZE):
        row_cells = cells[i * GRID_SIZE : (i + 1) * GRID_SIZE]
        rows.append(html.Div(row_cells, className="sudoku-row"))

    return html.Div(rows, className="sudoku-table")


def create_number_pad():
    """Create number input pad"""
    buttons = []
    for i in NUMBERS_RANGE:
        buttons.append(
            html.Div(
                str(i), id=f"num-{i}", className="number-button", **{"data-number": i}
            )
        )

    return html.Div(buttons, className="number-pad")


def create_mobile_number_pad():
    """Create mobile-optimized number pad with 2-row layout (1-5, 6-9 + X)"""
    buttons = []
    # First row: 1-5
    for i in range(1, 6):
        buttons.append(
            html.Div(
                str(i),
                id=f"mobile-num-{i}",
                className="number-button mobile-number-button",
                **{"data-number": i},
            )
        )
    # Second row: 6-9 + X (clear button)
    for i in range(6, 10):
        buttons.append(
            html.Div(
                str(i),
                id=f"mobile-num-{i}",
                className="number-button mobile-number-button",
                **{"data-number": i},
            )
        )
    # Add X (clear) button
    buttons.append(
        html.Div(
            "×",
            id="mobile-clear-btn",
            className="number-button mobile-number-button",
        )
    )

    return html.Div(buttons, className="number-pad mobile-number-pad")


def create_mobile_controls():
    """Create mobile-optimized controls: numbers (1-5), (6-9 + X), then action buttons"""
    return html.Div(
        [
            # Number pad with integrated clear button
            create_mobile_number_pad(),
            # Action buttons row - Undo, Hint, Check, Solve
            html.Div(
                [
                    html.Div(
                        "Undo",
                        id="mobile-undo-btn",
                        className="action-button mobile-action-button",
                    ),
                    dmc.Button(
                        "Hint",
                        id="mobile-hint-btn",
                        variant="outline",
                        className="mobile-action-button",
                    ),
                    dmc.Button(
                        "Check",
                        id="mobile-validate-btn",
                        variant="outline",
                        className="mobile-action-button",
                    ),
                    dmc.Button(
                        "Solve",
                        id="mobile-solve-btn",
                        variant="outline",
                        color="red",
                        className="mobile-action-button",
                    ),
                ],
                className="mobile-action-buttons",
            ),
        ],
        className="mobile-controls",
    )


def create_side_panel():
    """Create the side panel with controls and stats (desktop only)"""
    return html.Div(
        [
            html.H3("Game Controls"),
            # Number pad
            create_number_pad(),
            # Action buttons
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                "×",
                                id="clear-btn",
                                className="action-button",
                            ),
                            html.Div(
                                "Undo",
                                id="undo-btn",
                                className="action-button",
                            ),
                        ],
                        style={
                            "display": "grid",
                            "grid-template-columns": "1fr 1fr",
                            "gap": "0.5rem",
                            "margin": "0.5rem 0",
                        },
                    ),
                    dmc.Space(h=2),
                    dmc.Button(
                        "Hint", id="hint-btn", variant="outline", fullWidth=True
                    ),
                    dmc.Button(
                        "Check", id="validate-btn", variant="outline", fullWidth=True
                    ),
                    dmc.Button(
                        "Solve",
                        id="solve-btn",
                        variant="outline",
                        fullWidth=True,
                        color="red",
                    ),
                ],
                className="action-buttons",
            ),
        ],
        className="side-panel",
    )


# App layout
app.layout = dmc.MantineProvider(
    html.Div(
        [
            dcc.Store(
                id="game-state",
                data=create_new_game_state(puzzle, solution, given_cells, "medium"),
            ),
            # Victory celebration overlay
            html.Div(
                [
                    html.Div(
                        [
                            html.Div("🎉", className="victory-emoji"),
                            html.H1("Congratulations!", className="victory-title"),
                            html.P(
                                "You solved the puzzle!", className="victory-subtitle"
                            ),
                            html.Div(
                                [
                                    html.Div(className="confetti-piece"),
                                    html.Div(className="confetti-piece"),
                                    html.Div(className="confetti-piece"),
                                    html.Div(className="confetti-piece"),
                                    html.Div(className="confetti-piece"),
                                    html.Div(className="confetti-piece"),
                                    html.Div(className="confetti-piece"),
                                    html.Div(className="confetti-piece"),
                                    html.Div(className="confetti-piece"),
                                    html.Div(className="confetti-piece"),
                                ],
                                className="confetti-container",
                            ),
                            dmc.Button(
                                "New Game",
                                id="victory-new-game-btn",
                                size="lg",
                                className="victory-button",
                            ),
                        ],
                        className="victory-content",
                    ),
                ],
                id="victory-overlay",
                className="victory-overlay hidden",
            ),
            # Main game area
            html.Div(
                [
                    # Game board and controls container
                    html.Div(
                        [
                            # Sudoku grid container
                            html.Div(
                                [
                                    # Game controls (difficulty and new game buttons)
                                    html.Div(
                                        [
                                            html.Div(
                                                [
                                                    dmc.Menu(
                                                        [
                                                            dmc.MenuTarget(
                                                                dmc.Button(
                                                                    [
                                                                        DashIconify(
                                                                            icon="mdi:cog",
                                                                            width=16,
                                                                            style={
                                                                                "marginRight": "8px"
                                                                            },
                                                                        ),
                                                                        "New Game",
                                                                    ],
                                                                    id="new-game-menu-button",
                                                                    variant="filled",
                                                                )
                                                            ),
                                                            dmc.MenuDropdown(
                                                                [
                                                                    dmc.MenuItem(
                                                                        "Easy",
                                                                        id={
                                                                            "type": "new-game-item",
                                                                            "difficulty": "easy",
                                                                        },
                                                                    ),
                                                                    dmc.MenuItem(
                                                                        "Medium",
                                                                        id={
                                                                            "type": "new-game-item",
                                                                            "difficulty": "medium",
                                                                        },
                                                                    ),
                                                                    dmc.MenuItem(
                                                                        "Hard",
                                                                        id={
                                                                            "type": "new-game-item",
                                                                            "difficulty": "hard",
                                                                        },
                                                                    ),
                                                                ]
                                                            ),
                                                        ],
                                                        width=130,
                                                    ),
                                                    dmc.Button(
                                                        "Reset",
                                                        id="reset-btn",
                                                        variant="outline",
                                                    ),
                                                    # Hidden store for current difficulty
                                                    dcc.Store(
                                                        id="current-difficulty-store",
                                                        data="medium",
                                                    ),
                                                ],
                                                className="control-group",
                                            ),
                                        ],
                                        className="control-row",
                                    ),
                                    dmc.Space(h=15),
                                    html.Div(id="sudoku-grid-container"),
                                ],
                                className="sudoku-game-card",
                            ),
                            # Desktop side panel (hidden on mobile)
                            create_side_panel(),
                        ],
                        className="game-container",
                    ),
                    # Mobile controls (hidden on desktop)
                    create_mobile_controls(),
                ],
                className="main-game-area",
            ),
        ],
        className="sudoku-app",
    )
)


# Callback to update the grid display
@callback(Output("sudoku-grid-container", "children"), Input("game-state", "data"))
def update_grid_display(game_state):
    if not game_state:
        return html.Div()

    grid = np.array(game_state["grid"])
    given_cells = set(tuple(cell) for cell in game_state["given_cells"])
    selected_cell = (
        tuple(game_state["selected_cell"]) if game_state["selected_cell"] else None
    )
    highlighted_cells = set(tuple(cell) for cell in game_state["highlighted_cells"])
    completed_highlighted_cells = set(
        tuple(cell) for cell in game_state.get("completed_highlighted_cells", [])
    )
    conflict_cells = set(tuple(cell) for cell in game_state.get("conflict_cells", []))

    return create_sudoku_grid(
        grid,
        given_cells,
        selected_cell,
        highlighted_cells,
        completed_highlighted_cells,
        conflict_cells,
    )


# Callback for cell selection and highlighting
@callback(
    Output("game-state", "data", allow_duplicate=True),
    Input({"type": "cell", "row": dash.ALL, "col": dash.ALL}, "n_clicks"),
    State("game-state", "data"),
    prevent_initial_call=True,
)
def handle_cell_click(n_clicks_list, game_state):
    if not any(n_clicks_list) or not game_state:
        return game_state

    # Find which cell was clicked
    clicked_idx = None
    for i, clicks in enumerate(n_clicks_list):
        if clicks and clicks > 0:
            clicked_idx = i
            break

    if clicked_idx is None:
        return game_state

    # Calculate row and col from index
    row = clicked_idx // GRID_SIZE
    col = clicked_idx % GRID_SIZE

    # Update selected cell
    game_state["selected_cell"] = [row, col]

    # Update highlighted cells using helper function
    grid = np.array(game_state["grid"])
    cell_value = grid[row, col]

    highlighted_cells, completed_highlighted_cells = update_highlighting(
        grid, cell_value
    )

    game_state["highlighted_cells"] = highlighted_cells
    game_state["completed_highlighted_cells"] = completed_highlighted_cells
    game_state["conflict_cells"] = []  # Clear conflicts when selecting a new cell

    return game_state


# Callback for number input (desktop and mobile)
@callback(
    Output("game-state", "data", allow_duplicate=True),
    [Input(f"num-{i}", "n_clicks") for i in NUMBERS_RANGE]
    + [Input(f"mobile-num-{i}", "n_clicks") for i in NUMBERS_RANGE],
    State("game-state", "data"),
    prevent_initial_call=True,
)
def handle_number_input(*args):
    game_state = args[-1]  # Last argument is the state

    if not game_state or not game_state["selected_cell"]:
        return game_state

    # Use callback context to determine which button was clicked
    if not ctx.triggered:
        return game_state

    button_id = ctx.triggered[0]["prop_id"].split(".")[0]

    # Extract number from button ID (e.g., "num-4" or "mobile-num-4" -> 4)
    if button_id.startswith("num-"):
        try:
            number = int(button_id.split("-")[1])
        except (IndexError, ValueError):
            return game_state
    elif button_id.startswith("mobile-num-"):
        try:
            number = int(button_id.split("-")[2])
        except (IndexError, ValueError):
            return game_state
    else:
        return game_state

    row, col = game_state["selected_cell"]
    given_cells = set(tuple(cell) for cell in game_state["given_cells"])

    # Don't allow editing given cells
    if (row, col) in given_cells:
        return game_state

    # Update the grid
    grid = np.array(game_state["grid"])

    # Save move to history for undo functionality
    old_value = int(grid[row, col])
    if "move_history" not in game_state:
        game_state["move_history"] = []

    # Only save to history if the value is actually changing
    if old_value != number:
        game_state["move_history"].append(
            {"row": row, "col": col, "old_value": old_value, "new_value": number}
        )

    # Place number
    grid[row, col] = number
    game_state["grid"] = grid.tolist()

    # Update highlighted cells using helper function
    highlighted_cells, completed_highlighted_cells = update_highlighting(grid, number)
    game_state["highlighted_cells"] = highlighted_cells
    game_state["completed_highlighted_cells"] = completed_highlighted_cells

    return game_state


# Callback for undo (desktop and mobile)
@callback(
    Output("game-state", "data", allow_duplicate=True),
    Input("undo-btn", "n_clicks"),
    Input("mobile-undo-btn", "n_clicks"),
    State("game-state", "data"),
    prevent_initial_call=True,
)
def handle_undo(n_clicks_desktop, n_clicks_mobile, game_state):
    if (
        (n_clicks_desktop or n_clicks_mobile)
        and game_state
        and game_state.get("move_history")
    ):
        # Get the last move
        last_move = game_state["move_history"].pop()

        # Revert the move
        grid = np.array(game_state["grid"])
        grid[last_move["row"], last_move["col"]] = last_move["old_value"]
        game_state["grid"] = grid.tolist()

        # Update highlighted cells using helper function
        cell_value = last_move["old_value"]
        highlighted_cells, completed_highlighted_cells = update_highlighting(
            grid, cell_value
        )
        game_state["highlighted_cells"] = highlighted_cells
        game_state["completed_highlighted_cells"] = completed_highlighted_cells

    return game_state


# Callback for clear selected cell (desktop and mobile)
@callback(
    Output("game-state", "data", allow_duplicate=True),
    Input("clear-btn", "n_clicks"),
    Input("mobile-clear-btn", "n_clicks"),
    State("game-state", "data"),
    prevent_initial_call=True,
)
def handle_clear_selected(n_clicks_desktop, n_clicks_mobile, game_state):
    if (
        (n_clicks_desktop or n_clicks_mobile)
        and game_state
        and game_state.get("selected_cell")
    ):
        row, col = game_state["selected_cell"]
        given_cells = set(tuple(cell) for cell in game_state["given_cells"])

        # Don't allow clearing given cells
        if (row, col) not in given_cells:
            grid = np.array(game_state["grid"])
            old_value = int(grid[row, col])

            # Save move to history only if there was a value to clear
            if old_value != 0:
                if "move_history" not in game_state:
                    game_state["move_history"] = []
                game_state["move_history"].append(
                    {"row": row, "col": col, "old_value": old_value, "new_value": 0}
                )

            # Clear the cell (even if already empty for consistent behavior)
            grid[row, col] = 0
            game_state["grid"] = grid.tolist()
            game_state["highlighted_cells"] = []
            game_state["completed_highlighted_cells"] = []

    return game_state


# Callback for new game with difficulty selection
@callback(
    [
        Output("game-state", "data", allow_duplicate=True),
        Output("current-difficulty-store", "data"),
    ],
    Input({"type": "new-game-item", "difficulty": dash.ALL}, "n_clicks"),
    State("current-difficulty-store", "data"),
    prevent_initial_call=True,
)
def handle_new_game_selection(n_clicks_list, current_difficulty):
    if not any(n_clicks_list):
        return dash.no_update, dash.no_update

    # Find which difficulty was clicked
    ctx_id = ctx.triggered_id
    if ctx_id and "difficulty" in ctx_id:
        difficulty = ctx_id["difficulty"]

        # Load new game with selected difficulty
        puzzle, solution, given_cells = game_loader.load_next_game(difficulty)
        new_game_state = create_new_game_state(
            puzzle, solution, given_cells, difficulty
        )

        return new_game_state, difficulty

    return dash.no_update, dash.no_update


# Callback for reset
@callback(
    Output("game-state", "data", allow_duplicate=True),
    Input("reset-btn", "n_clicks"),
    State("game-state", "data"),
    prevent_initial_call=True,
)
def reset_puzzle(n_clicks, game_state):
    if n_clicks and game_state:
        # Reset to original puzzle state
        grid = np.array(game_state["solution"])
        given_cells = set(tuple(cell) for cell in game_state["given_cells"])

        # Clear non-given cells
        for i in range(GRID_SIZE):
            for j in range(GRID_SIZE):
                if (i, j) not in given_cells:
                    grid[i, j] = 0

        game_state["grid"] = grid.tolist()
        game_state["selected_cell"] = None
        game_state["highlighted_cells"] = []
        game_state["completed_highlighted_cells"] = []
        game_state["completed"] = False
        game_state["start_time"] = datetime.now().isoformat()
        game_state["move_history"] = []

    return game_state


# Callback for hint (desktop and mobile)
@callback(
    Output("game-state", "data", allow_duplicate=True),
    Input("hint-btn", "n_clicks"),
    Input("mobile-hint-btn", "n_clicks"),
    State("game-state", "data"),
    prevent_initial_call=True,
)
def provide_hint(n_clicks_desktop, n_clicks_mobile, game_state):
    if (n_clicks_desktop or n_clicks_mobile) and game_state:
        grid = np.array(game_state["grid"])
        solution = np.array(game_state["solution"])
        given_cells = set(tuple(cell) for cell in game_state["given_cells"])

        # Find empty cells
        empty_cells = [
            (i, j)
            for i in range(GRID_SIZE)
            for j in range(GRID_SIZE)
            if grid[i, j] == 0 and (i, j) not in given_cells
        ]

        if empty_cells:
            # Pick a random empty cell and fill it
            import random

            row, col = random.choice(empty_cells)
            grid[row, col] = solution[row, col]
            game_state["grid"] = grid.tolist()

            # Highlight the hint cell
            game_state["selected_cell"] = [row, col]
            game_state["highlighted_cells"] = [[row, col]]

    return game_state


# Callback for validate (desktop and mobile)
@callback(
    Output("game-state", "data", allow_duplicate=True),
    Input("validate-btn", "n_clicks"),
    Input("mobile-validate-btn", "n_clicks"),
    State("game-state", "data"),
    prevent_initial_call=True,
)
def validate_puzzle(n_clicks_desktop, n_clicks_mobile, game_state):
    if (n_clicks_desktop or n_clicks_mobile) and game_state:
        grid = np.array(game_state["grid"])
        given_cells = set(tuple(cell) for cell in game_state["given_cells"])
        conflict_cells = []

        # Check each filled cell for conflicts (excluding given cells)
        for row in range(GRID_SIZE):
            for col in range(GRID_SIZE):
                if grid[row, col] != 0 and (row, col) not in given_cells:
                    cell_value = grid[row, col]

                    # Check row conflicts
                    row_conflicts = np.where(grid[row, :] == cell_value)[0]
                    if len(row_conflicts) > 1:
                        for conflict_col in row_conflicts:
                            # Only add non-given cells to conflicts
                            if (row, conflict_col) not in given_cells:
                                conflict_cells.append([row, conflict_col])

                    # Check column conflicts
                    col_conflicts = np.where(grid[:, col] == cell_value)[0]
                    if len(col_conflicts) > 1:
                        for conflict_row in col_conflicts:
                            # Only add non-given cells to conflicts
                            if (conflict_row, col) not in given_cells:
                                conflict_cells.append([conflict_row, col])

                    # Check 3x3 box conflicts
                    box_row, box_col = BOX_SIZE * (row // BOX_SIZE), BOX_SIZE * (
                        col // BOX_SIZE
                    )
                    box = grid[
                        box_row : box_row + BOX_SIZE, box_col : box_col + BOX_SIZE
                    ]
                    box_positions = []
                    for i in range(BOX_SIZE):
                        for j in range(BOX_SIZE):
                            if box[i, j] == cell_value:
                                # Only add non-given cells to conflicts
                                if (box_row + i, box_col + j) not in given_cells:
                                    box_positions.append([box_row + i, box_col + j])

                    if len(box_positions) > 1:
                        conflict_cells.extend(box_positions)

        # Remove duplicates and store in game state
        unique_conflicts = []
        for cell in conflict_cells:
            if cell not in unique_conflicts:
                unique_conflicts.append(cell)

        game_state["conflict_cells"] = unique_conflicts

        # Clear other highlighting when showing conflicts
        if unique_conflicts:
            game_state["highlighted_cells"] = []
            game_state["completed_highlighted_cells"] = []

    return game_state


# Callback for solve (desktop and mobile)
@callback(
    Output("game-state", "data", allow_duplicate=True),
    Input("solve-btn", "n_clicks"),
    Input("mobile-solve-btn", "n_clicks"),
    State("game-state", "data"),
    prevent_initial_call=True,
)
def solve_puzzle(n_clicks_desktop, n_clicks_mobile, game_state):
    if (n_clicks_desktop or n_clicks_mobile) and game_state:
        game_state["grid"] = game_state["solution"]
        game_state["completed"] = True
        game_state["selected_cell"] = None
        game_state["highlighted_cells"] = []
        game_state["completed_highlighted_cells"] = []

    return game_state


# Check if puzzle is completed
@callback(
    Output("game-state", "data", allow_duplicate=True),
    Input("game-state", "data"),
    prevent_initial_call=True,
)
def check_completion(game_state):
    if game_state:
        grid = np.array(game_state["grid"])
        filled = np.count_nonzero(grid)

        # Check if completed
        if filled == GRID_SIZE * GRID_SIZE:
            game_state["completed"] = True

    return game_state


# Victory overlay visibility callback
@callback(
    Output("victory-overlay", "className"),
    Input("game-state", "data"),
    prevent_initial_call=True,
)
def show_victory_overlay(game_state):
    if game_state and game_state.get("completed", False):
        return "victory-overlay"
    return "victory-overlay hidden"


# Victory new game button callback
@callback(
    Output("game-state", "data", allow_duplicate=True),
    Input("victory-new-game-btn", "n_clicks"),
    State("game-state", "data"),
    prevent_initial_call=True,
)
def victory_new_game(n_clicks, game_state):
    if n_clicks and game_state:
        # Load new game with same difficulty
        difficulty = game_state.get("difficulty", "medium")
        puzzle, solution, given_cells = game_loader.load_next_game(difficulty)

        return create_new_game_state(puzzle, solution, given_cells, difficulty)

    return game_state


# Keyboard input support and mobile difficulty labels
app.clientside_callback(
    """
    function(n_intervals) {
        // Keyboard support
        document.addEventListener('keydown', function(event) {
            const key = event.key;
            if (key >= '1' && key <= '9') {
                // Try desktop number button first, then mobile
                let numButton = document.getElementById('num-' + key);
                if (!numButton) {
                    numButton = document.getElementById('mobile-num-' + key);
                }
                if (numButton) {
                    numButton.click();
                }
            } else if (key === 'Delete' || key === 'Backspace' || key === '0') {
                // Try desktop clear button first, then mobile
                let clearButton = document.getElementById('clear-btn');
                if (!clearButton) {
                    clearButton = document.getElementById('mobile-clear-btn');
                }
                if (clearButton) {
                    clearButton.click();
                }
            }
        });
        
        return window.dash_clientside.no_update;
    }
    """,
    Output("sudoku-grid-container", "style"),
    Input("sudoku-grid-container", "children"),
)

if __name__ == "__main__":
    app.run(debug=True)
