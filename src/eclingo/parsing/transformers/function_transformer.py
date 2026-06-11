"""Module providing an AST function Trasnformer"""

from clingo.core import Library

from eclingo.clingox.ast import normalize_symbolic_terms


def rule_to_symbolic_term_adapter(lib: Library, x):
    """
    Replaces all occurrences of objects of the class clingo.symbol.Symbol of
    type function in x by the corresponding object of the class
    clingo.ast.TermFunction.
    """
    return normalize_symbolic_terms(lib, x)
