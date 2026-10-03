import curses
import json
import random
import re
from dataclasses import asdict
from decimal import ROUND_HALF_UP, Decimal
from itertools import pairwise
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import mentalmaths.app as _app_mod
import mentalmaths.storage as _storage_mod
import mentalmaths.ui.game as _game_mod
import mentalmaths.ui.helpers as _helpers_mod
import mentalmaths.ui.menus as _menus_mod
from mentalmaths.app import _parse_last_config, _run_menus, _SessionState
from mentalmaths.constants import OPERATIONS, TIME_OPTIONS
from mentalmaths.models import OpConfig, Question, format_number
from mentalmaths.questions import _operand, check_answer, generate_question
from mentalmaths.storage import (
    cfg_from_dict,
    cfg_is_valid,
    load_data,
    load_sessions,
    make_session,
    save_data,
)
from mentalmaths.ui.game import Game
from mentalmaths.ui.menus import _build_rows, run_op_config
from mentalmaths.ui.results import _q_line, show_results
from mentalmaths.ui.viz import show_viz


class TestOpConfigLabel:
    def test_addition_basic(self):
        cfg = OpConfig("Addition", digits=2)
        assert cfg.label == "Addition (2-digit)"

    def test_addition_with_decimals(self):
        cfg = OpConfig("Addition", digits=3, decimals=2)
        assert cfg.label == "Addition (3-digit, 2dp)"

    def test_subtraction_no_negative(self):
        cfg = OpConfig("Subtraction", digits=1)
        assert cfg.label == "Subtraction (1-digit)"

    def test_subtraction_with_negative(self):
        cfg = OpConfig("Subtraction", digits=2, allow_negative=True)
        assert cfg.label == "Subtraction (2-digit, neg)"

    def test_subtraction_decimals_and_negative(self):
        cfg = OpConfig("Subtraction", digits=2, decimals=1, allow_negative=True)
        assert cfg.label == "Subtraction (2-digit, 1dp, neg)"

    def test_multiplication_shows_range(self):
        cfg = OpConfig("Multiplication", operand2_lo=3, operand2_hi=9)
        assert cfg.label == "Multiplication (3-9)"

    def test_multiplication_with_decimals(self):
        cfg = OpConfig("Multiplication", operand2_lo=2, operand2_hi=12, decimals=1)
        assert cfg.label == "Multiplication (2-12, 1dp)"

    def test_division_shows_range(self):
        cfg = OpConfig("Division", operand2_lo=2, operand2_hi=12)
        assert cfg.label == "Division (2-12)"

    def test_division_with_decimals(self):
        cfg = OpConfig("Division", operand2_lo=4, operand2_hi=8, decimals=2)
        assert cfg.label == "Division (4-8, 2dp)"


class TestQuestionAnswerStr:
    def test_integer_answer(self):
        q = Question("1 + 1", 2.0, 0)
        assert q.answer_str == "2"

    def test_integer_answer_rounds(self):
        q = Question("x", 2.9999999, 0)
        assert q.answer_str == "3"

    def test_decimal_1dp(self):
        q = Question("x", 1.5, 1)
        assert q.answer_str == "1.5"

    def test_decimal_2dp(self):
        q = Question("x", 3.14, 2)
        assert q.answer_str == "3.14"

    def test_negative_integer(self):
        q = Question("x", -5.0, 0)
        assert q.answer_str == "-5"

    def test_negative_decimal(self):
        q = Question("x", -1.25, 2)
        assert q.answer_str == "-1.25"


class TestFormatNumber:
    def test_integer_zero_dec(self):
        assert format_number(7.0, 0) == "7"

    def test_rounds_to_int(self):
        assert format_number(6.9, 0) == "7"

    def test_one_decimal(self):
        assert format_number(3.5, 1) == "3.5"

    def test_two_decimals(self):
        assert format_number(1.23, 2) == "1.23"

    def test_negative(self):
        assert format_number(-4.0, 0) == "-4"


class TestOperand:
    def test_integer_range(self):
        for _ in range(200):
            assert re.fullmatch(r"\d{2}", _operand(10, 99, 0))

    def test_decimal_range(self):
        for _ in range(200):
            v = _operand(1, 9, 2)
            assert re.fullmatch(r"\d\.\d{2}", v)
            assert 1 <= Decimal(v) < 10

    def test_single_value_range(self):
        for _ in range(50):
            assert _operand(5, 5, 0) == "5"


class TestGenerateQuestion:
    def test_addition_integer_format(self):
        cfg = OpConfig("Addition", digits=2, decimals=0)
        for _ in range(50):
            q = generate_question(cfg)
            assert "+" in q.display
            assert q.answer_dec == 0
            assert q.answer == int(round(q.answer))

    def test_addition_operand_range(self):
        cfg = OpConfig("Addition", digits=2, decimals=0)
        for _ in range(100):
            q = generate_question(cfg)
            a_str, b_str = q.display.split(" + ")
            a, b = int(a_str), int(b_str)
            assert 10 <= a <= 99
            assert 10 <= b <= 99
            assert q.answer == a + b

    def test_addition_decimal(self):
        cfg = OpConfig("Addition", digits=1, decimals=1)
        for _ in range(50):
            q = generate_question(cfg)
            assert "+" in q.display
            assert q.answer_dec == 1

    def test_addition_1digit(self):
        cfg = OpConfig("Addition", digits=1, decimals=0)
        for _ in range(100):
            q = generate_question(cfg)
            a_str, b_str = q.display.split(" + ")
            assert 1 <= int(a_str) <= 9
            assert 1 <= int(b_str) <= 9

    def test_subtraction_no_negative_result(self):
        cfg = OpConfig("Subtraction", digits=2, decimals=0, allow_negative=False)
        for _ in range(200):
            q = generate_question(cfg)
            assert q.answer >= 0

    def test_subtraction_allows_negative(self):
        cfg = OpConfig("Subtraction", digits=1, decimals=0, allow_negative=True)
        with patch.object(random, "randint", side_effect=[3, 7]):
            q = generate_question(cfg)
        assert q.answer < 0

    def test_subtraction_format(self):
        cfg = OpConfig("Subtraction", digits=2, decimals=0)
        for _ in range(20):
            q = generate_question(cfg)
            assert " - " in q.display

    def test_subtraction_answer_correct(self):
        cfg = OpConfig("Subtraction", digits=2, decimals=0, allow_negative=False)
        for _ in range(50):
            q = generate_question(cfg)
            a_str, b_str = q.display.split(" - ")
            assert float(a_str) - float(b_str) == pytest.approx(q.answer)

    def test_multiplication_format(self):
        cfg = OpConfig("Multiplication", operand2_lo=2, operand2_hi=12)
        for _ in range(20):
            q = generate_question(cfg)
            assert " x " in q.display

    def test_multiplication_operand_range(self):
        cfg = OpConfig("Multiplication", operand2_lo=3, operand2_hi=9)
        for _ in range(100):
            q = generate_question(cfg)
            a_str, b_str = q.display.split(" x ")
            a, b = int(a_str), int(b_str)
            assert 3 <= a <= 9
            assert 3 <= b <= 9
            assert q.answer == a * b

    def test_multiplication_answer_correct(self):
        cfg = OpConfig("Multiplication", operand2_lo=2, operand2_hi=12, decimals=0)
        for _ in range(50):
            q = generate_question(cfg)
            a_str, b_str = q.display.split(" x ")
            assert float(a_str) * float(b_str) == pytest.approx(q.answer)

    def test_division_format(self):
        cfg = OpConfig("Division", operand2_lo=2, operand2_hi=12)
        for _ in range(20):
            q = generate_question(cfg)
            assert " / " in q.display

    def test_division_integer_exact(self):
        cfg = OpConfig("Division", operand2_lo=2, operand2_hi=12, decimals=0)
        for _ in range(100):
            q = generate_question(cfg)
            assert q.answer == int(round(q.answer))

    def test_division_answer_correct_integer(self):
        cfg = OpConfig("Division", operand2_lo=2, operand2_hi=12, decimals=0)
        for _ in range(50):
            q = generate_question(cfg)
            dividend_str, divisor_str = q.display.split(" / ")
            assert float(dividend_str) / float(divisor_str) == pytest.approx(q.answer)

    def test_division_answer_correct_decimal(self):
        cfg = OpConfig("Division", operand2_lo=2, operand2_hi=9, decimals=2)
        for _ in range(50):
            q = generate_question(cfg)
            dividend_str, divisor_str = q.display.split(" / ")
            exact = Decimal(dividend_str) / Decimal(divisor_str)
            expected = exact.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            assert q.answer_str == str(expected)

    def test_multiplication_rounds_half_up(self):
        cfg = OpConfig("Multiplication", operand2_lo=1, operand2_hi=9, decimals=1)
        with patch.object(random, "randint", side_effect=[15, 15]):
            q = generate_question(cfg)
        assert q.display == "1.5 x 1.5"
        assert q.answer_str == "2.3"
        assert check_answer("2.3", q)
        assert not check_answer("2.2", q)

    def test_division_rounds_half_up(self):
        cfg = OpConfig("Division", operand2_lo=2, operand2_hi=9, decimals=1)
        with patch.object(random, "randint", side_effect=[2, 25]):
            q = generate_question(cfg)
        assert q.display == "2.5 / 2"
        assert q.answer_str == "1.3"

    def test_multiplication_no_float_error(self):
        cfg = OpConfig("Multiplication", operand2_lo=1, operand2_hi=9, decimals=1)
        with patch.object(random, "randint", side_effect=[23, 15]):
            q = generate_question(cfg)
        assert q.display == "2.3 x 1.5"
        assert q.answer_str == "3.5"

    def test_op_label_set(self):
        cfg = OpConfig("Addition", digits=2)
        q = generate_question(cfg)
        assert q.op_label == cfg.label


class TestCheckAnswer:
    def _q(self, answer, dec):
        return Question("x", answer, dec)

    def test_correct_integer(self):
        assert check_answer("42", self._q(42.0, 0)) is True

    def test_wrong_integer(self):
        assert check_answer("43", self._q(42.0, 0)) is False

    def test_negative_correct(self):
        assert check_answer("-5", self._q(-5.0, 0)) is True

    def test_integer_with_decimal_notation_accepted(self):
        assert check_answer("42.0", self._q(42.0, 0)) is True

    def test_integer_answer_rejects_non_whole_input(self):
        assert check_answer("41.6", self._q(42.0, 0)) is False
        assert check_answer("42.4", self._q(42.0, 0)) is False

    def test_integer_answer_rejects_half_rounding(self):
        assert check_answer("2.5", self._q(2.0, 0)) is False

    def test_correct_1dp(self):
        assert check_answer("3.5", self._q(3.5, 1)) is True

    def test_wrong_1dp(self):
        assert check_answer("3.6", self._q(3.5, 1)) is False

    def test_correct_2dp(self):
        assert check_answer("1.23", self._q(1.23, 2)) is True

    def test_decimal_rounding_tolerance(self):
        assert check_answer("1.235", self._q(1.24, 2)) is True

    def test_empty_string(self):
        assert check_answer("", self._q(5.0, 0)) is False

    def test_non_numeric(self):
        assert check_answer("abc", self._q(5.0, 0)) is False

    def test_none_value(self):
        assert check_answer(None, self._q(5.0, 0)) is False

    def test_just_minus(self):
        assert check_answer("-", self._q(-1.0, 0)) is False

    def test_just_dot(self):
        assert check_answer(".", self._q(0.0, 1)) is False

    def test_near_miss_not_rounded_by_float(self):
        # float() would round this to exactly 42.0.
        assert check_answer("41.99999999999999999", self._q(42.0, 0)) is False

    def test_extra_places_round_half_up(self):
        assert check_answer("2.25", self._q(2.3, 1)) is True

    @pytest.mark.parametrize("text", ["inf", "-inf", "nan", "sNaN", "1e999999999"])
    def test_non_finite_rejected(self, text):
        assert check_answer(text, self._q(5.0, 0)) is False
        assert check_answer(text, self._q(5.0, 2)) is False

    def test_zero_correct(self):
        assert check_answer("0", self._q(0.0, 0)) is True

    def test_zero_wrong(self):
        assert check_answer("1", self._q(0.0, 0)) is False


class TestCfgSerialization:
    @pytest.mark.parametrize(
        "cfg",
        [
            OpConfig("Addition"),
            OpConfig("Subtraction", digits=3, decimals=1, allow_negative=True),
            OpConfig("Multiplication", operand2_lo=5, operand2_hi=20),
            OpConfig("Division", operand2_lo=3, operand2_hi=15, decimals=2),
        ],
    )
    def test_roundtrip(self, cfg):
        assert cfg_from_dict(asdict(cfg)) == cfg

    def test_dict_to_cfg_uses_defaults_for_missing_keys(self):
        d = {"operation": "Addition"}
        cfg = cfg_from_dict(d)
        assert cfg.digits == 2
        assert cfg.decimals == 0
        assert cfg.operand2_lo == 2
        assert cfg.operand2_hi == 12
        assert cfg.allow_negative is False

    def test_dict_to_cfg_ignores_unknown_keys(self):
        cfg = cfg_from_dict({"operation": "Addition", "unknown_setting": True})
        assert cfg == OpConfig("Addition")

    def test_dict_to_cfg_requires_operation(self):
        with pytest.raises(KeyError):
            cfg_from_dict({"digits": 2})


class TestDataPersistence:
    def test_load_returns_empty_on_missing_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_storage_mod, "DATA_FILE", tmp_path / "nonexistent.json")
        assert load_data() == {}

    def test_load_returns_empty_on_corrupt_json(self, tmp_path, monkeypatch):
        f = tmp_path / "data.json"
        f.write_text("NOT JSON")
        monkeypatch.setattr(_storage_mod, "DATA_FILE", f)
        assert load_data() == {}

    def test_save_and_load_roundtrip(self, tmp_path, monkeypatch):
        f = tmp_path / "data.json"
        monkeypatch.setattr(_storage_mod, "DATA_FILE", f)
        data = {"sessions": [{"ts": "2024-01-01 12:00", "total": 10, "correct": 8}]}
        save_data(data)
        assert load_data() == data

    def test_save_raises_on_os_error(self, tmp_path, monkeypatch):
        f = tmp_path / "data.json"
        monkeypatch.setattr(_storage_mod, "DATA_FILE", f)
        with (
            patch.object(Path, "write_text", side_effect=OSError("no disk")),
            pytest.raises(OSError, match="no disk"),
        ):
            save_data({"x": 1})

    def test_load_returns_empty_on_non_dict_json(self, tmp_path, monkeypatch):
        f = tmp_path / "data.json"
        f.write_text("[1, 2, 3]")
        monkeypatch.setattr(_storage_mod, "DATA_FILE", f)
        assert load_data() == {}

    def test_save_failure_keeps_existing_file(self, tmp_path, monkeypatch):
        f = tmp_path / "data.json"
        f.write_text(json.dumps({"sessions": ["old"]}))
        monkeypatch.setattr(_storage_mod, "DATA_FILE", f)
        with (
            patch.object(_storage_mod.os, "replace", side_effect=OSError("boom")),
            pytest.raises(OSError),
        ):
            save_data({"sessions": ["new"]})
        assert load_data() == {"sessions": ["old"]}
        assert [p.name for p in tmp_path.iterdir()] == ["data.json"]

    @pytest.mark.parametrize(
        "content",
        ["[" * 100_000, "1" * 5000, b"\xff\xfe"],
        ids=["deep-nesting", "huge-int", "bad-utf8"],
    )
    def test_load_returns_empty_on_unparseable(self, tmp_path, monkeypatch, content):
        f = tmp_path / "data.json"
        if isinstance(content, bytes):
            f.write_bytes(content)
        else:
            f.write_text(content)
        monkeypatch.setattr(_storage_mod, "DATA_FILE", f)
        assert load_data() == {}

    @pytest.mark.parametrize("content", ["NOT JSON", "[1, 2, 3]"])
    def test_unusable_file_set_aside_not_overwritten(
        self, tmp_path, monkeypatch, content
    ):
        f = tmp_path / "data.json"
        f.write_text(content)
        monkeypatch.setattr(_storage_mod, "DATA_FILE", f)
        assert load_data() == {}
        save_data({"sessions": []})
        assert (tmp_path / "data.json.corrupt").read_text() == content
        assert load_data() == {"sessions": []}

    def test_unreadable_file_set_aside_not_overwritten(self, tmp_path, monkeypatch):
        f = tmp_path / "data.json"
        f.write_text('{"sessions": ["old"]}')
        monkeypatch.setattr(_storage_mod, "DATA_FILE", f)
        with patch.object(Path, "read_text", side_effect=PermissionError):
            assert load_data() == {}
        save_data({"sessions": []})
        assert (tmp_path / "data.json.corrupt").read_text() == '{"sessions": ["old"]}'

    def test_save_leaves_no_temp_file(self, tmp_path, monkeypatch):
        f = tmp_path / "data.json"
        monkeypatch.setattr(_storage_mod, "DATA_FILE", f)
        save_data({"x": 1})
        assert [p.name for p in tmp_path.iterdir()] == ["data.json"]

    def test_load_full_structure(self, tmp_path, monkeypatch):
        f = tmp_path / "data.json"
        payload = {"sessions": [], "last_config": {"t_idx": 2, "configs": []}}
        f.write_text(json.dumps(payload))
        monkeypatch.setattr(_storage_mod, "DATA_FILE", f)
        assert load_data() == payload


class TestMakeSession:
    def _q(self, op_label, correct):
        q = Question("x", 1.0, 0, op_label=op_label)
        q.correct = correct
        return q

    def test_returns_none_for_empty_questions(self):
        cfg = OpConfig("Addition")
        assert make_session([], [cfg], 30) is None

    def test_basic_session_structure(self):
        cfg = OpConfig("Addition")
        qs = [self._q(cfg.label, True), self._q(cfg.label, False)]
        sess = make_session(qs, [cfg], 30)
        assert sess is not None
        assert sess["total"] == 2
        assert sess["correct"] == 1
        assert sess["time_limit"] == 30

    def test_per_op_aggregation(self):
        add_cfg = OpConfig("Addition")
        sub_cfg = OpConfig("Subtraction")
        qs = [
            self._q(add_cfg.label, True),
            self._q(add_cfg.label, True),
            self._q(sub_cfg.label, False),
        ]
        sess = make_session(qs, [add_cfg, sub_cfg], 60)
        assert sess["per_op"][add_cfg.label] == {"total": 2, "correct": 2}
        assert sess["per_op"][sub_cfg.label] == {"total": 1, "correct": 0}

    def test_configs_serialized(self):
        cfg = OpConfig("Multiplication", operand2_lo=3, operand2_hi=9)
        qs = [self._q(cfg.label, True)]
        sess = make_session(qs, [cfg], 30)
        assert sess["configs"] == [asdict(cfg)]

    def test_time_limit_stored(self):
        cfg = OpConfig("Addition")
        qs = [self._q(cfg.label, True)]
        for _, secs in TIME_OPTIONS:
            sess = make_session(qs, [cfg], secs)
            assert sess["time_limit"] == secs

    def test_timestamp_format(self):
        cfg = OpConfig("Addition")
        qs = [self._q(cfg.label, True)]
        sess = make_session(qs, [cfg], 30)
        assert re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", sess["ts"])

    def test_all_correct(self):
        cfg = OpConfig("Addition")
        qs = [self._q(cfg.label, True) for _ in range(5)]
        sess = make_session(qs, [cfg], 30)
        assert sess["correct"] == 5
        assert sess["total"] == 5

    def test_all_wrong(self):
        cfg = OpConfig("Addition")
        qs = [self._q(cfg.label, False) for _ in range(3)]
        sess = make_session(qs, [cfg], 30)
        assert sess["correct"] == 0


class TestBuildRows:
    def _rows(self, cfg):
        return {r.field: r for r in _build_rows(cfg)}

    def test_addition_rows(self):
        assert list(self._rows(OpConfig("Addition"))) == ["digits", "decimals"]

    def test_subtraction_rows_includes_allow_negative(self):
        assert list(self._rows(OpConfig("Subtraction"))) == [
            "digits",
            "decimals",
            "allow_negative",
        ]

    @pytest.mark.parametrize("op", ["Multiplication", "Division"])
    def test_range_rows(self, op):
        assert list(self._rows(OpConfig(op))) == [
            "operand2_lo",
            "operand2_hi",
            "decimals",
        ]

    def test_row_values(self):
        row = self._rows(OpConfig("Addition", digits=3))["digits"]
        assert (row.value, row.min_val, row.max_val) == (3, 1, 4)

    def test_decimals_row_bounds(self):
        row = self._rows(OpConfig("Addition"))["decimals"]
        assert (row.min_val, row.max_val) == (0, 3)

    def test_multiplication_range_bounds(self):
        rows = self._rows(OpConfig("Multiplication", operand2_lo=5, operand2_hi=15))
        lo, hi = rows["operand2_lo"], rows["operand2_hi"]
        assert (lo.value, lo.min_val, lo.max_val) == (5, 1, 15)
        assert (hi.value, hi.min_val, hi.max_val) == (15, 5, 99)

    def test_division_divisor_min_is_2(self):
        row = self._rows(OpConfig("Division", operand2_lo=3))["operand2_lo"]
        assert row.min_val == 2


class TestRunOpConfig:
    def _run(self, monkeypatch, cfg, keys):
        monkeypatch.setattr(_menus_mod.curses, "color_pair", lambda _: 0)
        monkeypatch.setattr(_menus_mod.curses, "doupdate", lambda: None)
        stdscr = MagicMock()
        stdscr.getmaxyx.return_value = (24, 80)
        stdscr.getch.side_effect = [ord(k) if isinstance(k, str) else k for k in keys]
        return run_op_config(stdscr, cfg)

    def test_edits_fields_within_bounds(self, monkeypatch):
        cfg = OpConfig("Subtraction", digits=4)
        keys = ["l", "j", "l", "l", "j", "l", "l", 10]
        result = self._run(monkeypatch, cfg, keys)
        assert result == OpConfig(
            "Subtraction", digits=4, decimals=2, allow_negative=True
        )
        assert cfg == OpConfig("Subtraction", digits=4)

    def test_range_rows_bound_each_other(self, monkeypatch):
        cfg = OpConfig("Division", operand2_lo=5, operand2_hi=6)
        keys = ["l", "l", "l", "j", "h", "h", 10]
        result = self._run(monkeypatch, cfg, keys)
        assert (result.operand2_lo, result.operand2_hi) == (6, 6)

    def test_escape_cancels(self, monkeypatch):
        assert self._run(monkeypatch, OpConfig("Addition"), ["l", 27]) is None


class TestQLine:
    def test_correct_question_omits_user_answer(self):
        q = Question("5 + 3", 8.0, 0, user_answer="8")
        q.correct = True
        line = _q_line(q)
        assert line.startswith("[+]")
        assert "5 + 3" in line
        assert "8" in line
        assert "you:" not in line

    def test_wrong_question_shows_user_answer(self):
        q = Question("5 + 3", 8.0, 0, user_answer="9")
        q.correct = False
        line = _q_line(q)
        assert line.startswith("[-]")
        assert "5 + 3" in line
        assert "8" in line
        assert "you: 9" in line

    def test_decimal_answer_str(self):
        q = Question("1.5 + 1.5", 3.0, 1, user_answer="3.0")
        q.correct = True
        line = _q_line(q)
        assert "3.0" in line

    def test_negative_answer(self):
        q = Question("3 - 7", -4.0, 0, user_answer="-4")
        q.correct = True
        line = _q_line(q)
        assert "[+]" in line
        assert "-4" in line


class TestParseLastConfig:
    def test_valid_config(self):
        lc = {
            "t_idx": 2,
            "configs": [
                asdict(OpConfig("Division")),
                asdict(OpConfig("Addition")),
            ],
        }
        state = _parse_last_config(lc)
        assert state is not None
        assert [c.operation for c in state.configs] == ["Division", "Addition"]
        assert state.indices == [0, 3]
        assert state.t_idx == 2
        assert state.guest_mode is False

    def test_unknown_keys_ignored(self):
        lc = {"configs": [{"operation": "Addition"}], "unknown_setting": True}
        state = _parse_last_config(lc)
        assert state is not None
        assert state.configs == [OpConfig("Addition")]

    def test_t_idx_clamped(self):
        cfgs = [{"operation": "Addition"}]
        assert (
            _parse_last_config({"configs": cfgs, "t_idx": 99}).t_idx
            == len(TIME_OPTIONS) - 1
        )
        assert _parse_last_config({"configs": cfgs, "t_idx": -3}).t_idx == 0

    @pytest.mark.parametrize(
        "lc",
        [
            None,
            {},
            "garbage",
            {"configs": []},
            {"configs": "nope"},
            {"configs": [{"digits": 2}]},
            {"configs": [{"operation": "Exponentiation"}]},
            {"configs": [{"operation": "Addition"}], "t_idx": "x"},
            {"configs": [{"operation": "Addition"}], "t_idx": float("inf")},
            {"configs": [{"operation": "Addition"}], "t_idx": float("nan")},
            {"configs": [{"operation": ["Addition"]}]},
            {"configs": [{"operation": {"x": 1}}]},
            {"configs": [{"operation": "Addition"}, {"operation": "Addition"}]},
            {"configs": [{"operation": "Addition", "digits": "2"}]},
            {"configs": [{"operation": "Addition", "digits": 0}]},
            {"configs": [{"operation": "Addition", "digits": 5}]},
            {"configs": [{"operation": "Addition", "decimals": 4}]},
            {"configs": [{"operation": "Addition", "decimals": True}]},
            {"configs": [{"operation": "Subtraction", "allow_negative": "no"}]},
            {"configs": [{"operation": "Division", "operand2_lo": 1}]},
            {"configs": [{"operation": "Multiplication", "operand2_hi": 100}]},
            {
                "configs": [
                    {"operation": "Multiplication", "operand2_lo": 9, "operand2_hi": 3}
                ]
            },
        ],
    )
    def test_invalid_returns_none(self, lc):
        assert _parse_last_config(lc) is None


def _make_game():
    stdscr = MagicMock()
    stdscr.getmaxyx.return_value = (24, 80)
    return Game(stdscr, [OpConfig("Addition", digits=1, decimals=0)], 60)


def _type(game, text):
    for ch in text:
        game._handle_key(ord(ch))


class TestGameInput:
    def test_digits_append(self):
        g = _make_game()
        _type(g, "42")
        assert g.buf == "42"

    def test_backspace_removes_last_char(self):
        g = _make_game()
        _type(g, "42")
        g._handle_key(127)
        assert g.buf == "4"

    def test_backspace_on_empty_is_noop(self):
        g = _make_game()
        g._handle_key(127)
        assert g.buf == ""

    def test_single_decimal_point(self):
        g = _make_game()
        _type(g, "1.2.3")
        assert g.buf == "1.23"

    def test_minus_only_at_start(self):
        g = _make_game()
        _type(g, "-4-")
        assert g.buf == "-4"

    def test_other_keys_ignored(self):
        g = _make_game()
        _type(g, "a1 b")
        g._handle_key(1000)
        assert g.buf == "1"

    def test_enter_submits_and_advances(self):
        g = _make_game()
        first = g.current
        _type(g, first.answer_str)
        g._handle_key(10)
        assert g.questions == [first]
        assert first.correct is True
        assert first.user_answer == first.answer_str
        assert g.buf == ""
        assert g.current is not first

    def test_wrong_answer_recorded(self):
        g = _make_game()
        _type(g, "999")
        g._handle_key(13)
        assert g.questions[0].correct is False

    @pytest.mark.parametrize("text", ["", "-", ".", "-."])
    def test_incomplete_input_not_submitted(self, text):
        g = _make_game()
        _type(g, text)
        g._handle_key(10)
        assert g.questions == []

    def test_non_ascii_digits_ignored(self):
        g = _make_game()
        for key in (0xB2, 0xB3, 0xB9):
            g._handle_key(key)
        assert g.buf == ""


class TestGameDraw:
    @pytest.mark.parametrize("width", [30, 40, 60, 80, 120])
    def test_header_items_do_not_overlap(self, monkeypatch, width):
        monkeypatch.setattr(_game_mod.curses, "color_pair", lambda _: 0)
        monkeypatch.setattr(_game_mod.curses, "doupdate", lambda: None)
        stdscr = MagicMock()
        stdscr.getmaxyx.return_value = (24, width)
        g = Game(stdscr, [OpConfig(op) for op in OPERATIONS], 60, guest_mode=True)
        g._draw()
        header = sorted(
            c.args[1:3] for c in stdscr.addstr.call_args_list if c.args[0] == 1
        )
        assert len(header) == (3 if width == 30 else 4)
        for (x, text), (next_x, _) in pairwise(header):
            assert x + len(text) <= next_x


class TestGameTimer:
    def _game_at(self, monkeypatch, elapsed):
        clock = [1000.0]
        monkeypatch.setattr(_game_mod.time, "monotonic", lambda: clock[0])
        g = _make_game()
        clock[0] += elapsed
        return g

    @pytest.mark.parametrize(
        "elapsed, remaining",
        [(0, 60), (0.5, 60), (1.0, 59), (59.5, 1), (60, 0), (75, 0)],
    )
    def test_counts_down_whole_seconds(self, monkeypatch, elapsed, remaining):
        assert self._game_at(monkeypatch, elapsed).time_remaining == remaining

    def test_run_returns_answered_questions_when_time_is_up(self, monkeypatch):
        clock = [0.0]
        monkeypatch.setattr(_game_mod.time, "monotonic", lambda: clock[0])
        monkeypatch.setattr(_game_mod.curses, "curs_set", lambda _: None)
        monkeypatch.setattr(_game_mod.curses, "color_pair", lambda _: 0)
        monkeypatch.setattr(_game_mod.curses, "doupdate", lambda: None)
        flushinp = MagicMock()
        monkeypatch.setattr(_game_mod.curses, "flushinp", flushinp)
        g = _make_game()
        keys = [ord(c) for c in g.current.answer_str] + [10]

        def getch():
            if keys:
                return keys.pop(0)
            clock[0] += 61
            return -1

        g.stdscr.getch.side_effect = getch
        monkeypatch.setattr(_game_mod.time, "sleep", lambda _: None)
        questions = g.run()
        assert len(questions) == 1
        assert questions[0].correct is True
        flushinp.assert_called_once()


class TestCfgIsValid:
    @pytest.mark.parametrize("op", OPERATIONS)
    def test_defaults_valid(self, op):
        assert cfg_is_valid(OpConfig(op))

    def test_menu_extremes_valid(self):
        assert cfg_is_valid(OpConfig("Addition", digits=4, decimals=3))
        assert cfg_is_valid(OpConfig("Multiplication", operand2_lo=1, operand2_hi=99))
        assert cfg_is_valid(OpConfig("Division", operand2_lo=2, operand2_hi=2))

    def test_unknown_operation_invalid(self):
        assert not cfg_is_valid(OpConfig("Modulo"))


def _session(**overrides):
    s = {"ts": "2024-01-01 12:00", "total": 4, "correct": 3}
    s.update(overrides)
    return s


class TestLoadSessions:
    def test_missing_sessions_creates_list(self):
        data = {}
        assert load_sessions(data) == []
        assert data["sessions"] == []

    def test_non_list_sessions_replaced(self):
        data = {"sessions": {"oops": 1}}
        assert load_sessions(data) == []

    def test_returned_list_is_stored(self):
        data = {"sessions": [_session()]}
        sessions = load_sessions(data)
        sessions.append(_session())
        assert data["sessions"] is sessions

    def test_valid_sessions_kept(self):
        full = _session(
            per_op={"Addition (2-digit)": {"total": 4, "correct": 3}},
            configs=[asdict(OpConfig("Addition"))],
            time_limit=60,
        )
        data = {"sessions": [_session(), full]}
        assert load_sessions(data) == [_session(), full]

    @pytest.mark.parametrize(
        "bad",
        [
            "garbage",
            {"total": 4, "correct": 3},
            _session(total="4"),
            _session(correct=None),
            _session(correct=5),
            _session(total=True),
            _session(per_op=[]),
            _session(per_op={"Addition": {"total": 1}}),
            _session(configs={}),
            _session(configs=[{"digits": 2}]),
        ],
    )
    def test_malformed_sessions_dropped(self, bad):
        data = {"sessions": [bad, _session()]}
        assert load_sessions(data) == [_session()]


class TestRunMenus:
    def _run(self, monkeypatch, op_configs, t_idx, state=None):
        monkeypatch.setattr(
            _app_mod, "run_multiselect", MagicMock(return_value=([0, 2], True))
        )
        monkeypatch.setattr(
            _app_mod, "run_op_config", MagicMock(side_effect=op_configs)
        )
        monkeypatch.setattr(
            _app_mod, "run_single_select", MagicMock(return_value=t_idx)
        )
        return _run_menus(MagicMock(), state or _SessionState(), [])

    def test_completed(self, monkeypatch):
        add, mul = OpConfig("Addition", digits=3), OpConfig("Multiplication")
        state, done = self._run(monkeypatch, [add, mul], 1)
        assert done
        assert state == _SessionState([0, 2], [add, mul], 1, True)

    def test_back_from_op_config_keeps_choices(self, monkeypatch):
        add = OpConfig("Addition", digits=3)
        prev = _SessionState([1], [OpConfig("Subtraction")], 2, False)
        state, done = self._run(monkeypatch, [add, None], 0, state=prev)
        assert not done
        assert state.indices == [0, 2]
        assert state.guest_mode is True
        assert state.t_idx == 2
        assert add in state.configs

    @pytest.mark.parametrize("t_idx", [-1, len(TIME_OPTIONS)])
    def test_back_from_time_select_keeps_choices(self, monkeypatch, t_idx):
        add, mul = OpConfig("Addition", digits=3), OpConfig("Multiplication")
        state, done = self._run(monkeypatch, [add, mul], t_idx)
        assert not done
        assert state.indices == [0, 2]
        assert state.configs == [add, mul]
        assert state.t_idx == 0

    def test_previous_config_offered_again(self, monkeypatch):
        add = OpConfig("Addition", digits=4)
        mul = OpConfig("Multiplication")
        prev = _SessionState([0], [add], 0, False)
        self._run(monkeypatch, [add, mul], 0, state=prev)
        first_call = _app_mod.run_op_config.call_args_list[0]
        assert first_call.args[1] is add


class TestTerminalHelpers:
    def test_init_colours_skipped_without_colour_support(self, monkeypatch):
        start = MagicMock()
        monkeypatch.setattr(_helpers_mod.curses, "has_colors", lambda: False)
        monkeypatch.setattr(_helpers_mod.curses, "start_color", start)
        _helpers_mod.init_colours()
        start.assert_not_called()

    def test_addstr_clips_at_right_edge(self):
        stdscr = MagicMock()
        stdscr.getmaxyx.return_value = (24, 10)
        _helpers_mod.addstr(stdscr, 0, 6, "abcdef")
        stdscr.addstr.assert_called_once_with(0, 6, "abcd", 0)

    def test_hide_cursor_tolerates_unsupported_terminal(self, monkeypatch):
        def curs_set(_):
            raise curses.error("unsupported")

        monkeypatch.setattr(_helpers_mod.curses, "curs_set", curs_set)
        _helpers_mod.hide_cursor()


@pytest.fixture
def screen(monkeypatch):
    monkeypatch.setattr(curses, "color_pair", lambda _: 0)
    monkeypatch.setattr(curses, "doupdate", lambda: None)
    stdscr = MagicMock()
    stdscr.getmaxyx.return_value = (24, 80)
    return stdscr


def _answered(n):
    qs = [Question(f"{i} + 1", i + 1.0, 0, "Addition (1-digit)") for i in range(n)]
    for i, q in enumerate(qs):
        q.user_answer, q.correct = str(i), i % 2 == 0
    return qs


class TestScreens:
    @pytest.mark.parametrize(
        "key, result",
        [("q", "quit"), (27, "quit"), ("r", "again"), (10, "again"), ("m", "menu")],
    )
    def test_results_actions(self, screen, key, result):
        screen.getch.side_effect = [ord(key) if isinstance(key, str) else key]
        assert show_results(screen, _answered(3), []) == result

    def test_results_scrolls_long_lists(self, screen):
        screen.getch.side_effect = [ord(k) for k in "jjjkq"]
        assert show_results(screen, _answered(200), []) == "quit"

    def test_results_with_no_questions(self, screen):
        screen.getch.side_effect = [ord("q")]
        assert show_results(screen, [], [], guest_mode=True) == "quit"

    def test_viz_navigates_every_view(self, screen):
        cfg = asdict(OpConfig("Subtraction", decimals=1, allow_negative=True))
        sessions = [
            _session(
                time_limit=60,
                per_op={"Addition (2-digit)": {"total": 4, "correct": 3}},
                configs=[asdict(OpConfig("Division")), cfg],
            ),
            _session(total=0, correct=0),
        ]
        keys = ["l", "j", 10, "x", "h", 10, "x", "\t", "q"]
        screen.getch.side_effect = [ord(k) if isinstance(k, str) else k for k in keys]
        show_viz(screen, sessions)
        drawn = " ".join(str(c.args[2]) for c in screen.addstr.call_args_list)
        assert "Divisor range: 2–12" in drawn
        assert "Allow negatives: yes" in drawn

    def test_viz_without_sessions(self, screen):
        screen.getch.side_effect = [ord("\t"), 10, 27]
        show_viz(screen, [])


class TestRun:
    def test_exits_with_message_without_tty(self, monkeypatch):
        import mentalmaths.__main__ as _main_mod

        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        wrapper = MagicMock()
        monkeypatch.setattr(_main_mod.curses, "wrapper", wrapper)
        with pytest.raises(SystemExit) as exc:
            _main_mod.run()
        assert "interactive terminal" in str(exc.value.code)
        wrapper.assert_not_called()
