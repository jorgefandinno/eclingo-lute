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
    # solve with a limit of 0 conflicts to propagate direct consequences and
    # simplify the program (removes atoms that can never be true)
    solve_limit = ctl.config.solve.solve_limit.value
    ctl.config.solve.solve_limit.value = "0"
    result = ctl.solve()
    ctl.config.solve.solve_limit.value = solve_limit

    if result.unsatisfiable:
        return None

    # upper bound: atoms remaining in the simplified base
    upper = [sym for _sig, ab in ctl.base.items() for sym, _ in ab.items()]

    # lower bound: start with syntactic facts
    lower = [
        sym
        for _sig, ab in ctl.base.items()
        for sym, atom in ab.items()
        if ctl.base.is_fact(atom.literal)
    ]

    # for remaining atoms, use cautious enumeration to find atoms true in all models
    if len(lower) < len(upper):
        enum_mode = ctl.config.solve.enum_mode.value
        ctl.config.solve.enum_mode.value = "cautious"
        cautious: set = set()
        with ctl.start_solve(yield_=True) as handle:
            for m in handle:
                cautious = {str(s) for s in m.symbols(atoms=True)}
            result2 = handle.get()
        ctl.config.solve.enum_mode.value = enum_mode

        if result2.unsatisfiable:
            return None

        lower_set = {str(s) for s in lower}
        for sym in upper:
            if str(sym) in cautious and str(sym) not in lower_set:
                lower.append(sym)

    return lower, upper
