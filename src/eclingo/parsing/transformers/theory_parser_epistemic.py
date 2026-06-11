# pylint: disable=no-member
# pylint: disable=no-name-in-module
# pylint: disable=import-error
from functools import singledispatch
from typing import Iterable, List, Optional, Set, Tuple

from clingo import ast
from clingo.ast import Sign
from clingo.core import Library
from clingo.symbol import Function as SymbolFunction
from clingo.symbol import SymbolType

from eclingo.clingox.ast import filter_body_literals, theory_term_to_literal

from . import ast_reify
from .parser_negations import (
    SnReplacementType,
    default_negation_auxiliary_rule_replacement,
    make_default_negation_auxiliar,
    make_strong_negations_auxiliar,
)

####################################################################################

# pylint: disable=unused-argument
# pylint: disable=invalid-name


def theory_atom_name(atom) -> Optional[str]:
    """
    Return the name of the given theory atom if it has no arguments and None
    otherwise.
    """
    name_term = atom.name
    if isinstance(name_term, ast.TermFunction):
        if name_term.pool and any(
            t.arguments for t in name_term.pool
        ):  # pragma: no cover
            return None  # pragma: no cover
        return name_term.name
    if (
        isinstance(name_term, ast.TermSymbolic)
        and name_term.symbol.type == SymbolType.Function
        and not name_term.symbol.arguments
    ):  # pragma: no cover
        return name_term.symbol.name  # pragma: no cover
    return None  # pragma: no cover


def is_epistemic_atom(atom, names=("k", "m")) -> bool:
    """
    Check whether the given node is an epistemic theory atom.
    """
    return isinstance(atom, ast.BodyTheoryAtom) and theory_atom_name(atom) in names


@singledispatch
def _apply_to_epistemic_atoms_elements(x, lib: Library, fun, update_fun):
    return x.transform(lib, _apply_to_epistemic_atoms_elements, lib, fun, update_fun)


@_apply_to_epistemic_atoms_elements.register
def _apply_to_epistemic_atoms_elements_atom(
    x: ast.BodyTheoryAtom, lib: Library, fun, update_fun
):
    if not is_epistemic_atom(x):
        return None  # pragma: no cover
    if update_fun is None:
        new_elements = [fun(lib, e) for e in x.elements]
    else:
        new_elements = []
        for element in x.elements:
            new_element, update = fun(lib, element)
            new_elements.append(new_element)
            update_fun(update)
    return x.update(lib, elements=new_elements)


def apply_to_epistemic_atoms_elements(lib: Library, stm, fun, update_fun=None):
    """
    Apply the given function to the elements of all epistemic theory atoms in
    the given statement.
    """
    return _apply_to_epistemic_atoms_elements(stm, lib, fun, update_fun) or stm


####################################################################################


@singledispatch
def _old_eclingo_negation(x, lib: Library):
    return x.transform(lib, _old_eclingo_negation, lib)


@_old_eclingo_negation.register
def _old_eclingo_negation_function(x: ast.TheoryTermFunction, lib: Library):
    if x.name != "~":
        return None
    return x.update(lib, name="not")


####################################################################################


def _theory_term_to_literal_adapter(lib: Library, element):
    assert len(element.tuple) == 1
    element = _old_eclingo_negation(element, lib) or element
    literal = theory_term_to_literal(lib, element.tuple[0])
    canonical_term = ast_reify.literal_to_theory_term(lib, literal)
    return element.update(lib, tuple=[canonical_term])


def parse_epistemic_literals_elements(lib: Library, rule):
    """
    Parse the theory terms of all epistemic atoms in the given statement.

    The terms of the elements are normalized into theory terms encoding
    literals (see
    `eclingo.parsing.transformers.ast_reify.literal_to_theory_term`).
    """
    return apply_to_epistemic_atoms_elements(lib, rule, _theory_term_to_literal_adapter)


####################################################################################


def make_strong_negation_auxiliar_in_epistemic_literals(
    lib: Library, stms: Iterable
) -> Tuple[List, SnReplacementType]:
    """
    Replaces strong negation by an auxiliary atom inside epistemic literals.
    Returns a pair:
    - the first element is the result of such replacement
    - the second element is a set of triples containing information about the replacement:
      * the first element is the name of the strogly negated atom
      * the second element is its arity
      * the third element is the name of the auxiliary atom that replaces it
    """
    replacement: SnReplacementType = set()
    new_stms = [
        apply_to_epistemic_atoms_elements(
            lib, stm, make_strong_negations_auxiliar, replacement.update
        )
        for stm in stms
    ]
    return (new_stms, replacement)


####################################################################################


def make_default_negation_auxiliar_in_epistemic_literals(
    lib: Library, stms: Iterable
) -> Tuple[List, Iterable]:
    """
    Replaces default negation by an auxiliary atom inside epistemic literals.
    Returns a pair:
    - the first element is the result of such replacement
    - the second element is a set of pairs containing information about the
      replacement:
      * the first element is the original literal replaced
      * the second element is the auxiliary literal replacing the negated literal
    """
    replacement: Set = set()
    new_stms = [
        apply_to_epistemic_atoms_elements(
            lib,
            stm,
            make_default_negation_auxiliar,
            lambda x: replacement.add(x) if x is not None else None,
        )
        for stm in stms
    ]
    return (new_stms, replacement)


####################################################################################


def build_guard(body):
    return list(
        filter_body_literals(
            body,
            theory_atom_predicate=lambda x: ast_reify.theory_term_sign(
                x.elements[0].tuple[0]
            )
            == Sign.NoSign,
        )
    )


####################################################################################


def replace_negations_by_auxiliary_atoms_in_epistemic_literals(
    lib: Library, stm, user_prefix: str = "u"
) -> Tuple[List, SnReplacementType]:
    """
    Replaces strong and default negations by an auxiliary atom inside epistemic literals of the rule.

    user_prefix is preapend to the name of all symbols to avoid collisions with the axiliary atoms.

    Returns a pair:
    - the first element is a list with the result of such replacement together
      with the rules relating the auxiliary atoms used to replace default
      negation with their original literals
    - the second element contains the information about the replacements
      corresponding to strong negation
    """
    if not isinstance(stm, ast.StatementRule):
        return ([stm], set())  # pragma: no cover

    body, sn_replacement = make_strong_negation_auxiliar_in_epistemic_literals(
        lib, stm.body
    )
    guard = build_guard(body)
    body, not_replacement = make_default_negation_auxiliar_in_epistemic_literals(
        lib, body
    )
    aux_rules = list(
        default_negation_auxiliary_rule_replacement(
            lib, stm.location, not_replacement, guard
        )
    )
    rule = stm.update(lib, body=list(body))
    return ([rule] + aux_rules, sn_replacement)


####################################################################################


class _EpistemicReplacementsContext:
    def __init__(self):
        self.replacements = []


@singledispatch
def _replace_epistemic_atoms(x, lib: Library, ctx: _EpistemicReplacementsContext):
    return x.transform(lib, _replace_epistemic_atoms, lib, ctx)


@_replace_epistemic_atoms.register
def _replace_epistemic_atom(
    x: ast.BodyTheoryAtom, lib: Library, ctx: _EpistemicReplacementsContext
):
    if not is_epistemic_atom(x):
        return None  # pragma: no cover
    name = theory_atom_name(x)
    assert name is not None
    nested_literal = theory_term_to_literal(lib, x.elements[0].tuple[0], False)
    aux_term = ast.TermFunction(
        lib,
        x.location,
        name,
        [ast.ArgumentTuple(lib, [nested_literal.atom])],
        False,
    )
    ctx.replacements.append((nested_literal, aux_term, x.location))
    return ast.BodySimpleLiteral(
        lib, ast.LiteralSymbolic(lib, x.location, x.sign, aux_term)
    )


def _replace_epistemic_literals_by_auxiliary_atoms(
    lib: Library, stm, k_prefix: str = "k"
) -> List:
    ctx = _EpistemicReplacementsContext()
    rule = _replace_epistemic_atoms(stm, lib, ctx) or stm
    rules = [rule]
    for nested_literal, aux_term, location in ctx.replacements:
        aux_literal = ast.LiteralSymbolic(lib, location, Sign.NoSign, aux_term)
        conditional_literal = ast.SetAggregateElement(lib, location, aux_literal, [])
        aux_rule_head = ast.HeadSetAggregate(
            lib, location, None, [conditional_literal], None
        )
        aux_rule = ast.StatementRule(
            lib,
            location,
            aux_rule_head,
            [ast.BodySimpleLiteral(lib, nested_literal)],
        )
        rules.append(aux_rule)
    return rules


def replace_epistemic_literals_by_auxiliary_atoms(
    lib: Library, stms: Iterable, k_prefix: str = "k"
) -> List:
    rules = []
    for stm in stms:
        rules.extend(_replace_epistemic_literals_by_auxiliary_atoms(lib, stm, k_prefix))
    return rules


####################################################################################


def _update_theory_atom_name(lib: Library, atom, name: str):
    """
    Return a copy of the given theory atom with the given name.
    """
    name_term = atom.name
    new_name_term: ast.Term
    if isinstance(name_term, ast.TermFunction):
        new_name_term = name_term.update(lib, name=name)
    else:  # pragma: no cover
        assert isinstance(name_term, ast.TermSymbolic)
        new_name_term = name_term.update(lib, symbol=SymbolFunction(lib, name))
    return atom.update(lib, name=new_name_term)


def _negate_sign(sign: Sign) -> Sign:
    if sign == Sign.Single:
        return Sign.Double
    return Sign.Single


@singledispatch
def _parse_m_literals(x, lib: Library):
    return x.transform(lib, _parse_m_literals, lib)


@_parse_m_literals.register
def _parse_m_literal(x: ast.BodyTheoryAtom, lib: Library):
    if not is_epistemic_atom(x, names=("m",)):
        return None
    new_term = ast_reify.negate_theory_term(lib, x.elements[0].tuple[0])
    new_elements = [x.elements[0].update(lib, tuple=[new_term])]
    x = x.update(lib, sign=_negate_sign(x.sign), elements=new_elements)
    return _update_theory_atom_name(lib, x, "k")


def parse_m_literals(lib: Library, stm):
    """
    Replace `&m{L}` atoms by `not &k{ not L }`.
    """
    return _parse_m_literals(stm, lib) or stm


####################################################################################


@singledispatch
def _double_negate_epistemic_literals(x, lib: Library):
    return x.transform(lib, _double_negate_epistemic_literals, lib)


@_double_negate_epistemic_literals.register
def _double_negate_epistemic_literal(x: ast.BodyTheoryAtom, lib: Library):
    if x.sign == Sign.NoSign and is_epistemic_atom(x, names=("k",)):
        return x.update(lib, sign=Sign.Double)
    return None


def double_negate_epistemic_listerals(lib: Library, stm):
    """
    Double negate non negated `&k` atoms (used for the g94 semantics).
    """
    return _double_negate_epistemic_literals(stm, lib) or stm


####################################################################################


@singledispatch
def _reify_epistemic_elements(x, lib: Library, name: str, reify_strong_negation: bool):
    return x.transform(lib, _reify_epistemic_elements, lib, name, reify_strong_negation)


@_reify_epistemic_elements.register
def _reify_epistemic_element(
    x: ast.BodyTheoryAtom, lib: Library, name: str, reify_strong_negation: bool
):
    if not is_epistemic_atom(x):
        return None  # pragma: no cover
    new_elements = []
    for element in x.elements:
        term = element.tuple[0]
        sign = ast_reify.theory_term_sign(term)
        atom_term = ast_reify.theory_term_strip_sign(term)
        if (
            not reify_strong_negation
            and isinstance(atom_term, ast.TheoryTermFunction)
            and atom_term.name == "-"
        ):  # pragma: no cover
            new_atom_term = atom_term.update(
                lib,
                arguments=[
                    ast.TheoryTermFunction(
                        lib, term.location, name, [atom_term.arguments[0]]
                    )
                ],
            )
        else:
            new_atom_term = ast.TheoryTermFunction(
                lib, term.location, name, [atom_term]
            )
        new_term = new_atom_term
        if sign != Sign.NoSign:
            new_term = ast.TheoryTermFunction(lib, term.location, "not", [new_term])
            if sign == Sign.Double:
                new_term = ast.TheoryTermFunction(lib, term.location, "not", [new_term])
        new_elements.append(element.update(lib, tuple=[new_term]))
    return x.update(lib, elements=new_elements)


def reify_epistemic_elements(
    lib: Library, stm, name: str, reify_strong_negation: bool = True
):
    """
    Reify the atoms inside the elements of epistemic theory atoms with the
    given name.

    With clingo 5, this was done by
    `eclingo.clingox.ast.reify_symbolic_atoms`, which also visited the
    literals embedded in theory atom elements.
    """
    return _reify_epistemic_elements(stm, lib, name, reify_strong_negation) or stm
