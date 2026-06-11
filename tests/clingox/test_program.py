"""
Test cases for the ground program and observer.
"""

from typing import cast
from unittest import TestCase

from clingo.backend import ExternalType, HeuristicType
from clingo.control import Control
from clingo.core import Library
from clingo.symbol import Function

from eclingo.clingox.program import (
    Edge,
    External,
    Fact,
    Heuristic,
    Minimize,
    Program,
    ProgramObserver,
    Project,
    Remapping,
    Rule,
    Show,
    WeightRule,
    remap,
)


def _remap(lib: Library, prg: Program, mapping=None):
    """
    Add the given program to a backend passing it through an observer and then
    return the observer program.

    The resulting program is initialized with the symbols from the orginial
    program.
    """

    ctl, chk = Control(lib), Program()
    # note that output atoms are not passed to the backend
    if mapping is None:
        chk.output_atoms = prg.output_atoms
        chk.shows = prg.shows
    else:
        chk.output_atoms = {mapping(lit): sym for lit, sym in prg.output_atoms.items()}
        chk.shows = [cast(Show, remap(x, mapping)) for x in prg.shows]
    chk.facts = prg.facts

    with ctl.backend as b:
        prg.add_to_backend(b, mapping)

    ctl.observe(ProgramObserver(chk), preprocess=False)

    return chk


def _plus10(atom):
    """
    Simple mapping adding +10 to every atom.
    """
    return atom + 10


class TestProgram(TestCase):
    """
    Tests for the program observer.
    """

    lib: Library
    prg: Program
    obs: ProgramObserver

    def setUp(self):
        self.lib = Library(message_limit=0)
        self.prg = Program()
        self.obs = ProgramObserver(self.prg)

    def _add_atoms(self, *atoms: str):
        """
        Generate an output table for the given atom names.

        With clingo 6, the output table is computed from the base in
        `ProgramObserver.end_step`, so the table is added to the program
        directly here.
        """
        lit = 1
        out, out10 = {}, {}
        for atom in atoms:
            sym = Function(self.lib, atom)
            self.prg.output_atoms[lit] = sym
            out[lit] = sym
            out10[_plus10(lit)] = sym
            lit += 1
        return out, out10

    def _check(self, prg, prg10, prg_str):
        """
        Check various ways to remap a program.

        1. No remapping.
        2. Identity remapping via Backend and Control.
        3. Remapping via Backend and Control.
        4. Remapping via remap function without Backend and Control.
        5. Remap a program using the Remapping class.
        """
        self.assertEqual(self.prg, prg)
        self.assertEqual(str(self.prg), prg_str)

        r_prg = _remap(self.lib, self.prg)
        self.assertEqual(self.prg, r_prg)
        self.assertEqual(str(r_prg), prg_str)

        r_prg10 = _remap(self.lib, self.prg, _plus10)
        self.assertEqual(r_prg10, prg10)
        self.assertEqual(str(r_prg10), prg_str)

        ra_prg10 = self.prg.copy().remap(_plus10)
        self.assertEqual(ra_prg10, prg10)
        self.assertEqual(str(ra_prg10), prg_str)

        # note that the backend below is just used as an atom generator
        ctl = Control(self.lib)
        with ctl.backend as b:
            for _ in range(10):
                b.atom()
            rm_prg = prg.copy().remap(
                Remapping(b, self.prg.output_atoms, self.prg.facts)
            )
        self.assertEqual(str(rm_prg), prg_str)

    def test_normal_rule(self):
        """
        Test simple rules.
        """
        out, out10 = self._add_atoms("a", "b", "c")
        self.obs.rule([1], [2, -3], False)
        self._check(
            Program(
                output_atoms=out, rules=[Rule(choice=False, head=[1], body=[2, -3])]
            ),
            Program(
                output_atoms=out10,
                rules=[Rule(choice=False, head=[11], body=[12, -13])],
            ),
            "a :- b, not c.",
        )

    def test_aux_lit(self):
        """
        Test printing of auxiliary literals.
        """
        out, out10 = self._add_atoms("a", "b", "c")
        self.obs.rule([4], [1], False)
        self.assertEqual(
            self.prg,
            Program(output_atoms=out, rules=[Rule(choice=False, head=[4], body=[1])]),
        )
        self.assertEqual(str(self.prg), "__x4 :- a.")

        prg10 = _remap(self.lib, self.prg, _plus10)
        self.assertEqual(
            prg10,
            Program(
                output_atoms=out10, rules=[Rule(choice=False, head=[14], body=[11])]
            ),
        )
        self.assertEqual(str(prg10), "__x14 :- a.")

        ctl = Control(self.lib)
        with ctl.backend as b:
            b.atom()
            rm_prg = self.prg.copy().remap(
                Remapping(b, self.prg.output_atoms, self.prg.facts)
            )
        self.assertEqual(str(rm_prg), "__x5 :- a.")

    def test_facts(self):
        """
        Test simple rules.
        """
        out, out10 = self._add_atoms("a", "b", "c")
        self.prg.facts.append(Fact(Function(self.lib, "d")))
        self._check(
            Program(output_atoms=out, facts=[Fact(Function(self.lib, "d"))]),
            Program(output_atoms=out10, facts=[Fact(Function(self.lib, "d"))]),
            "d.",
        )

    def test_add_choice_rule(self):
        """
        Test choice rules.
        """
        out, out10 = self._add_atoms("a", "b", "c")
        self.obs.rule([1], [2, -3], True)
        self._check(
            Program(
                output_atoms=out, rules=[Rule(choice=True, head=[1], body=[2, -3])]
            ),
            Program(
                output_atoms=out10, rules=[Rule(choice=True, head=[11], body=[12, -13])]
            ),
            "{a} :- b, not c.",
        )

    def test_add_weight_rule(self):
        """
        Test weight rules.

        The weights and bound are chosen such that clingo 6 cannot normalize
        the weight rule into normal or cardinality rules when it is added to a
        backend. Positive body literals come first because clingo 6 reorders
        them this way when the rule is added.
        """
        out, out10 = self._add_atoms("a", "b", "c", "d")
        self.obs.weight_rule([1], 11, [(2, 7), (4, 4), (-3, 5)], True)
        self._check(
            Program(
                output_atoms=out,
                weight_rules=[
                    WeightRule(
                        choice=True,
                        head=[1],
                        lower_bound=11,
                        body=[(2, 7), (4, 4), (-3, 5)],
                    )
                ],
            ),
            Program(
                output_atoms=out10,
                weight_rules=[
                    WeightRule(
                        choice=True,
                        head=[11],
                        lower_bound=11,
                        body=[(12, 7), (14, 4), (-13, 5)],
                    )
                ],
            ),
            "{a} :- 11 #sum {7,0: b; 4,1: d; 5,2: not c}.",
        )

    def test_add_project(self):
        """
        Test project statements.
        """
        out, out10 = self._add_atoms("a", "b", "c")
        self.obs.project([1, 2])
        self._check(
            Program(output_atoms=out, projects=[Project(atom=1), Project(atom=2)]),
            Program(output_atoms=out10, projects=[Project(atom=11), Project(atom=12)]),
            "#project a.\n#project b.",
        )

    def test_add_empty_project(self):
        """
        Test empty projection statement.
        """
        out, out10 = self._add_atoms("a", "b", "c")
        self.obs.project([])
        self._check(
            Program(output_atoms=out, projects=[]),
            Program(output_atoms=out10, projects=[]),
            "#project x: #false.",
        )

    def test_add_external(self):
        """
        Test external statement.
        """
        out, out10 = self._add_atoms("a", "b", "c")
        self.obs.external(1, ExternalType.True_)
        self.obs.external(2, ExternalType.Free)
        self.obs.external(3, ExternalType.False_)
        self._check(
            Program(
                output_atoms=out,
                externals=[
                    External(atom=1, value=ExternalType.True_),
                    External(atom=2, value=ExternalType.Free),
                    External(atom=3, value=ExternalType.False_),
                ],
            ),
            Program(
                output_atoms=out10,
                externals=[
                    External(atom=11, value=ExternalType.True_),
                    External(atom=12, value=ExternalType.Free),
                    External(atom=13, value=ExternalType.False_),
                ],
            ),
            "#external a. [true]\n" "#external b. [free]\n" "#external c. [false]",
        )

    def test_add_minimize(self):
        """
        Test minimize statement.

        The atoms are made open using a choice rule because clingo 6 would
        otherwise simplify the unfounded atoms out of the minimize statement
        when it is added to a backend.
        """
        out, out10 = self._add_atoms("a", "b", "c")
        self.obs.rule([1, 2, 3], [], True)
        self.obs.minimize([(1, 7), (3, 5)], 10)
        self._check(
            Program(
                output_atoms=out,
                rules=[Rule(choice=True, head=[1, 2, 3], body=[])],
                minimizes=[Minimize(priority=10, literals=[(1, 7), (3, 5)])],
            ),
            Program(
                output_atoms=out10,
                rules=[Rule(choice=True, head=[11, 12, 13], body=[])],
                minimizes=[Minimize(priority=10, literals=[(11, 7), (13, 5)])],
            ),
            "{a; b; c}.\n#minimize{7@10,0: a; 5@10,1: c}.",
        )

    def test_add_edge(self):
        """
        Test edge statement.
        """
        out, out10 = self._add_atoms("a", "b", "c")
        self.obs.edge(1, 2, [1])
        self._check(
            Program(output_atoms=out, edges=[Edge(1, 2, [1])]),
            Program(output_atoms=out10, edges=[Edge(1, 2, [11])]),
            "#edge (1,2): a.",
        )

    def test_add_heuristic(self):
        """
        Test heuristic statement.
        """
        out, out10 = self._add_atoms("a", "b", "c")
        self.obs.heuristic(1, HeuristicType.Level, 2, 3, [2])
        self._check(
            Program(
                output_atoms=out,
                heuristics=[Heuristic(1, HeuristicType.Level, 2, 3, [2])],
            ),
            Program(
                output_atoms=out10,
                heuristics=[Heuristic(11, HeuristicType.Level, 2, 3, [12])],
            ),
            "#heuristic a: b. [2@3, Level]",
        )

    def test_add_assume(self):
        """
        Test assumptions.
        """
        out, out10 = self._add_atoms("a", "b", "c")
        self.obs.assume([1, 3])
        self._check(
            Program(output_atoms=out, assumptions=[1, 3]),
            Program(output_atoms=out10, assumptions=[11, 13]),
            "% assumptions: a, c",
        )

    def test_add_show(self):
        """
        Test show statement.
        """
        t = Function(self.lib, "t")
        out, out10 = self._add_atoms("a", "b", "c")
        self.prg.shows.append(Show(t, [1]))
        self._check(
            Program(output_atoms=out, shows=[Show(t, [1])]),
            Program(output_atoms=out10, shows=[Show(t, [11])]),
            "#show t: a.",
        )

    def test_control(self):
        """
        Test observer together with a control object.
        """
        ctl = Control(self.lib)
        ctl.parse_string("""\
            b.
            {c}.
            a :- b, not c.
            #minimize{7@10,a:a; 5@10,c:c}.
            #project a.
            #project b.
            #external d.
            """)
        ctl.ground()
        ctl.observe(self.obs, preprocess=False)
        a, b, c, d = (Function(self.lib, s) for s in ("a", "b", "c", "d"))
        la, lb, lc, ld = (ctl.base[sym].literal for sym in (a, b, c, d))

        self.prg.sort()

        self.assertEqual(
            self.prg,
            Program(
                output_atoms={la: a, lc: c, ld: d},
                shows=[],
                facts=[Fact(symbol=b)],
                rules=[
                    Rule(choice=False, head=[lb], body=[]),
                    Rule(choice=False, head=[la], body=[-lc]),
                    Rule(choice=True, head=[lc], body=[]),
                ],
                minimizes=[Minimize(priority=10, literals=[(la, 7), (lc, 5)])],
                externals=[External(atom=ld, value=ExternalType.False_)],
                projects=[Project(atom=lb), Project(atom=la)],
            ).sort(),
        )
