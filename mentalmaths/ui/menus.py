import curses
from dataclasses import replace
from typing import NamedTuple

from ..constants import (
    DECIMALS_RANGE,
    DIGITS_RANGE,
    OPERAND2_MAX,
    OPERAND2_MIN,
    OPERAND2_NAMES,
    TIME_OPTIONS,
    QuitGame,
)
from ..models import OpConfig
from .helpers import (
    ENTER_KEYS,
    ESC,
    GREEN,
    LEFT_KEYS,
    QUIT_KEYS,
    RIGHT_KEYS,
    SELECTED_ATTR,
    VIZ_KEYS,
    YELLOW,
    begin_frame,
    center,
    footer,
    move_cursor,
    refresh,
    title,
)
from .viz import show_viz


def _draw_options(stdscr, y0: int, options: list[str], cursor: int) -> None:
    for i, opt in enumerate(options):
        label = f"  {'>' if i == cursor else ' '}  {opt}  "
        center(stdscr, y0 + i, label, SELECTED_ATTR if i == cursor else 0)


def run_single_select(
    stdscr, heading: str, options: list[str], initial: int = 0
) -> int:
    cursor = initial
    stdscr.nodelay(False)
    while True:
        begin_frame(stdscr)
        title(stdscr, 2, heading)
        _draw_options(stdscr, 4, options, cursor)
        footer(stdscr, "j/k navigate   ENTER select   ESC back   q quit")
        refresh(stdscr)
        key = stdscr.getch()
        if key in ENTER_KEYS:
            return cursor
        elif key == ESC:
            return -1
        elif key in QUIT_KEYS:
            raise QuitGame
        else:
            cursor = move_cursor(cursor, key, len(options))


def run_multiselect(
    stdscr,
    heading: str,
    options: list[str],
    sessions: list,
    preselected: list[int] | None = None,
    guest: bool = False,
) -> tuple[list[int], bool]:
    cursor = 0
    selected: set[int] = set(preselected or [])
    stdscr.nodelay(False)
    while True:
        begin_frame(stdscr)
        title(stdscr, 1, heading)
        center(
            stdscr,
            2,
            "j/k navigate   SPACE toggle   ENTER confirm   g guest   v performance   q quit",
            curses.A_DIM,
        )
        max_opt = max(len(o) for o in options)
        for i, opt in enumerate(options):
            mark = "[X]" if i in selected else "[ ]"
            label = f"  {mark}  {opt:<{max_opt}}  "
            center(stdscr, 4 + i, label, SELECTED_ATTR if i == cursor else 0)
        confirm_attr = (
            (curses.A_BOLD | curses.color_pair(GREEN)) if selected else curses.A_DIM
        )
        center(stdscr, 4 + len(options) + 1, "[ Confirm ]", confirm_attr)
        guest_label = "[ Guest Mode: ON  ]" if guest else "[ Guest Mode: OFF ]"
        guest_attr = (
            curses.color_pair(YELLOW) | curses.A_BOLD if guest else curses.A_DIM
        )
        center(stdscr, 4 + len(options) + 2, guest_label, guest_attr)
        refresh(stdscr)
        key = stdscr.getch()
        if key == ord(" "):
            selected ^= {cursor}
        elif key in ENTER_KEYS:
            if selected:
                return sorted(selected), guest
        elif key in (ord("g"), ord("G")):
            guest = not guest
        elif key in VIZ_KEYS:
            show_viz(stdscr, sessions)
        elif key in QUIT_KEYS:
            raise QuitGame
        else:
            cursor = move_cursor(cursor, key, len(options))


class Row(NamedTuple):
    label: str
    value: int
    min_val: int
    max_val: int
    field: str


def _build_rows(cfg: OpConfig) -> list[Row]:
    op = cfg.operation
    if op in OPERAND2_NAMES:
        name = OPERAND2_NAMES[op]
        lo, hi = cfg.operand2_lo, cfg.operand2_hi
        rows = [
            Row(f"{name} min", lo, OPERAND2_MIN[op], hi, "operand2_lo"),
            Row(f"{name} max", hi, lo, OPERAND2_MAX, "operand2_hi"),
        ]
    else:
        rows = [Row("Integer digits", cfg.digits, *DIGITS_RANGE, "digits")]
    rows.append(Row("Decimal places", cfg.decimals, *DECIMALS_RANGE, "decimals"))
    if op == "Subtraction":
        rows.append(Row("Allow negatives", cfg.allow_negative, 0, 1, "allow_negative"))
    return rows


def run_op_config(stdscr, cfg: OpConfig) -> OpConfig | None:
    field_idx = 0
    stdscr.nodelay(False)
    while True:
        rows = _build_rows(cfg)
        begin_frame(stdscr)
        title(stdscr, 2, f"Configure: {cfg.operation}")
        max_label = max(len(r.label) for r in rows)
        for i, row in enumerate(rows):
            left = "<" if row.value > row.min_val else " "
            right = ">" if row.value < row.max_val else " "
            if row.field == "allow_negative":
                val_str = "Yes" if row.value else "No"
            else:
                val_str = f"{row.value:>2}"
            line = f"  {row.label:<{max_label}}   {left} {val_str} {right}  "
            center(stdscr, 5 + i * 2, line, SELECTED_ATTR if i == field_idx else 0)
        footer(
            stdscr,
            "j/k switch field   h/l change value   ENTER confirm   ESC cancel   q quit",
        )
        refresh(stdscr)
        key = stdscr.getch()
        if key in LEFT_KEYS or key in RIGHT_KEYS:
            row = rows[field_idx]
            delta = -1 if key in LEFT_KEYS else 1
            value = max(row.min_val, min(row.max_val, row.value + delta))
            # type(row.value) keeps allow_negative a bool.
            cfg = replace(cfg, **{row.field: type(row.value)(value)})
        elif key in ENTER_KEYS:
            return cfg
        elif key == ESC:
            return None
        elif key in QUIT_KEYS:
            raise QuitGame
        else:
            field_idx = move_cursor(field_idx, key, len(rows))


def show_quick_start(
    stdscr, configs: list[OpConfig], t_idx: int, sessions: list
) -> str:
    time_label = TIME_OPTIONS[t_idx][0]
    ops_label = " | ".join(c.label for c in configs)
    options = ["Quick Start", "New Game"]
    cursor = 0
    stdscr.nodelay(False)
    while True:
        begin_frame(stdscr)
        title(stdscr, 2, "MENTAL MATHS TRAINER")
        center(stdscr, 4, "Last session:", curses.A_DIM)
        center(stdscr, 5, ops_label, curses.A_BOLD)
        center(stdscr, 6, time_label, curses.A_DIM)
        _draw_options(stdscr, 9, options, cursor)
        footer(stdscr, "j/k navigate   ENTER select   v performance   q quit")
        refresh(stdscr)
        key = stdscr.getch()
        if key in ENTER_KEYS:
            return "quick" if cursor == 0 else "new"
        elif key in VIZ_KEYS:
            show_viz(stdscr, sessions)
        elif key in QUIT_KEYS:
            raise QuitGame
        else:
            cursor = move_cursor(cursor, key, len(options))
