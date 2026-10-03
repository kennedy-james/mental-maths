import contextlib
import curses
import sys

from .app import main


def run() -> None:
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        sys.exit("mental-maths needs an interactive terminal; run it directly in one.")
    with contextlib.suppress(KeyboardInterrupt):
        curses.wrapper(main)


if __name__ == "__main__":
    run()
