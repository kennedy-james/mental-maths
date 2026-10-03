from dataclasses import asdict, dataclass, field

from .constants import OPERATIONS, TIME_OPTIONS, QuitGame
from .models import OpConfig
from .storage import (
    cfg_from_dict,
    cfg_is_valid,
    load_data,
    load_sessions,
    make_session,
    save_data,
)
from .ui.game import Game
from .ui.helpers import hide_cursor, init_colours
from .ui.menus import (
    run_multiselect,
    run_op_config,
    run_single_select,
    show_quick_start,
)
from .ui.results import show_results


@dataclass
class _SessionState:
    indices: list[int] = field(default_factory=list)
    configs: list[OpConfig] = field(default_factory=list)
    t_idx: int = 0
    guest_mode: bool = False


def _parse_last_config(last_config) -> _SessionState | None:
    try:
        configs = [cfg_from_dict(c) for c in last_config["configs"]]
        t_idx = int(last_config.get("t_idx", 0))
    except (AttributeError, KeyError, TypeError, ValueError, OverflowError):
        return None
    # Validate before de-duplicating: an invalid operation may be unhashable.
    if not configs or not all(cfg_is_valid(c) for c in configs):
        return None
    operations = [c.operation for c in configs]
    if len(set(operations)) != len(operations):
        return None
    return _SessionState(
        indices=sorted(OPERATIONS.index(op) for op in operations),
        configs=configs,
        t_idx=max(0, min(t_idx, len(TIME_OPTIONS) - 1)),
    )


def _run_menus(
    stdscr, state: _SessionState, sessions: list
) -> tuple[_SessionState, bool]:
    indices, guest_mode = run_multiselect(
        stdscr,
        "MENTAL MATHS TRAINER — Select Operations",
        OPERATIONS,
        sessions,
        preselected=state.indices,
        guest=state.guest_mode,
    )

    chosen = {c.operation: c for c in state.configs}

    def partial() -> _SessionState:
        return _SessionState(indices, list(chosen.values()), state.t_idx, guest_mode)

    for idx in indices:
        op = OPERATIONS[idx]
        cfg = run_op_config(stdscr, chosen.get(op, OpConfig(op)))
        if cfg is None:
            return partial(), False
        chosen[op] = cfg

    t_idx = run_single_select(
        stdscr,
        "Select Time Limit",
        [label for label, _ in TIME_OPTIONS] + ["Back"],
        initial=state.t_idx,
    )
    if t_idx < 0 or t_idx == len(TIME_OPTIONS):
        return partial(), False

    configs = [chosen[OPERATIONS[i]] for i in indices]
    return _SessionState(indices, configs, t_idx, guest_mode), True


def main(stdscr) -> None:
    init_colours()
    hide_cursor()

    data = load_data()
    sessions = load_sessions(data)
    state = _SessionState()
    skip_menu = False

    try:
        saved = _parse_last_config(data.get("last_config"))
        if saved is not None:
            choice = show_quick_start(stdscr, saved.configs, saved.t_idx, sessions)
            if choice == "quick":
                state = saved
                skip_menu = True

        while True:
            if not skip_menu:
                state, done = _run_menus(stdscr, state, sessions)
                if not done:
                    continue

            time_limit = TIME_OPTIONS[state.t_idx][1]
            questions = Game(
                stdscr, state.configs, time_limit, guest_mode=state.guest_mode
            ).run()

            save_error = False
            if not state.guest_mode and (
                session := make_session(questions, state.configs, time_limit)
            ):
                sessions.append(session)
                data["last_config"] = {
                    "t_idx": state.t_idx,
                    "configs": [asdict(c) for c in state.configs],
                }
                try:
                    save_data(data)
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
