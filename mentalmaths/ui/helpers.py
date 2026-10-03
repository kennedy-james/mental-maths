import contextlib
import curses

GREEN, CYAN, RED, YELLOW = 1, 2, 3, 4

ESC = 27
ENTER_KEYS = (10, 13, curses.KEY_ENTER)
UP_KEYS = (curses.KEY_UP, ord("k"))
DOWN_KEYS = (curses.KEY_DOWN, ord("j"))
LEFT_KEYS = (curses.KEY_LEFT, ord("h"))
RIGHT_KEYS = (curses.KEY_RIGHT, ord("l"))
QUIT_KEYS = (ord("q"), ord("Q"))
VIZ_KEYS = (ord("v"), ord("V"))
SELECTED_ATTR = curses.A_REVERSE | curses.A_BOLD


def init_colours() -> None:
    if not curses.has_colors():
        return
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(GREEN, curses.COLOR_GREEN, -1)
    curses.init_pair(CYAN, curses.COLOR_CYAN, -1)
    curses.init_pair(RED, curses.COLOR_RED, -1)
    curses.init_pair(YELLOW, curses.COLOR_YELLOW, -1)


def hide_cursor() -> None:
    # Some terminals cannot hide the cursor; that is purely cosmetic.
    with contextlib.suppress(curses.error):
        curses.curs_set(0)


def refresh(stdscr) -> None:
    stdscr.noutrefresh()
    curses.doupdate()


def begin_frame(stdscr) -> tuple[int, int]:
    stdscr.erase()
    h, w = stdscr.getmaxyx()
    with contextlib.suppress(curses.error):
        stdscr.box()
    return h, w


def addstr(stdscr, y: int, x: int, text: str, attr: int = 0) -> None:
    _, w = stdscr.getmaxyx()
    with contextlib.suppress(curses.error):
        stdscr.addstr(y, x, text[: max(0, w - x)], attr)


def center(stdscr, y: int, text: str, attr: int = 0) -> None:
    _, w = stdscr.getmaxyx()
    addstr(stdscr, y, max(0, (w - len(text)) // 2), text, attr)


def title(stdscr, y: int, text: str) -> None:
    center(stdscr, y, text, curses.A_BOLD | curses.color_pair(CYAN))


def footer(stdscr, text: str) -> None:
    h, _ = stdscr.getmaxyx()
    center(stdscr, h - 2, text, curses.A_DIM)


def move_cursor(cursor: int, key: int, n: int) -> int:
    if key in UP_KEYS:
        return (cursor - 1) % n
    if key in DOWN_KEYS:
        return (cursor + 1) % n
    return cursor


def confirm_quit(stdscr) -> bool:
    h, w = stdscr.getmaxyx()
    msg = "  Quit?   y / n  "
    bw = len(msg) + 4
    bx = max(0, (w - bw) // 2)
    by = h // 2 - 1
    for dy in range(3):
        addstr(stdscr, by + dy, bx, " " * bw, curses.A_REVERSE)
    addstr(stdscr, by + 1, bx + 2, msg, curses.A_REVERSE | curses.A_BOLD)
    refresh(stdscr)
    stdscr.nodelay(False)
    while True:
        key = stdscr.getch()
        if key in (ord("y"), ord("Y")):
            return True
        if key in (ord("n"), ord("N"), ESC):
            return False
