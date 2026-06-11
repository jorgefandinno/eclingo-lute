from typing import Dict, List, Sequence, Tuple

from clingo.control import Control
from clingo.core import Library
from clingo.symbol import Symbol

from eclingo.clingox import program as clingox_program
from eclingo.clingox.reify import Reifier
from eclingo.config import AppConfig

from .parsing.parser import parse_program


class Grounder:
    def __init__(self, lib: Library, control: Control, config: AppConfig = AppConfig()):
        self.lib = lib
        self.control = control
        self.config = config
        self.facts: List[Symbol] = []
        self.reified_facts: List[Symbol] = []
        self.atom_to_symbol: Dict[int, Symbol] = dict()
        self.ground_program = clingox_program.Program()

    def add_program(
        self, program: str, parameters: Sequence[str] = (), name: str = "base"
    ) -> None:
        # With clingo 6 there is no program builder, so the parsed statements
        # are added back to the control object as text.
        statements: List = []
        parse_program(
            self.lib, program, statements.append, parameters, name, self.config
        )
        self.control.parse_string("\n".join(str(stm) for stm in statements))

    def ground(
        self, parts: Sequence[Tuple[str, Sequence[Symbol]]] = (("base", []),)
    ) -> None:  # pylint: disable=dangerous-default-value
        self.control.ground(parts)
        # With clingo 6 observers inspect the program after grounding
        self.control.observe(
            clingox_program.ProgramObserver(self.ground_program), preprocess=False
        )
        self.control.observe(
            Reifier(self.lib, self.reified_facts.append), preprocess=False
        )
