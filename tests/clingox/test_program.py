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

lib = Library()


def _copy_prg(prg: Program) -> Program:
    """
    Return an independent copy of the program.
    Program.copy() is shallow and remap() modifies lists in place, so we need
    to copy each list attribute to avoid mutating the original.
    """
    new_prg = Program()
    new_prg.output_atoms = dict(prg.output_atoms)
    new_prg.shows = list(prg.shows)
    new_prg.facts = list(prg.facts)
    new_prg.rules = list(prg.rules)
    new_prg.weight_rules = list(prg.weight_rules)
    new_prg.heuristics = list(prg.heuristics)
    new_prg.edges = list(prg.edges)
    new_prg.minimizes = list(prg.minimizes)
    new_prg.externals = list(prg.externals)
    new_prg.projects = list(prg.projects) if prg.projects is not None else None
    new_prg.assumptions = list(prg.assumptions)
    return new_prg


def _remap(prg: Program, mapping=None):
    """
    Return an independent copy of the program, optionally remapped.
    """
    if mapping is None:
        return _copy_prg(prg)
    return _copy_prg(prg).remap(mapping)


def _plus10(atom):
    """
    Simple mapping adding +10 to every atom.
    """
    return atom + 10


class TestProgram(TestCase):
    """
    Tests for the program observer.
    """

    prg: Program
    obs: ProgramObserver

    def __init__(self, *args, **kwargs):
        TestCase.__init__(self, *args, **kwargs)
        self.prg = Program()
        self.obs = ProgramObserver(self.prg)

    def tearDown(self):
        self.prg = Program()
        self.obs = ProgramObserver(self.prg)

    def _add_atoms(self, *atoms: str):
        """
        Generate an output table for the given atom names.
        """
        lit = 1
        lits = []
        out, out10 = {}, {}
        for atom in atoms:
            sym = Function(lib, atom)
            self.prg.output_atoms[lit] = sym
            lits.append(lit)
            out[lit] = sym
            out10[_plus10(lit)] = sym
            lit += 1
        return out, out10

    def _check(self, prg, prg10, prg_str):
        """
        Check various ways to remap a program.

        1. No remapping.
        2. Copy without remapping.
        3. Remapping via copy().remap().
        4. Remapping via remap function without Backend and Control.
        5. Remap a program using the Remapping class.
        """
        self.assertEqual(self.prg, prg)
        self.assertEqual(str(self.prg), prg_str)

        r_prg = _remap(self.prg)
        self.assertEqual(self.prg, r_prg)
        self.assertEqual(str(r_prg), prg_str)

        r_prg10 = _remap(self.prg, _plus10)
        self.assertEqual(r_prg10, prg10)
        self.assertEqual(str(r_prg10), prg_str)

        ra_prg10 = _copy_prg(self.prg).remap(_plus10)
        self.assertEqual(ra_prg10, prg10)
        self.assertEqual(str(ra_prg10), prg_str)

        # note that the backend below is just used as an atom generator
        ctl = Control(lib, [])
        with ctl.backend as b:
            for _ in range(10):
                b.atom()
            rm_prg = _copy_prg(prg).remap(
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

        prg10 = _remap(self.prg, _plus10)
        self.assertEqual(
            prg10,
            Program(
                output_atoms=out10, rules=[Rule(choice=False, head=[14], body=[11])]
            ),
        )
        self.assertEqual(str(prg10), "__x14 :- a.")

        ctl = Control(lib, [])
        with ctl.backend as b:
            b.atom()
            rm_prg = _copy_prg(self.prg).remap(
                Remapping(b, self.prg.output_atoms, self.prg.facts)
            )
        self.assertEqual(str(rm_prg), "__x5 :- a.")

    def test_facts(self):
        """
        Test simple rules.
        """
        out, out10 = self._add_atoms("a", "b", "c")
        self.prg.facts.append(Fact(Function(lib, "d")))
        self._check(
            Program(output_atoms=out, facts=[Fact(Function(lib, "d"))]),
            Program(output_atoms=out10, facts=[Fact(Function(lib, "d"))]),
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
        """
        out, out10 = self._add_atoms("a", "b", "c")
        self.obs.weight_rule([1], 10, [(2, 7), (-3, 5)], True)
        self._check(
            Program(
                output_atoms=out,
                weight_rules=[
                    WeightRule(
                        choice=True, head=[1], lower_bound=10, body=[(2, 7), (-3, 5)]
                    )
                ],
            ),
            Program(
                output_atoms=out10,
                weight_rules=[
                    WeightRule(
                        choice=True, head=[11], lower_bound=10, body=[(12, 7), (-13, 5)]
                    )
                ],
            ),
            "{a} :- 10 #sum {7,0: b; 5,1: not c}.",
        )

    def test_add_weight_choice_rule(self):
        """
        Test weight rules that are also choice rules.
        """
        out, out10 = self._add_atoms("a", "b", "c")
        self.obs.weight_rule([1], 10, [(2, 7), (-3, 5)], True)
        self._check(
            Program(
                output_atoms=out,
                weight_rules=[
                    WeightRule(
                        choice=True, head=[1], lower_bound=10, body=[(2, 7), (-3, 5)]
                    )
                ],
            ),
            Program(
                output_atoms=out10,
                weight_rules=[
                    WeightRule(
                        choice=True, head=[11], lower_bound=10, body=[(12, 7), (-13, 5)]
                    )
                ],
            ),
            "{a} :- 10 #sum {7,0: b; 5,1: not c}.",
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
        """
        out, out10 = self._add_atoms("a", "b", "c")
        self.obs.minimize([(1, 7), (3, 5)], 10)
        self._check(
            Program(
                output_atoms=out,
                minimizes=[Minimize(priority=10, literals=[(1, 7), (3, 5)])],
            ),
            Program(
                output_atoms=out10,
                minimizes=[Minimize(priority=10, literals=[(11, 7), (13, 5)])],
            ),
            "#minimize{7@10,0: a; 5@10,1: c}.",
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

        TODO: this test currently fails but probably has to be fixed in clingo
        because assumptions are not observed properly.
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
        t = Function(lib, "t")
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
        ctl = Control(lib, [])
        ctl.parse_string(
            """\
            b.
            {c}.
            a :- b, not c.
            #minimize{7@10,a:a; 5@10,c:c}.
            #project a.
            #project b.
            #external a.
            """
        )
        ctl.ground()
        ctl.observe(self.obs)

        a, b, c = (Function(lib, s) for s in ("a", "b", "c"))
        sym_to_lit = {}
        for _sig, atom_base in ctl.base.items():
            for sym, atom in atom_base.items():
                sym_to_lit[str(sym)] = atom.literal
        la, lb, lc = sym_to_lit["a"], sym_to_lit["b"], sym_to_lit["c"]

        self.prg.sort()

        self.assertEqual(
            self.prg,
            Program(
                output_atoms={la: a, lc: c},
                shows=[],
                facts=[Fact(symbol=b)],
                rules=[
                    Rule(choice=False, head=[lb], body=[]),
                    Rule(choice=False, head=[la], body=[-lc]),
                    Rule(choice=True, head=[lc], body=[]),
                ],
                minimizes=[Minimize(priority=10, literals=[(la, 7), (lc, 5)])],
                externals=[],
                projects=[Project(atom=lb), Project(atom=la)],
            ).sort(),
        )
