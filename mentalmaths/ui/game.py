import curses
import random
import threading
import time

from ..constants import QuitGame
from ..models import OpConfig, Question
from ..questions import check_answer, generate_question
from .helpers import _ENTER_KEYS, _box, _center, _confirm_quit

_BACKSPACE_KEYS = (curses.KEY_BACKSPACE, 127, 8)
_QUIT_KEYS = (27, ord("q"), ord("Q"))
_INCOMPLETE_ANSWERS = ("", "-", ".", "-.")


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
        self.time_remaining = time_limit
        self.questions: list[Question] = []
        self.current = self._next_question()
        self.buf = ""
        self._running = False
        self._lock = threading.Lock()

    def _next_question(self) -> Question:
        return generate_question(random.choice(self.configs))

    def _timer_thread(self) -> None:
        while self._running:
            time.sleep(1)
            with self._lock:
                if self.time_remaining > 0:
                    self.time_remaining -= 1

    def _time_attr(self, remaining: int) -> int:
        if remaining <= self._CRITICAL_SECS:
            return curses.color_pair(3)
        if remaining <= self._WARN_SECS:
            return curses.color_pair(4)
        return curses.color_pair(1)

    def _draw(self) -> None:
        s = self.stdscr
        s.erase()
        h, w = s.getmaxyx()
        _box(s)

        with self._lock:
            remaining = self.time_remaining

        correct = sum(1 for q in self.questions if q.correct)
        total = len(self.questions)

        score_str = f" Score: {correct}/{total} "
        timer_str = f" {remaining // 60:02d}:{remaining % 60:02d} "
        ops_str = " | ".join(c.label for c in self.configs)
        max_ops = w - len(score_str) - len(timer_str) - 4
        if len(ops_str) > max_ops:
            ops_str = ops_str[: max_ops - 1] + "…"

        time_attr = self._time_attr(remaining)
        try:
            s.addstr(1, 1, score_str, curses.A_BOLD)
            if self.guest_mode:
                s.addstr(
                    1,
                    1 + len(score_str),
                    " [G] ",
                    curses.color_pair(4) | curses.A_BOLD,
                )
            _center(s, 1, ops_str)
            s.addstr(1, w - len(timer_str) - 1, timer_str, time_attr | curses.A_BOLD)
        except curses.error:
            pass

        bar_w = max(4, w - 4)
        filled = round(remaining / self.time_limit * bar_w) if self.time_limit else 0
        try:
            s.addstr(2, 2, "#" * filled + "-" * (bar_w - filled), time_attr)
        except curses.error:
            pass

        q_line = f"{self.current.display}  =  {self.buf}_"
        _center(s, h // 2 - 1, q_line, curses.A_BOLD | curses.color_pair(2))

        if self.current.answer_dec > 0:
            dp = self.current.answer_dec
            _center(
                s,
                h // 2 + 1,
                f"(answer to {dp} decimal place{'s' if dp > 1 else ''})",
                curses.A_DIM,
            )

        if self.questions:
            last = self.questions[-1]
            if last.correct:
                fb = f"  Correct!   {last.display} = {last.answer_str}  "
                attr = curses.color_pair(1)
            else:
                fb = (
                    f"  Wrong   {last.display} = {last.answer_str}"
                    f"   (you: {last.user_answer})  "
                )
                attr = curses.color_pair(3)
            _center(s, h // 2 + 3, fb, attr)

        _center(
            s,
            h - 2,
            "Type answer and ENTER   BACKSPACE to correct   q to quit",
            curses.A_DIM,
        )
        s.noutrefresh()
        curses.doupdate()

    def _handle_key(self, key: int) -> None:
        """Apply a single keypress to the input buffer. Raises QuitGame on quit."""
        if key in _BACKSPACE_KEYS:
            self.buf = self.buf[:-1]
        elif key in _ENTER_KEYS:
            self._submit()
        elif key in _QUIT_KEYS:
            self._draw()
            if _confirm_quit(self.stdscr):
                raise QuitGame
            self.stdscr.nodelay(True)
        elif 0 <= key < 256:
            ch = chr(key)
            if ch.isdigit():
                self.buf += ch
            elif ch == "." and "." not in self.buf:
                self.buf += ch
            elif ch == "-" and not self.buf:
                self.buf = ch

    def run(self) -> list[Question]:
        self.stdscr.nodelay(True)
        self.stdscr.keypad(True)
        curses.curs_set(0)
        self._running = True
        threading.Thread(target=self._timer_thread, daemon=True).start()
        try:
            while True:
                with self._lock:
                    if self.time_remaining <= 0:
                        break
                self._draw()
                key = self.stdscr.getch()
                if key == -1:
                    time.sleep(0.05)
                else:
                    self._handle_key(key)
        finally:
            self._running = False
        return self.questions

    def _submit(self) -> None:
        if self.buf in _INCOMPLETE_ANSWERS:
            return
        self.current.user_answer = self.buf
        self.current.correct = check_answer(self.buf, self.current)
        self.questions.append(self.current)
        self.buf = ""
        self.current = self._next_question()
