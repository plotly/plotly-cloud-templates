"""
Game loader module for pre-generated Sudoku games.
Replaces the on-the-fly generation system with file-based loading.
"""

import json
import os
import random
from typing import Dict, List, Optional, Tuple

import numpy as np


class GameLoader:
    """Handles loading and managing pre-generated Sudoku games"""

    def __init__(self, games_directory: str = "games"):
        self.games_directory = games_directory
        self._game_indices = {"easy": 0, "medium": 0, "hard": 0}
        self._available_games = self._load_available_games()

    def _load_available_games(self) -> Dict[str, List[str]]:
        """Load list of available game files for each difficulty"""
        available = {"easy": [], "medium": [], "hard": []}

        for difficulty in ["easy", "medium", "hard"]:
            difficulty_dir = os.path.join(self.games_directory, difficulty)
            if os.path.exists(difficulty_dir):
                files = [f for f in os.listdir(difficulty_dir) if f.endswith(".json")]
                available[difficulty] = sorted(files)

        return available

    def get_available_game_count(self, difficulty: str) -> int:
        """Get the number of available games for a difficulty"""
        return len(self._available_games.get(difficulty, []))

    def load_game(
        self, difficulty: str, game_index: Optional[int] = None
    ) -> Tuple[np.ndarray, np.ndarray, set]:
        """
        Load a specific game by difficulty and index.

        Args:
            difficulty: The difficulty level ("easy", "medium", "hard")
            game_index: Specific game index (0-based). If None, uses current index for difficulty.

        Returns:
            Tuple of (puzzle, solution, given_cells_set)
        """
        if difficulty not in self._available_games:
            raise ValueError(f"Invalid difficulty: {difficulty}")

        available_files = self._available_games[difficulty]
        if not available_files:
            raise FileNotFoundError(f"No games available for difficulty: {difficulty}")

        # Use provided index or current index for this difficulty
        if game_index is not None:
            if game_index < 0 or game_index >= len(available_files):
                raise IndexError(
                    f"Game index {game_index} out of range for {difficulty} (0-{len(available_files)-1})"
                )
            file_index = game_index
        else:
            file_index = self._game_indices[difficulty]

        # Load the game file
        filename = available_files[file_index]
        filepath = os.path.join(self.games_directory, difficulty, filename)

        with open(filepath, "r") as f:
            game_data = json.load(f)

        # Convert to numpy arrays and set
        puzzle = np.array(game_data["puzzle"], dtype=int)
        solution = np.array(game_data["solution"], dtype=int)
        given_cells = set(tuple(cell) for cell in game_data["given_cells"])

        return puzzle, solution, given_cells

    def load_next_game(self, difficulty: str) -> Tuple[np.ndarray, np.ndarray, set]:
        """
        Load the next game in sequence for the given difficulty.
        Cycles back to the first game after the last one.

        Returns:
            Tuple of (puzzle, solution, given_cells_set)
        """
        if difficulty not in self._available_games:
            raise ValueError(f"Invalid difficulty: {difficulty}")

        available_files = self._available_games[difficulty]
        if not available_files:
            raise FileNotFoundError(f"No games available for difficulty: {difficulty}")

        # Load current game
        puzzle, solution, given_cells = self.load_game(difficulty)

        # Advance to next game (cycle back to 0 if at end)
        self._game_indices[difficulty] = (self._game_indices[difficulty] + 1) % len(
            available_files
        )

        return puzzle, solution, given_cells

    def load_random_game(self, difficulty: str) -> Tuple[np.ndarray, np.ndarray, set]:
        """
        Load a random game for the given difficulty.

        Returns:
            Tuple of (puzzle, solution, given_cells_set)
        """
        if difficulty not in self._available_games:
            raise ValueError(f"Invalid difficulty: {difficulty}")

        available_files = self._available_games[difficulty]
        if not available_files:
            raise FileNotFoundError(f"No games available for difficulty: {difficulty}")

        # Pick a random game
        random_index = random.randint(0, len(available_files) - 1)
        return self.load_game(difficulty, random_index)

    def get_current_game_info(self, difficulty: str) -> Dict:
        """Get information about the current game for a difficulty"""
        if difficulty not in self._available_games:
            raise ValueError(f"Invalid difficulty: {difficulty}")

        available_files = self._available_games[difficulty]
        if not available_files:
            return {"current_index": 0, "total_games": 0, "current_file": None}

        current_index = self._game_indices[difficulty]
        current_file = available_files[current_index]

        return {
            "current_index": current_index + 1,  # 1-based for display
            "total_games": len(available_files),
            "current_file": current_file,
        }

    def reset_game_index(self, difficulty: str):
        """Reset the game index for a difficulty back to 0"""
        if difficulty in self._game_indices:
            self._game_indices[difficulty] = 0

    def set_game_index(self, difficulty: str, index: int):
        """Set the current game index for a difficulty"""
        if difficulty not in self._available_games:
            raise ValueError(f"Invalid difficulty: {difficulty}")

        available_files = self._available_games[difficulty]
        if not available_files:
            raise FileNotFoundError(f"No games available for difficulty: {difficulty}")

        if index < 0 or index >= len(available_files):
            raise IndexError(
                f"Game index {index} out of range for {difficulty} (0-{len(available_files)-1})"
            )

        self._game_indices[difficulty] = index


# Global game loader instance
game_loader = GameLoader()
