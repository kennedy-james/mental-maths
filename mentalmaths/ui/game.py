import curses
import math
import random
import time

from ..constants import QuitGame
from ..models import OpConfig, Question
from ..questions import check_answer, generate_question
from .helpers import (
    CYAN,
    ENTER_KEYS,
    ESC,
    GREEN,
    QUIT_KEYS,
    RED,
    YELLOW,
    addstr,
    begin_frame,
    center,
    confirm_quit,
    footer,
    refresh,
)

_BACKSPACE_KEYS = (curses.KEY_BACKSPACE, 127, 8)
_QUIT_KEYS = (ESC, *QUIT_KEYS)
_INCOMPLETE_ANSWERS = ("", "-", ".", "-.")
_DIGITS = "0123456789"
_GUEST_TAG = " [G] "


class Game:
    _WARN_SECS = 30
    _CRITICAL_SECS = 10

    def __init__(
        self,
        stdscr,
        configs: list[OpConfig],
        time_limit: int,
        guest_mode: bool = False,
    ):
        self.stdscr = stdscr
        self.configs = configs
        self.guest_mode = guest_mode
        self.time_limit = time_limit
        self.questions: list[Question] = []
        self.current = self._next_question()
        self.buf = ""
        self._deadline = time.monotonic() + time_limit

    def _next_question(self) -> Question:
        return generate_question(random.choice(self.configs))

    @property
    def time_remaining(self) -> int:
        return max(0, math.ceil(self._deadline - time.monotonic()))

    def _time_attr(self, remaining: int) -> int:
        if remaining <= self._CRITICAL_SECS:
            return curses.color_pair(RED)
        if remaining <= self._WARN_SECS:
            return curses.color_pair(YELLOW)
        return curses.color_pair(GREEN)

    def _draw(self) -> None:
        s = self.stdscr
        h, w = begin_frame(s)

        remaining = self.time_remaining
        correct = sum(1 for q in self.questions if q.correct)
        total = len(self.questions)

        score_str = f" Score: {correct}/{total} "
        timer_str = f" {remaining // 60:02d}:{remaining % 60:02d} "
        ops_str = " | ".join(c.label for c in self.configs)
        # The label is centred, so it must clear the wider of the two sides.
        left_w = len(score_str) + (len(_GUEST_TAG) if self.guest_mode else 0)
        max_ops = w - 2 * max(left_w, len(timer_str)) - 4
        if len(ops_str) > max_ops:
            ops_str = ops_str[: max_ops - 1] + "…" if max_ops > 0 else ""

        time_attr = self._time_attr(remaining)
        addstr(s, 1, 1, score_str, curses.A_BOLD)
        if self.guest_mode:
            tag_attr = curses.color_pair(YELLOW) | curses.A_BOLD
            addstr(s, 1, 1 + len(score_str), _GUEST_TAG, tag_attr)
        if ops_str:
            center(s, 1, ops_str)
        addstr(s, 1, w - len(timer_str) - 1, timer_str, time_attr | curses.A_BOLD)

        bar_w = max(4, w - 4)
        filled = round(remaining / self.time_limit * bar_w)
        addstr(s, 2, 2, "#" * filled + "-" * (bar_w - filled), time_attr)

        q_line = f"{self.current.display}  =  {self.buf}_"
        center(s, h // 2 - 1, q_line, curses.A_BOLD | curses.color_pair(CYAN))

        if self.current.answer_dec > 0:
            dp = self.current.answer_dec
            center(
                s,
                h // 2 + 1,
                f"(answer to {dp} decimal place{'s' if dp > 1 else ''})",
                curses.A_DIM,
            )

        if self.questions:
            last = self.questions[-1]
            if last.correct:
                fb = f"  Correct!   {last.display} = {last.answer_str}  "
                attr = curses.color_pair(GREEN)
            else:
                fb = (
                    f"  Wrong   {last.display} = {last.answer_str}"
                    f"   (you: {last.user_answer})  "
                )
                attr = curses.color_pair(RED)
            center(s, h // 2 + 3, fb, attr)

        footer(s, "Type answer and ENTER   BACKSPACE to correct   q to quit")
        refresh(s)

    def _handle_key(self, key: int) -> None:
        if key in _BACKSPACE_KEYS:
            self.buf = self.buf[:-1]
        elif key in ENTER_KEYS:
            self._submit()
        elif key in _QUIT_KEYS:
            self._draw()
            if confirm_quit(self.stdscr):
                raise QuitGame
            self.stdscr.nodelay(True)
        elif 0 <= key < 256:
            ch = chr(key)
            # str.isdigit() would also accept non-ASCII digits such as "²".
            if ch in _DIGITS or (ch == "." and "." not in self.buf):
                self.buf += ch
            elif ch == "-" and not self.buf:
                self.buf = ch

    def _submit(self) -> None:
        if self.buf in _INCOMPLETE_ANSWERS:
            return
        self.current.user_answer = self.buf
        self.current.correct = check_answer(self.buf, self.current)
        self.questions.append(self.current)
        self.buf = ""
        self.current = self._next_question()

    def run(self) -> list[Question]:
        self.stdscr.nodelay(True)
        while self.time_remaining > 0:
            self._draw()
            key = self.stdscr.getch()
            if key == -1:
                time.sleep(0.05)
            else:
                self._handle_key(key)
        # Otherwise a late ENTER would trigger "again" on the results screen.
        curses.flushinp()
        return self.questions
