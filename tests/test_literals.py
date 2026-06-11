import unittest

from clingo.ast import Sign
from clingo.core import Library
from clingo.symbol import Function

from eclingo.literals import Literal


class Test(unittest.TestCase):
    def setUp(self):
        self.lib = Library(message_limit=0)

    def assert_str(self, literal: Literal, s: str) -> None:
        self.assertEqual(str(literal), s)

    def test_str(self):
        symbol = Function(self.lib, "a")
        self.assert_str(Literal(symbol, Sign.NoSign), "a")
        self.assert_str(Literal(symbol, Sign.Single), "not a")
        self.assert_str(Literal(symbol, Sign.Double), "not not a")

    def assert_repr(self, literal: Literal, s: str) -> None:
        self.assertEqual(repr(literal), s)

    def test_repr(self):
        symbol = Function(self.lib, "a")
        s = repr(symbol)
        self.assert_repr(Literal(symbol, Sign.NoSign), repr(Sign.NoSign) + s)
        self.assert_repr(Literal(symbol, Sign.Single), repr(Sign.Single) + s)
        self.assert_repr(Literal(symbol, Sign.Double), repr(Sign.Double) + s)
