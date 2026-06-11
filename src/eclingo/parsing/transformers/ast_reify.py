"""
This module contains functions for reififcation of `AST` objects
"""

from clingo import ast
from clingo.ast import Sign
from clingo.core import Library
from clingo.symbol import Function

from eclingo.clingox.ast import theory_term_to_literal, theory_term_to_term


def _positive_symbolic_literal_to_term(lib: Library, x):
    """
    Helper function to ensure proper treatment of clingo.symbol.Function and
    ast.TermFunction
    """
    if not isinstance(x, ast.TermFunction) or x.external:
        return x
    if x.pool and any(argument_tuple.arguments for argument_tuple in x.pool):
        return x
    return ast.TermSymbolic(lib, x.location, Function(lib, x.name))  # pragma: no cover


def theory_atom_to_term(lib: Library, x):
    """
    Convert the given theory atom into an ast.TermFunction
    - `x.name` -> subjective literal term
    - `x.elements[0]` -> AST of type TheoryAtomElement that is
    assumed as one TheoryAtomElement with unique term and empty condition

    Parameters
    ----------
    lib
        The library storing symbols.
    x
        An `AST` that represents a theory atom to be converted into a term.

    Returns
    -------
    An `AST` that represnts the reified Theory Atom Element as a term.
    """
    if isinstance(x.elements[0].tuple[0], ast.TheoryTermUnparsed):
        literal = theory_term_to_literal(lib, x.elements[0].tuple[0])
        term = symbolic_literal_to_term(lib, literal)

    else:
        term = x.elements[0].tuple[0]
        term = theory_term_to_term(lib, term, False)

    return ast.TermFunction(
        lib, x.location, str(x.name), [ast.ArgumentTuple(lib, [term])], False
    )


def symbolic_literal_to_term(
    lib: Library,
    lit,
    negation_name: str = "not1",
    double_negation_name: str = "not2",
):
    """
    Convert the given literal into a clingo term according to the following rules:
    - `atom => atom`
    - `not atom => not1(atom)`
    - `not not atom => not2(atom)`

    Parameters
    ----------
    lib
        The library storing symbols.
    lit
        An `AST` that represents a literal.
    negation_name
        A string to be used to represent negation.
    double_negation_name
        A string to be used to represent double negation.

    Returns
    -------
    An `AST` that represnts the reified literal as a term.
    """
    if isinstance(lit, ast.BodySimpleLiteral):
        lit = lit.literal  # pragma: no cover
    if not isinstance(lit, ast.LiteralSymbolic):
        return lit
    symbol = lit.atom

    if isinstance(symbol, ast.TermUnaryOperation):
        symbol = symbol.right

    symbol = _positive_symbolic_literal_to_term(lib, symbol)

    if isinstance(lit.atom, ast.TermUnaryOperation):
        symbol = ast.TermUnaryOperation(
            lib, lit.location, ast.UnaryOperator.Minus, symbol
        )

    if lit.sign == Sign.NoSign:
        return symbol

    sign_name = negation_name if lit.sign == Sign.Single else double_negation_name

    return ast.TermFunction(
        lib, lit.location, sign_name, [ast.ArgumentTuple(lib, [symbol])], False
    )


def term_to_theory_term(lib: Library, x):
    """
    Convert a plain clingo term into a theory term.

    This is the converse of `eclingo.clingox.ast.theory_term_to_term` for the
    terms that may occur in epistemic literals.
    """
    if isinstance(x, ast.TermSymbolic):
        return ast.TheoryTermSymbolic(lib, x.location, x.symbol)
    if isinstance(x, ast.TermVariable):
        return ast.TheoryTermVariable(lib, x.location, x.name)
    if isinstance(x, ast.TermUnaryOperation):
        return ast.TheoryTermFunction(
            lib, x.location, "-", [term_to_theory_term(lib, x.right)]
        )
    if isinstance(x, ast.TermFunction):
        arguments = x.pool[0].arguments if x.pool else []
        return ast.TheoryTermFunction(
            lib,
            x.location,
            x.name,
            [term_to_theory_term(lib, a) for a in arguments],
        )
    if isinstance(x, ast.TermBinaryOperation):  # pragma: no cover
        operators = {
            ast.BinaryOperator.Plus: "+",
            ast.BinaryOperator.Minus: "-",
            ast.BinaryOperator.Multiplication: "*",
            ast.BinaryOperator.Division: "/",
            ast.BinaryOperator.Modulo: "\\",
            ast.BinaryOperator.Power: "**",
            ast.BinaryOperator.And: "&",
            ast.BinaryOperator.Or: "?",
            ast.BinaryOperator.Xor: "^",
        }
        return ast.TheoryTermFunction(
            lib,
            x.location,
            operators[x.operator_type],
            [term_to_theory_term(lib, x.left), term_to_theory_term(lib, x.right)],
        )
    raise RuntimeError(f"cannot convert term to theory term: {x}")  # pragma: no cover


def literal_to_theory_term(lib: Library, lit):
    """
    Convert a symbolic literal into a theory term.

    The default negation signs of the literal are encoded using the unary
    `not` theory operator. With clingo 5, literals were stored directly inside
    theory atom elements, which is not possible with clingo 6 because theory
    atom elements can only contain theory terms.
    """
    assert isinstance(lit, ast.LiteralSymbolic)
    term = term_to_theory_term(lib, lit.atom)
    if lit.sign != Sign.NoSign:
        term = ast.TheoryTermFunction(lib, lit.location, "not", [term])
        if lit.sign == Sign.Double:
            term = ast.TheoryTermFunction(lib, lit.location, "not", [term])
    return term


def theory_term_sign(x) -> Sign:
    """
    Return the default negation sign encoded in the given theory term.
    """
    if isinstance(x, ast.TheoryTermFunction) and x.name == "not":
        inner = x.arguments[0]
        if isinstance(inner, ast.TheoryTermFunction) and inner.name == "not":
            return Sign.Double
        return Sign.Single
    return Sign.NoSign


def theory_term_strip_sign(x):
    """
    Remove the default negation signs encoded in the given theory term.
    """
    while isinstance(x, ast.TheoryTermFunction) and x.name == "not":
        x = x.arguments[0]
    return x


def negate_theory_term(lib: Library, x):
    """
    Negate the default negation sign encoded in the given theory term.

    The sign is negated in the same way as
    `eclingo.parsing.transformers.astutil.negate_literal`.
    """
    sign = theory_term_sign(x)
    atom = theory_term_strip_sign(x)
    term = ast.TheoryTermFunction(lib, x.location, "not", [atom])
    if sign == Sign.Single:
        term = ast.TheoryTermFunction(lib, x.location, "not", [term])
    return term


def reification_program_to_str(program):  # pragma: no cover
    """
    Helper function to convert a reified fact program into a string.
    """
    prg_string = []
    for e1 in program:
        prg_string.append(str(e1))

    program = ". ".join(prg_string)
    program = program + "."
    return program


def program_to_str(program):
    """
    Helper function to parse a given program into string.
    """
    prg_string = []
    for e1 in program:
        prg_string.append(str(e1))

    program = " ".join(prg_string)
    return program
