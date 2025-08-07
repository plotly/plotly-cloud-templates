import dash
from dash import (
    dcc,
    html,
    Input,
    Output,
    State,
    callback_context,
    ALL,
    clientside_callback,
    ClientsideFunction,
)
import random
import string
from word_list import WORD_LIST

# Convert word list to uppercase for consistent comparisons
WORD_LIST_UPPER = [word.upper() for word in WORD_LIST]

class WordleGame:
    def __init__(self):
        self.target_word = random.choice(WORD_LIST_UPPER)
        self.guesses = []
        self.current_guess = ""
        self.game_over = False
        self.won = False
        self.max_guesses = 6

    def add_letter(self, letter):
        if len(self.current_guess) < 5 and not self.game_over:
            self.current_guess += letter.upper()
            return True
        return False

    def remove_letter(self):
        if len(self.current_guess) > 0 and not self.game_over:
            self.current_guess = self.current_guess[:-1]
            return True
        return False

    def submit_guess(self):
        if len(self.current_guess) != 5:
            return False, "Word must be 5 letters"

        # Convert current guess to uppercase for comparison
        word_upper = self.current_guess.upper()

        if word_upper not in WORD_LIST_UPPER:
            return False, "Not a valid word"

        self.guesses.append(word_upper)
        self.current_guess = ""

        if word_upper == self.target_word:
            self.won = True
            self.game_over = True
            return True, "Congratulations! You won!"
        elif len(self.guesses) >= self.max_guesses:
            self.game_over = True
            return True, f"Game over! The word was {self.target_word}"
        else:
            return True, f"Guess {len(self.guesses)}/{self.max_guesses}"

    def get_letter_status(self, guess, position):
        """Return the status of a letter: correct, present, or absent"""
        # Ensure both guess and target are uppercase for comparison
        guess_upper = guess.upper()
        target_upper = self.target_word.upper()

        if guess_upper[position] == target_upper[position]:
            return "correct"
        elif guess_upper[position] in target_upper:
            return "present"
        else:
            return "absent"

    def get_keyboard_letter_status(self, letter):
        """Get the status of a letter on the keyboard based on all guesses"""
        letter_upper = letter.upper()
        statuses = []

        for guess in self.guesses:
            guess_upper = guess.upper()
            if letter_upper in guess_upper:
                for i, char in enumerate(guess_upper):
                    if char == letter_upper:
                        statuses.append(self.get_letter_status(guess_upper, i))

        if not statuses:
            return "unused"
        elif "correct" in statuses:
            return "correct"
        elif "present" in statuses:
            return "present"
        else:
            return "absent"

    def reset_game(self):
        self.target_word = random.choice(WORD_LIST_UPPER)
        self.guesses = []
        self.current_guess = ""
        self.game_over = False
        self.won = False


# Initialize the game
game = WordleGame()

# Initialize the Dash app
app = dash.Dash(__name__)
server = app.server

# Define keyboard layout
KEYBOARD_LAYOUT = [
    ["Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P"],
    ["A", "S", "D", "F", "G", "H", "J", "K", "L"],
    ["ENTER", "Z", "X", "C", "V", "B", "N", "M", "DELETE"],
]

# Define the app layout
app.layout = html.Div(
    [
        html.Div(
            [
                html.H1("WORDLE", className="title"),
                html.P("Guess the 5-letter word in 6 tries!", className="subtitle"),
            ],
            className="header",
        ),
        # Game board
        html.Div(id="game-board", className="game-board"),
        # Action buttons
        html.Div(
            [html.Button("NEW GAME", id="new-game-btn", className="new-game-btn")],
            className="action-section",
        ),
        # Virtual keyboard
        html.Div(
            id="keyboard",
            children=[
                html.Div(
                    [
                        html.Button(
                            key,
                            id={"type": "key", "key": key},
                            className=f"key {'key-wide' if key in ['ENTER', 'DELETE'] else 'key-letter'}",
                            n_clicks=0,
                        )
                        for key in row
                    ],
                    className="keyboard-row",
                )
                for row in KEYBOARD_LAYOUT
            ],
            className="keyboard",
        ),
        # Message area
        html.Div(id="message", className="message"),
        # Hidden components for keyboard handling
        dcc.Input(
            id="keyboard-listener",
            style={"opacity": 0, "position": "absolute", "left": "-9999px"},
            autoFocus=True,
        ),
        html.Div(id="keyboard-trigger", style={"display": "none"}),
        # Hidden div to store game state
        dcc.Store(
            id="game-state",
            data={
                "target_word": game.target_word,
                "guesses": game.guesses,
                "current_guess": game.current_guess,
                "game_over": game.game_over,
                "won": game.won,
            },
        ),
    ],
    className="container",
)

# Clientside callback to handle keyboard events
app.clientside_callback(
    """
    function(value) {
        // Remove any existing event listeners to prevent duplicates
        if (window.wordleKeyboardHandler) {
            document.removeEventListener('keydown', window.wordleKeyboardHandler);
        }
        
        window.wordleKeyboardHandler = function(event) {
            const key = event.key.toUpperCase();
            const validLetters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
            
            // Prevent default behavior for game keys
            if (validLetters.includes(key) || key === 'ENTER' || key === 'BACKSPACE') {
                event.preventDefault();
            }
            
            let keyButton = null;
            
            // Find the appropriate button and trigger click
            if (validLetters.includes(key)) {
                keyButton = document.querySelector(`[id*='"key":"${key}"']`);
            } else if (key === 'ENTER') {
                keyButton = document.querySelector(`[id*='"key":"ENTER"']`);
            } else if (key === 'BACKSPACE') {
                keyButton = document.querySelector(`[id*='"key":"DELETE"']`);
            }
            
            if (keyButton) {
                // Add visual feedback
                keyButton.classList.add('pressed');
                setTimeout(() => {
                    keyButton.classList.remove('pressed');
                }, 150);
                
                // Trigger the click
                keyButton.click();
            }
        };
        
        document.addEventListener('keydown', window.wordleKeyboardHandler);
        
        // Ensure the page stays focused for keyboard input
        document.addEventListener('click', function() {
            const listener = document.getElementById('keyboard-listener');
            if (listener) {
                setTimeout(() => listener.focus(), 100);
            }
        });
        
        return '';
    }
    """,
    Output("keyboard-trigger", "children"),
    Input("keyboard-listener", "value"),
)


# Callbacks
@app.callback(
    [
        Output("game-board", "children"),
        Output("message", "children"),
        Output("game-state", "data"),
        Output("keyboard", "children"),
    ],
    [Input({"type": "key", "key": ALL}, "n_clicks"), Input("new-game-btn", "n_clicks")],
    [State("game-state", "data")],
    prevent_initial_call=False,
)
def update_game(key_clicks, new_game_clicks, game_state):
    ctx = callback_context

    # Restore game state
    game.target_word = game_state["target_word"]
    game.guesses = game_state["guesses"]
    game.current_guess = game_state["current_guess"]
    game.game_over = game_state["game_over"]
    game.won = game_state["won"]

    message = ""

    if ctx.triggered:
        trigger_id = ctx.triggered[0]["prop_id"]

        if "new-game-btn" in trigger_id:
            game.reset_game()
            message = "New game started!"
        elif "key" in trigger_id and key_clicks:
            # Find which key was clicked by checking which click count increased
            trigger_prop = ctx.triggered[0]["prop_id"]
            if '{"key":"' in trigger_prop:
                # Extract the key from the prop_id string
                key_start = trigger_prop.find('"key":"') + 7
                key_end = trigger_prop.find('"', key_start)
                key = trigger_prop[key_start:key_end]

                if key == "ENTER":
                    success, msg = game.submit_guess()
                    message = msg
                elif key == "DELETE":
                    game.remove_letter()
                else:
                    game.add_letter(key)

    # Generate game board
    board = generate_game_board(game)

    # Generate keyboard with updated states
    keyboard = generate_keyboard(game)

    # Update game state
    new_game_state = {
        "target_word": game.target_word,
        "guesses": game.guesses,
        "current_guess": game.current_guess,
        "game_over": game.game_over,
        "won": game.won,
    }

    return board, message, new_game_state, keyboard


def generate_game_board(game):
    """Generate the visual game board"""
    rows = []

    # Create rows for guesses made
    for i, guess in enumerate(game.guesses):
        cells = []
        for j, letter in enumerate(guess):
            status = game.get_letter_status(guess, j)
            cells.append(html.Div(letter, className=f"cell {status}"))
        rows.append(html.Div(cells, className="row"))

    # Create current guess row if game is not over
    if not game.game_over and len(game.guesses) < game.max_guesses:
        cells = []
        current_row = len(game.guesses)
        for j in range(5):
            letter = game.current_guess[j] if j < len(game.current_guess) else ""
            cells.append(html.Div(letter, className="cell current"))
        rows.append(html.Div(cells, className="row"))

        # Add remaining empty rows
        for i in range(len(game.guesses) + 1, game.max_guesses):
            cells = []
            for j in range(5):
                cells.append(html.Div("", className="cell empty"))
            rows.append(html.Div(cells, className="row"))
    else:
        # Create empty rows for remaining guesses
        for i in range(len(game.guesses), game.max_guesses):
            cells = []
            for j in range(5):
                cells.append(html.Div("", className="cell empty"))
            rows.append(html.Div(cells, className="row"))

    return rows


def generate_keyboard(game):
    """Generate the virtual keyboard with letter states"""
    keyboard_rows = []

    for row in KEYBOARD_LAYOUT:
        keys = []
        for key in row:
            if key in ["ENTER", "DELETE"]:
                status_class = "key-action"
            else:
                status = game.get_keyboard_letter_status(key)
                status_class = f"key-{status}"

            keys.append(
                html.Button(
                    key,
                    id={"type": "key", "key": key},
                    className=f"key {'key-wide' if key in ['ENTER', 'DELETE'] else 'key-letter'} {status_class}",
                    n_clicks=0,
                )
            )
        keyboard_rows.append(html.Div(keys, className="keyboard-row"))

    return keyboard_rows


# CSS styles
app.index_string = """
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>Wordle Game</title>
        {%favicon%}
        {%css%}
        <style>
            body {
                font-family: 'Helvetica Neue', Arial, sans-serif;
                margin: 0;
                padding: 0;
                background-color: #f7f7f7;
                color: #333;
                user-select: none;
            }
            
            .container {
                max-width: 500px;
                margin: 0 auto;
                padding: 20px;
                text-align: center;
            }
            
            .header {
                margin-bottom: 30px;
            }
            
            .title {
                font-size: 36px;
                font-weight: bold;
                color: #333;
                margin: 0;
                letter-spacing: 2px;
            }
            
            .subtitle {
                color: #666;
                margin: 10px 0;
                font-size: 16px;
            }
            
            .game-board {
                margin: 20px 0;
                display: flex;
                flex-direction: column;
                gap: 5px;
                align-items: center;
            }
            
            .row {
                display: flex;
                gap: 5px;
            }
            
            .cell {
                width: 60px;
                height: 60px;
                border: 2px solid #d3d6da;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 24px;
                font-weight: bold;
                text-transform: uppercase;
                background-color: white;
                transition: all 0.2s ease;
            }
            
            .cell.empty {
                background-color: white;
            }
            
            .cell.current {
                background-color: white;
                border-color: #878a8c;
                animation: pulse 0.3s ease;
            }
            
            .cell.absent {
                background-color: #787c7e;
                color: white;
                border-color: #787c7e;
            }
            
            .cell.present {
                background-color: #c9b458;
                color: white;
                border-color: #c9b458;
            }
            
            .cell.correct {
                background-color: #6aaa64;
                color: white;
                border-color: #6aaa64;
            }
            
            @keyframes pulse {
                0% { transform: scale(1); }
                50% { transform: scale(1.1); }
                100% { transform: scale(1); }
            }
            
            .action-section {
                margin: 20px 0;
            }
            
            .new-game-btn {
                padding: 12px 20px;
                font-size: 16px;
                font-weight: bold;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                background-color: #787c7e;
                color: white;
                transition: background-color 0.2s;
            }
            
            .new-game-btn:hover {
                background-color: #6a6e70;
            }
            
            .keyboard {
                margin: 20px 0;
                display: flex;
                flex-direction: column;
                gap: 8px;
                align-items: center;
            }
            
            .keyboard-row {
                display: flex;
                gap: 6px;
            }
            
            .key {
                padding: 0;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 14px;
                font-weight: bold;
                display: flex;
                align-items: center;
                justify-content: center;
                transition: all 0.1s ease;
                text-transform: uppercase;
            }
            
            .key-letter {
                width: 43px;
                height: 58px;
                background-color: #d3d6da;
                color: #000;
            }
            
            .key-wide {
                height: 58px;
                padding: 0 12px;
                min-width: 65px;
                background-color: #d3d6da;
                color: #000;
                font-size: 12px;
            }
            
            .key:hover {
                transform: scale(1.05);
            }
            
                         .key:active {
                 transform: scale(0.95);
             }
             
             .key.pressed {
                 transform: scale(0.95);
                 filter: brightness(0.9);
             }
            
            .key-unused {
                background-color: #d3d6da;
                color: #000;
            }
            
            .key-absent {
                background-color: #787c7e;
                color: white;
            }
            
            .key-present {
                background-color: #c9b458;
                color: white;
            }
            
            .key-correct {
                background-color: #6aaa64;
                color: white;
            }
            
            .key-action {
                background-color: #d3d6da;
                color: #000;
            }
            
            .message {
                margin: 20px 0;
                padding: 15px;
                border-radius: 4px;
                font-size: 16px;
                font-weight: bold;
                min-height: 20px;
                background-color: #e8f5e8;
                color: #2d5a2d;
                border: 1px solid #c3e6c3;
            }
            
            @media (max-width: 600px) {
                .container {
                    padding: 10px;
                }
                
                .cell {
                    width: 50px;
                    height: 50px;
                    font-size: 20px;
                }
                
                .key-letter {
                    width: 35px;
                    height: 48px;
                    font-size: 12px;
                }
                
                .key-wide {
                    height: 48px;
                    min-width: 55px;
                    font-size: 10px;
                }
                
                .keyboard-row {
                    gap: 4px;
                }
                
                .keyboard {
                    gap: 6px;
                }
            }
        </style>
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

if __name__ == "__main__":
    app.run_server(debug=True)
