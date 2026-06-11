from eclingo.parsing.parser import _ProgramParser, parse_theory
from eclingo.parsing.transformers import ast_reify
from tests.test_reification2 import _lib, parse_literal, parse_term

from .ast_tester import ASTTestCase


class Test(ASTTestCase):
    def test_theory_atom(self):
        self.assertEqual(
            ast_reify.theory_atom_to_term(_lib, parse_literal("&k{ p(X) }")),
            parse_term("k(p(X))"),
        )

        self.assertEqual(
            ast_reify.theory_atom_to_term(_lib, parse_literal("&k{ a(Y) }")),
            parse_term("k(a(Y))"),
        )

        self.assertEqual(
            ast_reify.theory_atom_to_term(_lib, parse_literal("&k{ b(c) }")),
            parse_term("k(b(c))"),
        )

    def test_parsed_theory_atom(self):
        theory_parser = parse_theory(_lib, _ProgramParser.eclingo_theory)
        atom = theory_parser(parse_literal("&k{ a(X) }"))
        self.assertEqual(
            ast_reify.theory_atom_to_term(_lib, atom), parse_term("k(a(X))")
        )
