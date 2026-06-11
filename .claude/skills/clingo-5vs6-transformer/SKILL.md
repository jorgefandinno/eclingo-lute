---
description: updating from clingo API version 5.8 to version 6
---

clingo version 6 does not have the class `clingo.ast.Transformer`. Use `node.transform(lib, obj)`, `node.update(lib, **kw)`, `node.visit(obj)` instead.

This example shows how to use a Transformer in clingo version 5.8 to rename each variable by preapending the character `_`, that is `X` becomes `_X`.
```python
from clingo.ast import Transformer, Variable, parse_string
class VariableRenamer(Transformer):
    def visit_Variable(self, node):
        return node.update(name='_' + node.name)
vrt = VariableRenamer()
parse_string('p(X) :- q(X).', lambda stm: print(str(vrt(stm))))
```
The same example in version 6:
```python
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
```