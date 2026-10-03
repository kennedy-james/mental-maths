from dataclasses import dataclass

from .constants import OPERAND2_NAMES


def format_number(x: float, dec: int) -> str:
    return str(round(x)) if dec == 0 else f"{x:.{dec}f}"


def percent(correct: int, total: int) -> float:
    return correct / total * 100 if total else 0


@dataclass
class OpConfig:
    operation: str
    digits: int = 2
    decimals: int = 0
    operand2_lo: int = 2
    operand2_hi: int = 12
    allow_negative: bool = False

    @property
    def label(self) -> str:
        if self.operation in OPERAND2_NAMES:
            parts = [f"{self.operand2_lo}-{self.operand2_hi}"]
        else:
            parts = [f"{self.digits}-digit"]
        if self.decimals:
            parts.append(f"{self.decimals}dp")
        if self.operation == "Subtraction" and self.allow_negative:
            parts.append("neg")
        return f"{self.operation} ({', '.join(parts)})"


@dataclass
class Question:
    display: str
    answer: float
    answer_dec: int
    op_label: str = ""
    user_answer: str = ""
    correct: bool | None = None

    @property
    def answer_str(self) -> str:
        return format_number(self.answer, self.answer_dec)
