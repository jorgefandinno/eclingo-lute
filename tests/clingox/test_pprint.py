"""
Tests for pretty printing.
"""

from io import StringIO
from sys import version_info
from unittest import TestCase

from clingo.core import Library
from clingo.symbol import parse_term as parse_symbol

from eclingo.clingox import pprint as pp
from eclingo.clingox.testing.ast import parse_term

lib = Library()

# clingo 6 Symbol repr format: name without quotes for Function names,
# "b" for String, Tuple([...]) for tuples
SYM_REP1 = """\
Function('f',
         [Supremum,
          Infimum,
          Function(a, [], True),
          "b",
          Tuple([Number(1), Number(2)])],
         True)\
"""

SYM_REP2 = """\
Function('f',
         [Function('f',
                   [Function('f',
                             [Function('f',
                                       [Function('f',
                                                 [Function('f',
                                                           [Function('f',
                                                                     [Number(1000000000)],
                                                                     True)],
                                                           True)],
                                                 True)],
                                       True)],
                             True)],
                   True)],
         True)\
"""


class TestPPrint(TestCase):
    """
    Test cases for pretty printing.
    """

    def test_pprint_ast(self):
        """
        Test pprint functions for ASTs.
        """
        term = parse_term(lib, "f(X)")
        # pprint should not crash
        result = pp.pformat(term)
        self.assertIsInstance(result, str)
        # pprint with hide_location should also not crash
        result_hidden = pp.pformat(term, hide_location=True)
        self.assertIsInstance(result_hidden, str)

    def test_pprint_sym(self):
        """
        Test pprint functions for symbols.
        """
        self.assertEqual(
            pp.pformat(parse_symbol(lib, 'f(#sup,#inf,a,"b",(1,2))')), SYM_REP1
        )
        self.assertEqual(
            pp.pformat(parse_symbol(lib, "f(f(f(f(f(f(f(1000000000)))))))")), SYM_REP2
        )

    def test_pprint_module(self):
        """
        Test pprint module functions.
        """
        term = parse_term(lib, "f(X)")
        # pp.pprint should not crash
        out = StringIO()
        pp.pprint(term, stream=out)
        self.assertIsInstance(out.getvalue(), str)
        # saferepr, isreadable, isrecursive should work on symbols
        sym = parse_symbol(lib, "f(1)")
        self.assertIsInstance(pp.saferepr(sym), str)
        self.assertIsInstance(pp.isreadable(sym), bool)
        self.assertFalse(pp.isrecursive(sym))
        if version_info[:2] >= (3, 8):
            out = StringIO()  # nocoverage
            pp.pp(term, stream=out)  # nocoverage
            self.assertIsInstance(out.getvalue(), str)  # nocoverage
