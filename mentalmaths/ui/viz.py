import curses

from ..constants import OPERAND2_NAMES, TIME_OPTIONS
from ..models import percent
from ..storage import cfg_from_dict
from .helpers import (
    DOWN_KEYS,
    ENTER_KEYS,
    ESC,
    GREEN,
    LEFT_KEYS,
    QUIT_KEYS,
    RED,
    RIGHT_KEYS,
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

_Y_LABEL_W = 5
_METRIC_KEYS = (*UP_KEYS, ord("K"), *DOWN_KEYS, ord("J"))
_PREV_KEYS = (*LEFT_KEYS, ord("H"))
_NEXT_KEYS = (*RIGHT_KEYS, ord("L"))
_EXIT_KEYS = (ESC, *QUIT_KEYS, *VIZ_KEYS)


def _pct_attr(pct: float) -> int:
    if pct >= 70:
        return curses.color_pair(GREEN)
    if pct >= 50:
        return curses.color_pair(YELLOW)
    return curses.color_pair(RED)


def _history_n_show(n_sessions: int, max_w: int) -> int:
    return min(n_sessions, max(3, max_w - _Y_LABEL_W - 1))


def _draw_history_view(
    stdscr,
    sessions: list,
    y0: int,
    x0: int,
    max_h: int,
    max_w: int,
    metric: int = 0,
    sel: int = -1,
) -> None:
    chart_h = max(4, max_h - 4)
    n_show = _history_n_show(len(sessions), max_w)
    data = sessions[-n_show:]
    ax_x = x0 + _Y_LABEL_W - 1

    offset = len(sessions) - n_show
    sel_rel = (sel - offset) if (0 <= sel - offset < n_show) else -1

    if metric == 0:
        lbl = "< Accuracy % >"
        tick_labels = [f"{tick * 25:>3}%" for tick in range(5)]

        def segments(s: dict) -> list[tuple[int, int]]:
            pct = percent(s["correct"], s["total"])
            return [(round(pct / 100 * chart_h), _pct_attr(pct))]

        legend = [
            (0, "#", curses.color_pair(GREEN)),
            (2, ">=70%", curses.A_DIM),
            (9, "#", curses.color_pair(YELLOW)),
            (11, ">=50%", curses.A_DIM),
            (18, "#", curses.color_pair(RED)),
            (20, "<50%", curses.A_DIM),
        ]
    else:
        lbl = "< Correct count >"
        max_total = max((s["total"] for s in data), default=1) or 1
        tick_labels = [f"{round(tick / 4 * max_total):>3}q" for tick in range(5)]

        def segments(s: dict) -> list[tuple[int, int]]:
            return [
                (round(s["correct"] / max_total * chart_h), curses.color_pair(GREEN)),
                (round(s["total"] / max_total * chart_h), curses.color_pair(RED)),
            ]

        legend = [
            (0, "#", curses.color_pair(GREEN)),
            (2, "correct", curses.A_DIM),
            (11, "#", curses.color_pair(RED)),
            (13, "wrong", curses.A_DIM),
        ]

    addstr(stdscr, y0, ax_x + 1 + max(0, (n_show - len(lbl)) // 2), lbl, curses.A_BOLD)
    chart_y = y0 + 1

    for tick, tick_label in enumerate(tick_labels):
        row = chart_y + round((1 - tick / 4) * (chart_h - 1))
        addstr(stdscr, row, x0, tick_label, curses.A_DIM)
        addstr(stdscr, row, ax_x, "|")

    xaxis = "".join("v" if i == sel_rel else "-" for i in range(n_show))
    addstr(stdscr, chart_y + chart_h, ax_x, "+" + xaxis)

    for i, s in enumerate(data):
        bold = curses.A_BOLD if i == sel_rel else 0
        segs = segments(s)
        for row in range(chart_h):
            from_bottom = chart_h - 1 - row
            for seg_h, seg_attr in segs:
                if from_bottom < seg_h:
                    char, attr = "#", seg_attr | bold
                    break
            else:
                char, attr = ("|", curses.A_DIM) if i == sel_rel else (" ", 0)
            addstr(stdscr, chart_y + row, ax_x + 1 + i, char, attr)

    legend_y = chart_y + chart_h + 1
    for dx, text, attr in legend:
        addstr(stdscr, legend_y, x0 + dx, text, attr)

    info_y = chart_y + chart_h + 2
    if sel_rel >= 0:
        s = sessions[sel]
        pct = percent(s["correct"], s["total"])
        info = f"{s['ts']}  {s['correct']}/{s['total']} ({pct:.0f}%)  ENTER for details"
        addstr(stdscr, info_y, x0, info[:max_w], curses.A_BOLD)
    else:
        all_correct = sum(s["correct"] for s in sessions)
        all_total = sum(s["total"] for s in sessions)
        all_pcts = [percent(s["correct"], s["total"]) for s in sessions if s["total"]]
        if all_pcts:
            n = len(sessions)
            avg = sum(all_pcts) / len(all_pcts)
            best = max(all_pcts)
            stats = (
                f"{n} session{'s' if n != 1 else ''}  |  "
                f"{all_correct} correct / {all_total} total  |  "
                f"avg {avg:.0f}%  |  best {best:.0f}%"
            )
            addstr(stdscr, info_y, x0, stats[:max_w], curses.A_DIM)


def _fmt_time(secs: int) -> str:
    return next((label for label, s in TIME_OPTIONS if s == secs), f"{secs}s")


def _show_session_detail(stdscr, session: dict) -> None:
    h, w = stdscr.getmaxyx()
    total, correct = session["total"], session["correct"]
    lines = [
        f" Session: {session['ts']} ",
        f" Time:    {_fmt_time(session.get('time_limit', 0))} ",
        f" Score:   {correct} / {total}  ({percent(correct, total):.0f}%) ",
        "",
    ]

    configs = session.get("configs", [])
    if configs:
        lines.append(" Operations: ")
        for cfg in map(cfg_from_dict, configs):
            op = cfg.operation
            lines.append(f"   {op}")
            if op in OPERAND2_NAMES:
                name = OPERAND2_NAMES[op]
                lines.append(f"     {name} range: {cfg.operand2_lo}–{cfg.operand2_hi}")
            elif op in ("Addition", "Subtraction"):
                lines.append(f"     Digits: {cfg.digits}")
            if cfg.decimals:
                lines.append(f"     Decimal places: {cfg.decimals}")
            if op == "Subtraction" and cfg.allow_negative:
                lines.append("     Allow negatives: yes")
    else:
        per_op = session.get("per_op", {})
        if per_op:
            lines.append(" Operations: ")
            lines += [f"   {lbl}" for lbl in per_op]

    lines += ["", " Press any key to close "]

    box_w = min(w - 4, max(len(line) for line in lines) + 4)
    box_h = min(h - 4, len(lines) + 2)
    by = max(1, (h - box_h) // 2)
    bx = max(1, (w - box_w) // 2)

    inner = max(0, box_w - 2)
    rows = [
        "┌" + "─" * inner + "┐",
        *(f"│{line[:inner]:<{inner}}│" for line in lines[: max(0, box_h - 2)]),
        "└" + "─" * inner + "┘",
    ]
    for i, row in enumerate(rows):
        addstr(stdscr, by + i, bx, row, curses.A_REVERSE)

    refresh(stdscr)
    stdscr.getch()


def _draw_perop_view(stdscr, sessions: list, y0: int, x0: int, max_h: int) -> None:
    op_stats: dict = {}
    for s in sessions:
        for label, counts in s.get("per_op", {}).items():
            st = op_stats.setdefault(
                label, {"total": 0, "correct": 0, "sessions": 0, "best": 0}
            )
            st["total"] += counts["total"]
            st["correct"] += counts["correct"]
            st["sessions"] += 1
            st["best"] = max(st["best"], percent(counts["correct"], counts["total"]))

    if not op_stats:
        addstr(stdscr, y0, x0, "No per-operation data yet.", curses.A_DIM)
        return

    cols = ["Operation", "Sessions", "Total Q", "Correct", "Avg %", "Best %"]
    widths = [26, 9, 8, 8, 7, 7]
    header = "  ".join(f"{c:<{w}}" for c, w in zip(cols, widths, strict=True))
    addstr(stdscr, y0, x0, header, curses.A_BOLD)
    addstr(stdscr, y0 + 1, x0, "-" * len(header), curses.A_DIM)

    for i, (label, st) in enumerate(sorted(op_stats.items())):
        if i >= max_h - 3:
            break
        pct = percent(st["correct"], st["total"])
        row_data = [
            label[:26],
            str(st["sessions"]),
            str(st["total"]),
            str(st["correct"]),
            f"{pct:.0f}%",
            f"{st['best']:.0f}%",
        ]
        line = "  ".join(f"{d:<{w}}" for d, w in zip(row_data, widths, strict=True))
        addstr(stdscr, y0 + 2 + i, x0, line, _pct_attr(pct))


def show_viz(stdscr, sessions: list) -> None:
    view = 0
    history_metric = 0
    sel = len(sessions) - 1 if sessions else -1
    stdscr.nodelay(False)
    while True:
        h, w = begin_frame(stdscr)
        title(stdscr, 1, " PERFORMANCE ")

        tabs = ["[ History ]", "[ By Operation ]"]
        tab_str = "   ".join(tabs)
        tab_x0 = max(0, (w - len(tab_str)) // 2)
        x_cur = tab_x0
        for i, t in enumerate(tabs):
            attr = curses.A_REVERSE | curses.A_BOLD if i == view else curses.A_DIM
            addstr(stdscr, 2, x_cur, t, attr)
            x_cur += len(t) + 3

        content_y = 4
        content_h = h - content_y - 3

        if not sessions:
            center(stdscr, h // 2, "No sessions recorded yet.", curses.A_DIM)
        elif view == 0:
            sel_min = len(sessions) - _history_n_show(len(sessions), w - 4)
            sel = max(sel_min, min(len(sessions) - 1, sel))
            _draw_history_view(
                stdscr,
                sessions,
                y0=content_y,
                x0=2,
                max_h=content_h,
                max_w=w - 4,
                metric=history_metric,
                sel=sel,
            )
        else:
            _draw_perop_view(stdscr, sessions, y0=content_y, x0=2, max_h=content_h)

        if view == 0:
            footer(
                stdscr,
                "h/l select   j/k metric   ENTER details   TAB view   ESC/q back",
            )
        else:
            footer(stdscr, "TAB switch view   ESC / q back")
        refresh(stdscr)

        key = stdscr.getch()
        if key in _EXIT_KEYS:
            return
        elif key == ord("\t"):
            view = 1 - view
        elif view == 0 and key in _METRIC_KEYS:
            history_metric = 1 - history_metric
        elif view == 0 and key in _PREV_KEYS:
            sel = max(0, sel - 1)
        elif view == 0 and key in _NEXT_KEYS:
            sel = min(len(sessions) - 1, sel + 1)
        elif view == 0 and key in ENTER_KEYS and 0 <= sel < len(sessions):
            _show_session_detail(stdscr, sessions[sel])
