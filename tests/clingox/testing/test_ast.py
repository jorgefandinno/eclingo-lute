"""
Tests for the `clingox.testing.ast` module.
"""

import textwrap
from unittest import TestCase

from clingo.core import Library

from eclingo.clingox.testing.ast import (
    ASTTestCase,
    parse_literal,
    parse_statement,
    parse_term,
)

lib = Library()


def dedent(text):
    """
    Dedenting with special handling for long lines.
    """
    lines = textwrap.dedent(text).splitlines(keepends=True)
    return "".join(line.replace("\\\n", "") for line in lines)


class TestBasicASTParsing(TestCase):
    """
    Tests for basic AST parsing.
    """

    def test_parse_statement(self):
        """
        Test parse_statement.
        """
        rule = parse_statement(lib, "a :- b.")
        self.assertEqual(str(rule), "a :- b.")
        # Parsing the same statement twice gives equal results
        self.assertEqual(parse_statement(lib, "a :- b."), rule)
        # Different statements are not equal
        self.assertNotEqual(parse_statement(lib, "a :- c."), rule)
        with self.assertRaises(RuntimeError):
            parse_statement(lib, "a")
        with self.assertRaises(RuntimeError):
            parse_statement(lib, "a.b.")
        with self.assertRaises(RuntimeError):
            parse_statement(lib, "")

    def test_parse_literal(self):
        """
        Test parse_literal.
        """
        lit = parse_literal(lib, "a")
        self.assertEqual(str(lit), "a")
        self.assertEqual(parse_literal(lib, "a"), lit)
        self.assertNotEqual(parse_literal(lib, "b"), lit)
        with self.assertRaises(RuntimeError):
            parse_literal(lib, "+a")
        with self.assertRaises(RuntimeError):
            parse_literal(lib, "a: b")

    def test_parse_term(self):
        """
        Test parse_term.
        """
        term = parse_term(lib, "a")
        self.assertEqual(str(term), "a")
        self.assertEqual(parse_term(lib, "a"), term)
        self.assertNotEqual(parse_term(lib, "b"), term)
        with self.assertRaises(RuntimeError):
            parse_term(lib, "+a")


class TestASTTestCaseClass(ASTTestCase):
    """
    Test ASTTestCase class.
    """

    # pylint: disable=invalid-name

    def test_assertASTEqual(self):
        """
        Test assertASTEqual.
        """
        self.assertASTEqual(parse_term(lib, "a"), parse_term(lib, "a"))
        self.assertASTEqual(parse_term(lib, "a(b(X))"), parse_term(lib, "a(b(X))"))
        with self.assertRaises(AssertionError):
            self.assertASTEqual(parse_term(lib, "a"), parse_term(lib, "b"))

        with self.assertRaises(AssertionError):
            self.assertASTEqual(parse_term(lib, "a(b)"), parse_term(lib, "a(c)"))

        with self.assertRaises(AssertionError):
            self.assertASTEqual(parse_literal(lib, "a"), parse_term(lib, "a"))

    def test_assertEqual(self):
        """
        Test assertEqual.
        """
        self.assertEqual(parse_term(lib, "a"), parse_term(lib, "a"))
        self.assertEqual(parse_term(lib, "a(b(X))"), parse_term(lib, "a(b(X))"))
        with self.assertRaises(AssertionError):
            self.assertEqual(parse_term(lib, "a"), parse_term(lib, "b"))

        with self.assertRaises(AssertionError):
            self.assertEqual(parse_term(lib, "a(b)"), parse_term(lib, "a(c)"))

        with self.assertRaises(AssertionError):
            self.assertEqual(parse_literal(lib, "a"), parse_term(lib, "b"))

        with self.assertRaises(AssertionError):
            self.assertEqual(parse_literal(lib, "a"), parse_term(lib, "a"))
