# To be merged with test_reification.py later
# Let us keep it as a separated file until finishing with the current patch

from clingo import ast
from clingo.core import Library

from eclingo.parsing.transformers import ast_reify

from .ast_tester import ASTTestCase

_lib = Library(message_limit=0)


def last_stm(s: str):
    """
    Convert string to rule.
    """
    stm = None

    def set_stm(x):
        nonlocal stm
        stm = x

    ast.parse_string(_lib, s, set_stm)

    return stm


def parse_literal(s: str):
    stm = last_stm(f":-{s}.")
    lit = stm.body[0]
    if isinstance(lit, ast.BodySimpleLiteral):
        return lit.literal
    return lit


def parse_term(s: str):
    lit = parse_literal(f"p({s})")
    return lit.atom.pool[0].arguments[0]


if "unittest.util" in __import__("sys").modules:
    # Show full diff in self.assertEqual.
    __import__("sys").modules["unittest.util"]._MAX_LENGTH = 999999999


class Test(ASTTestCase):
    def assert_symbolic_literal_to_term(self, lit: str, term: str):
        parsed_lit = parse_literal(lit)
        parsed_term = parse_term(term)
        result = ast_reify.symbolic_literal_to_term(_lib, parsed_lit)
        self.maxDiff = None
        self.assertEqual(result, parsed_term)

    def test_symbolic_literal_to_term(self):
        self.assert_symbolic_literal_to_term("a(b)", "a(b)")
        self.assert_symbolic_literal_to_term("a", "a")
        self.assert_symbolic_literal_to_term("not a", "not1(a)")
        self.assert_symbolic_literal_to_term("not not a", "not2(a)")

        self.assert_symbolic_literal_to_term("a(b,c)", "a(b,c)")
        self.assert_symbolic_literal_to_term("not a(b,c)", "not1(a(b,c))")
        self.assert_symbolic_literal_to_term("not not a(b,c)", "not2(a(b,c))")

        self.assert_symbolic_literal_to_term("-a", "-a")
        self.assert_symbolic_literal_to_term("-a(b,c)", "-a(b,c)")
        self.assert_symbolic_literal_to_term("not -a(b,c)", "not1(-a(b,c))")
        self.assert_symbolic_literal_to_term("not not -a(b,c)", "not2(-a(b,c))")

    def test_non_ground_symbolic_literal_to_term(self):
        self.assert_symbolic_literal_to_term("a(X)", "a(X)")
        self.assert_symbolic_literal_to_term("not a(X)", "not1(a(X))")
        self.assert_symbolic_literal_to_term("not not a(X)", "not2(a(X))")

        self.assert_symbolic_literal_to_term("a(b(X),c,Y)", "a(b(X),c,Y)")
        self.assert_symbolic_literal_to_term("not a(b(X),c,Y)", "not1(a(b(X),c,Y))")
        self.assert_symbolic_literal_to_term("not not a(b(X),c,Y)", "not2(a(b(X),c,Y))")

        self.assert_symbolic_literal_to_term("-a(X)", "-a(X)")
        self.assert_symbolic_literal_to_term("-a(b(X),c,Y)", "-a(b(X),c,Y)")
        self.assert_symbolic_literal_to_term("not -a(b(X),c,Y)", "not1(-a(b(X),c,Y))")
        self.assert_symbolic_literal_to_term(
            "not not -a(b(X),c,Y)", "not2(-a(b(X),c,Y))"
        )

    def test_multiple_variables_symbolic_literal_to_term(self):
        self.assert_symbolic_literal_to_term("a(b(X,Z),c,Y)", "a(b(X,Z),c,Y)")
        self.assert_symbolic_literal_to_term("a(b(x,z),c)", "a(b(x,z),c)")

    def test_theory_atom_symbolic_literal_to_term(self):
        self.assertEqual(
            ast_reify.symbolic_literal_to_term(_lib, parse_literal("&k{ p(X) }")),
            parse_literal("&k{ p(X) }"),
        )
        self.assertEqual(
            ast_reify.symbolic_literal_to_term(_lib, parse_literal("&k{ p(X) }")),
            parse_literal("&k{ p(X) }"),
        )
        self.assertEqual(
            ast_reify.symbolic_literal_to_term(_lib, parse_literal("&k{ p(X) }")),
            parse_literal("&k{ p(X) }"),
        )
