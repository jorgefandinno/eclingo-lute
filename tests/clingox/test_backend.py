"""
Test cases for the symbolic symbolic_backend.
"""

from unittest import TestCase

from clingo.backend import ExternalType, HeuristicType
from clingo.control import Control
from clingo.core import Library
from clingo.symbol import Function

from eclingo.clingox.backend import SymbolicBackend
from eclingo.clingox.program import Program, ProgramObserver


class TestSymbolicBackend(TestCase):
    """
    Tests for the ymbolic symbolic_backend.
    """

    def setUp(self):
        self.lib = Library(message_limit=0)
        self.prg = Program()
        self.obs = ProgramObserver(self.prg)
        self.ctl = Control(self.lib)

    def program_str(self) -> str:
        """
        Replay the current ground program into the observer and return its
        string representation.
        """
        self.ctl.observe(self.obs, preprocess=False)
        return str(self.prg)

    def test_wrapped_backend(self):
        """
        Test attaching the symbolic backend to an already managed backend.
        """
        a = Function(self.lib, "a")
        with self.ctl.backend as backend:
            with SymbolicBackend(backend) as symbolic_backend:
                symbolic_backend.add_rule([a])
        self.assertEqual(self.program_str(), "a.\n__x1.")

    def test_add_acyc_edge(self):
        """
        Test edge statement.
        """
        a = Function(self.lib, "a", [Function(self.lib, "c1")])
        b = Function(self.lib, "b", [Function(self.lib, "c2")])
        c = Function(self.lib, "c", [Function(self.lib, "c3")])
        with SymbolicBackend(self.ctl.backend) as symbolic_backend:
            symbolic_backend.add_acyc_edge(1, 3, [a], [b, c])
        self.assertEqual(
            self.program_str(), "#edge (1,3): a(c1), not b(c2), not c(c3)."
        )

    def test_add_assume(self):
        """
        Test assumptions.
        """
        a = Function(self.lib, "a", [Function(self.lib, "c1")])
        b = Function(self.lib, "b", [Function(self.lib, "c2")])
        c = Function(self.lib, "c", [Function(self.lib, "c3")])
        with SymbolicBackend(self.ctl.backend) as symbolic_backend:
            symbolic_backend.add_assume([a, b, c])
        self.assertEqual(self.program_str(), "% assumptions: a(c1), b(c2), c(c3)")

    def test_add_external(self):
        """
        Test external statement.
        """
        a = Function(self.lib, "a", [Function(self.lib, "c1")])
        with SymbolicBackend(self.ctl.backend) as symbolic_backend:
            symbolic_backend.add_external(a, ExternalType.True_)
        self.assertEqual(self.program_str(), "#external a(c1). [true]")

    def test_add_heuristic(self):
        """
        Test heuristic statement.
        """
        a = Function(self.lib, "a", [Function(self.lib, "c1")])
        b = Function(self.lib, "b", [Function(self.lib, "c2")])
        c = Function(self.lib, "c", [Function(self.lib, "c3")])
        with SymbolicBackend(self.ctl.backend) as symbolic_backend:
            symbolic_backend.add_heuristic(a, HeuristicType.Level, 2, 3, [b], [c])
        self.assertEqual(
            self.program_str(), "#heuristic a(c1): b(c2), not c(c3). [2@3, Level]"
        )

    def test_add_minimize(self):
        """
        Test minimize statement.

        The atoms are made open using choice rules because clingo 6 would
        otherwise simplify the unfounded atoms out of the minimize statement
        when it is added.
        """
        a = Function(self.lib, "a", [Function(self.lib, "c1")])
        b = Function(self.lib, "b", [Function(self.lib, "c2")])
        c = Function(self.lib, "c", [Function(self.lib, "c3")])
        with SymbolicBackend(self.ctl.backend) as symbolic_backend:
            symbolic_backend.add_rule([a], choice=True)
            symbolic_backend.add_rule([b], choice=True)
            symbolic_backend.add_rule([c], choice=True)
            symbolic_backend.add_minimize(1, [(a, 3), (b, 5)], [(c, 7)])
        self.assertEqual(
            self.program_str(),
            "{a(c1); b(c2); c(c3)}.\n"
            "#minimize{3@1,0: a(c1); 5@1,1: b(c2); 7@1,2: not c(c3)}.",
        )

    def test_add_project(self):
        """
        Test project statements.
        """
        a = Function(self.lib, "a", [Function(self.lib, "c1")])
        b = Function(self.lib, "b", [Function(self.lib, "c2")])
        c = Function(self.lib, "c", [Function(self.lib, "c3")])
        with SymbolicBackend(self.ctl.backend) as symbolic_backend:
            symbolic_backend.add_project([a, b, c])
        self.assertEqual(
            self.program_str(), "#project a(c1).\n#project b(c2).\n#project c(c3)."
        )

    def test_add_empty_project(self):
        """
        Test project statements.
        """
        with SymbolicBackend(self.ctl.backend) as symbolic_backend:
            symbolic_backend.add_project([])
        self.assertEqual(self.program_str(), "#project x: #false.")

    def test_add_rule(self):
        """
        Test simple rules.
        """
        a = Function(self.lib, "a", [Function(self.lib, "c1")])
        b = Function(self.lib, "b", [Function(self.lib, "c2")])
        c = Function(self.lib, "c", [Function(self.lib, "c3")])
        with SymbolicBackend(self.ctl.backend) as symbolic_backend:
            symbolic_backend.add_rule([a], [b], [c])
        self.assertEqual(self.program_str(), "a(c1) :- b(c2), not c(c3).")

    def test_add_choice_rule(self):
        """
        Test choice rules.
        """
        a = Function(self.lib, "a", [Function(self.lib, "c1")])
        b = Function(self.lib, "b", [Function(self.lib, "c2")])
        c = Function(self.lib, "c", [Function(self.lib, "c3")])
        with SymbolicBackend(self.ctl.backend) as symbolic_backend:
            symbolic_backend.add_rule([a], [b], [c], choice=True)
        self.assertEqual(self.program_str(), "{a(c1)} :- b(c2), not c(c3).")

    def test_add_weight_rule(self):
        """
        Test weight rules.

        Note that clingo 6 normalizes weight rules when they are added.
        Here, each single body literal reaches the lower bound, so the weight
        rule is translated into two normal rules.
        """
        a = Function(self.lib, "a", [Function(self.lib, "c1")])
        b = Function(self.lib, "b", [Function(self.lib, "c2")])
        c = Function(self.lib, "c", [Function(self.lib, "c3")])
        with SymbolicBackend(self.ctl.backend) as symbolic_backend:
            symbolic_backend.add_weight_rule([a], 3, [(b, 5)], [(c, 7)])
        self.assertEqual(self.program_str(), "a(c1) :- not c(c3).\na(c1) :- b(c2).")

    def test_add_weight_choice_rule(self):
        """
        Test weight rules that are also choice rules.

        Note that clingo 6 normalizes weight rules when they are added. Here,
        each single body literal reaches the lower bound, so the weight rule
        is translated into a cardinality rule.
        """
        a = Function(self.lib, "a", [Function(self.lib, "c1")])
        b = Function(self.lib, "b", [Function(self.lib, "c2")])
        c = Function(self.lib, "c", [Function(self.lib, "c3")])
        with SymbolicBackend(self.ctl.backend) as symbolic_backend:
            symbolic_backend.add_weight_rule([a], 3, [(b, 5)], [(c, 7)], choice=True)
        self.assertEqual(
            self.program_str(), "{a(c1)} :- 1 #sum {1,0: b(c2); 1,1: not c(c3)}."
        )
