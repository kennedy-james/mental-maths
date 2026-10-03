import contextlib
import json
import os
from dataclasses import asdict, fields
from datetime import datetime

from .constants import (
    DATA_FILE,
    DECIMALS_RANGE,
    DIGITS_RANGE,
    OPERAND2_MAX,
    OPERAND2_MIN,
    OPERATIONS,
)
from .models import OpConfig, Question

_CFG_FIELDS = tuple(f.name for f in fields(OpConfig))


def cfg_from_dict(d: dict) -> OpConfig:
    settings = {k: d[k] for k in _CFG_FIELDS if k in d and k != "operation"}
    return OpConfig(d["operation"], **settings)


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def cfg_is_valid(cfg: OpConfig) -> bool:
    if cfg.operation not in OPERATIONS:
        return False
    ints = (cfg.digits, cfg.decimals, cfg.operand2_lo, cfg.operand2_hi)
    if not all(_is_int(v) for v in ints) or not isinstance(cfg.allow_negative, bool):
        return False
    lo_min = OPERAND2_MIN.get(cfg.operation, OPERAND2_MIN["Multiplication"])
    return (
        DIGITS_RANGE[0] <= cfg.digits <= DIGITS_RANGE[1]
        and DECIMALS_RANGE[0] <= cfg.decimals <= DECIMALS_RANGE[1]
        and lo_min <= cfg.operand2_lo <= cfg.operand2_hi <= OPERAND2_MAX
    )


def _is_counts(d) -> bool:
    return (
        isinstance(d, dict)
        and _is_int(d.get("total"))
        and _is_int(d.get("correct"))
        and 0 <= d["correct"] <= d["total"]
    )


def _session_is_valid(s) -> bool:
    if not (_is_counts(s) and isinstance(s.get("ts"), str)):
        return False
    per_op = s.get("per_op", {})
    if not isinstance(per_op, dict) or not all(map(_is_counts, per_op.values())):
        return False
    configs = s.get("configs", [])
    return isinstance(configs, list) and all(
        isinstance(c, dict) and isinstance(c.get("operation"), str) for c in configs
    )


def load_sessions(data: dict) -> list:
    sessions = data.get("sessions")
    if not isinstance(sessions, list):
        sessions = []
    data["sessions"] = [s for s in sessions if _session_is_valid(s)]
    return data["sessions"]


def load_data() -> dict:
    try:
        data = json.loads(DATA_FILE.read_text())
    except FileNotFoundError:
        return {}
    # ValueError covers bad UTF-8 and JSON; RecursionError covers deeply nested JSON.
    except (OSError, ValueError, RecursionError):
        data = None
    if isinstance(data, dict):
        return data
    # Set unusable contents aside so the next save cannot destroy the history.
    with contextlib.suppress(OSError):
        DATA_FILE.replace(DATA_FILE.with_name(DATA_FILE.name + ".corrupt"))
    return {}


def save_data(data: dict) -> None:
    # Write then rename, so an interrupted write cannot leave a truncated file.
    tmp = DATA_FILE.with_name(DATA_FILE.name + ".tmp")
    try:
        tmp.write_text(json.dumps(data, indent=2))
        os.replace(tmp, DATA_FILE)
    except BaseException:
        with contextlib.suppress(OSError):
            tmp.unlink(missing_ok=True)
        raise


def make_session(
    questions: list[Question], configs: list[OpConfig], time_limit: int
) -> dict | None:
    if not questions:
        return None
    per_op: dict = {}
    for q in questions:
        st = per_op.setdefault(q.op_label, {"total": 0, "correct": 0})
        st["total"] += 1
        if q.correct:
            st["correct"] += 1
    return {
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "time_limit": time_limit,
        "total": len(questions),
        "correct": sum(1 for q in questions if q.correct),
        "per_op": per_op,
        "configs": [asdict(c) for c in configs],
    }
