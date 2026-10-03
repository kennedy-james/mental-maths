import curses
import math

from ..models import Question, percent
from .helpers import (
    DOWN_KEYS,
    ENTER_KEYS,
    ESC,
    GREEN,
    QUIT_KEYS,
    RED,
    UP_KEYS,
    VIZ_KEYS,
    YELLOW,
    addstr,
    begin_frame,
    center,
    footer,
    refresh,
    title,
)
from .viz import show_viz


def _q_line(q: Question) -> str:
    line = f"[{'+' if q.correct else '-'}]  {q.display} = {q.answer_str}"
    if not q.correct:
        line += f"  (you: {q.user_answer})"
    return line


def show_results(
    stdscr,
    questions: list[Question],
    sessions: list,
    guest_mode: bool = False,
    save_error: bool = False,
) -> str:
    stdscr.nodelay(False)
    total = len(questions)
    correct = sum(1 for q in questions if q.correct)
    pct = percent(correct, total)
    lines = [_q_line(q) for q in questions]
    col_w = max(map(len, lines), default=0) + 4
    row_scroll = 0

    while True:
        h, w = begin_frame(stdscr)
        title(stdscr, 1, " RESULTS ")
        center(stdscr, 3, f"{correct} / {total} correct  ({pct:.0f}%)", curses.A_BOLD)
        if guest_mode:
            center(
                stdscr, 4, "(guest mode — results not saved)", curses.color_pair(YELLOW)
            )
        elif save_error:
            center(
                stdscr,
                4,
                "(warning: session could not be saved)",
                curses.color_pair(RED),
            )

        list_y = 5
        list_h = max(1, h - 8)
        num_cols = max(1, (w - 4) // col_w)
        num_rows = math.ceil(total / num_cols)
        max_scroll = max(0, num_rows - list_h)
        row_scroll = min(row_scroll, max_scroll)

        for vr in range(min(list_h, num_rows - row_scroll)):
            for col in range(num_cols):
                q_idx = col * num_rows + vr + row_scroll
                if q_idx >= total:
                    break
                color = curses.color_pair(GREEN if questions[q_idx].correct else RED)
                addstr(stdscr, list_y + vr, 2 + col * col_w, lines[q_idx], color)

        if max_scroll:
            bar_h = max(1, round(list_h / num_rows * list_h))
            bar_top = list_y + round(row_scroll / max_scroll * (list_h - bar_h))
            for dy in range(bar_h):
                addstr(stdscr, bar_top + dy, w - 2, "|")

        hint = "R again   M menu   V performance   Q quit"
        footer(stdscr, hint + ("   j/k scroll" if max_scroll else ""))
        refresh(stdscr)

        key = stdscr.getch()
        if key in (*QUIT_KEYS, ESC):
            return "quit"
        elif key in (*ENTER_KEYS, ord("r"), ord("R")):
            return "again"
        elif key in (ord("m"), ord("M")):
            return "menu"
        elif key in VIZ_KEYS:
            show_viz(stdscr, sessions)
        elif key in UP_KEYS:
            row_scroll = max(0, row_scroll - 1)
        elif key in DOWN_KEYS:
            row_scroll = min(max_scroll, row_scroll + 1)
