"""
This module provides functions to approximate the cautious consequences of a
program
"""

from typing import List, Optional, Sequence, Tuple

from clingo.control import Control
from clingo.propagate import Assignment, PropagateInit, Propagator
from clingo.symbol import Symbol

__all__ = ["approximate"]


class _RootLevelCollector(Propagator):
    """
    Propagator collecting the top-level truth values of all program atoms.

    With clingo 5, this information was obtained from the symbolic atoms after
    calling `Control.cleanup`, which no longer exists in clingo 6.
    """

    lower: List[Symbol]
    upper: List[Symbol]

    def __init__(self):
        super().__init__()
        self.lower = []
        self.upper = []

    def init(self, assignment: Assignment, init: PropagateInit) -> None:
        self.lower = []
        self.upper = []
        for atom_base in init.base.values():
            for atom in atom_base.values():
                value = assignment.value(init.solver_literal(atom.literal))
                if value is not False:
                    self.upper.append(atom.symbol)
                if value is True:
                    self.lower.append(atom.symbol)


def approximate(ctl: Control) -> Optional[Tuple[Sequence[Symbol], Sequence[Symbol]]]:
    """
    Approximate the stable models of a program.

    Parameters
    ----------
    ctl
        A control object with a program. Grounding should be performed on this
        control object before calling this function.

    Returns
    -------
    Returns `None` if the problem is determined unsatisfiable. Otherwise,
    returns an approximation of the stable models of the program in form of a
    pair of sequences of symbols. Atoms contained in the first sequence are
    true and atoms not contained in the second sequence are false in all stable
    models.

    Notes
    -----
    Runs in polynomial time. An approximation might be returned even if the
    problem is unsatisfiable.
    """
    # solve with a limit of 0 conflicts to propagate direct consequences
    collector = _RootLevelCollector()
    ctl.register_propagator(collector)

    solve_limit = ctl.config.solve.solve_limit.value
    ctl.config.solve.solve_limit.value = "0"
    result = ctl.solve()
    ctl.config.solve.solve_limit.value = solve_limit

    # check if the problem is conflicting
    if result.unsatisfiable:
        return None

    # return approximation
    return collector.lower, collector.upper
