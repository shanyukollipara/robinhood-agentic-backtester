import pandas as pd
import pytest

from rhbt.expr import ExpressionError, evaluate, evaluate_bool
from tests.conftest import make_frame


@pytest.fixture
def frame():
    return make_frame(seed=1, periods=400)


def test_boolean_ops_are_elementwise(frame):
    result = evaluate_bool("close > 0 and close > 0", frame)
    assert result.all() and len(result) == len(frame)


def test_or_and_not(frame):
    assert evaluate_bool("close > 0 or close < 0", frame).all()
    assert not evaluate_bool("not (close > 0)", frame).any()


def test_chained_comparison(frame):
    assert evaluate_bool("0 < close < 1e9", frame).all()


def test_params_are_visible(frame):
    fast = evaluate_bool("sma(close, window) > 0", frame, {"window": 10})
    assert fast.iloc[-1]


def test_unknown_name_is_rejected(frame):
    with pytest.raises(ExpressionError, match="unknown name"):
        evaluate_bool("closee > 0", frame)


@pytest.mark.parametrize("source", [
    "__import__('os').system('ls')",
    "close.__class__",
    "[x for x in close]",
    "lambda: 1",
    "open('/etc/passwd')" ,
])
def test_dangerous_expressions_are_blocked(frame, source):
    with pytest.raises(ExpressionError):
        evaluate(source, frame)


def test_nan_is_false_not_an_error(frame):
    result = evaluate_bool("sma(close, 300) > close", frame)
    assert not bool(result.iloc[0])
