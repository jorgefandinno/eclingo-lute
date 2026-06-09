"""
Simple tests for term evaluation.
"""

from unittest import TestCase

from clingo.control import Control
from clingo.core import Library
from clingo.symbol import Function, Number, String, Symbol, Tuple_

from eclingo.clingox.theory import (
    evaluate,
    invert_symbol,
    is_clingo_operator,
    is_operator,
    require_number,
)

lib = Library()


def eval_term_sym(s: str) -> Symbol:
    """
    Evaluate the given theory term and return its string representation.
    """
    ctl = Control(lib, [])
    ctl.parse_string(
        f"""
#theory test {{
    t {{
    +  : 3, unary;
    -  : 3, unary;
    ?  : 3, unary;
    ?  : 3, binary, left;
    ** : 2, binary, right;
    *  : 1, binary, left;
    /  : 1, binary, left;
    \\ : 1, binary, left;
    +  : 0, binary, left;
    -  : 0, binary, left
    }};
    &a/0 : t, head
}}.
&a {{{s}}}.
"""
    )
    ctl.ground()
    for x in ctl.base.theory:
        return evaluate(lib, x.elements[0].tuple[0])
    assert False


def eval_term(s: str) -> str:
    """
    Evaluate the given theory term and return its string representation.
    """
    return str(eval_term_sym(s))


class TestTheory(TestCase):
    """
    Tests for theory term evaluation.
    """

    def test_binary(self):
        """
        Test evaluation of binary terms.
        """
        self.assertEqual(eval_term("2+3"), "5")
        self.assertEqual(eval_term("2-3"), "-1")
        self.assertEqual(eval_term("2*3"), "6")
        self.assertEqual(eval_term("7/2"), "3")
        self.assertEqual(eval_term("7\\2"), "1")
        self.assertEqual(eval_term("2**3"), "8")

    def test_unary(self):
        """
        Test evaluation of unary terms.
        """
        self.assertEqual(eval_term("-1"), "-1")
        self.assertEqual(eval_term("+1"), "1")
        self.assertEqual(eval_term("-f"), "-f")
        self.assertEqual(eval_term("-f(x)"), "-f(x)")
        self.assertEqual(eval_term("-(-f(x))"), "f(x)")

    def test_nesting(self):
        """
        Test evaluation of nested terms
        """
        self.assertEqual(eval_term("f(2+3*4,-g(-1))"), "f(14,-g(-1))")
        self.assertEqual(eval_term("f(2+3*4,-g(-1),0)"), "f(14,-g(-1),0)")

    def test_string(self):
        """
        Test evaluation of strings.
        """
        self.assertEqual(eval_term_sym('"a\\\\b\\nc\\"d"'), String(lib, 'a\\b\nc"d'))

    def test_tuple(self):
        """
        Test evaluation of tuple terms.
        """
        self.assertEqual(eval_term("(1,2)"), "(1,2)")
        self.assertEqual(eval_term("(1,2,3)"), "(1,2,3)")
        self.assertEqual(eval_term("(1+1,2*3)"), "(2,6)")

    def test_list_error(self):
        """
        Test that list terms raise a RuntimeError.
        """
        self.assertRaises(RuntimeError, eval_term, "[1]")
        self.assertRaises(RuntimeError, eval_term, "[1,2]")

    def test_error(self):
        """
        Test failed term evaluation.
        """
        self.assertRaises(TypeError, eval_term, "-(1,2)")
        self.assertRaises(TypeError, eval_term, "+a")
        self.assertRaises(RuntimeError, eval_term, "{1}")
        self.assertRaises(AttributeError, eval_term, "?2")
        self.assertRaises(AttributeError, eval_term, "1?2")
        self.assertRaises(ZeroDivisionError, eval_term, "1\\0")
        self.assertRaises(ZeroDivisionError, eval_term, "1/0")


class TestRequireNumber(TestCase):
    def test_number(self):
        self.assertEqual(require_number(Number(lib, 5)), 5)
        self.assertEqual(require_number(Number(lib, -3)), -3)
        self.assertEqual(require_number(Number(lib, 0)), 0)

    def test_non_number(self):
        self.assertRaises(TypeError, require_number, Function(lib, "a"))
        self.assertRaises(TypeError, require_number, String(lib, "hello"))


class TestInvertSymbol(TestCase):
    def test_number(self):
        self.assertEqual(invert_symbol(lib, Number(lib, 5)), Number(lib, -5))
        self.assertEqual(invert_symbol(lib, Number(lib, -3)), Number(lib, 3))
        self.assertEqual(invert_symbol(lib, Number(lib, 0)), Number(lib, 0))

    def test_positive_function(self):
        self.assertEqual(
            invert_symbol(lib, Function(lib, "a", [], True)), Function(lib, "a", [], False)
        )
        self.assertEqual(
            invert_symbol(lib, Function(lib, "f", [Number(lib, 1)], True)),
            Function(lib, "f", [Number(lib, 1)], False),
        )

    def test_negative_function(self):
        self.assertEqual(
            invert_symbol(lib, Function(lib, "a", [], False)), Function(lib, "a", [], True)
        )

    def test_error(self):
        self.assertRaises(TypeError, invert_symbol, lib, String(lib, "hello"))
        self.assertRaises(TypeError, invert_symbol, lib, Tuple_(lib, [Number(lib, 1), Number(lib, 2)]))
        self.assertRaises(TypeError, invert_symbol, lib, Function(lib, "", [], True))


class TestIsOperator(TestCase):
    def test_symbol_operators(self):
        for op in (
            "+",
            "-",
            "*",
            "/",
            "\\",
            "**",
            "<",
            "<=",
            "==",
            "!=",
            "?",
            "&",
            "@",
            "|",
        ):
            self.assertTrue(is_operator(op), msg=f"expected {op!r} to be an operator")

    def test_not_keyword(self):
        self.assertTrue(is_operator("not"))

    def test_non_operators(self):
        self.assertFalse(is_operator("f"))
        self.assertFalse(is_operator("abc"))
        self.assertFalse(is_operator(""))


class TestIsClingo_operator(TestCase):
    def test_clingo_operators(self):
        for op in ("+", "-", "*", "/", "\\"):
            self.assertTrue(
                is_clingo_operator(op), msg=f"expected {op!r} to be a clingo operator"
            )

    def test_non_clingo_operators(self):
        self.assertFalse(is_clingo_operator("**"))
        self.assertFalse(is_clingo_operator("?"))
        self.assertFalse(is_clingo_operator("not"))
        self.assertFalse(is_clingo_operator("f"))
        self.assertFalse(is_clingo_operator(""))
