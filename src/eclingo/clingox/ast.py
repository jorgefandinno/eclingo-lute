'''
This module provides highlevel functions to work with clingo's AST.

Theory Parsing Examples
-----------------------

The following examples shows how to construct and use a theory parser:

```python-repl
>>> from clingo.ast import TheoryAtomType, parse_string
>>> from clingo.core import Library
>>> from eclingo.clingox.ast import Arity, Associativity, TheoryParser
>>>
>>> lib = Library()
>>> terms = {"term":
...     {("-", Arity.Unary): (3, Associativity.NoAssociativity),
...      ("**", Arity.Binary): (2, Associativity.Right),
...      ("*", Arity.Binary): (1, Associativity.Left),
...      ("+", Arity.Binary): (0, Associativity.Left),
...      ("-", Arity.Binary): (0, Associativity.Left)}}
>>> atoms = {("eval", 0): (TheoryAtomType.Head, "term", None)}
>>> parser = TheoryParser(lib, terms, atoms)
>>>
>>> parse_string(lib, '&eval{ -1 * 2 + 3 }.', print)
#program base.
&eval { (- 1 * 2 + 3) }.
>>> parse_string(lib, '&eval{ -1 * 2 + 3 }.', lambda x: print(parser(x)))
#program base.
&eval { +(*(-(1),2),3) }.
```

The same parser can also be constructed from a theory:

```python-repl
>>> from clingo.ast import StatementTheory, parse_string
>>> from clingo.core import Library
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
>>> lib = Library()
>>> parsers = []
>>> def extract(stm):
...     if isinstance(stm, StatementTheory):
...         parsers.append(theory_parser_from_definition(lib, stm))
...
>>> parse_string(lib, theory, extract)
>>> parse_string(lib, '&eval{ -1 * 2 + 3 }.', print)
#program base.
&eval { (- 1 * 2 + 3) }.
>>> parse_string(lib, '&eval{ -1 * 2 + 3 }.', lambda x: print(parsers[0](x)))
#program base.
&eval { +(*(-(1),2),3) }.
```
'''

from enum import Enum, auto
from functools import partial, singledispatch
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

from clingo import ast
from clingo.ast import (
    Sign,
    TheoryAtomType,
    TheoryOperatorType,
    parse_string,
)
from clingo.core import Library, Location, Position
from clingo.symbol import Function as SymbolFunction
from clingo.symbol import Symbol, SymbolType

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
    "clingo_literal_parser",
    "clingo_term_parser",
    "filter_body_literals",
    "location_to_str",
    "negate_sign",
    "normalize_symbolic_terms",
    "parse_theory",
    "partition_body_literals",
    "prefix_symbolic_atoms",
    "reify_symbolic_atoms",
    "rename_symbolic_atoms",
    "rewrite_symbolic_atoms",
    "str_to_location",
    "theory_parser_from_definition",
    "theory_term_to_literal",
    "theory_term_to_term",
]

# There is no common base class for AST nodes in clingo 6. This alias is used
# in signatures that accept or return arbitrary AST nodes.
ASTNode = Any


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


def str_to_location(lib: Library, loc: str) -> Location:
    """
    This function parses a location from its string representation.

    Parameters
    ----------
    lib
        The library storing symbols.
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
    begin = Position(lib, _unquote(m["bf"]), int(m["bl"]), int(m["bc"]))
    end = Position(
        lib, _unquote(_s(m, "bf", "ef")), int(_s(m, "bl", "el")), int(_s(m, "bc", "ec"))
    )
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
    lib
        The library storing symbols.
    table
        Mapping of operator/arity pairs to priority/associativity pairs.
    """

    _lib: Library
    _stack: List[Tuple[str, Arity]]
    _terms: List[ASTNode]
    _table: OperatorTable

    def __init__(self, lib: Library, table: OperatorTable):
        self._lib = lib
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
            self._terms.append(
                ast.TheoryTermFunction(self._lib, b.location, operator, [b])
            )
        else:
            a = self._terms.pop()
            loc = Location(a.location.begin, b.location.end)
            self._terms.append(ast.TheoryTermFunction(self._lib, loc, operator, [a, b]))

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

    def parse(self, x: ast.TheoryTermUnparsed) -> ASTNode:
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


@singledispatch
def _parse_theory_term(x: ASTNode, parser: "TheoryTermParser") -> Optional[ASTNode]:
    """
    Generic case parsing theory terms in the children of the given node.
    """
    return x.transform(parser.lib, _parse_theory_term, parser)


@_parse_theory_term.register
def _parse_theory_term_function(x: ast.TheoryTermFunction, parser) -> Optional[ASTNode]:
    """
    Parse the theory function and check if it agrees with the grammar.
    """
    arity = None
    if len(x.arguments) == 1:
        arity = Arity.Unary
    if len(x.arguments) == 2:
        arity = Arity.Binary
    if arity is not None and is_operator(x.name):
        parser.parser.check_operator(x.name, arity, x.location)

    return x.transform(parser.lib, _parse_theory_term, parser)


@_parse_theory_term.register
def _parse_theory_term_unparsed(x: ast.TheoryTermUnparsed, parser) -> Optional[ASTNode]:
    """
    Parse the given unparsed term.
    """
    parsed = parser.parser.parse(x)
    return _parse_theory_term(parsed, parser) or parsed


class TheoryTermParser:
    """
    Parser for theory terms in clingo's AST that works like the inbuilt one.

    With clingo 5, this was implemented as a `Transformer`. With clingo 6, the
    traversal uses the `transform` method of the AST nodes.

    Parameters
    ----------
    lib
        The library storing symbols.
    table
        This must either be a table of operators or a `TheoryUnparsedTermParser`.

    See Also
    --------
    TheoryUnparsedTermParser
    """

    # pylint: disable=invalid-name

    lib: Library
    parser: TheoryUnparsedTermParser

    def __init__(
        self, lib: Library, table: Union[OperatorTable, TheoryUnparsedTermParser]
    ):
        self.lib = lib
        self.parser = (
            table
            if isinstance(table, TheoryUnparsedTermParser)
            else TheoryUnparsedTermParser(lib, table)
        )

    def __call__(self, x: ASTNode) -> ASTNode:
        """
        Parse the theory terms in the given node.
        """
        return _parse_theory_term(x, self) or x


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


def clingo_term_parser(lib: Library) -> TheoryTermParser:
    """
    Return a theory term parser that parses theory terms like clingo terms.

    Note that for technical reasons pools and the absolute function are not
    supported.
    """
    return TheoryTermParser(lib, _clingo_term_table)


def clingo_literal_parser(lib: Library) -> TheoryTermParser:
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
    return TheoryTermParser(lib, clingo_literal_table)


def _theory_atom_name_arity(term: ASTNode) -> Tuple[str, int]:
    """
    Extract the name and arity of a theory atom name term.
    """
    if isinstance(term, ast.TermFunction):
        if not term.pool:  # pragma: no cover
            return term.name, 0  # pragma: no cover
        return term.name, len(term.pool[0].arguments)
    if (
        isinstance(term, ast.TermSymbolic) and term.symbol.type == SymbolType.Function
    ):  # pragma: no cover
        return term.symbol.name, len(term.symbol.arguments)  # pragma: no cover
    raise RuntimeError(  # pragma: no cover
        f"invalid theory atom name: {location_to_str(term.location)}"
    )


@singledispatch
def _parse_theory_atoms(
    x: ASTNode, parser: "TheoryParser", is_directive: bool
) -> Optional[ASTNode]:
    """
    Generic case parsing theory atoms in the children of the given node.
    """
    # pylint: disable=unused-argument
    return x.transform(parser.lib, _parse_theory_atoms, parser, False)


@_parse_theory_atoms.register
def _parse_theory_atoms_rule(
    x: ast.StatementRule, parser, is_directive: bool
) -> Optional[ASTNode]:
    """
    Parse theory atoms in body and head.
    """
    # pylint: disable=unused-argument
    head = _parse_theory_atoms(x.head, parser, not x.body) or x.head
    body = [(_parse_theory_atoms(b, parser, False) or b) for b in x.body]
    return x.update(parser.lib, head=head, body=body)


@_parse_theory_atoms.register
def _parse_theory_atoms_head(
    x: ast.HeadTheoryAtom, parser, is_directive: bool
) -> Optional[ASTNode]:
    """
    Parse the given theory atom in a head context.
    """
    return parser.parse_atom(x, in_head=True, in_body=False, is_directive=is_directive)


@_parse_theory_atoms.register
def _parse_theory_atoms_body(
    x: ast.BodyTheoryAtom, parser, is_directive: bool
) -> Optional[ASTNode]:
    """
    Parse the given theory atom in a body context.
    """
    # pylint: disable=unused-argument
    return parser.parse_atom(x, in_head=False, in_body=True, is_directive=False)


class TheoryParser:
    """
    This class parses theory atoms in the same way as clingo's internal parser.

    Parameters
    ----------
    lib
        The library storing symbols.
    terms
        Mapping from term identifiers to `TheoryTermParser`s. If an operator
        table is given, the `TheoryTermParser` is constructed from this table.

    atoms
        Mapping from atom name/arity pairs to tuples defining the acceptable
        structure of the theory atom.
    """

    # pylint: disable=invalid-name
    lib: Library
    _table: Mapping[
        Tuple[str, int],
        Tuple[
            TheoryAtomType,
            TheoryTermParser,
            Optional[Tuple[Set[str], TheoryTermParser]],
        ],
    ]

    def __init__(
        self,
        lib: Library,
        terms: Mapping[str, Union[OperatorTable, TheoryTermParser]],
        atoms: AtomTable,
    ):
        self.lib = lib

        term_parsers = {}
        for term_key, parser in terms.items():
            if isinstance(parser, TheoryTermParser):
                term_parsers[term_key] = parser
            else:
                term_parsers[term_key] = TheoryTermParser(lib, parser)

        self._table = {}
        for atom_key, (atom_type, term_key, guard) in atoms.items():
            guard_table = None
            if guard is not None:
                guard_table = (set(guard[0]), term_parsers[guard[1]])
            self._table[atom_key] = (atom_type, term_parsers[term_key], guard_table)

    def parse_atom(
        self,
        x: ASTNode,
        in_head: bool = True,
        in_body: bool = True,
        is_directive: bool = True,
    ) -> ASTNode:
        """
        Parse the given theory atom.

        Parameters
        ----------
        x
            The theory atom to rewrite.
        in_head
            Whether the atom appears in a head context.
        in_body
            Whether the atom appears in a body context.
        is_directive
            Whether the atom forms a directive.

        Returns
        -------
        The rewritten AST.
        """
        name, arity = _theory_atom_name_arity(x.name)
        if (name, arity) not in self._table:
            raise RuntimeError(
                f"theory atom definiton not found: {location_to_str(x.location)}"
            )

        type_, element_parser, guard_table = self._table[(name, arity)]
        if type_ == TheoryAtomType.Head and not in_head:
            raise RuntimeError(
                f"theory atom only accepted in head: {location_to_str(x.location)}"
            )
        if type_ == TheoryAtomType.Body and not in_body:
            raise RuntimeError(
                f"theory atom only accepted in body: {location_to_str(x.location)}"
            )
        if type_ == TheoryAtomType.Directive and not (in_head and is_directive):
            raise RuntimeError(
                f"theory atom must be a directive: {location_to_str(x.location)}"
            )

        elements = [element_parser(element) for element in x.elements]

        right = x.right
        if right is not None:
            if guard_table is None:
                raise RuntimeError(
                    f"unexpected guard in theory atom: {location_to_str(x.location)}"
                )

            guards, guard_parser = guard_table
            if right.theory_operator not in guards:
                raise RuntimeError(
                    f"unexpected guard in theory atom: {location_to_str(x.location)}"
                )

            right = right.update(self.lib, term=guard_parser(right.term))

        return x.update(self.lib, elements=elements, right=right)

    def __call__(self, x: ASTNode) -> ASTNode:
        """
        Parse theory atoms in the given statement or theory atom.
        """
        if isinstance(x, (ast.HeadTheoryAtom, ast.BodyTheoryAtom)):
            return self.parse_atom(x)
        return _parse_theory_atoms(x, self, True) or x


def theory_parser_from_definition(lib: Library, x: ast.StatementTheory) -> TheoryParser:
    """
    Turn an AST node of type StatementTheory into a TheoryParser.

    Parameters
    ----------
    lib
        The library storing symbols.
    x
        An AST representing a theory definition.

    Returns
    -------
    The corresponding `TheoryParser`.
    """
    assert isinstance(x, ast.StatementTheory)

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
            guard = (list(atom_def.guard.operators), atom_def.guard.term)

        atoms[(atom_def.name, atom_def.arity)] = (
            atom_def.atom_type,
            atom_def.term,
            guard,
        )

    return TheoryParser(lib, terms, atoms)


def parse_theory(lib: Library, s: str) -> TheoryParser:
    """
    Turn the given theory into a parser.
    """
    parser = None

    def extract(stm):
        nonlocal parser
        if isinstance(stm, ast.StatementTheory):
            if parser is not None:
                raise ValueError("multiple theory definitions")
            parser = theory_parser_from_definition(lib, stm)
        else:
            assert (
                isinstance(stm, ast.StatementProgram)
                and stm.name == "base"
                and not stm.arguments
            )

    parse_string(lib, f"{s}.", extract)
    if parser is None:
        raise ValueError("no theory definition found")
    return cast(TheoryParser, parser)


@singledispatch
def _rewrite_symbolic_atoms(
    x: ASTNode, lib: Library, fun: Callable[[ASTNode], ASTNode]
) -> Optional[ASTNode]:
    """
    Generic case rewriting symbolic atoms in the children of the given node.
    """
    return x.transform(lib, _rewrite_symbolic_atoms, lib, fun)


@_rewrite_symbolic_atoms.register
def _rewrite_symbolic_atoms_literal(
    x: ast.LiteralSymbolic, lib: Library, fun: Callable[[ASTNode], ASTNode]
) -> Optional[ASTNode]:
    """
    Rewrite the atom of the given symbolic literal.
    """
    term = x.atom
    new_term = fun(term)
    return None if new_term is term else x.update(lib, atom=new_term)


@_rewrite_symbolic_atoms.register
def _rewrite_symbolic_atoms_disjunction(
    x: ast.HeadDisjunction, lib: Library, fun: Callable[[ASTNode], ASTNode]
) -> Optional[ASTNode]:
    """
    Rewrite the atoms in the elements of the given head disjunction.

    Note that passing new literals as elements of head disjunctions fails
    with clingo 6.0.0, so the new literals are wrapped inside conditional
    literals with an empty condition.
    """
    changed = False
    elements = []
    for element in x.elements:
        new_element = _rewrite_symbolic_atoms(element, lib, fun)
        if new_element is None:
            elements.append(element)
            continue
        changed = True
        if isinstance(new_element, ast.Literal):
            new_element = ast.HeadConditionalLiteral(
                lib, new_element.location, new_element, []
            )
        elements.append(new_element)
    if not changed:
        return None
    return ast.HeadDisjunction(lib, x.location, elements)


def _rewrite_symbolic_atoms_statement_atom(
    x: ASTNode, lib: Library, fun: Callable[[ASTNode], ASTNode]
) -> Optional[ASTNode]:
    """
    Rewrite the atom and the body of statements with an atom field.
    """
    body = [(_rewrite_symbolic_atoms(b, lib, fun) or b) for b in x.body]
    return x.update(lib, atom=fun(x.atom), body=body)


@_rewrite_symbolic_atoms.register
def _rewrite_symbolic_atoms_heuristic(
    x: ast.StatementHeuristic, lib: Library, fun: Callable[[ASTNode], ASTNode]
) -> Optional[ASTNode]:
    return _rewrite_symbolic_atoms_statement_atom(x, lib, fun)


@_rewrite_symbolic_atoms.register
def _rewrite_symbolic_atoms_project(
    x: ast.StatementProject, lib: Library, fun: Callable[[ASTNode], ASTNode]
) -> Optional[ASTNode]:
    return _rewrite_symbolic_atoms_statement_atom(x, lib, fun)


@_rewrite_symbolic_atoms.register
def _rewrite_symbolic_atoms_external(
    x: ast.StatementExternal, lib: Library, fun: Callable[[ASTNode], ASTNode]
) -> Optional[ASTNode]:
    return _rewrite_symbolic_atoms_statement_atom(x, lib, fun)


def rewrite_symbolic_atoms(
    lib: Library, x: ASTNode, rewrite_function: Callable[[ASTNode], ASTNode]
) -> ASTNode:
    """
    Rewrite all symbolic atoms in the given AST node with the given function.

    Parameters
    ----------
    lib
        The library storing symbols.
    x
        The ast in which to rename symbolic atoms.
    rewrite_function
        A function applied to the term representation of the symbolic atom. The
        function has to return a term compatible with symbolic atoms.

    Returns
    -------
    The rewritten AST.
    """
    if isinstance(x, ast.Term):
        new_term = rewrite_function(x)
        return x if new_term is None else new_term
    return _rewrite_symbolic_atoms(x, lib, rewrite_function) or x


def rename_symbolic_atoms(
    lib: Library, x: ASTNode, rename_function: Callable[[str], str]
) -> ASTNode:
    """
    Rename all symbolic atoms in the given AST node with the given function.

    Parameters
    ----------
    lib
        The library storing symbols.
    x
        The ast in which to rename symbolic atoms.
    rename_function
        A function for renaming symbols.

    Returns
    -------
    The rewritten AST.
    """

    def renamer(term: ASTNode):
        if isinstance(term, ast.TermUnaryOperation):
            return term.update(lib, right=renamer(term.right))
        if isinstance(term, ast.TermSymbolic):
            sym = term.symbol
            if sym.type != SymbolType.Function:  # pragma: no cover
                return term  # pragma: no cover
            return term.update(
                lib,
                symbol=SymbolFunction(
                    lib, rename_function(sym.name), sym.arguments, sym.is_positive
                ),
            )
        if isinstance(term, ast.TermFunction):
            return term.update(lib, name=rename_function(term.name))
        return term

    return rewrite_symbolic_atoms(lib, x, renamer)


def prefix_symbolic_atoms(lib: Library, x: ASTNode, prefix: str) -> ASTNode:
    """
    Prefix all symbolic atoms in the given AST with the given string.

    Parameters
    ----------
    lib
        The library storing symbols.
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
    return rename_symbolic_atoms(lib, x, lambda s: prefix + s)


def reify_symbolic_atoms(
    lib: Library,
    x: ASTNode,
    name: str,
    argument_extender: Optional[Callable[[ASTNode], Sequence[ASTNode]]] = None,
    reify_strong_negation: bool = False,
) -> ASTNode:
    """
    Reify all symbolic atoms in the given AST node with the given name and
    function.

    Parameters
    ----------
    lib
        The library storing symbols.
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

    def reifier(term: ASTNode):
        if isinstance(term, ast.TermUnaryOperation) and not reify_strong_negation:
            return term.update(lib, right=reifier(term.right))
        arguments = argument_extender(term) if argument_extender else [term]
        return ast.TermFunction(
            lib, term.location, name, [ast.ArgumentTuple(lib, arguments)], False
        )

    return rewrite_symbolic_atoms(lib, x, reifier)


ASTPredicate = Union[Callable[[ASTNode], bool], bool]


def _eval_predicate(predicate: ASTPredicate, arg: ASTNode) -> bool:
    if callable(predicate):
        return predicate(arg)
    return predicate


def _body_literal_predicate(
    lit: ASTNode,
    symbolic_atom_predicate: ASTPredicate = True,
    theory_atom_predicate: ASTPredicate = True,
    aggregate_predicate: ASTPredicate = True,
    conditional_literal_predicate: ASTPredicate = True,
    signs: Container[Sign] = (Sign.NoSign, Sign.Single, Sign.Double),
) -> bool:
    if isinstance(lit, ast.BodySimpleLiteral):
        literal = lit.literal
        if literal.sign not in signs:
            return False
        if isinstance(literal, ast.LiteralSymbolic):
            return _eval_predicate(symbolic_atom_predicate, literal.atom)
        return True
    if isinstance(lit, (ast.BodyAggregate, ast.BodySetAggregate)):
        if lit.sign not in signs:
            return False
        return _eval_predicate(aggregate_predicate, lit)
    if isinstance(lit, ast.BodyTheoryAtom):
        if lit.sign not in signs:
            return False
        return _eval_predicate(theory_atom_predicate, lit)
    if isinstance(lit, ast.BodyConditionalLiteral):
        return lit.literal.sign in signs and _eval_predicate(
            conditional_literal_predicate, lit
        )
    return True


def filter_body_literals(
    body: Iterable[ASTNode],
    symbolic_atom_predicate: ASTPredicate = True,
    theory_atom_predicate: ASTPredicate = True,
    aggregate_predicate: ASTPredicate = True,
    conditional_literal_predicate: ASTPredicate = True,
    signs: Container[Sign] = (Sign.NoSign, Sign.Single, Sign.Double),
) -> Iterable[ASTNode]:
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
    body: Iterable[ASTNode],
    symbolic_atom_predicate: ASTPredicate = True,
    theory_atom_predicate: ASTPredicate = True,
    aggregate_predicate: ASTPredicate = True,
    conditional_literal_predicate: ASTPredicate = True,
    signs: Container[Sign] = (Sign.NoSign, Sign.Single, Sign.Double),
) -> Tuple[List[ASTNode], List[ASTNode]]:
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
    part_a: List[ASTNode] = []
    part_b: List[ASTNode] = []
    for lit in body:
        if pred(lit):
            part_a.append(lit)
        else:
            part_b.append(lit)
    return part_a, part_b


_unary_operator_map = {
    "-": ast.UnaryOperator.Minus,
    "~": ast.UnaryOperator.Negation,
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


def _make_interval(lib: Library, location: Location, lhs: ASTNode, rhs: ASTNode):
    """
    Create an interval term.

    The range operator is missing from `clingo.ast.BinaryOperator`, so the
    term is created by updating a parsed template.
    """
    template = ast.parse_term(lib, "0..0")
    return template.update(lib, location=location, left=lhs, right=rhs)


def _theory_term_to_term(lib: Library, x: ASTNode) -> ASTNode:
    """
    Convert a given theory term into a plain clingo term.
    """
    if isinstance(x, ast.TheoryTermSymbolic):
        return ast.TermSymbolic(lib, x.location, x.symbol)

    if isinstance(x, ast.TheoryTermVariable):
        return ast.TermVariable(lib, x.location, x.name)

    if isinstance(x, ast.TheoryTermFunction):
        if len(x.arguments) == 1 and x.name in _unary_operator_map:
            arg = _theory_term_to_term(lib, x.arguments[0])
            uop = _unary_operator_map[x.name]

            return ast.TermUnaryOperation(lib, x.location, uop, arg)

        if len(x.arguments) == 2:
            lhs = _theory_term_to_term(lib, x.arguments[0])
            rhs = _theory_term_to_term(lib, x.arguments[1])

            if x.name in _binary_operator_map:
                bop = _binary_operator_map[x.name]
                return ast.TermBinaryOperation(lib, x.location, lhs, bop, rhs)

            if x.name == "..":
                return _make_interval(lib, x.location, lhs, rhs)

        if not is_operator(x.name):
            arguments = [_theory_term_to_term(lib, a) for a in x.arguments]
            return ast.TermFunction(
                lib,
                x.location,
                x.name,
                [ast.ArgumentTuple(lib, arguments)],
                False,
            )

    elif isinstance(x, ast.TheoryTermTuple):
        if x.tuple_type == ast.TheoryTupleType.Tuple:
            arguments = [_theory_term_to_term(lib, a) for a in x.arguments]
            return ast.TermTuple(lib, x.location, [ast.ArgumentTuple(lib, arguments)])

    raise RuntimeError(f"{location_to_str(x.location)}: invalid term `{x}`")


def theory_term_to_term(lib: Library, x: ASTNode, parse: bool = True) -> ASTNode:
    """
    Convert the given theory term into a plain clingo term.

    If argument `parse` is set to true, occurences of unparsed theory terms are
    parsed using `clingo_term_parser()`.
    """
    if parse:
        x = clingo_term_parser(lib)(x)
    return _theory_term_to_term(lib, x)


def _build_atom(
    lib: Library, location: Location, positive: bool, name: str, arguments: List
) -> ASTNode:
    """
    Helper function to create an atom.

    Arguments:
    lib       -- Library to use.
    location  -- Location to use.
    positive  -- Classical sign of the atom.
    name      -- The name of the atom.
    arguments -- The arguments of the atom.
    """
    ret: ASTNode
    if arguments:
        ret = ast.TermFunction(
            lib, location, name, [ast.ArgumentTuple(lib, arguments)], False
        )
    else:
        # clingo parses constants in atom positions as symbolic terms
        ret = ast.TermSymbolic(lib, location, SymbolFunction(lib, name))
    if not positive:
        ret = ast.TermUnaryOperation(lib, location, ast.UnaryOperator.Minus, ret)
    return ret


def negate_sign(sign: Sign) -> Sign:
    """
    Negate the given sign.
    """
    if sign == Sign.Single:
        return Sign.Double
    return Sign.Single


def _theory_term_to_literal(
    lib: Library, x: ASTNode, positive: bool = True, sign: Sign = Sign.NoSign
) -> ASTNode:
    """
    Convert a given theory term into a symbolic clingo literal.
    """
    if isinstance(x, ast.TheoryTermFunction):
        if x.name == "-":
            return _theory_term_to_literal(lib, x.arguments[0], not positive, sign)

        if x.name == "not":
            sign = negate_sign(sign)
            if not positive:
                sign = negate_sign(sign)
            return _theory_term_to_literal(lib, x.arguments[0], True, sign)

        if not is_operator(x.name):
            atom = _build_atom(
                lib,
                x.location,
                positive,
                x.name,
                [theory_term_to_term(lib, a) for a in x.arguments],
            )
            return ast.LiteralSymbolic(lib, x.location, sign, atom)

    elif (
        isinstance(x, ast.TheoryTermSymbolic)
        and x.symbol.type == SymbolType.Function
        and x.symbol.name
    ):
        atom = _build_atom(
            lib,
            x.location,
            (positive == x.symbol.is_positive),
            x.symbol.name,
            [ast.TermSymbolic(lib, x.location, a) for a in x.symbol.arguments],
        )
        return ast.LiteralSymbolic(lib, x.location, sign, atom)

    raise RuntimeError(f"{location_to_str(x.location)}: invalid literal `{x}`")


def theory_term_to_literal(lib: Library, x: ASTNode, parse: bool = True) -> ASTNode:
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
        x = clingo_literal_parser(lib)(x)
    return _theory_term_to_literal(lib, x, True, Sign.NoSign)


def _symbol_to_ast(lib: Library, x: Symbol, location: Location) -> ASTNode:
    """
    Convert the given symbol into an AST.

    Parameters
    ----------
    lib
        The library storing symbols.
    x
        The symbol to convert.
    location
        The location to use.

    Returns
    -------
    The converted AST.
    """
    if x.type != SymbolType.Function:
        return ast.TermSymbolic(lib, location, x)
    arguments = [_symbol_to_ast(lib, a, location) for a in x.arguments]
    return ast.TermFunction(
        lib,
        location,
        x.name,
        [ast.ArgumentTuple(lib, arguments)],
        False,
    )


@singledispatch
def _normalize_symbolic_terms(x: ASTNode, lib: Library) -> Optional[ASTNode]:
    """
    Generic case normalizing symbolic terms in the children of the given node.
    """
    return x.transform(lib, _normalize_symbolic_terms, lib)


@_normalize_symbolic_terms.register
def _normalize_symbolic_term(x: ast.TermSymbolic, lib: Library) -> Optional[ASTNode]:
    """
    Transform the given symbolic term.
    """
    symbol = x.symbol

    if symbol.type != SymbolType.Function:
        return None

    return _symbol_to_ast(lib, symbol, x.location)


def normalize_symbolic_terms(lib: Library, x: ASTNode) -> ASTNode:
    """
    Replaces all occurrences of objects of the class clingo.symbol.Symbol of
    type function in an AST by the corresponding object of the class
    clingo.ast.TermFunction.

    Parameters
    ----------
    lib
        The library storing symbols.
    x
        The AST to rewrite.

    Returns
    -------
    The rewritten AST.
    """
    return _normalize_symbolic_terms(x, lib) or x
