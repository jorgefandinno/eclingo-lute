"""
This module provides high-level functions to create unit tests for
`clingo.ast` nodes.
"""

from typing import Any
from unittest import TestCase

from clingo import ast
from clingo.core import Library

__all__ = [
    "ASTTestCase",
    "parse_literal",
    "parse_statement",
    "parse_term",
]

# All AST node classes in clingo.ast. They are identified by providing the
# `visit` method.
_AST_CLASSES = tuple(
    cls
    for cls in (getattr(ast, name) for name in dir(ast) if not name.startswith("_"))
    if isinstance(cls, type) and hasattr(cls, "visit")
)


def parse_statement(lib: Library, stm: str) -> ast.Statement:
    """
    Parse a statement.
    """
    try:
        return ast.parse_statement(lib, stm)
    except RuntimeError as exc:
        raise RuntimeError(f"syntax error: {exc}") from None


def parse_literal(lib: Library, lit: str) -> ast.Literal:
    """
    Parse a literal.
    """
    try:
        return ast.parse_literal(lib, lit)
    except RuntimeError as exc:
        raise RuntimeError(f"syntax error: {exc}") from None


def parse_term(lib: Library, term: str) -> ast.Term:
    """
    Parse a term.
    """
    try:
        return ast.parse_term(lib, term)
    except RuntimeError as exc:
        raise RuntimeError(f"syntax error: {exc}") from None


class ASTTestCase(TestCase):
    """
    Class for comparing `clingo.ast` nodes.
    """

    def __init__(self, methodName: str = "runTest"):
        """
        Create an instance of the class that will use the named test method
        when executed. Raises a ValueError if the instance does not have a
        method with the specified name.
        """
        super().__init__(methodName)
        for cls in _AST_CLASSES:
            self.addTypeEqualityFunc(cls, self.assertASTEqual)

    def assertASTEqual(self, first: Any, second: Any, msg: Any = None):
        """
        Test whether two `clingo.ast` nodes are equal.
        """
        # pylint: disable=invalid-name
        self.assertEqual(str(first), str(second), msg)
        self.assertEqual(type(first).__name__, type(second).__name__, msg)
        assert first == second
