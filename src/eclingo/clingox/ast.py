'''
This module provides highlevel functions to work with clingo's AST.

Theory Parsing Examples
-----------------------

The following examples shows how to construct and use a theory parser:

```python-repl
>>> from clingo.ast import TheoryAtomType, parse_string
>>> from eclingo.clingox.ast import Arity, Associativity, TheoryParser
>>>
>>> terms = {"term":
...     {("-", Arity.Unary): (3, Associativity.NoAssociativity),
...      ("**", Arity.Binary): (2, Associativity.Right),
...      ("*", Arity.Binary): (1, Associativity.Left),
...      ("+", Arity.Binary): (0, Associativity.Left),
...      ("-", Arity.Binary): (0, Associativity.Left)}}
>>> atoms = {("eval", 0): (TheoryAtomType.Head, "term", None)}
>>> parser = TheoryParser(terms, atoms)
>>>
>>> parse_string('&eval{ -1 * 2 + 3 }.', print)
#program base.
&eval { (- 1 * 2 + 3) }.
>>> parse_string('&eval{ -1 * 2 + 3 }.', lambda x: print(parser(x)))
#program base.
&eval { +(*(-(1),2),3) }.
```

The same parser can also be constructed from a theory:

```python-repl
>>> from clingo.ast import parse_string, ASTType
>>> from eclingo.clingox.ast import theory_parser_from_definition
>>>
>>> theory = """\\
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
... """
>>>
>>> parsers = []
>>> def extract(stm):
...     if stm.ast_type == ASTType.TheoryDefinition:
...         parsers.append(theory_parser_from_definition(stm))
...
>>> parse_string(theory, extract)
>>> parse_string('&eval{ -1 * 2 + 3 }.', print)
#program base.
&eval { (- 1 * 2 + 3) }.
>>> parse_string('&eval{ -1 * 2 + 3 }.', lambda x: print(parsers[0](x)))
#program base.
&eval { +(*(-(1),2),3) }.
```

AST to dict Conversion Example
------------------------------

Another interesting feature is to convert ASTs to YAML:

```python-repl
>>> from json import dumps
>>> from clingo.ast import parse_string
>>> from eclingo.clingox.ast import ast_to_dict
>>>
>>> prg = []
>>> parse_string('a.', lambda x: prg.append(ast_to_dict(x)))
>>>
>>> print(dumps(prg, indent=2))
[
  {
    "ast_type": "Program",
    "location": "<string>:1:1",
    "name": "base",
    "parameters": []
  },
  {
    "ast_type": "Rule",
    "location": "<string>:1:1-3",
    "head": {
      "ast_type": "Literal",
      "location": "<string>:1:1-2",
      "sign": 0,
      "atom": {
        "ast_type": "SymbolicAtom",
        "symbol": {
          "ast_type": "Function",
          "location": "<string>:1:1-2",
          "name": "a",
          "arguments": [],
          "external": 0
        }
      }
    },
    "body": []
  }
]
```
'''

from enum import Enum, auto
from functools import lru_cache, partial, singledispatch
from re import fullmatch
from typing import (
    Any,
    Callable,
    Container,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
    cast,
)

import clingo
from clingo import ast
from clingo.ast import (
    LiteralSymbolic,
    Relation,
    Sign,
    TermSymbolic,
    TermUnaryOperation,
    TheoryAtomType,
    TheoryOperatorType,
    UnaryOperator,
    parse_string,
)
from clingo.core import Library, Location, Position
from clingo.symbol import Symbol, parse_term as parse_symbol

_DEFAULT_LIB = Library()

if not hasattr(Sign, "Negation"):
    Sign.Negation = Sign.Single
    Sign.DoubleNegation = Sign.Double


def _get_lib(lib: Optional[Library] = None) -> Library:
    return _DEFAULT_LIB if lib is None else lib


def Function(
    location: Location,
    name: str,
    arguments: Sequence["AST"],
    external: bool = False,
    lib: Optional[Library] = None,
):
    lib = _get_lib(lib)
    return ast.TermFunction(lib, location, name, [ast.ArgumentTuple(lib, list(arguments))], external)


def SymbolicTerm(
    location: Location, symbol: Symbol, lib: Optional[Library] = None
):
    return ast.TermSymbolic(_get_lib(lib), location, symbol)


def Variable(location: Location, name: str, lib: Optional[Library] = None):
    return ast.TermVariable(_get_lib(lib), location, name)


def UnaryOperation(
    location: Location,
    operator_type: ast.UnaryOperator,
    argument: "AST",
    lib: Optional[Library] = None,
):
    return ast.TermUnaryOperation(_get_lib(lib), location, operator_type, argument)


def BinaryOperation(
    location: Location,
    operator_type: ast.BinaryOperator,
    left: "AST",
    right: "AST",
    lib: Optional[Library] = None,
):
    return ast.TermBinaryOperation(_get_lib(lib), location, left, operator_type, right)


def TheoryFunction(
    location: Location, name: str, arguments: Sequence["AST"], lib: Optional[Library] = None
):
    return ast.TheoryTermFunction(_get_lib(lib), location, name, list(arguments))


ASTSequence = list
StrSequence = list


class ASTType(Enum):
    Program = "Program"
    Rule = "Rule"
    Literal = "Literal"
    SymbolicAtom = "SymbolicAtom"
    SymbolicTerm = "SymbolicTerm"
    Variable = "Variable"
    Function = "Function"
    UnaryOperation = "UnaryOperation"
    BinaryOperation = "BinaryOperation"
    Aggregate = "Aggregate"
    BodyAggregate = "BodyAggregate"
    TheoryAtom = "TheoryAtom"
    ConditionalLiteral = "ConditionalLiteral"
    TheoryDefinition = "TheoryDefinition"
    TheoryFunction = "TheoryFunction"
    TheorySequence = "TheorySequence"
    TheoryUnparsedTerm = "TheoryUnparsedTerm"

    def __str__(self) -> str:
        return f"ASTType.{self.name}"


class Transformer:
    def __init__(self, lib: Optional[Library] = None):
        self._lib = _get_lib(lib)

    def __call__(self, x):
        lib = getattr(self, "_lib", _DEFAULT_LIB)
        handler = getattr(self, f"visit_{type(x).__name__}", None)
        if handler is None and hasattr(x, "ast_type"):
            handler = getattr(self, f"visit_{x.ast_type.name}", None)
        if handler is not None:
            return handler(x)
        transformed = x.transform(lib, self)
        return x if transformed is None else transformed

    def visit(self, x):
        return self(x)

    def visit_sequence(self, xs):
        ret = []
        changed = False
        for x in xs:
            new_x = self(x)
            changed = changed or new_x is not x
            ret.append(new_x)
        return ret if changed else xs


def _set_ast_type(cls, ast_type: ASTType) -> None:
    cls.ast_type = property(lambda self, _ast_type=ast_type: _ast_type)


for _cls, _ast_type in (
    (ast.StatementProgram, ASTType.Program),
    (ast.StatementRule, ASTType.Rule),
    (ast.StatementTheory, ASTType.TheoryDefinition),
    (ast.HeadSimpleLiteral, ASTType.Literal),
    (ast.BodySimpleLiteral, ASTType.Literal),
    (ast.LiteralSymbolic, ASTType.Literal),
    (ast.LiteralBoolean, ASTType.Literal),
    (ast.LiteralComparison, ASTType.Literal),
    (ast.TermFunction, ASTType.Function),
    (ast.TermSymbolic, ASTType.SymbolicTerm),
    (ast.TermVariable, ASTType.Variable),
    (ast.TermUnaryOperation, ASTType.UnaryOperation),
    (ast.TermBinaryOperation, ASTType.BinaryOperation),
    (ast.BodyAggregate, ASTType.BodyAggregate),
    (ast.BodyTheoryAtom, ASTType.TheoryAtom),
    (ast.HeadTheoryAtom, ASTType.TheoryAtom),
    (ast.BodyConditionalLiteral, ASTType.ConditionalLiteral),
    (ast.TheoryTermFunction, ASTType.TheoryFunction),
    (ast.TheoryTermTuple, ASTType.TheorySequence),
    (ast.TheoryTermUnparsed, ASTType.TheoryUnparsedTerm),
    (ast.TheoryTermSymbolic, ASTType.SymbolicTerm),
    (ast.TheoryTermVariable, ASTType.Variable),
):
    _set_ast_type(_cls, _ast_type)

AST = (
    ast.Statement
    | ast.Term
    | ast.Literal
    | ast.ArgumentTuple
    | ast.BodyLiteral
    | ast.BodyAggregateElement
    | ast.Edge
    | ast.HeadAggregateElement
    | ast.HeadConditionalLiteral
    | ast.HeadLiteral
    | ast.LeftGuard
    | ast.OptimizeElement
    | ast.OptimizeTuple
    | ast.ProgramPart
    | ast.Projection
    | ast.RightGuard
    | ast.SetAggregateElement
    | ast.TheoryAtomDefinition
    | ast.TheoryAtomElement
    | ast.TheoryGuardDefinition
    | ast.TheoryOperatorDefinition
    | ast.TheoryRightGuard
    | ast.TheoryTermDefinition
    | ast.TheoryTermFunction
    | ast.TheoryTermSymbolic
    | ast.TheoryTermTuple
    | ast.TheoryTermUnparsed
    | ast.TheoryTermVariable
    | ast.UnparsedElement
)

from .theory import is_operator

__all__ = [
    "Arity",
    "Associativity",
    "ASTPredicate",
    "AtomTable",
    "OperatorTable",
    "TheoryParser",
    "TheoryTermParser",
    "TheoryUnparsedTermParser",
    "ast_to_dict",
    "clingo_literal_parser",
    "clingo_term_parser",
    "dict_to_ast",
    "filter_body_literals",
    "location_to_str",
    "negate_sign",
    "normalize_symbolic_terms",
    "parse_theory",
    "partition_body_literals",
    "prefix_symbolic_atoms",
    "reify_symbolic_atoms",
    "rename_symbolic_atoms",
    "str_to_location",
    "theory_parser_from_definition",
    "theory_term_to_literal",
    "theory_term_to_term",
]


class Arity(Enum):
    """
    Enumeration of operator arities.
    """

    # pylint:disable=invalid-name
    Unary = 1
    Binary = 2


class Associativity(Enum):
    """
    Enumeration of operator associativities.
    """

    # pylint: disable=invalid-name
    Left = auto()
    Right = auto()
    NoAssociativity = auto()


def _s(m, a: str, b: str):
    """
    Select the match group b if not None and group a otherwise.
    """
    return m[a] if m[b] is None else m[b]


def _quote(s: str) -> str:
    return s.replace("\\", "\\\\").replace(":", "\\:")


def _unquote(s: str) -> str:
    return s.replace("\\:", ":").replace("\\\\", "\\")


def location_to_str(loc: Location) -> str:
    """
    This function transfroms a loctation object into a readable string.

    Colons in the location will be quoted ensuring that the resulting is
    parsable using `str_to_location`.

    Parameters
    ----------
    loc
        The location to transform.

    Returns
    -------
    The string representation of the given location.
    """
    begin, end = loc.begin, loc.end
    bf, ef = _quote(begin.file), _quote(end.file)
    ret = f"{bf}:{begin.line}:{begin.column}"
    dash, eq = True, bf == ef
    if not eq:
        ret += f"{'-' if dash else ':'}{ef}"
        dash = False
    eq = eq and begin.line == end.line
    if not eq:
        ret += f"{'-' if dash else ':'}{end.line}"
        dash = False
    eq = eq and begin.column == end.column
    if not eq:
        ret += f"{'-' if dash else ':'}{end.column}"
        dash = False
    return ret


def str_to_location(loc: str) -> Location:
    """
    This function parses a location from its string representation.

    Parameters
    ----------
    loc
        The string to parse.

    Returns
    -------
    The parsed location.

    See Also
    --------
    location_to_str
    """
    m = fullmatch(
        r"(?P<bf>([^\\:]|\\\\|\\:)*):(?P<bl>[0-9]*):(?P<bc>[0-9]+)"
        r"(-(((?P<ef>([^\\:]|\\\\|\\:)*):)?(?P<el>[0-9]*):)?(?P<ec>[0-9]+))?",
        loc,
    )
    if not m:
        raise RuntimeError("could not parse location")
    end = Position(
        _DEFAULT_LIB,
        _unquote(_s(m, "bf", "ef")),
        int(_s(m, "bl", "el")),
        int(_s(m, "bc", "ec")),
    )
    begin = Position(_DEFAULT_LIB, _unquote(m["bf"]), int(m["bl"]), int(m["bc"]))
    return Location(begin, end)


OperatorTable = Mapping[Tuple[str, Arity], Tuple[int, Associativity]]
AtomTable = Mapping[
    Tuple[str, int], Tuple[TheoryAtomType, str, Optional[Tuple[List[str], str]]]
]


class TheoryUnparsedTermParser:
    """
    Parser for unparsed theory terms in clingo's AST that works like the
    inbuilt one.

    Note that associativity for unary operators is ignored and binary
    operators must use either `Associativity.Left` or `Associativity.Right`.

    Parameters
    ----------
    table
        Mapping of operator/arity pairs to priority/associativity pairs.
    """

    _stack: List[Tuple[str, Arity]]
    _terms: List[AST]
    _table: OperatorTable

    def __init__(self, table: OperatorTable):
        self._stack = []
        self._terms = []
        self._table = table

    def _priority_and_associativity(self, operator: str) -> Tuple[int, Associativity]:
        """
        Get priority and associativity of the given binary operator.
        """
        return self._table[(operator, Arity.Binary)]

    def _priority(self, operator: str, arity: Arity) -> int:
        """
        Get priority of the given unary or binary operator.
        """
        return self._table[(operator, arity)][0]

    def _check(self, operator: str) -> bool:
        """
        Returns true if the stack has to be reduced because of the precedence
        of the given binary operator is lower than the preceeding operator on
        the stack.
        """
        if not self._stack:
            return False
        priority, associativity = self._priority_and_associativity(operator)
        previous_priority = self._priority(*self._stack[-1])
        return previous_priority > priority or (
            previous_priority == priority and associativity == Associativity.Left
        )

    def _reduce(self) -> None:
        """
        Combines the last unary or binary term on the stack.
        """
        b = self._terms.pop()
        operator, arity = self._stack.pop()
        if arity == Arity.Unary:
            self._terms.append(TheoryFunction(b.location, operator, [b]))
        else:
            a = self._terms.pop()
            loc = Location(a.location.begin, b.location.end)
            self._terms.append(TheoryFunction(loc, operator, [a, b]))

    def check_operator(self, operator: str, arity: Arity, location: Location) -> None:
        """
        Check if the given operator is in the parse table raising a runtime
        error if absent.

        Parameters
        ----------
        operator
            The operator name.
        arity
            The arity of the operator.
        location
            Location of the operator for error reporting.
        """
        if (operator, arity) not in self._table:
            raise RuntimeError(
                f"cannot parse operator `{operator}`: {location_to_str(location)}"
            )

    def parse(self, x: AST) -> AST:
        """
        Parses the given unparsed term, replacing it by nested theory
        functions.

        Parameters
        ----------
        x
            The AST to parse.

        Returns
        -------
        The rewritten AST.
        """
        del self._stack[:]
        del self._terms[:]

        arity = Arity.Unary

        for element in x.elements:
            for operator in element.operators:
                self.check_operator(operator, arity, x.location)

                while arity == Arity.Binary and self._check(operator):
                    self._reduce()

                self._stack.append((operator, arity))
                arity = Arity.Unary

            self._terms.append(element.term)
            arity = Arity.Binary

        while self._stack:
            self._reduce()

        return self._terms[0]


class TheoryTermParser(Transformer):
    """
    Parser for theory terms in clingo's AST that works like the inbuilt one.

    This is implemented as a transformer that traverses the AST replacing all
    terms found.

    Parameters
    ----------
    table
        This must either be a table of operators or a `TheoryUnparsedTermParser`.

    See Also
    --------
    TheoryUnparsedTermParser
    """

    # pylint: disable=invalid-name

    def __init__(self, table: Union[OperatorTable, TheoryUnparsedTermParser]):
        self._parser = (
            table
            if isinstance(table, TheoryUnparsedTermParser)
            else TheoryUnparsedTermParser(table)
        )

    def visit_TheoryFunction(self, x) -> AST:
        """
        Parse the theory function and check if it agrees with the grammar.

        Parameters
        ----------
        x
            The AST to rewrite.

        Returns
        -------
        The rewritten AST.
        """
        arity = None
        if len(x.arguments) == 1:
            arity = Arity.Unary
        if len(x.arguments) == 2:
            arity = Arity.Binary
        if arity is not None and is_operator(x.name):
            self._parser.check_operator(x.name, arity, x.location)

        lib = getattr(self, "_lib", _DEFAULT_LIB)
        transformed = x.transform(lib, self)
        return transformed if transformed is not None else x

    def visit_TheoryUnparsedTerm(self, x: AST) -> AST:
        """
        Parse the given unparsed term.

        Parameters
        ----------
        x
            The AST to rewrite.

        Returns
        -------
        The rewritten AST.
        """
        return cast(AST, self(self._parser.parse(x)))


_clingo_term_table = {
    ("-", Arity.Unary): (5, Associativity.NoAssociativity),
    ("~", Arity.Unary): (5, Associativity.NoAssociativity),
    ("**", Arity.Binary): (4, Associativity.Right),
    ("*", Arity.Binary): (3, Associativity.Left),
    ("/", Arity.Binary): (3, Associativity.Left),
    ("\\", Arity.Binary): (3, Associativity.Left),
    ("+", Arity.Binary): (2, Associativity.Left),
    ("-", Arity.Binary): (2, Associativity.Left),
    ("&", Arity.Binary): (1, Associativity.Left),
    ("?", Arity.Binary): (1, Associativity.Left),
    ("^", Arity.Binary): (1, Associativity.Left),
    ("..", Arity.Binary): (0, Associativity.Left),
}


@lru_cache(maxsize=None)
def clingo_term_parser() -> TheoryTermParser:
    """
    Return a theory term parser that parses theory terms like clingo terms.

    Note that for technical reasons pools and the absolute function are not
    supported.
    """
    return TheoryTermParser(_clingo_term_table)


@lru_cache(maxsize=None)
def clingo_literal_parser() -> TheoryTermParser:
    """
    Return a theory term parser that parses theory literals similar to clingo's
    parser for symbolic literals.

    Note that for technical reasons pools and the absolute function are not
    supported.
    """
    clingo_literal_table = _clingo_term_table.copy()
    clingo_literal_table.update(
        {
            ("-", Arity.Unary): (0, Associativity.NoAssociativity),
            ("not", Arity.Unary): (0, Associativity.NoAssociativity),
        }
    )
    return TheoryTermParser(clingo_literal_table)


class TheoryParser(Transformer):
    """
    This class parses theory atoms in the same way as clingo's internal parser.

    Parameters
    ----------
    terms
        Mapping from term identifiers to `TheoryTermParser`s. If an operator
        table is given, the `TheoryTermParser` is constructed from this table.

    atoms
        Mapping from atom name/arity pairs to tuples defining the acceptable
        structure of the theory atom.
    """

    # pylint: disable=invalid-name
    _table: Mapping[
        Tuple[str, int],
        Tuple[
            TheoryAtomType,
            TheoryTermParser,
            Optional[Tuple[Set[str], TheoryTermParser]],
        ],
    ]
    _in_body: bool
    _in_head: bool
    _is_directive: bool

    def __init__(
        self,
        terms: Mapping[str, Union[OperatorTable, TheoryTermParser]],
        atoms: AtomTable,
    ):
        self._reset()

        term_parsers = {}
        for term_key, parser in terms.items():
            if isinstance(parser, TheoryTermParser):
                term_parsers[term_key] = parser
            else:
                term_parsers[term_key] = TheoryTermParser(parser)

        self._table = {}
        for atom_key, (atom_type, term_key, guard) in atoms.items():
            guard_table = None
            if guard is not None:
                guard_table = (set(guard[0]), term_parsers[guard[1]])
            self._table[atom_key] = (atom_type, term_parsers[term_key], guard_table)

    def _reset(self, in_head=True, in_body=True, is_directive=True):
        """
        Set state information about active scope.
        """
        self._in_head = in_head
        self._in_body = in_body
        self._is_directive = is_directive

    def _visit_body(self, x: AST) -> AST:
        lib = getattr(self, "_lib", _DEFAULT_LIB)
        try:
            self._reset(False, True, False)
            old = x.body
            new = self.visit_sequence(old)
            return x if new is old else x.update(lib, body=new)
        finally:
            self._reset()

    def visit_Rule(self, x: AST) -> AST:
        """
        Parse theory atoms in body and head.

        Parameters
        ----------
        x
            The AST to rewrite.

        Returns
        -------
        The rewritten AST.
        """
        lib = getattr(self, "_lib", _DEFAULT_LIB)
        ret = self._visit_body(x)
        try:
            self._reset(True, False, not x.body)
            head = self(x.head)
            if head is not x.head:
                ret = ret.update(lib, head=head)
        finally:
            self._reset()

        return ret

    def visit_StatementShow(self, x: AST) -> AST:
        """
        Parse theory atoms in body.

        Parameters
        ----------
        x
            The AST to rewrite.

        Returns
        -------
        The rewritten AST.
        """
        return self._visit_body(x)

    def visit_StatementWeakConstraint(self, x: AST) -> AST:
        """
        Parse theory atoms in body.

        Parameters
        ----------
        x
            The AST to rewrite.

        Returns
        -------
        The rewritten AST.
        """
        return self._visit_body(x)

    def visit_StatementEdge(self, x: AST) -> AST:
        """
        Parse theory atoms in body.

        Parameters
        ----------
        x
            The AST to rewrite.

        Returns
        -------
        The rewritten AST.
        """
        return self._visit_body(x)

    def visit_StatementHeuristic(self, x: AST) -> AST:
        """
        Parse theory atoms in body.

        Parameters
        ----------
        x
            The AST to rewrite.

        Returns
        -------
        The rewritten AST.
        """
        return self._visit_body(x)

    def visit_TheoryAtom(self, x: AST) -> AST:
        """
        Parse the given theory atom.

        Parameters
        ----------
        x
            The AST to rewrite.

        Returns
        -------
        The rewritten AST.
        """
        lib = getattr(self, "_lib", _DEFAULT_LIB)
        name = x.name.name
        arity = len(x.name.pool[0].arguments) if x.name.pool else 0
        if (name, arity) not in self._table:
            raise RuntimeError(
                f"theory atom definiton not found: {location_to_str(x.location)}"
            )

        type_, element_parser, guard_table = self._table[(name, arity)]
        if type_ == TheoryAtomType.Head and not self._in_head:
            raise RuntimeError(
                f"theory atom only accepted in head: {location_to_str(x.location)}"
            )
        if type_ == TheoryAtomType.Body and not self._in_body:
            raise RuntimeError(
                f"theory atom only accepted in body: {location_to_str(x.location)}"
            )
        if type_ == TheoryAtomType.Directive and not (
            self._in_head and self._is_directive
        ):
            raise RuntimeError(
                f"theory atom must be a directive: {location_to_str(x.location)}"
            )

        new_name = element_parser(x.name)
        new_elements = element_parser.visit_sequence(x.elements)
        new_right = x.right

        if x.right is not None:
            if guard_table is None:
                raise RuntimeError(
                    f"unexpected guard in theory atom: {location_to_str(x.location)}"
                )

            guards, guard_parser = guard_table
            if x.right.theory_operator not in guards:
                raise RuntimeError(
                    f"unexpected guard in theory atom: {location_to_str(x.location)}"
                )

            new_right = x.right.update(lib, term=guard_parser(x.right.term))

        return x.update(lib, name=new_name, elements=new_elements, right=new_right)


def theory_parser_from_definition(x: AST) -> TheoryParser:
    """
    Turn an AST node of type TheoryDefinition into a TheoryParser.

    Parameters
    ----------
    x
        An AST representing a theory definition.

    Returns
    -------
    The corresponding `TheoryParser`.
    """
    assert x.ast_type == ASTType.TheoryDefinition

    terms = {}
    atoms = {}

    for term_def in x.terms:
        term_table = {}

        for op_def in term_def.operators:
            op_assoc: Associativity
            if op_def.operator_type == TheoryOperatorType.BinaryLeft:
                op_type = Arity.Binary
                op_assoc = Associativity.Left
            elif op_def.operator_type == TheoryOperatorType.BinaryRight:
                op_type = Arity.Binary
                op_assoc = Associativity.Right
            else:
                op_type = Arity.Unary
                op_assoc = Associativity.NoAssociativity

            term_table[(op_def.name, op_type)] = (op_def.priority, op_assoc)

        terms[term_def.name] = term_table

    for atom_def in x.atoms:
        guard = None
        if atom_def.guard is not None:
            guard = (atom_def.guard.operators, atom_def.guard.term)

        atoms[(atom_def.name, atom_def.arity)] = (
            atom_def.atom_type,
            atom_def.term,
            guard,
        )

    return TheoryParser(terms, atoms)


def parse_theory(s: str) -> TheoryParser:
    """
    Turn the given theory into a parser.
    """
    parser = None

    def extract(stm):
        nonlocal parser
        if stm.ast_type == ASTType.TheoryDefinition:
            if parser is not None:
                raise ValueError("multiple theory definitions")
            parser = theory_parser_from_definition(stm)
        else:
            assert (
                stm.ast_type == ASTType.Program
                and stm.name == "base"
                and not stm.arguments
            )

    parse_string(_DEFAULT_LIB, f"{s}.", extract)
    if parser is None:
        raise ValueError("no theory definition found")
    return cast(TheoryParser, parser)


class _SymbolicAtomTransformer(Transformer):
    """
    Transforms symbolic atoms with the given function.
    """

    # pylint: disable=invalid-name

    def __init__(self, transformer_function: Callable[[AST], AST]):
        self._transformer_function = transformer_function

    def visit_LiteralSymbolic(self, x: AST) -> AST:
        """
        Transform the given symbolic literal (clingo6: LiteralSymbolic replaces SymbolicAtom).
        """
        lib = getattr(self, "_lib", _DEFAULT_LIB)
        atom = x.atom
        new_atom = self._transformer_function(atom)
        if new_atom is atom:
            return x
        return x.update(lib, atom=new_atom)


def rewrite_symbolic_atoms(x: AST, rewrite_function: Callable[[AST], AST]) -> AST:
    """
    Rewrite all symbolic atoms in the given AST node with the given function.

    Parameters
    ----------
    x
        The ast in which to rename symbolic atoms.
    rename_function
        A function applied to the term representation of the symbolic atom. The
        function has to return a term compatible with symbolic atoms.

    Returns
    -------
    The rewritten AST.
    """
    return cast(AST, _SymbolicAtomTransformer(rewrite_function)(x))


def rename_symbolic_atoms(x: AST, rename_function: Callable[[str], str]) -> AST:
    """
    Rename all symbolic atoms in the given AST node with the given function.

    Parameters
    ----------
    x
        The ast in which to rename symbolic atoms.
    rename_function
        A function for renaming symbols.

    Returns
    -------
    The rewritten AST.
    """

    def renamer(term: AST):
        if term.ast_type == ASTType.UnaryOperation:
            return UnaryOperation(
                term.location, term.operator_type, renamer(term.right)
            )
        if term.ast_type == ASTType.SymbolicTerm:
            sym = term.symbol
            new_name = rename_function(sym.name)
            return SymbolicTerm(
                term.location,
                clingo.symbol.Function(_get_lib(), new_name, sym.arguments, sym.is_positive),
            )
        if term.ast_type == ASTType.Function:
            args = term.pool[0].arguments if term.pool else []
            return Function(
                term.location, rename_function(term.name), args, term.external
            )
        return term

    return rewrite_symbolic_atoms(x, renamer)


def prefix_symbolic_atoms(x: AST, prefix: str) -> AST:
    """
    Prefix all symbolic atoms in the given AST with the given string.

    Parameters
    ----------
    x
        The ast in which to prefix symbolic atom names.
    prefix
        The prefix to add.

    Returns
    -------
    The rewritten AST.

    See Also
    --------
    rename_symbolic_atoms
    """
    return rename_symbolic_atoms(x, lambda s: prefix + s)


def reify_symbolic_atoms(
    x: AST,
    name: str,
    argument_extender: Optional[Callable[[AST], Sequence[AST]]] = None,
    reify_strong_negation: bool = False,
) -> AST:
    """
    Reify all symbolic atoms in the given AST node with the given name and
    function.

    Parameters
    ----------
    x
        The ast in which to rename symbolic atoms.
    name
        A string to serve as name of the new symbolic atom.
    argument_extender
        A function to provide extra arguments. If not provided, no extra
        arguments are added. The term passed as argument should be placed in
        the correct position.
    reify_strong_negation
        Boolean indicating how to encode strong negation. If false, `-p(X)` is
        reified as `-name(p(X))`. If true, then `-p(X)` is reified as
        `name(-p(X))`. In the latter case, this means that stable models
        containing both `name(p(a))` and `name(-p(a))` are possible. Clingo
        style consistency can be restored by adding the constraint
        `:- name(X), name(-X), X<-X.`

    Returns
    -------
    The rewritten AST.
    """

    def reifier(term: AST):
        if term.ast_type == ASTType.UnaryOperation and not reify_strong_negation:
            return UnaryOperation(
                term.location, term.operator_type, reifier(term.right)
            )
        arguments = argument_extender(term) if argument_extender else [term]
        return Function(term.location, name, arguments, False)

    return rewrite_symbolic_atoms(x, reifier)


@singledispatch
def _encode(x: Any) -> Any:
    assert False, f"unknown value to encode: {x}"


@_encode.register(str)
def _encode_str(x: str) -> str:
    return x


@_encode.register(Symbol)
def _encode_symbol(x: Symbol) -> str:
    return str(x)


@_encode.register(int)
def _encode_int(x: int) -> int:
    return x

# SIGN_STRINGS = {
#     Sign.NoSign: "Sign.NoSign",
#     Sign.Negation: "Sign.Negation",
#     Sign.DoubleNegation: "Sign.DoubleNegation",
# }

@_encode.register(Sign)
def _encode_sign(x: Sign) -> Sign:
    return x

# RELATION_STRINGS = {
#     Relation.Equal: "Relation.Equal",
#     Relation.NotEqual: "Relation.NotEqual",
#     Relation.Less: "Relation.Less",
#     Relation.LessEqual: "Relation.LessEqual",
#     Relation.Greater: "Relation.Greater",
#     Relation.GreaterEqual: "Relation.GreaterEqual",
# }

@_encode.register(Relation)
def _encode_relation(x: Relation) -> Relation:
    return x


@_encode.register(ASTSequence)
def _encode_ast_seq(x: ASTSequence) -> List[Any]:
    return [_encode(y) for y in x]


@_encode.register(StrSequence)
def _encode_str_seq(x: StrSequence) -> List[Any]:
    return [_encode(y) for y in x]


@_encode.register(type(None))
def _encode_none(x: None) -> None:
    return x


@_encode.register(AST)
def _encode_ast(x: AST) -> Any:
    return ast_to_dict(x)


def ast_to_dict(x: AST) -> dict:
    """
    Convert the given ast node into a dictionary representation whose elements
    only involve the data structures: `dict`, `list`, `int`, and `str`.

    The resulting value can be used with other Python modules like the `yaml`
    or `pickle` modules.

    Parameters
    ----------
    x
        The ast to transform.

    Returns
    -------
    The corresponding Python representation.

    See Also
    --------
    dict_to_ast
    """
    ret = {"ast_type": type(x).__name__}
    for key in dir(x):
        if key == "ast_type" or key.startswith("_") or callable((val :=getattr(x, key))):
            continue
        if key == "location":
            assert isinstance(val, Location), f"expected location to be of type Location, got {type(val)} in {x} of type {type(x)}"
            enc = location_to_str(val)
        else:
            enc = _encode(val)
        ret[key] = enc
    return ret


@singledispatch
def _decode(x: Any, key: str) -> Any:
    raise RuntimeError(f"unknown key/value to decode: {key}: {x}")


@_decode.register(str)
def _decode_str(x: str, key: str) -> Any:
    if key == "location":
        return str_to_location(x)

    if key == "symbol":
        return parse_symbol(_get_lib(), x)

    assert key in ("name", "id", "code", "elements", "term", "list", "operator_name")
    return x


@_decode.register(int)
def _decode_int(x: int, key: str) -> Any:
    # pylint: disable=unused-argument
    return x


@_decode.register(type(None))
def _decode_none(x: None, key: str) -> Any:
    # pylint: disable=unused-argument
    return x


@_decode.register(list)
def _decode_list(x: list, key_: str) -> Any:
    # pylint: disable=unused-argument
    return [_decode(y, "list") for y in x]


@_decode.register(dict)
def _decode_dict(x: dict, key_: str) -> Any:
    # pylint: disable=unused-argument
    return dict_to_ast(x)


def dict_to_ast(x: dict) -> AST:
    """
    Convert the Python dict representation of an AST node into an AST node.

    Parameters
    ----------
    x
        The Python representation of the AST.

    Returns
    -------
    The corresponding AST.

    See Also
    --------
    ast_to_dict
    """
    return getattr(ast, x["ast_type"])(
        **{key: _decode(value, key) for key, value in x.items() if key != "ast_type"}
    )


ASTPredicate = Union[Callable[[AST], bool], bool]


def _eval_predicate(predicate: ASTPredicate, arg: AST) -> bool:
    if callable(predicate):
        return predicate(arg)
    return predicate


def _body_literal_predicate(
    lit: AST,
    symbolic_atom_predicate: ASTPredicate = True,
    theory_atom_predicate: ASTPredicate = True,
    aggregate_predicate: ASTPredicate = True,
    conditional_literal_predicate: ASTPredicate = True,
    signs: Container[Sign] = (Sign.NoSign, Sign.Negation, Sign.DoubleNegation),
) -> bool:
    if not hasattr(lit, "ast_type"):
        # clingo6: BodySetAggregate has no ast_type
        if hasattr(lit, "sign") and lit.sign not in signs:
            return False
        return _eval_predicate(aggregate_predicate, lit)
    if lit.ast_type == ASTType.Literal:
        # clingo6: BodySimpleLiteral wraps a LiteralSymbolic via .literal
        inner = lit.literal
        if inner.sign not in signs:
            return False
        atom = inner.atom
        if atom.ast_type == ASTType.SymbolicAtom:
            # clingo5: SymbolicAtom wrapper around the actual symbol
            return _eval_predicate(symbolic_atom_predicate, atom.symbol)
        # clingo6: atom is directly TermFunction / TermSymbolic / etc.
        return _eval_predicate(symbolic_atom_predicate, atom)
    elif lit.ast_type == ASTType.BodyAggregate:
        # clingo6: top-level body item
        if lit.sign not in signs:
            return False
        return _eval_predicate(aggregate_predicate, lit)
    elif lit.ast_type == ASTType.TheoryAtom:
        # clingo6: top-level body item
        if lit.sign not in signs:
            return False
        return _eval_predicate(theory_atom_predicate, lit)
    elif lit.ast_type == ASTType.ConditionalLiteral:
        return lit.literal.sign in signs and _eval_predicate(
            conditional_literal_predicate, lit
        )
    return True


def filter_body_literals(
    body: Iterable[AST],
    symbolic_atom_predicate: ASTPredicate = True,
    theory_atom_predicate: ASTPredicate = True,
    aggregate_predicate: ASTPredicate = True,
    conditional_literal_predicate: ASTPredicate = True,
    signs: Container[Sign] = (Sign.NoSign, Sign.Negation, Sign.DoubleNegation),
) -> Iterable[AST]:
    """
    Filters the given body literals according to the given predicates.

    Parameters
    ----------
    body
        An iterable of `AST`s for body literals.
    symbolic_atom_predicate
        Predicate to filter symbolic atoms.
    theory_atom_predicate
        Predicate to filter theory atoms.
    aggregate_predicate
        Predicate to filter aggregates.
    conditional_literal_predicate
        Predicate to filter conditional literals.
    signs
        Only include literals with the given signs.

    Returns
    -------
    An iterarable of body literals.

    Notes
    -----
    An `ASTPredicate` is a callable that takes an `AST` and returns a Boolean.
    Booleans `True` and `False` are also accepted, meaning that the predicate
    is always `True` or `False`, respectively.
    """
    pred = partial(
        _body_literal_predicate,
        symbolic_atom_predicate=symbolic_atom_predicate,
        theory_atom_predicate=theory_atom_predicate,
        aggregate_predicate=aggregate_predicate,
        conditional_literal_predicate=conditional_literal_predicate,
        signs=signs,
    )
    return filter(pred, body)


def partition_body_literals(
    body: Iterable[AST],
    symbolic_atom_predicate: ASTPredicate = True,
    theory_atom_predicate: ASTPredicate = True,
    aggregate_predicate: ASTPredicate = True,
    conditional_literal_predicate: ASTPredicate = True,
    signs: Container[Sign] = (Sign.NoSign, Sign.Negation, Sign.DoubleNegation),
) -> Tuple[List[AST], List[AST]]:
    """
    Partition the given body literals according to the given predicates.

    Parameters
    ----------
    body
        An iterable of `AST` that represents a body.
    symbolic_atom_predicate
        Predicate to partition symbolic atoms.
    theory_atom_predicate
        Predicate to partition theory atoms.
    aggregate_predicate
        Predicate to partition aggregates.
    conditional_literal_predicate
        Predicate to partition conditional literals.
    signs
        Only include literals with the given signs in the first list.

    Returns
    -------
    A pair of lists of body literals. The first iterable yields the literals
    that satisfy the predicate while the second one yields the ones that do
    not.

    Notes
    -----
    An `ASTPredicate` is a callable that takes an `AST` and returns a Boolean.
    Booleans `True` and `False` are also accepted, meaning that the predicate
    is always `True` or `False`, respectively.
    """
    pred = partial(
        _body_literal_predicate,
        symbolic_atom_predicate=symbolic_atom_predicate,
        theory_atom_predicate=theory_atom_predicate,
        aggregate_predicate=aggregate_predicate,
        conditional_literal_predicate=conditional_literal_predicate,
        signs=signs,
    )
    part_a: List[AST] = []
    part_b: List[AST] = []
    for lit in body:
        if pred(lit):
            part_a.append(lit)
        else:
            part_b.append(lit)
    return part_a, part_b


_unary_operator_map = {
    "-": ast.UnaryOperator.Minus,
    "~": ast.UnaryOperator.Negation,
    "|": "absolute",
}

_binary_operator_map = {
    "+": ast.BinaryOperator.Plus,
    "-": ast.BinaryOperator.Minus,
    "*": ast.BinaryOperator.Multiplication,
    "/": ast.BinaryOperator.Division,
    "\\": ast.BinaryOperator.Modulo,
    "**": ast.BinaryOperator.Power,
    "&": ast.BinaryOperator.And,
    "?": ast.BinaryOperator.Or,
    "^": ast.BinaryOperator.Xor,
}


@lru_cache(maxsize=1)
def _get_interval_template() -> AST:
    """Get a cached TermBinaryOperation template for interval terms (operator_type=9)."""
    stmts: List[AST] = []
    parse_string(_DEFAULT_LIB, ":- _dummy_(1..1).", stmts.append)
    for s in stmts:
        if type(s).__name__ == "StatementRule":
            return s.body[0].literal.atom.pool[0].arguments[0]
    raise RuntimeError("Failed to create interval template")


def _theory_term_to_term(x: AST) -> AST:
    """
    Convert a given theory term into a plain clingo term.
    """
    if x.ast_type == ASTType.SymbolicTerm:
        if isinstance(x, ast.TheoryTermSymbolic):
            return SymbolicTerm(x.location, x.symbol)
        return x
    if x.ast_type == ASTType.Variable:
        if isinstance(x, ast.TheoryTermVariable):
            return Variable(x.location, x.name)
        return x

    if x.ast_type == ASTType.TheoryFunction:
        if len(x.arguments) == 1 and x.name in _unary_operator_map:
            arg = _theory_term_to_term(x.arguments[0])
            uop = _unary_operator_map[x.name]
            if uop == "absolute":
                return ast.TermAbsolute(_get_lib(), x.location, [arg])
            return UnaryOperation(x.location, uop, arg)

        if len(x.arguments) == 2:
            lhs = _theory_term_to_term(x.arguments[0])
            rhs = _theory_term_to_term(x.arguments[1])

            if x.name in _binary_operator_map:
                bop = _binary_operator_map[x.name]
                return BinaryOperation(x.location, bop, lhs, rhs)

            if x.name == "..":
                return _get_interval_template().update(_get_lib(), left=lhs, right=rhs, location=x.location)

        if not is_operator(x.name):
            return Function(x.location, x.name, [_theory_term_to_term(a) for a in x.arguments])

    elif x.ast_type == ASTType.TheorySequence:
        if x.tuple_type == ast.TheoryTupleType.Tuple:
            args = [_theory_term_to_term(a) for a in x.arguments]
            return ast.TermTuple(_get_lib(), x.location, [ast.ArgumentTuple(_get_lib(), args)])

    raise RuntimeError(f"{location_to_str(x.location)}: invalid term `{x}`")


def theory_term_to_term(x: AST, parse: bool = True) -> AST:
    """
    Convert the given theory term into a plain clingo term.

    If argument `parse` is set to true, occurences of unparsed theory terms are
    parsed using `clingo_term_parser()`.
    """
    if parse:
        x = clingo_term_parser()(x)
    return _theory_term_to_term(x)


def _build_atom(
    location: Location, positive: bool, name: str, arguments: List
) -> AST:
    """
    Helper function to create an atom.

    Arguments:
    location  -- Location to use.
    positive  -- Classical sign of the atom.
    name      -- The name of the atom.
    arguments -- The arguments of the atom.
    """
    ret = Function(location, name, arguments)
    if not positive:
        ret = UnaryOperation(location, ast.UnaryOperator.Minus, ret)
    return ret


def negate_sign(sign: Sign) -> Sign:
    """
    Negate the given sign.
    """
    if sign == Sign.Negation:
        return Sign.DoubleNegation
    return Sign.Negation


def _theory_term_to_literal(
    x: AST, positive: bool = True, sign: Sign = Sign.NoSign
) -> AST:
    """
    Convert a given theory term into a symbolic clingo literal.
    """
    if x.ast_type == ASTType.TheoryFunction:
        if x.name == "-":
            return _theory_term_to_literal(x.arguments[0], not positive, sign)

        if x.name == "not":
            sign = negate_sign(sign)
            if not positive:
                sign = negate_sign(sign)
            return _theory_term_to_literal(x.arguments[0], True, sign)

        if not is_operator(x.name):
            atom = _build_atom(
                x.location,
                positive,
                x.name,
                [theory_term_to_term(a) for a in x.arguments],
            )
            return ast.LiteralSymbolic(_get_lib(), x.location, sign, atom)

    elif (
        x.ast_type == ASTType.SymbolicTerm
        and x.symbol.type == clingo.symbol.SymbolType.Function
        and x.symbol.name
    ):
        atom = _build_atom(
            x.location,
            (positive == x.symbol.is_positive),
            x.symbol.name,
            [SymbolicTerm(x.location, a) for a in x.symbol.arguments],
        )
        return ast.LiteralSymbolic(_get_lib(), x.location, sign, atom)

    raise RuntimeError(f"{location_to_str(x.location)}: invalid literal `{x}`")


def theory_term_to_literal(x: AST, parse: bool = True) -> AST:
    """
    Convert the given theory term into a symbolic clingo literal.

    If argument `parse` is set to true, occurences of unparsed theory terms are
    parsed using `clingo_literal_parser()`.

    Literals can use an arbitrary number of classical and default negation
    signs. They are normalized using the following equivalences:

    - `- - lit = lit`
    - `- not lit = not not lit`
    - `not not not lit = not lit`
    """
    if parse:
        x = clingo_literal_parser()(x)
    return _theory_term_to_literal(x, True, Sign.NoSign)


def normalize_symbolic_terms(x: AST):
    """
    Replaces all occurrences of objects of the class clingo.Function in an AST
    by the corresponding object of the class ast.Function.

    Parameters
    ----------
    x
        The AST to rewrite.

    Returns
    -------
    The rewritten AST.
    """
    return _NormalizeSymbolicTermTransformer().visit(x)


def _symbol_to_ast(x: Symbol, location: Location) -> AST:
    """
    Convert the given symbol into an AST.

    Parameters
    ----------
    x
        The symbol to convert.
    location
        The location to use.

    Returns
    -------
    The converted AST.
    """
    if x.type != clingo.symbol.SymbolType.Function:
        return SymbolicTerm(location, x)
    return Function(location, x.name, [_symbol_to_ast(a, location) for a in x.arguments])


class _NormalizeSymbolicTermTransformer(Transformer):
    """Transforms a SymbolicTerm AST of type Function into an AST of type ast.Function."""

    def visit_SymbolicTerm(self, x: AST):  # pylint: disable=invalid-name
        """
        Transform the given symbolic term.

        Parameters
        ----------
        x
            The AST to rewrite.

        Returns
        -------
        The rewritten AST.
        """

        symbol = x.symbol

        if symbol.type != clingo.symbol.SymbolType.Function:
            return x

        return _symbol_to_ast(symbol, x.location)
