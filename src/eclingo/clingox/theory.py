'''
This module provides functions to work with clingo's theories.

Example
-------

```python-repl
>>> from clingo.core import Library
>>> from clingo.control import Control
>>> from eclingo.clingox.theory import evaluate
>>>
>>> prg = """\
... #theory test {
...     term {
...         -  : 3, unary;
...         ** : 2, binary, right;
...         *  : 1, binary, left;
...         +  : 0, binary, left;
...         -  : 0, binary, left
...     };
...     &eval/0 : term, head
... }.
...
... &eval{ 3**5-201 }.
... """
>>>
>>> lib = Library()
>>> ctl = Control(lib)
>>> ctl.parse_string(prg)
>>> ctl.ground()
>>>
>>> atom = next(iter(ctl.base.theory))
>>> print(evaluate(lib, atom.elements[0].tuple[0]))
42
```
'''

from typing import Any

from clingo.base import TheoryTermType
from clingo.core import Library
from clingo.symbol import Function, Number, String, Symbol, SymbolType, Tuple_

__all__ = [
    "evaluate",
    "invert_symbol",
    "is_clingo_operator",
    "is_operator",
    "require_number",
    "TermEvaluator",
]
__pdoc__ = {}


def require_number(x: Symbol) -> int:
    """
    Requires the argument to be a number returning the given number or throwing
    a type error.
    """
    if x.type == SymbolType.Number:
        return x.number

    raise TypeError("number exepected")


def invert_symbol(lib: Library, sym: Symbol) -> Symbol:
    """
    Inverts the given symbol.

    Parameters
    ----------
    lib
        The library storing symbols.
    sym
        The symbol to invert.

    Returns
    -------
    The inverted symbol.
    """
    if sym.type == SymbolType.Number:
        return Number(lib, -sym.number)

    if sym.type == SymbolType.Function and sym.name:
        return Function(lib, sym.name, sym.arguments, not sym.is_positive)

    raise TypeError("cannot invert symbol")


def is_clingo_operator(op: str):
    """
    Return true if the given string is a operator as supported by the
    Evaluator.
    """
    return op in ("+", "-", "*", "\\", "/")


def is_operator(op: str):
    """
    Return true if the given string is an operator.

    Parameters
    ----------
    op
        The operator name to check.

    Returns
    -------
    Whether the string is an operator name.
    """
    return (op and op[0] in "/!<=>+-*\\?&@|:;~^.") or (op == "not")


def _unquote(s: str) -> str:
    """
    Remove quotes in the same fashion as clingo.
    """
    ret = []
    slash = False
    for c in s:
        if slash:
            if c == "n":
                ret.append("\n")
            else:
                assert c in '\\"'
                ret.append(c)
            slash = False
        elif c == "\\":
            slash = True
        else:
            ret.append(c)

    return "".join(ret)


class TermEvaluator:
    """
    This class provides a call operator to evaluate the operators in a theory
    term in the same fashion as clingo evaluates its arithmetic functions.

    This class can easily be extended for additional binary and unary
    operators.
    """

    def __init__(self, lib: Library):
        self._lib = lib

    def evaluate_binary(self, op: str, lhs: Symbol, rhs: Symbol) -> Symbol:
        """
        Evaluate binary terms as clingo would.

        Parameters
        ----------
        op
            The operator name.
        lhs
            The left-hand-side argument.
        lhs
            The right-hand-side argument.

        Returns
        -------
        The evaluated operator in form of a symbol.
        """
        if op == "+":
            return Number(self._lib, require_number(lhs) + require_number(rhs))
        if op == "-":
            return Number(self._lib, require_number(lhs) - require_number(rhs))
        if op == "*":
            return Number(self._lib, require_number(lhs) * require_number(rhs))
        if op == "**":
            return Number(self._lib, require_number(lhs) ** require_number(rhs))
        if op == "\\":
            if rhs == Number(self._lib, 0):
                raise ZeroDivisionError("division by zero")
            return Number(self._lib, require_number(lhs) % require_number(rhs))
        if op == "/":
            if rhs == Number(self._lib, 0):
                raise ZeroDivisionError("division by zero")
            return Number(self._lib, require_number(lhs) // require_number(rhs))

        if is_operator(op):
            raise AttributeError("unexpected operator")

        return Function(self._lib, op, [lhs, rhs])

    def evaluate_unary(self, op: str, arg: Symbol):
        """
        Evaluate unary terms as clingo would.

        Parameters
        ----------
        op
            The operator name.
        arg
            The argument of the operator.

        Returns
        -------
        The evaluated operator in form of a symbol.
        """
        if op == "+":
            return Number(self._lib, require_number(arg))
        if op == "-":
            return invert_symbol(self._lib, arg)
        if is_operator(op):
            raise AttributeError("unexpected operator")

        return Function(self._lib, op, [arg])

    def __call__(self, term: Any):
        """
        Evaluate the given term.

        Parameters
        ----------
        term
            The term to evaluate.

        Returns
        -------
        The evaluated term in form of a symbol.
        """
        # tuples
        if term.type == TheoryTermType.Tuple:
            return Tuple_(self._lib, [self(x) for x in term.arguments])

        # functions and arithmetic operations
        if term.type == TheoryTermType.Function:
            arguments = [self(x) for x in term.arguments]
            # binary operations
            if len(arguments) == 2:
                return self.evaluate_binary(term.name, *arguments)

            # unary operations
            if len(arguments) == 1:
                return self.evaluate_unary(term.name, *arguments)

            # functions
            return Function(self._lib, term.name, arguments)

        # constants
        if term.type == TheoryTermType.Symbol:
            if term.name.startswith('"') and term.name.endswith('"'):
                return String(self._lib, _unquote(term.name[1:-1]))

            return Function(self._lib, term.name)

        # numbers
        if term.type == TheoryTermType.Number:
            return Number(self._lib, term.number)

        raise RuntimeError("cannot evaluate term")


__pdoc__["TermEvaluator.__call__"] = True


def evaluate(lib: Library, term: Any) -> Symbol:
    """
    Evaluates the operators in a theory term in the same fashion as clingo
    evaluates its arithmetic functions.

    We use `Any` as a type hint here to allow for evaluating terms that are
    duck typing copmatible with clingo's `TheoryTerm` class.

    Parameters
    ----------
    lib
        The library storing symbols.
    term
        The theory term to evaluate.

    Returns
    -------
    The evaluated term in form of a symbol.
    """
    return TermEvaluator(lib)(term)
