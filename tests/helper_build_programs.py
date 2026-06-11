from typing import Iterable, List, Optional, Tuple, Union

from clingo import ast
from clingo.core import Library
from clingo.symbol import Function, Symbol

from eclingo.clingox.testing.ast import parse_term
from eclingo.solver.candidate import Assumptions, Candidate


def ast_to_symbol(lib: Library, x) -> Symbol:
    """
    Transforms a term AST into the corresponding symbol.
    """
    if isinstance(x, ast.TermSymbolic):
        return x.symbol
    if isinstance(x, ast.TermUnaryOperation):
        a = ast_to_symbol(lib, x.right)
        return Function(lib, a.name, a.arguments, not a.is_positive)
    assert isinstance(x, ast.TermFunction)
    arguments = x.pool[0].arguments if x.pool else []
    return Function(lib, x.name, [ast_to_symbol(lib, a) for a in arguments], True)


def build_objective_atom(lib: Library, atom: Symbol) -> Symbol:
    if atom.name == "not1":
        return Function(lib, "not1", [Function(lib, "u", [atom.arguments[0]])])
    return Function(lib, "u", [atom])


def build_subjective_atom(lib: Library, atom: Symbol) -> Symbol:
    atom = build_objective_atom(lib, atom.arguments[0])
    return Function(lib, "k", [atom])


def build_atom(lib: Library, atom: Symbol) -> Symbol:
    if atom.name == "k":
        return build_subjective_atom(lib, atom)
    return build_objective_atom(lib, atom)


def build_candidate_without_assumptions(
    lib: Library, candidate: str, assumptions=None
) -> Candidate:
    candidate = candidate.strip()
    if not candidate:
        return Candidate(pos=[], neg=[])
    atoms = candidate.split(" ")
    atoms = [atom.strip() for atom in atoms if atom]
    atoms = [parse_term(lib, atom) for atom in atoms]
    atoms = [ast_to_symbol(lib, atom) for atom in atoms]
    pos = [build_subjective_atom(lib, atom) for atom in atoms if atom.name != "no"]
    neg = [
        build_subjective_atom(lib, atom.arguments[0])
        for atom in atoms
        if atom.name == "no"
    ]
    if assumptions is not None:
        return Candidate(pos=pos, neg=neg, extra_assumptions=assumptions)
    return Candidate(pos=pos, neg=neg)


def build_assumptions(lib: Library, assumptions: str) -> Assumptions:
    if not assumptions:
        return Assumptions(pos=[], neg=[])
    atoms = assumptions.split(" ")
    atoms = [ast_to_symbol(lib, parse_term(lib, atom)) for atom in atoms]
    pos = [build_objective_atom(lib, atom) for atom in atoms if atom.name != "no"]
    neg = [
        build_objective_atom(lib, atom.arguments[0])
        for atom in atoms
        if atom.name == "no"
    ]
    return Assumptions(pos=pos, neg=neg)


def build_candidate(
    lib: Library, candidate: Union[str, Tuple[str, str]]
) -> Optional[Candidate]:
    if isinstance(candidate, str):
        return build_candidate_without_assumptions(lib, candidate)
    assumptions = build_assumptions(lib, candidate[1])
    return build_candidate_without_assumptions(lib, candidate[0], assumptions)


def build_candidates(
    lib: Library, candidates: Optional[Iterable[str]]
) -> Optional[List[Candidate]]:
    if candidates is None:
        return None
    if isinstance(candidates, str) or isinstance(candidates, tuple):
        candidates = [candidates]
    return [build_candidate(lib, candidate) for candidate in candidates]
