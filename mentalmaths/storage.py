import json
import os
from datetime import datetime

from .constants import DATA_FILE
from .models import OpConfig, Question


def _cfg_to_dict(cfg: OpConfig) -> dict:
    return {
        "operation": cfg.operation,
        "digits": cfg.digits,
        "decimals": cfg.decimals,
        "operand2_lo": cfg.operand2_lo,
        "operand2_hi": cfg.operand2_hi,
        "allow_negative": cfg.allow_negative,
    }


def _dict_to_cfg(d: dict) -> OpConfig:
    return OpConfig(
        operation=d["operation"],
        digits=d.get("digits", 2),
        decimals=d.get("decimals", 0),
        operand2_lo=d.get("operand2_lo", 2),
        operand2_hi=d.get("operand2_hi", 12),
        allow_negative=d.get("allow_negative", False),
    )


def _load_data() -> dict:
    try:
        data = json.loads(DATA_FILE.read_text())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_data(data: dict) -> None:
    # Write to a temporary file then rename, so an interrupted write can never
    # leave a truncated data file behind (which would lose all history).
    tmp = DATA_FILE.with_name(DATA_FILE.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    os.replace(tmp, DATA_FILE)


def _make_session(
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
        "configs": [_cfg_to_dict(c) for c in configs],
    }
