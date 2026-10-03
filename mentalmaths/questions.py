import operator
import random
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from .models import OpConfig, Question, format_number

_OPERATORS = {
    "Addition": ("+", operator.add),
    "Subtraction": ("-", operator.sub),
    "Multiplication": ("x", operator.mul),
    "Division": ("/", operator.truediv),
}


def _operand(lo: int, hi: int, dec: int) -> str:
    scale = 10**dec
    return format_number(random.randint(lo * scale, (hi + 1) * scale - 1) / scale, dec)


def _round_half_up(x: Decimal, dec: int) -> Decimal:
    # Round 2.25 to 2.3 as taught in school, not to 2.2 as banker's rounding does.
    return x.quantize(Decimal(1).scaleb(-dec), rounding=ROUND_HALF_UP)


def generate_question(cfg: OpConfig) -> Question:
    op, dec = cfg.operation, cfg.decimals
    lo, hi = cfg.operand2_lo, cfg.operand2_hi
    if op == "Division":
        divisor = random.randint(lo, hi)
        if dec == 0:
            quotient = random.randint(lo, hi)
            return Question(
                f"{divisor * quotient} / {divisor}", float(quotient), 0, cfg.label
            )
        a, b = _operand(lo, hi, dec), str(divisor)
    elif op == "Multiplication":
        a, b = _operand(lo, hi, dec), _operand(lo, hi, dec)
    else:
        lo, hi = 10 ** (cfg.digits - 1), 10**cfg.digits - 1
        a, b = _operand(lo, hi, dec), _operand(lo, hi, dec)
        if op == "Subtraction" and not cfg.allow_negative and Decimal(b) > Decimal(a):
            a, b = b, a

    # Decimal avoids binary float error: 2.3 x 1.5 must be 3.45, not 3.4499...
    symbol, fn = _OPERATORS[op]
    answer = _round_half_up(fn(Decimal(a), Decimal(b)), dec)
    return Question(f"{a} {symbol} {b}", float(answer), dec, cfg.label)


def check_answer(user_str: str, q: Question) -> bool:
    try:
        value = Decimal(user_str)
        # Extra decimal places are rounded like the answer, but a whole-number
        # answer must be exact so that "41.6" is not accepted for 42.
        if q.answer_dec == 0:
            return value == round(q.answer)
        return _round_half_up(value, q.answer_dec) == Decimal(q.answer_str)
    except (InvalidOperation, TypeError, ValueError):
        return False
