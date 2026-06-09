"""
This module provides high-level functions to create unit tests for
`clingo.ast` nodes.
"""

from typing import Any, List, cast
from unittest import TestCase

from clingo.ast import BodySimpleLiteral, parse_string
from clingo.core import Library

from eclingo.clingox.pprint import pformat

__all__ = [
    "ASTTestCase",
    "parse_literal",
    "parse_statement",
    "parse_term",
]


def parse_statement(lib: Library, stm: str) -> Any:
    """
    Parse a statement.
    """
    stms: List[Any] = []
    parse_string(lib, stm, stms.append)
    if len(stms) != 2:
        raise RuntimeError(
            f"syntax error: stm must contain exactly one statement, {len(stms)} given"
        )
    return stms[1]


def parse_literal(lib: Library, lit: str) -> Any:
    """
    Parse a literal.
    """
    stm = parse_statement(lib, f":-{lit}.")
    if not isinstance(stm.body[0], BodySimpleLiteral):
        raise RuntimeError("syntax error: lit must be a string representing a literal")
    return stm.body[0]


def parse_term(lib: Library, term: str) -> Any:
    """
    Parse a term.
    """
    lit = parse_literal(lib, f"atom({term})")
    return lit.literal.atom.pool[0].arguments[0]


def _ast_eq(first: Any, second: Any) -> bool:
    """
    Compare two AST nodes for equality, returning False on TypeError (incompatible types).
    """
    try:
        return first == second
    except TypeError:
        return False


class ASTTestCase(TestCase):
    """
    Class for comparing clingo AST nodes.
    """

    def assertASTEqual(self, first: Any, second: Any, msg: Any = None):
        """
        Test whether two clingo AST nodes are equal.
        """
        # pylint: disable=invalid-name
        first_repr = f"{type(first).__name__}({str(first)})"
        second_repr = f"{type(second).__name__}({str(second)})"
        self.assertEqual(first_repr, second_repr, msg)
        if not _ast_eq(first, second):
            raise AssertionError(f"{first!r} != {second!r}" if msg is None else msg)

    def assertEqual(self, first: Any, second: Any, msg: Any = None) -> None:
        """
        Test equality using clingo 6 AST-compatible comparison.
        """
        # pylint: disable=invalid-name
        if not _ast_eq(first, second):
            if not isinstance(first, str) and not isinstance(second, str):
                raise AssertionError(
                    f"{first!r} != {second!r}" if msg is None else msg
                )
        super().assertEqual(first, second, msg)
