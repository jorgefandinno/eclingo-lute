"""
Test cases for the reify module.

The expected reified outputs below follow the format of `clingo --output=reify`
of clingo 5. The outputs of simple examples have been checked to be identical
to the ones produced by clingox with clingo 5.8; for the larger examples the
outputs agree up to the renumbering of program atoms and theory terms.
"""

from typing import Callable, Dict, List, Set
from unittest import TestCase

from clingo.base import TheoryTermType
from clingo.core import Library
from clingo.symbol import Function, Number, Symbol

from eclingo.clingox.reify import (
    ReifiedTheory,
    ReifiedTheoryTerm,
    Reifier,
    reify_program,
)
from eclingo.clingox.theory import evaluate, is_clingo_operator, is_operator

GRAMMAR = """
#theory theory {
    term { +  : 6, binary, left;
           <? : 5, binary, left;
           <  : 4, unary };
    &tel/0 : term, any;
    &tel2/0 : term, {=}, term, head
}.
"""

THEORY = """
#theory theory {
    t { + : 0, binary, left;
        - : 0, unary };
    &a/0 : t, {=}, t, head;
    &b/0 : t, directive
}.
"""


def term_symbols(lib: Library, term: ReifiedTheoryTerm, ret: Dict[int, Symbol]) -> None:
    """
    Represent arguments to theory operators using clingo's
    `clingo.symbol.Symbol` class.

    Theory terms are evaluated using `clingox.theory.evaluate` and added to the
    given dictionary using the index of the theory term as key.
    """
    if (
        term.type == TheoryTermType.Function
        and is_operator(term.name)
        and not is_clingo_operator(term.name)
    ):
        term_symbols(lib, term.arguments[0], ret)
        term_symbols(lib, term.arguments[1], ret)
    elif term.index not in ret:
        ret[term.index] = evaluate(lib, term)


def visit_terms(thy: ReifiedTheory, cb: Callable[[ReifiedTheoryTerm], None]):
    """
    Visit the terms occurring in the theory atoms of the given theory.

    This function does not recurse into terms.
    """
    for atm in thy:
        for elem in atm.elements:
            for term in elem.terms:
                cb(term)
        cb(atm.term)
        guard = atm.guard
        if guard:
            cb(guard[1])


class TestReifier(TestCase):
    """
    Tests for the Reifier.
    """

    lib: Library

    def setUp(self):
        self.lib = Library(message_limit=0)

    def reify(self, prg: str, calculate_sccs: bool = False, reify_steps: bool = False):
        """
        Reify the given program returning the reified facts as strings.
        """
        return [
            str(sym)
            for sym in reify_program(self.lib, prg, calculate_sccs, reify_steps)
        ]

    def test_reify_simple(self):
        """
        Test reification of a simple program.

        The expected output is identical to the one of clingox with clingo 5.8.
        """
        self.assertListEqual(
            self.reify("b :- a. {a}."),
            [
                "tag(incremental)",
                "atom_tuple(0)",
                "atom_tuple(0,1)",
                "literal_tuple(0)",
                "rule(choice(0),normal(0))",
                "atom_tuple(1)",
                "atom_tuple(1,2)",
                "literal_tuple(1)",
                "literal_tuple(1,1)",
                "rule(disjunction(1),normal(1))",
                "output(a,1)",
                "literal_tuple(2)",
                "literal_tuple(2,2)",
                "output(b,2)",
            ],
        )

    def test_reify_theory_atom(self):
        """
        Test reification of a simple theory atom.

        The expected output is identical to the one of clingox with clingo 5.8.
        """
        self.assertListEqual(
            self.reify("#theory theory { t { }; &p/0 : t, any }. &p { t }."),
            [
                "tag(incremental)",
                "atom_tuple(0)",
                "atom_tuple(0,1)",
                "literal_tuple(0)",
                "rule(disjunction(0),normal(0))",
                'theory_string(0,"p")',
                'theory_string(1,"t")',
                "theory_tuple(0)",
                "theory_tuple(0,0,1)",
                "theory_element(0,0,0)",
                "theory_element_tuple(0)",
                "theory_element_tuple(0,0)",
                "theory_atom(1,0,0)",
            ],
        )

    def test_reify_negative_literal(self):
        """
        Test reification of rules with negative literals.
        """
        self.assertListEqual(
            self.reify(":- not b. {b}."),
            [
                "tag(incremental)",
                "atom_tuple(0)",
                "literal_tuple(0)",
                "literal_tuple(0,-1)",
                "rule(disjunction(0),normal(0))",
                "atom_tuple(1)",
                "atom_tuple(1,1)",
                "literal_tuple(1)",
                "rule(choice(1),normal(1))",
                "literal_tuple(2)",
                "literal_tuple(2,1)",
                "output(b,2)",
            ],
        )

    def test_reify_show_term(self):
        """
        Test reification of show statements.
        """
        self.assertListEqual(
            self.reify("a(1..2). #show b(X): a(X)."),
            [
                "tag(incremental)",
                "atom_tuple(0)",
                "atom_tuple(0,1)",
                "literal_tuple(0)",
                "rule(disjunction(0),normal(0))",
                "output(a(1),0)",
                "output(a(2),0)",
                "output(b(1),0)",
                "output(b(2),0)",
            ],
        )

    def test_reify_minimize(self):
        """
        Test reification of minimize statements.
        """
        result = self.reify("1{ a(1..2) }. #minimize { X@2: a(X) }.")
        self.assertIn("weighted_literal_tuple(0)", result)
        self.assertIn("weighted_literal_tuple(0,3,1)", result)
        self.assertIn("weighted_literal_tuple(0,4,2)", result)
        self.assertIn("minimize(2,0)", result)

    def test_reify_external(self):
        """
        Test reification of external statements.
        """
        self.assertListEqual(
            self.reify("#external a. [free]"),
            [
                "tag(incremental)",
                "external(1,free)",
                "literal_tuple(0)",
                "literal_tuple(0,1)",
                "output(a,0)",
            ],
        )
        self.assertIn("external(1,true)", self.reify("#external a. [true]"))
        self.assertIn("external(1,false)", self.reify("#external a. [false]"))

    def test_reify_heuristic(self):
        """
        Test reification of heuristic statements.
        """
        self.assertIn(
            "heuristic(1,true,1,0,0)", self.reify("#heuristic a. [1,true] {a}.")
        )

    def test_reify_edge(self):
        """
        Test reification of edge statements.
        """
        result = self.reify("#edge (a,b): c. {c}.")
        self.assertIn("edge(0,1,1)", result)
        self.assertIn("literal_tuple(1,1)", result)

    def test_reify_theory_guard(self):
        """
        Test reification of theory atoms with guards.
        """
        self.assertListEqual(
            self.reify(GRAMMAR + "&tel2 { a <? b } = c."),
            [
                "tag(incremental)",
                "atom_tuple(0)",
                "atom_tuple(0,1)",
                "literal_tuple(0)",
                "rule(disjunction(0),normal(0))",
                'theory_string(0,"tel2")',
                'theory_string(1,"a")',
                'theory_string(2,"b")',
                'theory_string(3,"<?")',
                "theory_tuple(0)",
                "theory_tuple(0,0,1)",
                "theory_tuple(0,1,2)",
                "theory_function(4,3,0)",
                "theory_tuple(1)",
                "theory_tuple(1,0,4)",
                "theory_element(0,1,0)",
                "theory_element_tuple(0)",
                "theory_element_tuple(0,0)",
                'theory_string(5,"=")',
                'theory_string(6,"c")',
                "theory_atom(1,0,0,5,6)",
            ],
        )

    def test_reify_theory_sequence(self):
        """
        Test reification of theory atoms with tuples and functions.
        """
        self.assertListEqual(
            self.reify(GRAMMAR + "&tel { a(s) <? b((2,3)) }."),
            [
                "tag(incremental)",
                "atom_tuple(0)",
                "atom_tuple(0,1)",
                "literal_tuple(0)",
                "rule(disjunction(0),normal(0))",
                'theory_string(0,"tel")',
                'theory_string(1,"s")',
                'theory_string(2,"a")',
                "theory_tuple(0)",
                "theory_tuple(0,0,1)",
                "theory_function(3,2,0)",
                "theory_number(4,2)",
                "theory_number(5,3)",
                "theory_tuple(1)",
                "theory_tuple(1,0,4)",
                "theory_tuple(1,1,5)",
                "theory_sequence(6,tuple,1)",
                'theory_string(7,"b")',
                "theory_tuple(2)",
                "theory_tuple(2,0,6)",
                "theory_function(8,7,2)",
                'theory_string(9,"<?")',
                "theory_tuple(3)",
                "theory_tuple(3,0,3)",
                "theory_tuple(3,1,8)",
                "theory_function(10,9,3)",
                "theory_tuple(4)",
                "theory_tuple(4,0,10)",
                "theory_element(0,4,0)",
                "theory_element_tuple(0)",
                "theory_element_tuple(0,0)",
                "theory_atom(1,0,0)",
            ],
        )

    def test_reify_sccs(self):
        """
        Test reification with SCC calculation.
        """
        result = self.reify("a :- b. b :- a. c :- d. {a; d}.", calculate_sccs=True)
        self.assertIn("scc(0,1)", result)
        self.assertIn("scc(0,3)", result)
        self.assertEqual(2, sum(1 for s in result if s.startswith("scc")))

    def test_reify_steps(self):
        """
        Test reification with step numbers.
        """
        self.assertListEqual(
            self.reify("{a}. b :- a.", reify_steps=True),
            [
                "tag(incremental)",
                "atom_tuple(0,0)",
                "atom_tuple(0,1,0)",
                "literal_tuple(0,0)",
                "rule(choice(0),normal(0),0)",
                "atom_tuple(1,0)",
                "atom_tuple(1,2,0)",
                "literal_tuple(1,0)",
                "literal_tuple(1,1,0)",
                "rule(disjunction(1),normal(1),0)",
                "output(a,1,0)",
                "literal_tuple(2,0)",
                "literal_tuple(2,2,0)",
                "output(b,2,0)",
            ],
        )

    def test_reifier_callback(self):
        """
        Test using the Reifier class directly with a callback.
        """
        from clingo.control import Control

        ctl = Control(self.lib)
        symbols: List[Symbol] = []
        reifier = Reifier(self.lib, symbols.append)
        ctl.parse_string("{a}.")
        ctl.ground()
        ctl.observe(reifier, preprocess=False)
        self.assertIn("rule(choice(0),normal(0))", [str(s) for s in symbols])

    def test_theory(self):
        """
        Test the reified theory class.
        """

        def get_theory(prg):
            symbols = reify_program(self.lib, prg)
            thy = ReifiedTheory(symbols)
            return list(thy)

        atm1 = get_theory(THEORY + "&a { f(1+ -2): x } = z. { x }.")[0]
        atm2 = get_theory(THEORY + "&a { f((1,2)): x }. { x }.")[0]
        atm3 = get_theory(THEORY + "&a { f([1,2]): x }. { x }.")[0]
        atm4 = get_theory(THEORY + "&a { f({1,2}): x }. { x }.")[0]
        atm5 = get_theory(THEORY + "&a. { x }.")[0]
        self.assertEqual(str(atm1), "&a { f((1)+(-(2))): literal_tuple(1) } = z")
        self.assertEqual(str(atm2), "&a { f((1,2)): literal_tuple(1) }")
        self.assertEqual(str(atm3), "&a { f([1,2]): literal_tuple(1) }")
        self.assertEqual(str(atm4), "&a { f({1,2}): literal_tuple(1) }")
        self.assertEqual(str(atm5), "&a")

        self.assertEqual(
            evaluate(self.lib, atm1.elements[0].terms[0]),
            Function(self.lib, "f", [Number(self.lib, -1)]),
        )
        self.assertGreaterEqual(atm1.literal, 1)

        # Note: with clingo 5 directives were associated with atom 0, with
        # clingo 6 they get a regular program atom.
        dir1 = get_theory(THEORY + "&b.")[0]
        self.assertGreaterEqual(dir1.literal, 1)

        atms = get_theory(THEORY + "&a { 1 }. &a { 2 }. &a { 3 }.")
        self.assertEqual(len(set(atms)), 3)
        self.assertNotEqual(atms[0], atms[1])
        self.assertNotEqual(atms[0] < atms[1], atms[0] > atms[1])

        aele = get_theory(THEORY + "&a { 1; 2; 3 }.")[0]
        self.assertEqual(len(set(aele.elements)), 3)
        self.assertNotEqual(aele.elements[0], aele.elements[1])
        self.assertNotEqual(
            aele.elements[0] < aele.elements[1], aele.elements[0] > aele.elements[1]
        )

        atup = get_theory(THEORY + "&a { 1,2,3 }.")[0]
        self.assertEqual(len(set(atup.elements[0].terms)), 3)
        self.assertNotEqual(atup.elements[0].terms[0], atup.elements[0].terms[1])
        self.assertNotEqual(
            atup.elements[0].terms[0] < atup.elements[0].terms[1],
            atup.elements[0].terms[0] > atup.elements[0].terms[1],
        )

    def test_theory_symbols(self):
        """
        Test function to get symbols in a theory.
        """

        def theory_symbols(prg: str) -> Set[str]:
            ret: Dict[int, Symbol] = {}
            visit_terms(
                ReifiedTheory(reify_program(self.lib, prg)),
                lambda term: term_symbols(self.lib, term, ret),
            )
            return set(str(x) for x in ret.values())

        prg = GRAMMAR + "&tel { a(s) <? b((2,3)) }."
        self.assertSetEqual(theory_symbols(prg), set(["a(s)", "b((2,3))", "tel"]))

        prg = GRAMMAR + '&tel2 { (a("s") <? 2+3) <? b((2,3)) } = z.'
        self.assertSetEqual(
            theory_symbols(prg), set(["5", 'a("s")', "z", "tel2", "b((2,3))"])
        )

        prg = GRAMMAR + "&tel{ a({b,c}) <? c}."
        self.assertRaises(RuntimeError, theory_symbols, prg)
