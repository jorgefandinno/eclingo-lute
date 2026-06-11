"""
This module provides functions to reify programs.

This includes a `Reifier` implementing clingo's `clingo.backend.Observer`
interface that can be passed to `clingo.control.Control.observe` after
grounding to inspect the current ground program.

Additionally, the module provides a `ReifiedTheory` class that provides a
similar interface as clingo's theory atoms but uses the reified symbols.

Examples
--------

The following example uses the `reify_program` function to reify a program:

```python-repl
>>> from clingo.core import Library
>>> from eclingo.clingox.reify import reify_program
>>> lib = Library()
>>> prg = 'b :- a. {a}.'
>>> symbols = reify_program(lib, prg)
>>> print([str(sym) for sym in symbols])
['tag(incremental)', 'atom_tuple(0)', 'atom_tuple(0,1)', 'literal_tuple(0)',
'rule(choice(0),normal(0))', 'atom_tuple(1)', 'atom_tuple(1,2)',
'literal_tuple(1)', 'literal_tuple(1,1)', 'rule(disjunction(1),normal(1))',
'output(a,1)', 'literal_tuple(2)', 'literal_tuple(2,2)', 'output(b,2)']
```

The last example shows how to use the `ReifiedTheory` class.

```python-repl
>>> from clingo.core import Library
>>> from eclingo.clingox.reify import ReifiedTheory, reify_program
>>> lib = Library()
>>> prg = '#theory theory { t { }; &p/0 : t, any }. &p { t }.'
>>> thy = ReifiedTheory(reify_program(lib, prg))
>>> print([str(atm) for atm in thy])
['&p { t: literal_tuple(0) }']
>>> from eclingo.clingox.theory import evaluate
>>> evaluate(lib, next(iter(thy)).term)
Function('p', [], True)
```
"""

from dataclasses import dataclass, field
from typing import (
    Callable,
    Dict,
    Generic,
    Iterator,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    TypeVar,
)

from clingo.backend import ExternalType, HeuristicType, Observer
from clingo.base import Base, TheoryTermType
from clingo.control import Control
from clingo.core import Library
from clingo.symbol import Function, Number, String, Symbol

from .theory import is_operator

__all__ = [
    "Reifier",
    "ReifiedTheory",
    "ReifiedTheoryAtom",
    "ReifiedTheoryElement",
    "ReifiedTheoryTerm",
    "ReifiedTheory",
    "reify_program",
]

T = TypeVar("T")  # pylint: disable=invalid-name
U = TypeVar("U", int, Tuple[int, int])  # pylint: disable=invalid-name


@dataclass
class _Vertex(Generic[T]):
    """
    Vertex data to calculate SCCs of a graph.
    """

    name: T
    visited: int
    index: int = 0
    edges: List[int] = field(default_factory=list)


class _Graph(Generic[T]):
    """
    Simple class to compute strongly connected components using Tarjan's
    algorithm.
    """

    _names: Dict[T, int]
    _vertices: List[_Vertex]
    _phase: bool

    def __init__(self):
        self._names = {}
        self._vertices = []
        self._phase = True

    def _visited(self, key_u: int) -> bool:
        return self._vertices[key_u].visited != int(not self._phase)

    def _active(self, key_u: int) -> bool:
        return self._vertices[key_u].visited != int(self._phase)

    def _add_vertex(self, val_u: T) -> int:
        n = len(self._vertices)
        key_u = self._names.setdefault(val_u, n)
        if n == key_u:
            self._vertices.append(_Vertex(val_u, int(not self._phase)))
        return key_u

    def add_edge(self, val_u: T, val_v: T) -> None:
        """
        Add an edge to the graph.
        """
        key_u = self._add_vertex(val_u)
        key_v = self._add_vertex(val_v)
        self._vertices[key_u].edges.append(key_v)

    def tarjan(self) -> List[List[T]]:
        """
        Returns the strictly connected components of the graph.
        """
        sccs: List[List[T]] = []
        stack = []
        trail = []
        index = 1

        def push(key_u: int):
            nonlocal index
            index += 1
            vtx_u = self._vertices[key_u]
            vtx_u.visited = index
            vtx_u.index = 0
            stack.append(key_u)
            trail.append(key_u)

        for key_u in range(len(self._vertices)):
            if self._visited(key_u):
                continue
            index = 1
            push(key_u)
            while stack:
                key_v = stack[-1]
                vtx_v = self._vertices[key_v]
                len_v = len(vtx_v.edges)
                while vtx_v.index < len_v:
                    key_w = vtx_v.edges[vtx_v.index]
                    vtx_v.index += 1
                    if not self._visited(key_w):
                        push(key_w)
                        break
                else:
                    stack.pop()
                    root = True
                    for key_w in vtx_v.edges:
                        vtx_w = self._vertices[key_w]
                        if self._active(key_w) and vtx_w.visited < vtx_v.visited:
                            root = False
                            vtx_v.visited = vtx_w.visited
                    if root:
                        key_last = None
                        sccs.append([])
                        while key_last != key_v:
                            key_last = trail[-1]
                            vtx_last = self._vertices[key_last]
                            sccs[-1].append(vtx_last.name)
                            vtx_last.visited = int(self._phase)
                            trail.pop()
                        if len(sccs[-1]) == 1:
                            sccs.pop()

        self._phase = not self._phase
        return sccs


@dataclass
class _StepData:
    atom_tuples: Dict[Sequence[int], int] = field(default_factory=dict)
    lit_tuples: Dict[Sequence[int], int] = field(default_factory=dict)
    wlit_tuples: Dict[Sequence[Tuple[int, int]], int] = field(default_factory=dict)
    theory_tuples: Dict[Sequence[int], int] = field(default_factory=dict)
    theory_element_tuples: Dict[Sequence[int], int] = field(default_factory=dict)
    theory_term_ids: Dict[tuple, int] = field(default_factory=dict)
    theory_element_ids: Dict[tuple, int] = field(default_factory=dict)
    graph: _Graph = field(default_factory=_Graph)


class Reifier(Observer):
    """
    An observer that will gather the symbols of the reification, in the same
    way as `clingo --output=reify`.

    Unlike with clingo 5, where observers were registered before grounding,
    this observer must be passed to `clingo.control.Control.observe` after
    grounding, which replays the current ground program. The output table and
    the theory atoms are reified from the base passed to `end_step`.

    Parameters
    ----------
    lib
        The library storing symbols
    cb
        A callback function that will be called with each symbol of the reification
    calculate_sccs
        Flag to calculate the SCCs
    reify_steps
        Flag to add a number as the last argument of all reification symbols for the corresponding step

    """

    # pylint:disable=too-many-public-methods
    _lib: Library
    _step: int
    # Bug in mypy???
    # _cb: Callable[[Symbol], None]
    _calculate_sccs: bool
    _reify_steps: bool
    _step_data: _StepData

    def __init__(
        self,
        lib: Library,
        cb: Callable[[Symbol], None],
        calculate_sccs: bool = False,
        reify_steps: bool = False,
    ):
        super().__init__()
        self._lib = lib
        self._step = 0
        self._cb = cb
        self._calculate_sccs = calculate_sccs
        self._reify_steps = reify_steps
        self._step_data = _StepData()

    def calculate_sccs(self) -> None:
        """
        Trigger computation of SCCs.

        SCCs can only be computed if the Reifier has been initialized with
        `calculate_sccs=True`, This function is called automatically if
        `reify_steps=True` has been set when initializing the Reifier.
        """
        for idx, scc in enumerate(self._step_data.graph.tarjan()):
            for atm in scc:
                self._output("scc", [Number(self._lib, idx), Number(self._lib, atm)])

    def _add_edges(self, head: Sequence[int], body: Sequence[int]):
        if self._calculate_sccs:
            for u in head:
                for v in body:
                    if v > 0:
                        self._step_data.graph.add_edge(u, v)

    def _output(self, name: str, args: Sequence[Symbol]):
        if self._reify_steps:
            args = list(args) + [Number(self._lib, self._step)]
        self._cb(Function(self._lib, name, args))

    def _theory(self, i: Symbol, pos: int, lit: int) -> Sequence[Symbol]:
        return [i, Number(self._lib, pos), Number(self._lib, lit)]

    def _lit(self, i: Symbol, pos: int, lit: int) -> Sequence[Symbol]:
        # pylint: disable=unused-argument
        return [i, Number(self._lib, lit)]

    def _wlit(self, i: Symbol, pos: int, wlit: Tuple[int, int]) -> Sequence[Symbol]:
        # pylint: disable=unused-argument
        return [i, Number(self._lib, wlit[0]), Number(self._lib, wlit[1])]

    def _tuple(
        self,
        name: str,
        snmap: Dict[Sequence[U], int],
        elems: Sequence[U],
        afun: Callable[[Symbol, int, U], Sequence[Symbol]],
        ordered: bool = False,
    ) -> Symbol:
        pruned: Sequence[U]
        if ordered:
            pruned = elems
            ident = tuple(elems)
        else:
            seen: Set[U] = set()
            pruned = []
            for elem in elems:
                if elem not in seen:
                    seen.add(elem)
                    pruned.append(elem)
            ident = tuple(sorted(pruned))

        n = len(snmap)
        i = Number(self._lib, snmap.setdefault(ident, n))
        if n == i.number:
            self._output(name, [i])
            for idx, atm in enumerate(pruned):
                self._output(name, afun(i, idx, atm))
        return i

    def _atom_tuple(self, atoms: Sequence[int]):
        return self._tuple("atom_tuple", self._step_data.atom_tuples, atoms, self._lit)

    def _lit_tuple(self, lits: Sequence[int]):
        return self._tuple("literal_tuple", self._step_data.lit_tuples, lits, self._lit)

    def _wlit_tuple(self, wlits: Sequence[Tuple[int, int]]):
        return self._tuple(
            "weighted_literal_tuple", self._step_data.wlit_tuples, wlits, self._wlit
        )

    def init_program(self, incremental: bool) -> None:
        if incremental:
            self._cb(Function(self._lib, "tag", [Function(self._lib, "incremental")]))

    def begin_step(self) -> None:
        pass

    def rule(self, head: Sequence[int], body: Sequence[int], choice: bool) -> None:
        hn = "choice" if choice else "disjunction"
        hd = Function(self._lib, hn, [self._atom_tuple(head)])
        bd = Function(self._lib, "normal", [self._lit_tuple(body)])
        self._output("rule", [hd, bd])
        self._add_edges(head, body)

    def weight_rule(
        self,
        head: Sequence[int],
        lower_bound: int,
        body: Sequence[Tuple[int, int]],
        choice: bool,
    ) -> None:
        hn = "choice" if choice else "disjunction"
        hd = Function(self._lib, hn, [self._atom_tuple(head)])
        bd = Function(
            self._lib,
            "sum",
            [self._wlit_tuple(body), Number(self._lib, lower_bound)],
        )
        self._output("rule", [hd, bd])
        self._add_edges(head, [lit for lit, w in body])

    def minimize(self, literals: Sequence[Tuple[int, int]], priority: int) -> None:
        self._output(
            "minimize", [Number(self._lib, priority), self._wlit_tuple(literals)]
        )

    def project(self, atoms: Sequence[int]) -> None:
        for atom in atoms:
            self._output("project", [Number(self._lib, atom)])

    def external(self, atom: int, type: ExternalType) -> None:
        # pylint: disable=redefined-builtin
        value_name = type.name.lower().rstrip("_")
        self._output(
            "external", [Number(self._lib, atom), Function(self._lib, value_name)]
        )

    def assume(self, literals: Sequence[int]) -> None:
        for lit in literals:
            self._output("assume", [Number(self._lib, lit)])

    def heuristic(
        self,
        atom: int,
        type: HeuristicType,
        weight: int,
        priority: int,
        condition: Sequence[int],
    ) -> None:
        # pylint: disable=redefined-builtin
        type_name = type.name.lower().rstrip("_")
        condition_lit = self._lit_tuple(list(condition))
        self._output(
            "heuristic",
            [
                Number(self._lib, atom),
                Function(self._lib, type_name),
                Number(self._lib, weight),
                Number(self._lib, priority),
                condition_lit,
            ],
        )

    def edge(self, node_u: int, node_v: int, condition: Sequence[int]) -> None:
        self._output(
            "edge",
            [
                Number(self._lib, node_u),
                Number(self._lib, node_v),
                self._lit_tuple(list(condition)),
            ],
        )

    def _reify_theory_term(self, term) -> int:
        """
        Reify the given theory term of the base returning its id.
        """
        ids = self._step_data.theory_term_ids
        term_type = term.type

        key: tuple
        if term_type == TheoryTermType.Number:
            key = ("number", term.number)
            if key not in ids:
                ids[key] = len(ids)
                self._output(
                    "theory_number",
                    [Number(self._lib, ids[key]), Number(self._lib, term.number)],
                )
            return ids[key]

        if term_type == TheoryTermType.Symbol:
            return self._reify_theory_string(term.name)

        argument_ids = [self._reify_theory_term(a) for a in term.arguments]

        if term_type == TheoryTermType.Function:
            name_id = self._reify_theory_string(term.name)
            key = ("function", name_id, tuple(argument_ids))
            if key not in ids:
                tuple_id = self._tuple(
                    "theory_tuple",
                    self._step_data.theory_tuples,
                    argument_ids,
                    self._theory,
                    True,
                )
                ids[key] = len(ids)
                self._output(
                    "theory_function",
                    [Number(self._lib, ids[key]), Number(self._lib, name_id), tuple_id],
                )
            return ids[key]

        names = {
            TheoryTermType.Tuple: "tuple",
            TheoryTermType.Set: "set",
            TheoryTermType.List: "list",
        }
        name = names[term_type]
        key = (name, tuple(argument_ids))
        if key not in ids:
            tuple_id = self._tuple(
                "theory_tuple",
                self._step_data.theory_tuples,
                argument_ids,
                self._theory,
                True,
            )
            ids[key] = len(ids)
            self._output(
                "theory_sequence",
                [
                    Number(self._lib, ids[key]),
                    Function(self._lib, name),
                    tuple_id,
                ],
            )
        return ids[key]

    def _reify_theory_string(self, name: str) -> int:
        """
        Reify the given theory string returning its id.
        """
        ids = self._step_data.theory_term_ids
        key = ("string", name)
        if key not in ids:
            ids[key] = len(ids)
            self._output(
                "theory_string",
                [Number(self._lib, ids[key]), String(self._lib, name)],
            )
        return ids[key]

    def _reify_theory_element(self, element) -> int:
        """
        Reify the given theory element of the base returning its id.
        """
        term_ids = [self._reify_theory_term(term) for term in element.tuple]
        tuple_id = self._tuple(
            "theory_tuple",
            self._step_data.theory_tuples,
            term_ids,
            self._theory,
            True,
        )
        condition_id = self._lit_tuple(list(element.condition))

        ids = self._step_data.theory_element_ids
        key = (tuple_id.number, condition_id.number)
        if key not in ids:
            ids[key] = len(ids)
            self._output(
                "theory_element",
                [Number(self._lib, ids[key]), tuple_id, condition_id],
            )
        return ids[key]

    def _reify_theory_atom(self, atom) -> None:
        """
        Reify the given theory atom of the base.
        """
        term_id = self._reify_theory_term(atom.name)
        element_ids = [self._reify_theory_element(el) for el in atom.elements]
        tuple_e_id = self._tuple(
            "theory_element_tuple",
            self._step_data.theory_element_tuples,
            element_ids,
            self._lit,
        )
        args = [
            Number(self._lib, atom.literal),
            Number(self._lib, term_id),
            tuple_e_id,
        ]
        guard = atom.guard
        if guard is not None:
            operator_id = self._reify_theory_string(guard[0])
            rhs_id = self._reify_theory_term(guard[1])
            args.append(Number(self._lib, operator_id))
            args.append(Number(self._lib, rhs_id))
        self._output("theory_atom", args)

    def end_step(self, base: Base) -> None:
        """
        Reify the theory atoms and the output table of the base.
        """
        for atom in base.theory:
            self._reify_theory_atom(atom)
        for atom_base in base.values():
            for base_atom in atom_base.values():
                condition: Sequence[int] = (
                    [] if base.is_fact(base_atom.literal) else [base_atom.literal]
                )
                self._output("output", [base_atom.symbol, self._lit_tuple(condition)])
        for term in base.terms.values():
            for condition in term.condition:
                self._output("output", [term.symbol, self._lit_tuple(list(condition))])

        if self._reify_steps:
            self.calculate_sccs()
            self._step += 1
            self._step_data = _StepData()


def _set(
    matches: Sequence[Tuple[str, int]],
    lst: List,
    sym,
    append: bool = False,
) -> bool:
    for match in matches:
        if not sym.match(*match):
            continue
        idx = len(lst) if append else sym.arguments[0].number
        while len(lst) <= idx:
            lst.append(None)
        lst[idx] = sym
        return True
    return False


def _ensure(name: str, lst: List[List[int]], sym: Symbol, ordered=False) -> bool:
    empty = sym.match(name, 1)
    if empty or sym.match(name, 3 if ordered else 2):
        idx = sym.arguments[0].number
        while len(lst) <= idx:
            lst.append([])
        if not empty:
            if ordered:
                tup = lst[idx]
                jdx = sym.arguments[1].number
                while len(tup) <= jdx:
                    tup.append(0)
                tup[jdx] = sym.arguments[2].number
            else:
                lst[idx].append(sym.arguments[1].number)
        return True
    return False


class ReifiedTheory:
    """
    Class indexing the symbols related to a theory.

    The `ReifiedTheoryTerm`, `ReifiedTheoryElement`, and `ReifiedTheoryElement`
    classes provide views on this data that behave as the corresponding classes
    in clingo's `clingo.base` module.
    """

    terms: List[Symbol]
    elements: List[Symbol]
    atoms: List[Symbol]
    term_tuples: List[List[int]]
    element_tuples: List[List[int]]

    def __init__(self, symbols: Sequence[Symbol]):
        self.terms = []
        self.elements = []
        self.atoms = []
        self.term_tuples = []
        self.element_tuples = []

        for sym in symbols:
            _ = (
                _set(
                    (("theory_atom", 3), ("theory_atom", 5)),
                    self.atoms,
                    sym,
                    True,
                )
                or _set((("theory_element", 3),), self.elements, sym)
                or _set(
                    (
                        ("theory_sequence", 3),
                        ("theory_string", 2),
                        ("theory_number", 2),
                        ("theory_function", 3),
                    ),
                    self.terms,
                    sym,
                )
                or _ensure("theory_tuple", self.term_tuples, sym, True)
                or _ensure("theory_element_tuple", self.element_tuples, sym)
            )

    def __iter__(self) -> Iterator["ReifiedTheoryAtom"]:
        for idx in range(len(self.atoms)):
            yield ReifiedTheoryAtom(idx, self)


class ReifiedTheoryTerm:
    """
    Class to represent theory terms.

    ReifiedTheory terms have a readable string representation, implement Python's rich
    comparison operators, and can be used as dictionary keys.
    """

    _idx: int
    _theory: ReifiedTheory

    def __init__(self, idx: int, theory: ReifiedTheory):
        self._idx = idx
        self._theory = theory
        assert self.index < len(theory.terms)

    @property
    def index(self) -> int:
        """
        The index of the corresponding reified fact.
        """
        return self._idx

    @property
    def _args(self) -> Sequence[Symbol]:
        return self._theory.terms[self._idx].arguments

    @property
    def arguments(self) -> List["ReifiedTheoryTerm"]:
        """
        The arguments of the term (for functions, tuples, list, and sets).
        """
        assert self.type in (
            TheoryTermType.List,
            TheoryTermType.Set,
            TheoryTermType.Tuple,
            TheoryTermType.Function,
        )
        term_ids = self._theory.term_tuples[self._args[2].number]
        return [ReifiedTheoryTerm(term_id, self._theory) for term_id in term_ids]

    @property
    def name(self) -> str:
        """
        The name of the term (for symbols and functions).
        """
        assert self.type in (TheoryTermType.Symbol, TheoryTermType.Function)
        if self.type == TheoryTermType.Function:
            return self._theory.terms[self._args[1].number].arguments[1].string
        return self._args[1].string

    @property
    def number(self) -> int:
        """
        The numeric representation of the term (for numbers).
        """
        assert self.type == TheoryTermType.Number
        return self._args[1].number

    @property
    def type(self) -> TheoryTermType:
        """
        The type of the theory term.
        """
        name = self._theory.terms[self._idx].name
        if name == "theory_number":
            return TheoryTermType.Number
        if name == "theory_string":
            return TheoryTermType.Symbol
        if name == "theory_function":
            return TheoryTermType.Function
        assert name == "theory_sequence"
        type_ = self._args[1].name
        if type_ == "tuple":
            return TheoryTermType.Tuple
        if type_ == "set":
            return TheoryTermType.Set
        assert type_ == "list"
        return TheoryTermType.List

    def __hash__(self):
        return self._idx

    def __eq__(self, other):
        return self._idx == other._idx

    def __lt__(self, other):
        return self._idx < other._idx

    def __str__(self):
        type_ = self.type

        if type_ == TheoryTermType.Number:
            return f"{self.number}"

        if type_ == TheoryTermType.Symbol:
            return f"{self.name}"

        if type_ == TheoryTermType.Function:
            args = self.arguments
            name = self.name
            if len(args) == 1 and is_operator(name):
                return f"{name}({args[0]})"
            if len(args) == 2 and is_operator(name):
                return f"({args[0]}){name}({args[1]})"
            return f'{name}({",".join(str(arg) for arg in args)})'

        if type_ == TheoryTermType.Tuple:
            lhs, rhs = "(", ")"
        elif type_ == TheoryTermType.List:
            lhs, rhs = "[", "]"
        else:
            lhs, rhs = "{", "}"
        return f'{lhs}{",".join(str(arg) for arg in self.arguments)}{rhs}'


class ReifiedTheoryElement:
    """
    Class to represent theory elements.

    ReifiedTheory elements have a readable string representation, implement Python's
    rich comparison operators, and can be used as dictionary keys.
    """

    _idx: int
    _theory: ReifiedTheory

    def __init__(self, idx: int, theory: ReifiedTheory):
        self._idx = idx
        self._theory = theory
        assert self.index < len(theory.elements)

    @property
    def index(self) -> int:
        """
        The index of the corresponding reified fact.
        """
        return self._idx

    @property
    def _args(self) -> Sequence[Symbol]:
        return self._theory.elements[self._idx].arguments

    @property
    def condition_id(self) -> int:
        """
        The id of the literal tuple of the condition.
        """
        return self._args[2].number

    @property
    def terms(self) -> List[ReifiedTheoryTerm]:
        """
        The tuple of the element.
        """
        term_ids = self._theory.term_tuples[self._args[1].number]
        return [ReifiedTheoryTerm(term_id, self._theory) for term_id in term_ids]

    def __hash__(self):
        return self._idx

    def __eq__(self, other):
        return self._idx == other._idx

    def __lt__(self, other):
        return self._idx < other._idx

    def __str__(self):
        return f'{",".join(str(term) for term in self.terms)}: literal_tuple({self.condition_id})'


class ReifiedTheoryAtom:
    """
    Class to represent theory atoms.

    Theory atoms have a readable string representation, implement Python's rich
    comparison operators, and can be used as dictionary keys.
    """

    _idx: int
    _theory: ReifiedTheory

    def __init__(self, idx: int, theory: ReifiedTheory):
        self._idx = idx
        self._theory = theory
        assert self.index < len(theory.atoms)

    @property
    def index(self) -> int:
        """
        The index of the corresponding reified fact.
        """
        return self._idx

    @property
    def _args(self) -> Sequence[Symbol]:
        return self._theory.atoms[self._idx].arguments

    @property
    def elements(self) -> List[ReifiedTheoryElement]:
        """
        The elements of the atom.
        """
        tuple_id = self._args[2].number
        return [
            ReifiedTheoryElement(elem_id, self._theory)
            for elem_id in self._theory.element_tuples[tuple_id]
        ]

    @property
    def guard(self) -> Optional[Tuple[str, ReifiedTheoryTerm]]:
        """
        The guard of the atom or None if the atom has no guard.
        """
        args = self._args
        if len(args) <= 3:
            return None

        op = self._theory.terms[args[3].number].arguments[1].string
        return (op, ReifiedTheoryTerm(args[4].number, self._theory))

    @property
    def literal(self) -> int:
        """
        The reified literal associated with the atom.
        """
        return self._args[0].number

    @property
    def term(self) -> ReifiedTheoryTerm:
        """
        The term of the atom.
        """
        return ReifiedTheoryTerm(self._args[1].number, self._theory)

    def __hash__(self):
        return self._idx

    def __eq__(self, other):
        return self._idx == other._idx

    def __lt__(self, other):
        return self._idx < other._idx

    def __str__(self):
        name = f"&{self.term}"

        elems = self.elements
        if elems:
            estr = f' {{ {"; ".join(str(elem) for elem in elems)} }}'
        else:
            estr = ""

        guard = self.guard
        if guard:
            gstr = f" {guard[0]} {guard[1]}"
        else:
            gstr = ""

        return f"{name}{estr}{gstr}"


def reify_program(
    lib: Library,
    prg: str,
    calculate_sccs: bool = False,
    reify_steps: bool = False,
) -> List[Symbol]:
    """
    Reify the given program and return the reified symbols.

    Parameters
    ----------
    lib
        The library storing symbols.
    prg
        The program to reify in form of a string.
    calculate_sccs
        Whether to calculate SCCs of the reified program.
    reify_steps
        Whether to add a step number to the reified facts.

    Returns
    -------
    A list of symbols containing the reified facts.
    """
    ret: List[Symbol] = []
    ctl = Control(lib)
    reifier = Reifier(lib, ret.append, calculate_sccs, reify_steps)
    ctl.parse_string(prg)
    ctl.ground()
    ctl.observe(reifier, preprocess=False)
    if calculate_sccs and not reify_steps:
        reifier.calculate_sccs()

    return ret
