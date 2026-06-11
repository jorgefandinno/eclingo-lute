"""
Simple tests for ast manipulation.
"""

from typing import Callable, Container, List, Optional, Sequence
from unittest import TestCase

from clingo import ast
from clingo.ast import Sign
from clingo.core import Library, Location, Position
from clingo.symbol import Function, Number

from eclingo.clingox.ast import (
    ASTPredicate,
    rewrite_symbolic_atoms,
    TheoryAtomType,
    TheoryParser,
    clingo_literal_parser,
    clingo_term_parser,
    filter_body_literals,
    location_to_str,
    normalize_symbolic_terms,
    parse_theory,
    partition_body_literals,
    prefix_symbolic_atoms,
    reify_symbolic_atoms,
    str_to_location,
    theory_term_to_literal,
    theory_term_to_term,
)
from eclingo.clingox.testing.ast import parse_term

TEST_THEORY = """\
#theory test {
    t {
        -  : 3, unary;
        ** : 2, binary, right;
        *  : 1, binary, left;
        /  : 1, binary, left;
        +  : 0, binary, left;
        -  : 0, binary, left
    };
    &p/0 : t, head;
    &q/1 : t, body;
    &r/0 : t, { < }, t, directive
}\
"""


class TestAST(TestCase):
    """
    Tests for AST manipulation.
    """

    lib: Library

    def setUp(self):
        self.lib = Library(message_limit=0)
        self.loc = Location(
            Position(self.lib, "a", 1, 2), Position(self.lib, "a", 1, 2)
        )
        self.term_table = {"t": clingo_term_parser(self.lib)}
        self.atom_table = {
            ("p", 0): (TheoryAtomType.Head, "t", None),
            ("q", 1): (TheoryAtomType.Body, "t", None),
            ("r", 0): (TheoryAtomType.Directive, "t", (["<"], "t")),
        }

    def theory_atom(self, s: str):
        """
        Convert string to a theory atom.
        """
        found: list = []

        def collect(x, *args):
            if isinstance(x, (ast.HeadTheoryAtom, ast.BodyTheoryAtom)):
                found.append(x)
                return None
            return x.transform(self.lib, collect)

        stms: list = []
        ast.parse_string(self.lib, f"{s}.", stms.append)
        for stm in stms:
            collect(stm)
        return found[0]

    def last_stm(self, s: str):
        """
        Convert string to the last statement in it.
        """
        stms: list = []
        ast.parse_string(self.lib, s, stms.append)
        return stms[-1]

    def parse_theory_term(self, s: str):
        """
        Parse the given theory term using a simple parse table for testing.
        """
        return clingo_term_parser(self.lib)(
            self.theory_atom(f"&p {{{s}}}").elements[0].tuple[0]
        )

    def parse_theory_term_as_literal(self, s: str):
        """
        Parse the given theory term using a simple parse table for testing.
        """
        return clingo_literal_parser(self.lib)(
            self.theory_atom(f"&p {{{s}}}").elements[0].tuple[0]
        )

    def parse_clingo_term(self, s: str):
        """
        Parse the given term as a plain clingo term.
        """
        atom = self.last_stm(f"p({s}).").head.literal.atom
        return atom.pool[0].arguments[0]

    def parse_clingo_literal(self, s: str):
        """
        Parse the given literal as a plain clingo literal.
        """
        return self.last_stm(f"{s}.").head.literal

    def parse_atom(self, s: str, parser: Optional[TheoryParser] = None) -> str:
        """
        Parse the given theory atom using a simple parse table for testing.
        """
        if parser is None:
            parser = TheoryParser(self.lib, self.term_table, self.atom_table)
        return str(parser(self.theory_atom(s)))

    def parse_stm(self, s: str, parser: Optional[TheoryParser] = None) -> str:
        """
        Parse the given statement using a simple parse table for testing.
        """
        if parser is None:
            parser = TheoryParser(self.lib, self.term_table, self.atom_table)
        return str(parser(self.last_stm(s)))

    def parse_with(self, s: str, f: Callable = lambda x: x) -> Sequence[str]:
        """
        Parse the given program and apply the given function to it.
        """
        prg: List[str] = []

        def append(stm):
            ret = f(stm)
            if ret is not None:
                prg.append(str(ret))

        ast.parse_string(self.lib, s, append)
        return prg

    def rename(self, s: str) -> Sequence[str]:
        """
        Parse the given program and rename symbolic atoms in it.
        """
        return self.parse_with(
            s, lambda stm: prefix_symbolic_atoms(self.lib, stm, "u_")
        )

    def reify(
        self,
        s: str,
        f: Optional[Callable] = None,
        st: bool = False,
    ) -> Sequence[str]:
        """
        Parse the given program and reify symbolic atoms in it.
        """
        return self.parse_with(
            s, lambda x: reify_symbolic_atoms(self.lib, x, "u", f, st)
        )

    def test_loc(self):
        """
        Test string representation of location.
        """
        lib = self.lib
        loc = self.loc
        self.assertEqual(location_to_str(loc), "a:1:2")
        self.assertEqual(str_to_location(lib, location_to_str(loc)), loc)
        loc = Location(loc.begin, Position(lib, loc.end.file, loc.end.line, 4))
        self.assertEqual(location_to_str(loc), "a:1:2-4")
        self.assertEqual(str_to_location(lib, location_to_str(loc)), loc)
        loc = Location(loc.begin, Position(lib, loc.end.file, 3, loc.end.column))
        self.assertEqual(location_to_str(loc), "a:1:2-3:4")
        self.assertEqual(str_to_location(lib, location_to_str(loc)), loc)
        loc = Location(loc.begin, Position(lib, "b", loc.end.line, loc.end.column))
        self.assertEqual(location_to_str(loc), "a:1:2-b:3:4")
        self.assertEqual(str_to_location(lib, location_to_str(loc)), loc)
        loc = Location(
            Position(lib, r"a:1:2-3\:", loc.begin.line, loc.begin.column),
            Position(lib, "b:1:2-3", loc.end.line, loc.end.column),
        )
        self.assertEqual(location_to_str(loc), r"a\:1\:2-3\\\::1:2-b\:1\:2-3:3:4")
        self.assertEqual(str_to_location(lib, location_to_str(loc)), loc)
        self.assertRaises(RuntimeError, str_to_location, lib, "a:1:2-")

    def test_parse_term(self):
        """
        Test parsing of theory terms.
        """
        self.assertEqual(str(self.parse_theory_term("1+2")), "(1 + 2)")
        self.assertEqual(str(self.parse_theory_term("1+2+3")), "((1 + 2) + 3)")
        self.assertEqual(str(self.parse_theory_term("1+2*3")), "(1 + (2 * 3))")
        self.assertEqual(str(self.parse_theory_term("1**2**3")), "(1 ** (2 ** 3))")
        self.assertEqual(str(self.parse_theory_term("-1+2")), "((- 1) + 2)")
        self.assertEqual(str(self.parse_theory_term("f(1+2)+3")), "(f((1 + 2)) + 3)")
        self.assertRaises(RuntimeError, self.parse_theory_term, "1++2")

    def test_parse_atom(self):
        """
        Test parsing of theory atoms.
        """
        self.assertEqual(self.parse_atom("&p {1+2}"), "&p { (1 + 2) }")
        self.assertEqual(self.parse_atom("&p {1+2+3}"), "&p { ((1 + 2) + 3) }")
        self.assertEqual(self.parse_atom("&q(1+2+3) { }"), "&q(1+2+3)")
        self.assertEqual(self.parse_atom("&r { } < 1+2+3"), "&r { } < ((1 + 2) + 3)")

    def test_parse_atom_occ(self):
        """
        Test parsing of different theory atom types.
        """
        self.assertEqual(self.parse_stm("&p {1+2}."), "&p { (1 + 2) }.")
        self.assertRaises(RuntimeError, self.parse_stm, ":- &p {1+2}.")
        self.assertRaises(RuntimeError, self.parse_stm, "&q(1+2+3) { }.")
        self.assertEqual(self.parse_stm(":- &q(1+2+3) { }."), " :- &q(1+2+3).")
        self.assertEqual(self.parse_stm("&r { } < 1+2+3."), "&r { } < ((1 + 2) + 3).")
        self.assertRaises(RuntimeError, self.parse_stm, "&r { } < 1+2+3 :- x.")
        self.assertRaises(RuntimeError, self.parse_stm, ":- &r { } < 1+2+3.")

    def test_parse_theory(self):
        """
        Test creating parsers from theory definitions.
        """
        with self.assertRaisesRegex(ValueError, "no theory definition found"):
            parse_theory(self.lib, "#program base")
        with self.assertRaisesRegex(ValueError, "multiple theory definitions"):
            parse_theory(self.lib, TEST_THEORY + "." + TEST_THEORY)
        parser = parse_theory(self.lib, TEST_THEORY)

        self.assertEqual(self.parse_atom("&p {1+2}", parser), "&p { (1 + 2) }")
        self.assertEqual(self.parse_atom("&p {1+2+3}", parser), "&p { ((1 + 2) + 3) }")
        self.assertEqual(self.parse_atom("&q(1+2+3) { }", parser), "&q(1+2+3)")
        self.assertEqual(
            self.parse_atom("&r { } < 1+2+3", parser), "&r { } < ((1 + 2) + 3)"
        )

        self.assertEqual(self.parse_stm("&p {1+2}.", parser), "&p { (1 + 2) }.")
        self.assertEqual(
            self.parse_stm("#show x : &q(0) {1+2}.", parser),
            "#show x: &q(0) { (1 + 2) }.",
        )
        self.assertEqual(
            self.parse_stm(":~ &q(0) {1+2}. [0]", parser),
            " :~ &q(0) { (1 + 2) }. [0]",
        )
        self.assertEqual(
            self.parse_stm("#edge (u, v) : &q(0) {1+2}.", parser),
            "#edge (u,v): &q(0) { (1 + 2) }.",
        )
        self.assertEqual(
            self.parse_stm("#heuristic a : &q(0) {1+2}. [sign,true]", parser),
            "#heuristic a: &q(0) { (1 + 2) }. [sign,true]",
        )
        self.assertRaises(RuntimeError, self.parse_stm, ":- &p {1+2}.", parser)
        self.assertRaises(RuntimeError, self.parse_stm, "&q(1+2+3) { }.", parser)
        self.assertEqual(self.parse_stm(":- &q(1+2+3) { }.", parser), " :- &q(1+2+3).")
        self.assertEqual(
            self.parse_stm("&r { } < 1+2+3.", parser), "&r { } < ((1 + 2) + 3)."
        )
        self.assertRaises(RuntimeError, self.parse_stm, "&r { } < 1+2+3 :- x.", parser)
        self.assertRaises(RuntimeError, self.parse_stm, ":- &r { } < 1+2+3.", parser)
        self.assertRaises(RuntimeError, self.parse_stm, "&s(1+2+3) { }.", parser)
        self.assertRaises(RuntimeError, self.parse_stm, "&p { } <= 3.", parser)
        self.assertRaises(RuntimeError, self.parse_stm, "&r { } <= 3.", parser)

    def test_rename(self):
        """
        Test renaming symbolic atoms.
        """
        lib = self.lib
        self.assertEqual(
            self.rename("a :- b(X,Y), not c(f(3,b))."),
            ["#program base.", "u_a :- u_b(X,Y); not u_c(f(3,b))."],
        )
        sym = parse_term(lib, "-a")
        self.assertEqual(str(prefix_symbolic_atoms(lib, sym, "u_")), "-u_a")
        self.assertEqual(
            self.rename("-a :- -b(X,Y), not -c(f(3,b))."),
            ["#program base.", "-u_a :- -u_b(X,Y); not -u_c(f(3,b))."],
        )
        sym = ast.TermSymbolic(lib, self.loc, Function(lib, "a", [Function(lib, "b")]))
        self.assertEqual(str(prefix_symbolic_atoms(lib, sym, "u_")), "u_a(b)")
        sym = ast.TermVariable(lib, self.loc, "B")
        self.assertEqual(prefix_symbolic_atoms(lib, sym, "u"), sym)

    def test_reify(self):
        """
        Test reifying symbolic atoms.
        """
        lib = self.lib
        self.assertEqual(self.reify("a."), ["#program base.", "u(a)."])
        self.assertEqual(
            self.reify("a :- b(X,Y), not c(f(3,b))."),
            ["#program base.", "u(a) :- u(b(X,Y)); not u(c(f(3,b)))."],
        )
        sym = parse_term(lib, "-a")
        self.assertEqual(str(reify_symbolic_atoms(lib, sym, "u")), "-u(a)")
        self.assertEqual(
            str(reify_symbolic_atoms(lib, sym, "u", reify_strong_negation=True)),
            "u(-a)",
        )
        self.assertEqual(
            self.reify("-a :- -b(X,Y), not -c(f(3,b))."),
            ["#program base.", "-u(a) :- -u(b(X,Y)); not -u(c(f(3,b)))."],
        )
        self.assertEqual(
            self.reify(
                "-a :- b(X,Y), not -c(f(3,b)). a :- -b(X,Y), not c(f(3,b)).", st=True
            ),
            [
                "#program base.",
                "u(-a) :- u(b(X,Y)); not u(-c(f(3,b))).",
                "u(a) :- u(-b(X,Y)); not u(c(f(3,b))).",
            ],
        )
        self.assertEqual(
            self.reify(
                "a :- b(X,Y), not c(f(3,b)).",
                f=lambda x: [
                    x,
                    ast.TermVariable(lib, self.loc, "T"),
                    ast.TermVariable(lib, self.loc, "I"),
                ],
            ),
            ["#program base.", "u(a,T,I) :- u(b(X,Y),T,I); not u(c(f(3,b)),T,I)."],
        )
        self.assertEqual(
            self.reify("-a :- -b(X,Y), &theory(X){ p(X): q(X), -r(X) }."),
            [
                "#program base.",
                "-u(a) :- -u(b(X,Y)); &theory(X) { p(X): u(q(X)), -u(r(X)) }.",
            ],
        )
        self.assertEqual(
            self.reify("-a :- -b(X,Y), &theory(X){ p(X): q(X), not r(X) }."),
            [
                "#program base.",
                "-u(a) :- -u(b(X,Y)); &theory(X) { p(X): u(q(X)), not u(r(X)) }.",
            ],
        )

        def fun(x):
            return [
                ast.TermVariable(lib, self.loc, "T"),
                x,
                ast.TermVariable(lib, self.loc, "I"),
            ]

        self.assertEqual(
            self.reify("a :- -b(X,Y), not c(f(3,b)).", f=fun, st=True),
            ["#program base.", "u(T,a,I) :- u(T,-b(X,Y),I); not u(T,c(f(3,b)),I)."],
        )

        sym = ast.TermSymbolic(lib, self.loc, Function(lib, "a", [Function(lib, "b")]))
        self.assertEqual(str(reify_symbolic_atoms(lib, sym, "u")), "u(a(b))")

    def test_rename_statements(self):
        """
        Test renaming symbolic atoms in disjunctions and statements with atoms.
        """
        self.assertEqual(
            self.rename("a, b :- c."),
            ["#program base.", "u_a: ; u_b:  :- u_c."],
        )
        # rewriting that does not change the atoms keeps the statement
        stm = self.last_stm("a, b.")
        self.assertEqual(
            str(rewrite_symbolic_atoms(self.lib, stm, lambda term: term)), "a; b."
        )
        self.assertEqual(
            self.rename("#project a."), ["#program base.", "#project u_a."]
        )
        self.assertEqual(
            self.rename("#external a."), ["#program base.", "#external u_a."]
        )

    def helper_body_elements(
        self,
        stm: str,
        body: Sequence[str],
        signs: Container[Sign] = (Sign.NoSign,),
        symbolic_atom_predicate: ASTPredicate = True,
        theory_atom_predicate: ASTPredicate = True,
        aggregate_predicate: ASTPredicate = True,
        conditional_literal_predicate: ASTPredicate = True,
    ):
        """
        Helper for testing filter_body_literals.
        """
        parsed_body = self.last_stm(stm).body
        res = filter_body_literals(
            parsed_body,
            symbolic_atom_predicate,
            theory_atom_predicate,
            aggregate_predicate,
            conditional_literal_predicate,
            signs,
        )
        self.assertListEqual(sorted(body), sorted(str(s) for s in res))
        res_true, res_false = partition_body_literals(
            parsed_body,
            symbolic_atom_predicate,
            theory_atom_predicate,
            aggregate_predicate,
            conditional_literal_predicate,
            signs,
        )
        self.assertListEqual(sorted(body), sorted(str(s) for s in res_true))
        full_body = filter_body_literals(
            parsed_body,
            True,
            True,
            True,
            True,
            (Sign.NoSign, Sign.Single, Sign.Double),
        )
        body_false = [str(e) for e in full_body if str(e) not in body]
        self.assertListEqual(sorted(body_false), sorted(str(s) for s in res_false))

    def test_get_positive_body(self):
        """
        Test for filter_body_literals.
        """
        self.helper_body_elements(
            "a(X) :- b(X), c(Y), not d(X), not not e(X,Y).", ["b(X)", "c(Y)"]
        )
        self.helper_body_elements(
            "a(X) :- b(X), c(Y), Z = #sum { X: d(X) }.",
            ["b(X)", "c(Y)", "Z = #sum { X: d(X) }"],
        )
        self.helper_body_elements(
            "a(X) :- b(X), c(Y), &sum { X: d(X) } = Z.",
            ["b(X)", "c(Y)", "&sum { X: d(X) } = Z"],
        )
        self.helper_body_elements(
            "a(X) :- b(X), c(Y), Z = { d(X) }.", ["b(X)", "c(Y)", "Z = { d(X) }"]
        )
        self.helper_body_elements(
            "a(X) :- b(X), c(Y), d(Z): e(X,Z).", ["b(X)", "c(Y)", "d(Z): e(X,Z)"]
        )

        self.helper_body_elements(
            "a(X) :- b(X), c(Y), &sum { X: d(X) } = Z.",
            ["b(X)", "c(Y)"],
            theory_atom_predicate=False,
        )
        self.helper_body_elements(
            "a(X) :- b(X), c(Y), Z = #sum { X: d(X) }.",
            ["b(X)", "c(Y)"],
            aggregate_predicate=False,
        )
        self.helper_body_elements(
            "a(X) :- b(X), c(Y), Z = { d(X) }.",
            ["b(X)", "c(Y)"],
            aggregate_predicate=False,
        )
        self.helper_body_elements(
            "a(X) :- b(X), c(Y), d(Z): e(X,Z).",
            ["b(X)", "c(Y)"],
            conditional_literal_predicate=False,
        )

        self.helper_body_elements(
            "a(X) :- b(X), c(Y), not d(X), not not e(X,Y).",
            ["b(X)", "c(Y)", "not d(X)"],
            signs=(Sign.NoSign, Sign.Single),
        )
        self.helper_body_elements(
            "a(X) :- b(X), c(Y), not d(X), not not e(X,Y).",
            ["b(X)", "c(Y)", "not not e(X,Y)"],
            signs=(Sign.NoSign, Sign.Double),
        )
        self.helper_body_elements(
            "a(X) :- b(X), c(Y), not d(X), not not e(X,Y).",
            ["not d(X)", "not not e(X,Y)"],
            signs=(Sign.Single, Sign.Double),
        )
        self.helper_body_elements(
            "a(X) :- b(X), c(Y), Z = #sum { X: d(X) }.",
            [],
            signs=(Sign.Single, Sign.Double),
        )
        self.helper_body_elements(
            "a(X) :- b(X), c(Y), &sum { X: d(X) } = Z.",
            [],
            signs=(Sign.Single, Sign.Double),
        )

        self.helper_body_elements(
            "a(X) :- b(X), c(Y), Z = #sum { X: d(X) }, Z = #count { X: d(X) }.",
            ["Z = #count { X: d(X) }", "Z = #sum { X: d(X) }"],
            symbolic_atom_predicate=False,
        )

        self.helper_body_elements(
            "a(X) :- b(X), c(Y), Z = #sum { X: d(X) }, Z = #count { X: d(X) }.",
            ["Z = #count { X: d(X) }", "Z = #sum { X: d(X) }", "b(X)"],
            symbolic_atom_predicate=lambda x: isinstance(x, ast.TermFunction)
            and x.name == "b",
        )

        self.helper_body_elements(
            "a(X) :- b(X), c(Y), Z = #sum { X: d(X) }, Z = #count { X: d(X) }.",
            ["Z = #count { X: d(X) }", "b(X)", "c(Y)"],
            aggregate_predicate=lambda x: isinstance(x, ast.BodyAggregate)
            and x.function == ast.AggregateFunction.Count,
        )

        self.helper_body_elements(
            "a(X) :- &k{ b(X) }, &k{ not c(X)}.",
            ["&k { b(X) }"],
            theory_atom_predicate=lambda x: not (
                x.elements
                and x.elements[0].tuple
                and isinstance(x.elements[0].tuple[0], ast.TheoryTermUnparsed)
                and x.elements[0].tuple[0].elements
                and x.elements[0].tuple[0].elements[0].operators
                and x.elements[0].tuple[0].elements[0].operators[0] == "not"
            ),
        )
        self.helper_body_elements(
            "a(X) :- b(X), not c(Y), d(Z): e(X,Z); not d(Z): e(X,Z).",
            ["b(X)", "d(Z): e(X,Z)"],
            signs=(Sign.NoSign,),
        )
        self.helper_body_elements(
            "a(X) :- b(X), not c(Y), d(Z): e(X,Z); not d(Z): e(X,Z).",
            ["b(X)", "d(Z): e(X,Z)"],
            signs=(Sign.NoSign,),
            conditional_literal_predicate=lambda x: x.literal.sign != Sign.Single,
        )
        stm = self.last_stm("#show a.")
        self.assertListEqual(list(filter_body_literals([stm])), [stm])

    def _aux_theory_term_to_term(self, s: str) -> None:
        """
        Parse the given theory term using a simple parse table for testing.
        """
        parsed = self.parse_theory_term(s)
        unparsed = self.theory_atom(f"&p {{{s}}}").elements[0].tuple[0]
        term = self.parse_clingo_term(s)

        self.assertEqual(
            theory_term_to_term(self.lib, parsed, False), term, "without parsing"
        )
        self.assertEqual(
            theory_term_to_term(self.lib, unparsed, True), term, "with parsing"
        )

    def test_theory_term_to_term(self):
        """
        Tests for converting theory terms into terms.
        """
        self._aux_theory_term_to_term("(1,-1,~1)")
        self._aux_theory_term_to_term("(1+X,1-X,1*X,1/X,1\\X,1**X,1&X,1?X,1^X)")
        self._aux_theory_term_to_term("1..X")
        self._aux_theory_term_to_term("f(X)")
        self._aux_theory_term_to_term("-1+ ~2-3*4/5\\6**7&8?9^10..11")

        with self.assertRaisesRegex(RuntimeError, "invalid term"):
            theory_term_to_term(self.lib, self.parse_theory_term("[3*4]"))
        with self.assertRaisesRegex(RuntimeError, "invalid term"):
            theory_term_to_term(self.lib, self.parse_theory_term("{3*4}"))

    def _aux_theory_term_to_literal(self, s: str, s_expected: Optional[str] = None):
        """
        Test parsing the given string representing a theory literal.
        """
        parsed = self.parse_theory_term_as_literal(s)
        unparsed = self.theory_atom(f"&p {{{s}}}").elements[0].tuple[0]
        expected = self.parse_clingo_literal(s if s_expected is None else s_expected)

        self.assertEqual(
            theory_term_to_literal(self.lib, parsed, False),
            expected,
            "without parsing",
        )
        self.assertEqual(
            theory_term_to_literal(self.lib, unparsed, True), expected, "with parsing"
        )

    def test_theory_term_to_literal(self):
        """
        Tests for converting theory terms into terms.
        """
        self._aux_theory_term_to_literal("p")
        self._aux_theory_term_to_literal("p(1)")
        self._aux_theory_term_to_literal("not p(1+X,1-X,1*X,1/X,1\\X,1**X,1&X,1?X,1^X)")
        self._aux_theory_term_to_literal("not not p(1..X)")
        self._aux_theory_term_to_literal("-p(f(X))")
        self._aux_theory_term_to_literal("not -p(1)")
        self._aux_theory_term_to_literal("not not -p(1)")

        self._aux_theory_term_to_literal("not not not p(1)", "not p(1)")
        self._aux_theory_term_to_literal("not not not not p(1)", "not not p(1)")
        self._aux_theory_term_to_literal("- -p(1)", "p(1)")
        self._aux_theory_term_to_literal("- - -p(1)", "-p(1)")
        self._aux_theory_term_to_literal("- not p(1)", "not not p(1)")
        self._aux_theory_term_to_literal("- - not p(1)", "not p(1)")
        self._aux_theory_term_to_literal("- not not p(1)", "not p(1)")
        self._aux_theory_term_to_literal("- not not - not p(1)", "not p(1)")
        self._aux_theory_term_to_literal("- -not not p(1)", "not not p(1)")

        with self.assertRaisesRegex(RuntimeError, "cannot parse operator"):
            theory_term_to_literal(
                self.lib, self.parse_theory_term_as_literal("p(not 1)")
            )
        with self.assertRaisesRegex(RuntimeError, "invalid literal"):
            theory_term_to_literal(self.lib, self.parse_theory_term_as_literal("(a,b)"))
        with self.assertRaisesRegex(RuntimeError, "invalid literal"):
            theory_term_to_literal(
                self.lib, self.parse_theory_term_as_literal("not 3*4")
            )

    def test_function_transformer(self):
        """
        Tests for converting clingo.symbol.Symbol to ast.TermFunction
        """
        lib = self.lib
        loc = self.loc

        def fun(name, arguments):
            return ast.TermFunction(
                lib, loc, name, [ast.ArgumentTuple(lib, arguments)], False
            )

        atom = parse_term(lib, "u(a)")
        self.assertEqual(
            atom, fun("u", [ast.TermSymbolic(lib, loc, Function(lib, "a"))])
        )
        normalized_atom = normalize_symbolic_terms(lib, atom)
        self.assertEqual(normalized_atom, fun("u", [fun("a", [])]))

        atom = parse_term(lib, "u(1)")
        self.assertEqual(atom, fun("u", [ast.TermSymbolic(lib, loc, Number(lib, 1))]))
        normalized_atom = normalize_symbolic_terms(lib, atom)
        self.assertEqual(
            normalized_atom, fun("u", [ast.TermSymbolic(lib, loc, Number(lib, 1))])
        )

        atom = ast.TermSymbolic(lib, loc, Function(lib, "u", [Function(lib, "a")]))
        normalized_atom = normalize_symbolic_terms(lib, atom)
        self.assertEqual(normalized_atom, fun("u", [fun("a", [])]))

        atom = ast.TermSymbolic(lib, loc, Function(lib, "u", [Number(lib, 1)]))
        normalized_atom = normalize_symbolic_terms(lib, atom)
        self.assertEqual(
            normalized_atom, fun("u", [ast.TermSymbolic(lib, loc, Number(lib, 1))])
        )
