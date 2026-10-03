"""Mental Maths Trainer — terminal arithmetic practice with countdown timer."""

import curses
from dataclasses import dataclass, field

from .constants import OPERATIONS, TIME_OPTIONS, QuitGame
from .models import OpConfig
from .storage import _cfg_to_dict, _dict_to_cfg, _load_data, _make_session, _save_data
from .ui.game import Game
from .ui.menus import (
    run_multiselect,
    run_op_config,
    run_single_select,
    show_quick_start,
)
from .ui.results import show_results


@dataclass
class _SessionState:
    """Carries the configuration chosen in the most recent menu pass."""

    indices: list[int] = field(default_factory=list)
    configs: list[OpConfig] = field(default_factory=list)
    t_idx: int = 0
    guest_mode: bool = False


def _parse_last_config(last_config) -> _SessionState | None:
    """Rebuild the previous session's settings, or None if missing or corrupt."""
    try:
        configs = [_dict_to_cfg(c) for c in last_config["configs"]]
        indices = sorted({OPERATIONS.index(c.operation) for c in configs})
        t_idx = int(last_config.get("t_idx", 0))
        guest_mode = bool(last_config.get("guest_mode", False))
    except (AttributeError, KeyError, TypeError, ValueError):
        return None
    if not configs:
        return None
    return _SessionState(
        indices=indices,
        configs=configs,
        t_idx=max(0, min(t_idx, len(TIME_OPTIONS) - 1)),
        guest_mode=guest_mode,
    )


def _run_menus(stdscr, state: _SessionState, sessions: list) -> _SessionState | None:
    """Walk through operation, per-operation and time selection.

    Returns the new state, or None if the user backed out part-way.
    """
    indices, guest_mode = run_multiselect(
        stdscr,
        "MENTAL MATHS TRAINER — Select Operations",
        OPERATIONS,
        sessions,
        preselected=state.indices,
        guest=state.guest_mode,
    )

    prev = {c.operation: c for c in state.configs}
    configs: list[OpConfig] = []
    for idx in indices:
        op = OPERATIONS[idx]
        cfg = run_op_config(stdscr, prev.get(op, OpConfig(op)))
        if cfg is None:
            return None
        configs.append(cfg)

    t_idx = run_single_select(
        stdscr,
        "Select Time Limit",
        [label for label, _ in TIME_OPTIONS] + ["Back"],
        initial=state.t_idx,
    )
    if t_idx < 0 or t_idx == len(TIME_OPTIONS):
        return None

    return _SessionState(indices, configs, t_idx, guest_mode)


def main(stdscr) -> None:
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_GREEN, -1)
    curses.init_pair(2, curses.COLOR_CYAN, -1)
    curses.init_pair(3, curses.COLOR_RED, -1)
    curses.init_pair(4, curses.COLOR_YELLOW, -1)
    curses.curs_set(0)
    stdscr.keypad(True)

    data = _load_data()
    sessions = data.setdefault("sessions", [])
    state = _SessionState()
    skip_menu = False

    try:
        # Offer a quick start once on startup if a previous config exists.
        saved = _parse_last_config(data.get("last_config"))
        if saved is not None:
            choice = show_quick_start(stdscr, saved.configs, saved.t_idx, sessions)
            if choice == "quick":
                state = saved
                skip_menu = True

        while True:
            if not skip_menu:
                new_state = _run_menus(stdscr, state, sessions)
                if new_state is None:
                    continue
                state = new_state

            time_limit = TIME_OPTIONS[state.t_idx][1]
            questions = Game(
                stdscr, state.configs, time_limit, guest_mode=state.guest_mode
            ).run()

            # Persist (skipped in guest mode)
            save_error = False
            if not state.guest_mode:
                session = _make_session(questions, state.configs, time_limit)
                if session:
                    sessions.append(session)
                    data["last_config"] = {
                        "t_idx": state.t_idx,
                        "configs": [_cfg_to_dict(c) for c in state.configs],
                        "guest_mode": state.guest_mode,
                    }
                    try:
                        _save_data(data)
                    except OSError:
                        save_error = True

            result = show_results(
                stdscr,
                questions,
                sessions,
                guest_mode=state.guest_mode,
                save_error=save_error,
            )
            if result == "quit":
                break
            skip_menu = result == "again"

    except QuitGame:
        pass
