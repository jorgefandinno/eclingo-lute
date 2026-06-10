from clingo.ast import Transformer, Variable, parse_string
class VariableRenamer(Transformer):
    def visit_Variable(self, node):
        return node.update(name='_' + node.name)
vrt = VariableRenamer()
parse_string('p(X) :- q(X).', lambda stm: print(str(vrt(stm))))