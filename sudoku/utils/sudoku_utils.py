from datetime import datetime

import numpy as np

# Constants
GRID_SIZE = 9
BOX_SIZE = 3
NUMBERS_RANGE = range(1, 10)


def is_number_completed(grid, number):
    """Check if all 9 instances of a number are filled in the grid"""
    count = np.sum(grid == number)
    return count == GRID_SIZE


def update_highlighting(grid, cell_value):
    """Update highlighted and completed highlighted cells based on cell value"""
    highlighted_cells = []
    completed_highlighted_cells = []

    if cell_value != 0:
        # Check if this number is completed (all 9 instances filled)
        if is_number_completed(grid, cell_value):
            # Use completion highlighting (brighter orange)
            for i in range(GRID_SIZE):
                for j in range(GRID_SIZE):
                    if grid[i, j] == cell_value:
                        completed_highlighted_cells.append([i, j])
        else:
            # Use regular highlighting
            for i in range(GRID_SIZE):
                for j in range(GRID_SIZE):
                    if grid[i, j] == cell_value:
                        highlighted_cells.append([i, j])

    return highlighted_cells, completed_highlighted_cells


def create_new_game_state(puzzle, solution, given_cells, difficulty):
    """Create a new game state dictionary"""
    return {
        "grid": puzzle.tolist(),
        "solution": solution.tolist(),
        "given_cells": list(given_cells),
        "selected_cell": None,
        "highlighted_cells": [],
        "completed_highlighted_cells": [],
        "conflict_cells": [],
        "difficulty": difficulty,
        "start_time": datetime.now().isoformat(),
        "completed": False,
        "move_history": [],
    }
