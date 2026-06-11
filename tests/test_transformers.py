import unittest

from clingo import ast
from clingo.core import Library

from eclingo.parsing.transformers.theory_parser_epistemic import (
    parse_epistemic_literals_elements as _parse_epistemic_literals_elements,
)


class Test(unittest.TestCase):
    def setUp(self):
        self.lib = Library(message_limit=0)

    def theory_atom_statment_from_str(self, s):
        statements = []
        ast.parse_string(self.lib, ":- " + s, statements.append)
        return statements[-1].body[0]

    def test_epistemic_atom(self):
        statement = self.theory_atom_statment_from_str("&k{a}.")
        self.assertIsInstance(statement, ast.BodyTheoryAtom)
        self.assertEqual(len(statement.elements), 1)
        element = statement.elements[0]
        self.assertIsInstance(element, ast.TheoryAtomElement)
        terms = element.tuple
        self.assertEqual(len(terms), 1)
        self.assertIsInstance(terms[0], ast.TheoryTermUnparsed)

        result = _parse_epistemic_literals_elements(self.lib, statement)
        self.assertEqual(len(result.elements), 1)
        element = result.elements[0]
        self.assertIsInstance(element, ast.TheoryAtomElement)

        terms = element.tuple
        self.assertEqual(len(terms), 1)
        # with clingo 6, the literal is encoded as a theory term
        self.assertIsInstance(terms[0], ast.TheoryTermSymbolic)
