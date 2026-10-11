"""Symbolic/numeric equivalence checks for math answers and worked-solution claims."""

from __future__ import annotations

import random
from typing import Any

import sympy as sp
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

_TRANSFORMS = standard_transformations + (implicit_multiplication_application, convert_xor)


def _parse(expr: str, symbols: dict[str, sp.Symbol]) -> sp.Expr:
    expr = expr.strip()
    if "=" in expr and "==" not in expr:
        lhs, rhs = expr.split("=", 1)
        return _parse(lhs, symbols) - _parse(rhs, symbols)
    return parse_expr(expr, local_dict=symbols, transformations=_TRANSFORMS, evaluate=True)


def check_math(expr_a: str, expr_b: str, variables: list[str] | None = None,
               tolerance: float = 1e-9) -> dict[str, Any]:
    """Are two expressions equivalent? Tries exact simplification, then random sampling.

    Equations ``lhs = rhs`` are compared as ``lhs - rhs``. Returns
    ``{"equivalent": True|False|None, "method": ..., "detail": ...}``; ``None`` means undecided.
    """
    symbols = {v: sp.Symbol(v) for v in (variables or [])}
    try:
        a, b = _parse(expr_a, symbols), _parse(expr_b, symbols)
    except Exception as exc:  # noqa: BLE001 - parse errors are reported, not raised
        return {"equivalent": None, "method": "parse", "detail": f"could not parse: {exc}"}

    try:
        if sp.simplify(a - b) == 0:
            return {"equivalent": True, "method": "symbolic", "detail": "simplify(a - b) == 0"}
    except Exception:  # noqa: BLE001
        pass

    free = sorted((a - b).free_symbols, key=str)
    if not free:
        try:
            diff = abs(complex(sp.N(a - b)))
            return {"equivalent": diff <= tolerance, "method": "numeric", "detail": f"|a-b| = {diff:.3g}"}
        except (TypeError, ValueError):
            return {"equivalent": None, "method": "numeric", "detail": "could not evaluate numerically"}

    rng = random.Random(0)
    f = sp.lambdify(free, a - b, modules="mpmath")
    checked = 0
    for _ in range(40):
        point = [rng.uniform(-3, 3) for _ in free]
        try:
            value = abs(complex(f(*point)))
        except (ZeroDivisionError, ValueError, TypeError, OverflowError):
            continue
        checked += 1
        if value > max(tolerance, 1e-7):
            return {"equivalent": False, "method": "sampling",
                    "detail": f"differ at {dict(zip(map(str, free), point))}"}
        if checked >= 12:
            break
    if checked == 0:
        return {"equivalent": None, "method": "sampling", "detail": "no valid sample points"}
    return {"equivalent": True, "method": "sampling", "detail": f"agree on {checked} random points"}
