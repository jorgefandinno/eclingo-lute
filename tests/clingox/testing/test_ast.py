"""
Tests for the `clingox.testing.ast` module.
"""

from unittest import TestCase

from clingo import ast
from clingo.core import Library, Location, Position
from clingo.symbol import Function

from eclingo.clingox.testing.ast import (
    ASTTestCase,
    parse_literal,
    parse_statement,
    parse_term,
)


class TestBasicASTParsing(TestCase):
    """
    Tests for basic AST parsing.
    """

    def setUp(self):
        self.lib = Library(message_limit=0)
        self.loc = Location(
            Position(self.lib, "a", 1, 2), Position(self.lib, "a", 1, 2)
        )

    def symbolic_literal(self, name: str) -> ast.Literal:
        """
        Create a positive symbolic literal with the given constant name.
        """
        return ast.LiteralSymbolic(
            self.lib,
            self.loc,
            ast.Sign.NoSign,
            ast.TermSymbolic(self.lib, self.loc, Function(self.lib, name)),
        )

    def test_parse_statement(self):
        """
        Test parse_statement.
        """
        rule = ast.StatementRule(
            self.lib,
            self.loc,
            ast.HeadSimpleLiteral(self.lib, self.symbolic_literal("a")),
            [ast.BodySimpleLiteral(self.lib, self.symbolic_literal("b"))],
        )
        self.assertEqual(parse_statement(self.lib, "a :- b."), rule)
        with self.assertRaisesRegex(RuntimeError, "syntax error"):
            parse_statement(self.lib, "a")
        with self.assertRaisesRegex(RuntimeError, "syntax error"):
            parse_statement(self.lib, "a.b.")
        with self.assertRaisesRegex(RuntimeError, "syntax error"):
            parse_statement(self.lib, "")

    def test_parse_literal(self):
        """
        Test parse_literal.
        """
        lit = self.symbolic_literal("a")
        self.assertEqual(parse_literal(self.lib, "a"), lit)
        with self.assertRaisesRegex(RuntimeError, "syntax error"):
            parse_literal(self.lib, "+a")
        with self.assertRaisesRegex(RuntimeError, "syntax error"):
            parse_literal(self.lib, "a: b")

    def test_parse_term(self):
        """
        Test parse_term.
        """
        term = ast.TermSymbolic(self.lib, self.loc, Function(self.lib, "a"))
        self.assertEqual(parse_term(self.lib, "a"), term)
        with self.assertRaisesRegex(RuntimeError, "syntax error"):
            parse_term(self.lib, "+a")


class TestASTTestCaseClass(ASTTestCase):
    """
    Test ASTTestCase class.
    """

    # pylint: disable=invalid-name

    def setUp(self):
        self.lib = Library(message_limit=0)

    def test_assertASTEqual(self):
        """
        Test assertASTEqual.
        """
        lib = self.lib
        self.assertEqual(parse_term(lib, "a"), parse_term(lib, "a"))
        self.assertEqual(parse_term(lib, "a(b(X))"), parse_term(lib, "a(b(X))"))
        with self.assertRaises(AssertionError) as ar:
            self.assertEqual(parse_term(lib, "a"), parse_term(lib, "b"))
        self.assertIn("'a' != 'b'", str(ar.exception))

        with self.assertRaises(AssertionError) as ar:
            self.assertEqual(parse_term(lib, "a(b)"), parse_term(lib, "a(c)"))
        self.assertIn("'a(b)' != 'a(c)'", str(ar.exception))

    def test_assertEqual(self):
        """
        Test assertEqual.
        """
        lib = self.lib
        self.assertEqual(parse_term(lib, "a"), parse_term(lib, "a"))
        self.assertEqual(parse_literal(lib, "a"), parse_literal(lib, "a"))
        with self.assertRaises(AssertionError) as ar:
            self.assertEqual(parse_literal(lib, "a"), parse_literal(lib, "b"))
        self.assertIn("'a' != 'b'", str(ar.exception))
