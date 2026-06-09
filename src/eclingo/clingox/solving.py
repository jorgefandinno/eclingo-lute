"""
This module provides functions to approximate the cautious consequences of a
program
"""

from typing import Optional, Sequence, Tuple

from clingo.control import Control
from clingo.symbol import Symbol


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
    solve_limit = ctl.config.solve.solve_limit.value
    ctl.config.solve.solve_limit.value = "0"
    result = ctl.solve()
    ctl.config.solve.solve_limit.value = solve_limit

    # check if the problem is conflicting
    if result.unsatisfiable:
        return None

    # return approximation
    lower = []
    upper = []
    for _sig, ab in ctl.base.items():
        for sym, atom in ab.items():
            upper.append(sym)
            if ctl.base.is_fact(atom.literal):
                lower.append(sym)
    return lower, upper
