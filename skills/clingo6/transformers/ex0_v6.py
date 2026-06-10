from functools import singledispatch

from clingo.core import Library
from clingo.ast import TermVariable, parse_string

@singledispatch
def vrt(stm, lib):
    return stm.transform(lib, vrt, lib)

@vrt.register
def _(var: TermVariable, lib):
    return var.update(lib, name="_" + var.name)

lib = Library()
parse_string(lib, 'p(X) :- q(X).', lambda stm: print(str(vrt(stm, lib) or stm)))