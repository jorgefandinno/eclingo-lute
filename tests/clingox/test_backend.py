"""
Test cases for the symbolic symbolic_backend.
"""

from unittest import TestCase

from clingo.backend import ExternalType, HeuristicType
from clingo.control import Control
from clingo.core import Library
from clingo.symbol import Function

from eclingo.clingox.backend import SymbolicBackend

lib = Library()


def _symbols(ctl):
    """Get atoms from all models (expects at most one model)."""
    result = []
    with ctl.start_solve(yield_=True) as handle:
        for model in handle:
            result = sorted(str(s) for s in model.symbols(atoms=True))
    return result


class TestSymbolicBackend(TestCase):
    """
    Tests for the symbolic symbolic_backend.
    """

    def setUp(self):
        self.ctl = Control(lib, [])

    def test_add_acyc_edge(self):
        """
        Test edge statement: ensure acyclicity constraints work.
        """
        a = Function(lib, "a")
        b = Function(lib, "b")
        c = Function(lib, "c")
        with SymbolicBackend(self.ctl.backend) as symbolic_backend:
            symbolic_backend.add_acyc_edge(1, 2, [a], [])
            symbolic_backend.add_acyc_edge(2, 1, [b], [])
            symbolic_backend.add_rule([a])
            symbolic_backend.add_rule([b])
        # Both a and b: creates cycle 1->2->1, should be unsatisfiable
        with self.ctl.start_solve(yield_=True) as handle:
            models = list(handle)
        self.assertEqual(len(models), 0)

    def test_add_assume(self):
        """
        Test assumptions.
        """
        a = Function(lib, "a")
        b = Function(lib, "b")
        with SymbolicBackend(self.ctl.backend) as symbolic_backend:
            symbolic_backend.add_rule([a], choice=True)
            symbolic_backend.add_rule([b], choice=True)
            symbolic_backend.add_assume([a, b])
        result = _symbols(self.ctl)
        self.assertIn("a", result)
        self.assertIn("b", result)

    def test_add_external(self):
        """
        Test external statement.
        """
        a = Function(lib, "a", [Function(lib, "c1")])
        with SymbolicBackend(self.ctl.backend) as symbolic_backend:
            symbolic_backend.add_external(a, ExternalType.True_)
        result = _symbols(self.ctl)
        self.assertIn("a(c1)", result)

    def test_add_heuristic(self):
        """
        Test heuristic statement (just checks it doesn't crash).
        """
        a = Function(lib, "a", [Function(lib, "c1")])
        b = Function(lib, "b", [Function(lib, "c2")])
        c = Function(lib, "c", [Function(lib, "c3")])
        with SymbolicBackend(self.ctl.backend) as symbolic_backend:
            symbolic_backend.add_rule([a], choice=True)
            symbolic_backend.add_rule([b], choice=True)
            symbolic_backend.add_rule([c], choice=True)
            symbolic_backend.add_heuristic(a, HeuristicType.Level, 2, 3, [b], [c])
        # Just check it doesn't crash; heuristic affects search not models
        with self.ctl.start_solve(yield_=True) as handle:
            models = list(handle)
        self.assertGreater(len(models), 0)

    def test_add_minimize(self):
        """
        Test minimize statement.
        """
        a = Function(lib, "a", [Function(lib, "c1")])
        b = Function(lib, "b", [Function(lib, "c2")])
        with SymbolicBackend(self.ctl.backend) as symbolic_backend:
            symbolic_backend.add_rule([a], choice=True)
            symbolic_backend.add_rule([b], choice=True)
            symbolic_backend.add_minimize(1, [(a, 3), (b, 5)], [])
        # Optimal model minimizes cost: empty model has cost 0
        result = _symbols(self.ctl)
        self.assertEqual(result, [])

    def test_add_project(self):
        """
        Test project statements.
        """
        a = Function(lib, "a", [Function(lib, "c1")])
        b = Function(lib, "b", [Function(lib, "c2")])
        with SymbolicBackend(self.ctl.backend) as symbolic_backend:
            symbolic_backend.add_rule([a])
            symbolic_backend.add_rule([b])
            symbolic_backend.add_project([a])
        # Just verify it runs without error
        with self.ctl.start_solve(yield_=True) as handle:
            models = list(handle)
        self.assertGreater(len(models), 0)

    def test_add_empty_project(self):
        """
        Test empty project statement.
        """
        a = Function(lib, "a", [Function(lib, "c1")])
        with SymbolicBackend(self.ctl.backend) as symbolic_backend:
            symbolic_backend.add_rule([a])
            symbolic_backend.add_project([])
        # Empty project should still allow solving
        with self.ctl.start_solve(yield_=True) as handle:
            models = list(handle)
        self.assertGreater(len(models), 0)

    def test_add_rule(self):
        """
        Test simple rules.
        """
        a = Function(lib, "a", [Function(lib, "c1")])
        b = Function(lib, "b", [Function(lib, "c2")])
        c = Function(lib, "c", [Function(lib, "c3")])
        with SymbolicBackend(self.ctl.backend) as symbolic_backend:
            symbolic_backend.add_rule([a], [b], [c])
            symbolic_backend.add_rule([b])  # b is a fact
        # b is true, c is false => a should be true
        result = _symbols(self.ctl)
        self.assertIn("a(c1)", result)
        self.assertIn("b(c2)", result)
        self.assertNotIn("c(c3)", result)

    def test_add_choice_rule(self):
        """
        Test choice rules.
        """
        ctl = Control(lib, ["0"])  # enumerate all models
        a = Function(lib, "a", [Function(lib, "c1")])
        b = Function(lib, "b", [Function(lib, "c2")])
        c = Function(lib, "c", [Function(lib, "c3")])
        with SymbolicBackend(ctl.backend) as symbolic_backend:
            symbolic_backend.add_rule([a], [b], [c], choice=True)
            symbolic_backend.add_rule([b])
        # b is true, c is false => {a} is possible; multiple models
        with ctl.start_solve(yield_=True) as handle:
            models = [sorted(str(s) for s in m.symbols(atoms=True)) for m in handle]
        self.assertIn(["b(c2)"], models)
        self.assertIn(["a(c1)", "b(c2)"], models)

    def test_add_weight_rule(self):
        """
        Test weight rules.
        """
        a = Function(lib, "a", [Function(lib, "c1")])
        b = Function(lib, "b", [Function(lib, "c2")])
        c = Function(lib, "c", [Function(lib, "c3")])
        with SymbolicBackend(self.ctl.backend) as symbolic_backend:
            symbolic_backend.add_weight_rule([a], 3, [(b, 5)], [(c, 7)])
            symbolic_backend.add_rule([b])  # b is a fact, c is false
        # b=true(5), not c(7) => sum = 12 >= 3 => a is true
        result = _symbols(self.ctl)
        self.assertIn("a(c1)", result)

    def test_add_weight_choice_rule(self):
        """
        Test weight rules that are also choice rules.
        """
        ctl = Control(lib, ["0"])  # enumerate all models
        a = Function(lib, "a", [Function(lib, "c1")])
        b = Function(lib, "b", [Function(lib, "c2")])
        c = Function(lib, "c", [Function(lib, "c3")])
        with SymbolicBackend(ctl.backend) as symbolic_backend:
            symbolic_backend.add_weight_rule([a], 3, [(b, 5)], [(c, 7)], choice=True)
            symbolic_backend.add_rule([b])
        # b=true(5), not c(7) => sum = 12 >= 3 => {a} is available; two models
        with ctl.start_solve(yield_=True) as handle:
            models = [sorted(str(s) for s in m.symbols(atoms=True)) for m in handle]
        self.assertIn(["b(c2)"], models)
        self.assertIn(["a(c1)", "b(c2)"], models)
