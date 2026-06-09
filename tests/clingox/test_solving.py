"""
Simple tests for solving.
"""

from unittest import TestCase

from clingo.control import Control
from clingo.core import Library

from eclingo.clingox.solving import approximate

lib = Library()


class TestSolving(TestCase):
    """
    Tests for solving module.
    """

    def approximate(self, prg: str, expected_res):
        """
        Auxiliary function to test approximate.
        """
        ctl = Control(lib, [])
        ctl.parse_string(prg)
        ctl.ground()
        res = approximate(ctl)
        if res:
            sorted_res = (
                sorted([str(s) for s in res[0]]),
                sorted([str(s) for s in res[1]]),
            )
        else:
            sorted_res = None

        self.assertEqual(sorted_res, expected_res)

    def test_approximate(self):
        """
        Tests for approximate.
        """
        self.approximate("a. {b}. c :- not d." "d :- not c. e :- not e.", None)
        self.approximate(
            "a. {b}. c :- not d." "d :- not c.", (["a"], ["a", "b", "c", "d"])
        )
        self.approximate("{a}. :- not a.", (["a"], ["a"]))
        self.approximate("{a}. :- a.", ([], []))
        self.approximate("a, b.", ([], ["a", "b"]))
        self.approximate("a, b. :- not a.", (["a"], ["a"]))
