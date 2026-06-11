import unittest

from clingo import ast
from clingo.core import Library, Location, Position
from clingo.symbol import Function

from eclingo.clingox.ast import theory_parser_from_definition

theory = """#theory eclingo {
    term { not : 0, unary;
           -   : 0, unary
         };
    &k/0 : term, body
}.
"""


class TesterCase(unittest.TestCase):
    def setUp(self):
        self.lib = Library(message_limit=0)
        self.location = Location(
            Position(self.lib, "<string>", 1, 1), Position(self.lib, "<string>", 1, 1)
        )
        self.theory_parse = None

        def extract(stm):
            if isinstance(stm, ast.StatementTheory):
                self.theory_parse = theory_parser_from_definition(self.lib, stm)

        ast.parse_string(self.lib, theory, extract)

    def theory_atom(self, s: str, mode: int = 0):
        """
        Convert string to the first theory atom in it.
        """
        found = []

        def collect(x, *args):
            if isinstance(x, (ast.HeadTheoryAtom, ast.BodyTheoryAtom)):
                if mode == 2:
                    x = self.theory_parse(x)
                found.append(x)
                return None
            return x.transform(self.lib, collect)

        prg = f"{s}." if mode in (0, 2) else theory + f"{s}."
        stms = []
        ast.parse_string(self.lib, prg, stms.append)
        for stm in stms:
            collect(stm)
        return found[0]

    def element(self, *terms):
        """
        Create a theory atom element with the given terms and no condition.
        """
        return ast.TheoryAtomElement(self.lib, self.location, list(terms), [])

    def symbolic(self, name: str):
        """
        Create a symbolic theory term with the given constant name.
        """
        return ast.TheoryTermSymbolic(self.lib, self.location, Function(self.lib, name))

    def function(self, name: str, *arguments):
        """
        Create a theory function term.
        """
        return ast.TheoryTermFunction(self.lib, self.location, name, list(arguments))

    def variable(self, name: str):
        """
        Create a theory variable term.
        """
        return ast.TheoryTermVariable(self.lib, self.location, name)

    def unparsed(self, operators, term):
        """
        Create an unparsed theory term with a single element.
        """
        return ast.TheoryTermUnparsed(
            self.lib,
            self.location,
            [ast.UnparsedElement(self.lib, list(operators), term)],
        )

    def test_theory_parse(self):
        # note that clingo 6 wraps theory terms in unparsed terms even if
        # there are no operators
        result = self.theory_atom("&k{ a }").elements[0]
        self.assertEqual(result, self.element(self.unparsed([], self.symbolic("a"))))

        result = self.theory_atom("&k{ a(X) }").elements[0]
        self.assertEqual(
            result,
            self.element(
                self.unparsed(
                    [], self.function("a", self.unparsed([], self.variable("X")))
                )
            ),
        )

        result = self.theory_atom("&k{ not a(X) }").elements[0]
        self.assertEqual(
            result,
            self.element(
                self.unparsed(
                    ["not"],
                    self.function("a", self.unparsed([], self.variable("X"))),
                )
            ),
        )

    def test_theory_parse_with_theory(self):
        result = self.theory_atom("&k{ a }", mode=1).elements[0]
        self.assertEqual(result, self.element(self.unparsed([], self.symbolic("a"))))

        result = self.theory_atom("&k{ a(X) }", mode=1).elements[0]
        self.assertEqual(
            result,
            self.element(
                self.unparsed(
                    [], self.function("a", self.unparsed([], self.variable("X")))
                )
            ),
        )

        result = self.theory_atom("&k{ not a(X) }", mode=1).elements[0]
        self.assertEqual(
            result,
            self.element(
                self.unparsed(
                    ["not"],
                    self.function("a", self.unparsed([], self.variable("X"))),
                )
            ),
        )

    def test_theory_parse_with_clingox_theory(self):
        result = self.theory_atom("&k{ a }", mode=2).elements[0]
        self.assertEqual(result, self.element(self.symbolic("a")))

        result = self.theory_atom("&k{ a(X) }", mode=2).elements[0]
        self.assertEqual(result, self.element(self.function("a", self.variable("X"))))

        result = self.theory_atom("&k{ not a }", mode=2).elements[0]
        self.assertEqual(result, self.element(self.function("not", self.symbolic("a"))))

        result = self.theory_atom("&k{ not a(X) }", mode=2).elements[0]
        self.assertEqual(
            result,
            self.element(self.function("not", self.function("a", self.variable("X")))),
        )

        result = self.theory_atom("&k{ - a(X) }", mode=2).elements[0]
        self.assertEqual(
            result,
            self.element(self.function("-", self.function("a", self.variable("X")))),
        )

        result = self.theory_atom("&k{ not not a(X) }", mode=2).elements[0]
        self.assertEqual(
            result,
            self.element(
                self.function(
                    "not",
                    self.function("not", self.function("a", self.variable("X"))),
                )
            ),
        )

        result = self.theory_atom("&k{ not - a(X) }", mode=2).elements[0]
        self.assertEqual(
            result,
            self.element(
                self.function(
                    "not", self.function("-", self.function("a", self.variable("X")))
                )
            ),
        )

        result = self.theory_atom("&k{ - not a(X) }", mode=2).elements[0]
        self.assertEqual(
            result,
            self.element(
                self.function(
                    "-", self.function("not", self.function("a", self.variable("X")))
                )
            ),
        )

    def test_theory_parse_element(self):
        element = self.element(
            self.function("-", self.function("a", self.variable("X")))
        )
        expected = self.element(
            self.function("-", self.function("a", self.variable("X")))
        )
        self.assertEqual(element, expected)

    def test_theory_parse_term(self):
        term = self.unparsed(["-"], self.symbolic("a"))
        self.assertEqual(term, self.unparsed(["-"], self.symbolic("a")))
