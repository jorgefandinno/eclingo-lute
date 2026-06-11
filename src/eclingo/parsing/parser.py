from typing import Callable, Iterable, List, Sequence, cast

from clingo import ast
from clingo.ast import Sign, parse_string
from clingo.core import Library, Location, Position

from eclingo.clingox.ast import TheoryParser, theory_parser_from_definition
from eclingo.config import AppConfig

from .transformers.astutil import atom as make_atom
from .transformers.parser_negations import StrongNegationReplacement
from .transformers.theory_parser_epistemic import (
    double_negate_epistemic_listerals,
    parse_epistemic_literals_elements,
    parse_m_literals,
    reify_epistemic_elements,
    replace_epistemic_literals_by_auxiliary_atoms,
    replace_negations_by_auxiliary_atoms_in_epistemic_literals,
)

_CallbackType = Callable[[ast.Statement], None]

from eclingo.clingox.ast import reify_symbolic_atoms

U_NAME = "u"


def parse_theory(lib: Library, s: str) -> TheoryParser:
    """
    Turn the given theory into a parser.
    """
    parser = None

    def extract(stm):
        nonlocal parser
        if isinstance(stm, ast.StatementTheory):
            parser = theory_parser_from_definition(lib, stm)

    parse_string(lib, s, extract)
    return cast(TheoryParser, parser)


class _ProgramParser(object):
    eclingo_theory = """
    #theory eclingo {
    term { not : 0, unary;
           -   : 0, unary;
           ~   : 0, unary
         };
    &k/0 : term, body;
    &m/0 : term, body
    }.
    """

    def __init__(
        self,
        lib: Library,
        program: str,
        callback: _CallbackType,
        parameters: Sequence[str] = (),
        name: str = "base",
        config: AppConfig = AppConfig(semantics="c19-1"),
        only_m_normal_form: bool = False,
    ):
        self.lib = lib
        self.initial_location = Location(
            Position(lib, "<string>", 1, 1),
            Position(lib, "<string>", 1, 1),
        )
        self.config = config
        self.program = program
        self.callback = callback
        self.parameters = list(parameters)
        self.name = name
        self.strong_negation_replacements = StrongNegationReplacement()
        self.semantics = self.config.eclingo_semantics
        self.rewritten_prg = self.config.rewritten_program
        self.rewritten = self.config.eclingo_rewritten
        self.theory_parser = parse_theory(lib, _ProgramParser.eclingo_theory)
        self.only_m_normal_form = only_m_normal_form

    def __call__(self) -> None:
        ast.parse_string(self.lib, self.program, self._parse_statement)
        # for aux_rule in self.strong_negation_replacements.get_auxiliary_rules(
        #     self.reification
        # ):
        #     self.callback(aux_rule)

    def _parse_statement(self, statement: ast.Statement) -> None:
        statement = self.theory_parser(statement)
        statement = parse_epistemic_literals_elements(self.lib, statement)
        statement = parse_m_literals(self.lib, statement)

        if self.only_m_normal_form:
            self.callback(statement)
            return

        statement = reify_symbolic_atoms(
            self.lib, statement, U_NAME, reify_strong_negation=True
        )
        statement = reify_epistemic_elements(
            self.lib, statement, U_NAME, reify_strong_negation=True
        )

        # this avoids collitions between user predicates and auxiliary predicates
        if isinstance(statement, ast.StatementRule):
            for rule in self._parse_rule(statement):
                self.callback(rule)
        elif isinstance(statement, ast.StatementProgram):
            for statement in self._parse_program_statement(statement):
                self.callback(statement)
        elif isinstance(statement, ast.StatementShowSignature):
            for stm in self._parse_show_signature_statement(statement):
                self.callback(stm)

        # No show staments currently supported by reification version
        # elif isinstance(statement, ast.StatementShow):
        #     raise RuntimeError(
        #         'syntax error: only show statements of the form "#show atom/n." are allowed.'
        #     )

        else:
            self.callback(statement)

    def _parse_rule(self, rule: ast.StatementRule) -> Iterable[ast.Statement]:
        if self.semantics == "g94":
            rule = double_negate_epistemic_listerals(self.lib, rule)
        (
            rules,
            sn_replacement,
        ) = replace_negations_by_auxiliary_atoms_in_epistemic_literals(self.lib, rule)
        self.strong_negation_replacements.update(sn_replacement)
        return replace_epistemic_literals_by_auxiliary_atoms(self.lib, rules, "k")

    def _parse_program_statement(
        self, statement: ast.StatementProgram
    ) -> List[ast.Statement]:
        begin = statement.location.begin
        initial_begin = self.initial_location.begin
        if (
            statement.name != "base"
            or statement.arguments
            or begin.file != initial_begin.file
            or begin.line != initial_begin.line
            or begin.column != initial_begin.column
        ):
            return [statement]

        if self.name == "base" and not self.parameters:
            return [statement]

        new_statement = ast.StatementProgram(
            self.lib, statement.location, self.name, self.parameters
        )

        return [new_statement]

    def _parse_show_signature_statement(
        self, statement: ast.StatementShowSignature
    ) -> List[ast.Statement]:
        lib = self.lib
        location = statement.location
        args = [
            ast.TermVariable(lib, location, f"X{i}") for i in range(0, statement.arity)
        ]
        fun = make_atom(lib, location, True, statement.name, args)
        literal = ast.BodySimpleLiteral(
            lib,
            ast.LiteralSymbolic(
                lib,
                location,
                Sign.NoSign,
                ast.TermFunction(
                    lib, location, U_NAME, [ast.ArgumentTuple(lib, [fun])], False
                ),
            ),
        )
        hfun = ast.TermFunction(
            lib, location, "show_statement", [ast.ArgumentTuple(lib, [fun])], False
        )
        hliteral = ast.HeadSimpleLiteral(
            lib, ast.LiteralSymbolic(lib, location, Sign.NoSign, hfun)
        )
        rule = ast.StatementRule(lib, location, hliteral, [literal])
        return [rule]


#######################################################################################################


def parse_program(
    lib: Library,
    program: str,
    callback: _CallbackType,
    parameters: Sequence[str] = (),
    name: str = "base",
    config: AppConfig = AppConfig(semantics="c19-1"),
    *,
    only_m_normal_form: bool = False,
) -> None:
    _ProgramParser(
        lib, program, callback, parameters, name, config, only_m_normal_form
    )()
