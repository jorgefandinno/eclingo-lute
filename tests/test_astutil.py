import unittest

from clingo import ast
from clingo.core import Location, Position, Sign

from eclingo.parsing.transformers.astutil import atom, negate_literal


def make_location():
    return Location(Position("<string>", 1, 1), Position("<string>", 1, 2))


def parse_literal(s):
    stms = []
    ast.parse_string(":- " + s + ".", stms.append)
    return stms[1].body[0]


class TestAtom(unittest.TestCase):
    def setUp(self):
        self.loc = make_location()

    def test_positive_atom(self):
        result = atom(self.loc, True, "p", [])
        self.assertEqual(result.ast_type, ast.ASTType.SymbolicAtom)
        self.assertEqual(str(result), "p")

    def test_negative_atom(self):
        result = atom(self.loc, False, "p", [])
        self.assertEqual(result.ast_type, ast.ASTType.SymbolicAtom)
        self.assertEqual(str(result), "-p")

    def test_positive_atom_with_arguments(self):
        arg = ast.SymbolicTerm(self.loc, __import__("clingo").Number(1))
        result = atom(self.loc, True, "f", [arg])
        self.assertEqual(str(result), "f(1)")

    def test_negative_atom_with_arguments(self):
        arg = ast.SymbolicTerm(self.loc, __import__("clingo").Number(1))
        result = atom(self.loc, False, "f", [arg])
        self.assertEqual(str(result), "-f(1)")


class TestNegateLiteral(unittest.TestCase):
    def test_no_sign_becomes_negation(self):
        lit = parse_literal("a")
        self.assertEqual(lit.sign, Sign.NoSign)
        result = negate_literal(lit)
        self.assertEqual(result.sign, Sign.Negation)
        self.assertEqual(str(result), "not a")

    def test_negation_becomes_double_negation(self):
        lit = parse_literal("not a")
        self.assertEqual(lit.sign, Sign.Negation)
        result = negate_literal(lit)
        self.assertEqual(result.sign, Sign.DoubleNegation)
        self.assertEqual(str(result), "not not a")

    def test_double_negation_becomes_negation(self):
        lit = parse_literal("not not a")
        self.assertEqual(lit.sign, Sign.DoubleNegation)
        result = negate_literal(lit)
        self.assertEqual(result.sign, Sign.Negation)
        self.assertEqual(str(result), "not a")

    def test_atom_is_preserved(self):
        lit = parse_literal("f(1,2)")
        result = negate_literal(lit)
        self.assertEqual(result.sign, Sign.Negation)
        self.assertEqual(str(result.atom), "f(1,2)")
