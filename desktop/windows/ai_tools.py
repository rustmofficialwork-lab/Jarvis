"""Small, strictly allowlisted tools for JARVIS AI conversations.

Only deterministic, read-only utilities are exposed to the model. This module
never executes shell commands, Python supplied by a model, or filesystem work.
"""
from __future__ import annotations

import ast
import operator
from datetime import datetime
from typing import Any

MAX_EXPRESSION_LENGTH = 120
MAX_ABS_RESULT = 1_000_000_000_000
MAX_POWER = 8

_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
}
_UNARY_OPERATORS = {ast.UAdd: operator.pos, ast.USub: operator.neg}

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "Evaluate a basic arithmetic expression. Use only for calculations.",
            "parameters": {
                "type": "object",
                "properties": {"expression": {"type": "string", "maxLength": MAX_EXPRESSION_LENGTH}},
                "required": ["expression"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_local_time",
            "description": "Get the computer's current local date, time, and timezone.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
]


def _safe_number(value: Any) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Only numeric arithmetic is supported.")
    if abs(value) > MAX_ABS_RESULT:
        raise ValueError("The result is outside the supported range.")
    return value


def _evaluate_node(node: ast.AST, depth: int = 0) -> int | float:
    if depth > 20:
        raise ValueError("Expression is too complex.")
    if isinstance(node, ast.Expression):
        return _evaluate_node(node.body, depth + 1)
    if isinstance(node, ast.Constant):
        return _safe_number(node.value)
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPERATORS:
        left = _evaluate_node(node.left, depth + 1)
        right = _evaluate_node(node.right, depth + 1)
        if isinstance(node.op, ast.Pow):
            if abs(right) > MAX_POWER:
                raise ValueError("Powers are limited to an exponent of 8.")
            result = left ** right
        else:
            result = _BINARY_OPERATORS[type(node.op)](left, right)
        return _safe_number(result)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPERATORS:
        return _safe_number(_UNARY_OPERATORS[type(node.op)](_evaluate_node(node.operand, depth + 1)))
    raise ValueError("Use numbers, parentheses, and basic arithmetic operators only.")


def calculate(expression: str) -> str:
    if not isinstance(expression, str):
        raise ValueError("Expression must be text.")
    expression = expression.strip()
    if not expression or len(expression) > MAX_EXPRESSION_LENGTH:
        raise ValueError("Expression must contain 1 to 120 characters.")
    try:
        tree = ast.parse(expression, mode="eval")
        result = _evaluate_node(tree)
    except (SyntaxError, ZeroDivisionError, OverflowError) as exc:
        raise ValueError("That arithmetic expression could not be evaluated.") from exc
    if isinstance(result, float) and result.is_integer():
        return str(int(result))
    return str(result)


def execute_tool(name: str, arguments: dict[str, Any]) -> str:
    """Execute one allowlisted read-only tool with exact argument validation."""
    if not isinstance(arguments, dict):
        raise ValueError("Tool arguments must be a JSON object.")
    if name == "calculator":
        if set(arguments) != {"expression"}:
            raise ValueError("Calculator requires only an expression.")
        return calculate(arguments["expression"])
    if name == "get_local_time":
        if arguments:
            raise ValueError("The time tool does not accept arguments.")
        return datetime.now().astimezone().isoformat(timespec="seconds")
    raise ValueError("That JARVIS tool is not available.")
