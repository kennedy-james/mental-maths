from pathlib import Path

DATA_FILE = Path.home() / ".mental-maths.json"
OPERATIONS = ["Addition", "Subtraction", "Multiplication", "Division"]
TIME_OPTIONS = [
    ("30 seconds", 30),
    ("1 minute", 60),
    ("2 minutes", 120),
    ("5 minutes", 300),
    ("10 minutes", 600),
]

DIGITS_RANGE = (1, 4)
DECIMALS_RANGE = (0, 3)
OPERAND2_MIN = {"Multiplication": 1, "Division": 2}
OPERAND2_NAMES = {"Multiplication": "Multiplier", "Division": "Divisor"}
OPERAND2_MAX = 99


class QuitGame(Exception):
    pass
