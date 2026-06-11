from eclingo.parsing.transformers import ast_reify
from tests.test_reification2 import _lib, parse_literal, parse_term

from .ast_tester import ASTTestCase


class Test(ASTTestCase):
    def test_theory_atom_negation(self):
        self.assertEqual(
            ast_reify.theory_atom_to_term(_lib, parse_literal("&k{ a(X) }")),
            parse_term("k(a(X))"),
        )

        self.assertEqual(
            ast_reify.theory_atom_to_term(_lib, parse_literal("&k{ not a(X) }")),
            parse_term("k(not1(a(X)))"),
        )

        self.assertEqual(
            ast_reify.theory_atom_to_term(_lib, parse_literal("&k{ not not a(X) }")),
            parse_term("k(not2(a(X)))"),
        )

        self.assertEqual(
            ast_reify.theory_atom_to_term(
                _lib, parse_literal("&k{ not not not a(X) }")
            ),
            parse_term("k(not1(a(X)))"),
        )
