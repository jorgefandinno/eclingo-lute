import unittest

from clingo import ast
from clingo.ast import Sign
from clingo.core import Library, Location, Position
from clingo.symbol import Number

from eclingo.parsing.transformers.astutil import atom, negate_literal


class TestAtom(unittest.TestCase):
    def setUp(self):
        self.lib = Library(message_limit=0)
        self.loc = Location(
            Position(self.lib, "<string>", 1, 1), Position(self.lib, "<string>", 1, 2)
        )

    def test_positive_atom(self):
        result = atom(self.lib, self.loc, True, "p", [])
        self.assertIsInstance(result, ast.TermSymbolic)
        self.assertEqual(str(result), "p")

    def test_negative_atom(self):
        result = atom(self.lib, self.loc, False, "p", [])
        self.assertIsInstance(result, ast.TermUnaryOperation)
        self.assertEqual(str(result), "-p")

    def test_positive_atom_with_arguments(self):
        arg = ast.TermSymbolic(self.lib, self.loc, Number(self.lib, 1))
        result = atom(self.lib, self.loc, True, "f", [arg])
        self.assertEqual(str(result), "f(1)")

    def test_negative_atom_with_arguments(self):
        arg = ast.TermSymbolic(self.lib, self.loc, Number(self.lib, 1))
        result = atom(self.lib, self.loc, False, "f", [arg])
        self.assertEqual(str(result), "-f(1)")


class TestNegateLiteral(unittest.TestCase):
    def setUp(self):
        self.lib = Library(message_limit=0)

    def parse_literal(self, s):
        return ast.parse_literal(self.lib, s)

    def test_no_sign_becomes_negation(self):
        lit = self.parse_literal("a")
        self.assertEqual(lit.sign, Sign.NoSign)
        result = negate_literal(self.lib, lit)
        self.assertEqual(result.sign, Sign.Single)
        self.assertEqual(str(result), "not a")

    def test_negation_becomes_double_negation(self):
        lit = self.parse_literal("not a")
        self.assertEqual(lit.sign, Sign.Single)
        result = negate_literal(self.lib, lit)
        self.assertEqual(result.sign, Sign.Double)
        self.assertEqual(str(result), "not not a")

    def test_double_negation_becomes_negation(self):
        lit = self.parse_literal("not not a")
        self.assertEqual(lit.sign, Sign.Double)
        result = negate_literal(self.lib, lit)
        self.assertEqual(result.sign, Sign.Single)
        self.assertEqual(str(result), "not a")

    def test_atom_is_preserved(self):
        lit = self.parse_literal("f(1,2)")
        result = negate_literal(self.lib, lit)
        self.assertEqual(result.sign, Sign.Single)
        self.assertEqual(str(result.atom), "f(1,2)")
