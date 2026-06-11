from clingo.control import Control
from clingo.core import Library

import eclingo.clingox.program


def parse_program(lib: Library, program_str: str):
    control = Control(lib)
    program = eclingo.clingox.program.Program()
    control.parse_string(program_str)
    control.ground()
    control.observe(eclingo.clingox.program.ProgramObserver(program), preprocess=False)
    return [f.symbol for f in program.facts]
