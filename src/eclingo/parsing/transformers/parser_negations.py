"""
Module to replace strong and default negations by auxiliary atoms.
"""

from typing import Iterable, List, Optional, Set, Tuple

from clingo import ast
from clingo.core import Library

from eclingo.clingox.ast import theory_term_to_literal

from . import ast_reify

# pylint: disable=all

####################################################################################


class StrongNegationReplacement(Set[Tuple[str, int, str]]):
    pass


SnReplacementType = Set[Tuple[str, int, str]]


def simplify_strong_negations(stm):
    """
    Removes duplicate occurrences of strong negation and provides
    an equivalent formula.
    """
    return stm  # pragma: no cover


def make_strong_negations_auxiliar(
    lib: Library, stm
) -> Tuple[object, SnReplacementType]:
    """
    Replaces strong negation by an auxiliary atom.
    Returns a pair:
    - the first element is the result of such replacement
    - the second element is a set of triples containing information about the replacement:
      * the first element is the name of the strogly negated atom
      * the second element is its arity
      * the third element is the name of the auxiliary atom that replaces it
    """
    return (stm, set())


####################################################################################


NotReplacementType = Optional[Tuple[object, object]]


def make_default_negation_auxiliar(
    lib: Library, stm
) -> Tuple[object, NotReplacementType]:
    """
    Replaces default negation by an auxiliary atom.

    The statement is a theory atom element whose unique term encodes a literal
    as a theory term (see
    `eclingo.parsing.transformers.ast_reify.literal_to_theory_term`).

    Returns a pair:
    - the first element is the result of such replacement
    - the second element is a pair containing information about the replacement:
      * the first element is the original literal replaced
      * the second element is the auxiliary literal replacing the negated literal
    """
    assert isinstance(stm, ast.TheoryAtomElement)
    assert len(stm.tuple) == 1
    term = stm.tuple[0]
    sign = ast_reify.theory_term_sign(term)

    if sign == ast.Sign.NoSign:
        return (stm, None)

    atom_term = ast_reify.theory_term_strip_sign(term)
    aux_name = "not1" if sign == ast.Sign.Single else "not2"
    aux_term = ast.TheoryTermFunction(lib, term.location, aux_name, [atom_term])

    new_stm = stm.update(lib, tuple=[aux_term])

    original_literal = theory_term_to_literal(lib, term, False)
    aux_literal = theory_term_to_literal(lib, aux_term, False)

    return (new_stm, (original_literal, aux_literal))


def default_negation_auxiliary_rule(
    lib: Library, location, aux_literal, original_literal, gard: List
):
    """
    Returns a rule of the form:
        aux_literal :- gard, original_literal
    """
    rule_body = list(gard)
    rule_body.append(ast.BodySimpleLiteral(lib, original_literal))
    return ast.StatementRule(
        lib, location, ast.HeadSimpleLiteral(lib, aux_literal), rule_body
    )


def default_negation_auxiliary_rule_replacement(
    lib: Library, location, replacement: Iterable, gard: List
):
    """
    Returns a rule of the form:
        aux_literal :- gard, original_literal
    for each tuple in replacement
    """
    for original_literal, aux_literal in replacement:  # type: ignore
        yield default_negation_auxiliary_rule(
            lib, location, aux_literal, original_literal, gard
        )
