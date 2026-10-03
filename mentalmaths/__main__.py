import curses

from .app import main


def run() -> None:
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass  # Ctrl+C exits quietly instead of printing a traceback


if __name__ == "__main__":
    run()
