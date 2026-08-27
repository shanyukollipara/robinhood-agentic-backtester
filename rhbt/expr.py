"""Safe, vectorised evaluation of strategy rule expressions.

A rule is an ordinary Python expression written against price columns and the
indicator library, e.g.::

    sma(close, 50) > sma(close, 200) and rsi(close, 14) < 70

It is parsed, validated against an allow-list (no imports, attribute access,
subscripting, comprehensions, lambdas or dunder names), rewritten so that
``and`` / ``or`` / ``not`` operate element-wise on pandas Series, and evaluated
once over the whole price history. The result is a boolean Series aligned to
the bar index, which the engine then reads bar by bar.
"""

from __future__ import annotations

import ast
from typing import Any, Mapping

import numpy as np
import pandas as pd

from .indicators import INDICATORS

_ALLOWED_NODES = (
    ast.Expression, ast.BoolOp, ast.BinOp, ast.UnaryOp, ast.Compare, ast.Call,
    ast.Name, ast.Load, ast.Constant, ast.IfExp, ast.Tuple,
    ast.And, ast.Or, ast.Not, ast.Invert, ast.USub, ast.UAdd,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
    ast.BitAnd, ast.BitOr, ast.BitXor,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
    ast.keyword,
)

PRICE_COLUMNS = ("open", "high", "low", "close", "volume")


class ExpressionError(ValueError):
    """Raised when a rule expression is malformed or uses a forbidden name."""


class _BoolRewriter(ast.NodeTransformer):
    """Rewrite ``and``/``or``/``not`` into element-wise ``&``/``|``/``~``."""

    def visit_BoolOp(self, node: ast.BoolOp) -> ast.AST:
        self.generic_visit(node)
        op = ast.BitAnd() if isinstance(node.op, ast.And) else ast.BitOr()
        expr = node.values[0]
        for right in node.values[1:]:
            expr = ast.BinOp(left=expr, op=op, right=right)
        return ast.copy_location(expr, node)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> ast.AST:
        self.generic_visit(node)
        if isinstance(node.op, ast.Not):
            return ast.copy_location(ast.UnaryOp(op=ast.Invert(), operand=node.operand), node)
        return node

    def visit_Compare(self, node: ast.Compare) -> ast.AST:
        # a < b < c  ->  (a < b) & (b < c)
        self.generic_visit(node)
        if len(node.ops) == 1:
            return node
        parts, left = [], node.left
        for op, right in zip(node.ops, node.comparators):
            parts.append(ast.Compare(left=left, ops=[op], comparators=[right]))
            left = right
        expr = parts[0]
        for part in parts[1:]:
            expr = ast.BinOp(left=expr, op=ast.BitAnd(), right=part)
        return ast.copy_location(expr, node)


def _validate(tree: ast.AST, allowed_names: set[str], source: str) -> None:
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise ExpressionError(
                f"{type(node).__name__} is not allowed in a rule expression: {source!r}"
            )
        if isinstance(node, ast.Name):
            if node.id.startswith("_"):
                raise ExpressionError(f"name {node.id!r} is not allowed")
            if node.id not in allowed_names:
                near = sorted(n for n in allowed_names if n.startswith(node.id[:2]))[:5]
                hint = f" Did you mean one of {near}?" if near else ""
                raise ExpressionError(
                    f"unknown name {node.id!r} in rule {source!r}.{hint}"
                )
        if isinstance(node, ast.Call) and not isinstance(node.func, ast.Name):
            raise ExpressionError("only direct calls to indicator functions are allowed")


def build_namespace(frame: pd.DataFrame, params: Mapping[str, Any] | None = None) -> dict:
    """Names visible to a rule expression for one symbol's price frame."""
    ns: dict[str, Any] = dict(INDICATORS)
    for col in PRICE_COLUMNS:
        if col in frame.columns:
            ns[col] = frame[col]
    ns["price"] = frame["close"]
    ns["typical"] = (frame["high"] + frame["low"] + frame["close"]) / 3.0
    ns["returns"] = frame["close"].pct_change()
    ns["bar"] = pd.Series(np.arange(len(frame), dtype=float), index=frame.index)
    ns["dayofweek"] = pd.Series(frame.index.dayofweek.astype(float), index=frame.index)
    ns["month"] = pd.Series(frame.index.month.astype(float), index=frame.index)
    ns["day"] = pd.Series(frame.index.day.astype(float), index=frame.index)
    ns["year"] = pd.Series(frame.index.year.astype(float), index=frame.index)
    ns["true"] = ns["True"] = True
    ns["false"] = ns["False"] = False
    ns["nan"] = float("nan")
    ns["pi"] = np.pi
    if params:
        for key, value in params.items():
            if not str(key).isidentifier() or str(key).startswith("_"):
                raise ExpressionError(f"invalid parameter name {key!r}")
            ns[str(key)] = value
    return ns


def evaluate(expression: str, frame: pd.DataFrame, params: Mapping[str, Any] | None = None):
    """Evaluate ``expression`` over a whole price frame. Returns a Series or scalar."""
    if expression is None:
        return None
    source = str(expression).strip()
    if not source:
        return None
    ns = build_namespace(frame, params)
    try:
        tree = ast.parse(source, mode="eval")
    except SyntaxError as exc:  # pragma: no cover - message passthrough
        raise ExpressionError(f"could not parse rule {source!r}: {exc.msg}") from exc
    _validate(tree, set(ns), source)
    tree = ast.fix_missing_locations(_BoolRewriter().visit(tree))
    try:
        result = eval(compile(tree, "<rule>", "eval"), {"__builtins__": {}}, ns)
    except Exception as exc:
        raise ExpressionError(f"error evaluating rule {source!r}: {exc}") from exc
    return result


def evaluate_bool(expression: str, frame: pd.DataFrame, params: Mapping[str, Any] | None = None) -> pd.Series:
    """Evaluate a rule and coerce the result to a boolean Series on the bar index."""
    result = evaluate(expression, frame, params)
    if result is None:
        return pd.Series(False, index=frame.index)
    if isinstance(result, pd.Series):
        return result.reindex(frame.index).fillna(False).astype(bool)
    return pd.Series(bool(result), index=frame.index)


def evaluate_numeric(expression, frame: pd.DataFrame, params: Mapping[str, Any] | None = None) -> pd.Series:
    """Evaluate a rule that yields a number (a constant is broadcast to all bars)."""
    if isinstance(expression, (int, float)) and not isinstance(expression, bool):
        return pd.Series(float(expression), index=frame.index)
    result = evaluate(expression, frame, params)
    if result is None:
        return pd.Series(np.nan, index=frame.index)
    if isinstance(result, pd.Series):
        return result.reindex(frame.index).astype(float)
    return pd.Series(float(result), index=frame.index)
