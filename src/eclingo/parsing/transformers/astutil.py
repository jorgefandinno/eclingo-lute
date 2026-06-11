from typing import List

from clingo import ast
from clingo.core import Library, Location
from clingo.symbol import Function

# pylint: disable=all


def atom(
    lib: Library, location: Location, positive: bool, name: str, arguments: List
) -> ast.Term:
    """
    Helper function to create an atom.

    With clingo 6, symbolic atoms are plain terms, so this function returns a
    term.

    Arguments:
    lib      --  Library to use.
    location --  Location to use.
    positive --  Classical sign of the atom.
    name     --  The name of the atom.
    arguments -- The arguments of the atom.
    """
    ret: ast.Term
    if arguments:
        ret = ast.TermFunction(
            lib, location, name, [ast.ArgumentTuple(lib, arguments)], False
        )
    else:
        ret = ast.TermSymbolic(lib, location, Function(lib, name))
    if not positive:
        ret = ast.TermUnaryOperation(lib, location, ast.UnaryOperator.Minus, ret)
    return ret


def negate_literal(lib: Library, literal: ast.Literal) -> ast.Literal:
    """
    Negates a literal.

    Arguments:
    lib     -- Library to use.
    literal -- The literal to negate.
    """
    if literal.sign == ast.Sign.Single:
        sign = ast.Sign.Double
    else:
        sign = ast.Sign.Single
    return literal.update(lib, sign=sign)
