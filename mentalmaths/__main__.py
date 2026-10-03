import contextlib
import curses

from .app import main


def run() -> None:
    with contextlib.suppress(KeyboardInterrupt):
        curses.wrapper(main)


if __name__ == "__main__":
    run()
