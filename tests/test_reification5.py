#  u(a) :- u(b), k(c) | --output=reify
# echo "a :- b. &k{b}." | clingo --output=reify

from clingo.control import Control
from clingo.core import Library

from eclingo.clingox.reify import Reifier
from eclingo.clingox.testing.ast import ASTTestCase
from eclingo.config import AppConfig
from eclingo.parsing import parser
from eclingo.parsing.transformers import function_transformer
from eclingo.parsing.transformers.ast_reify import program_to_str

_lib = Library(message_limit=0)


def flatten(lst):
    result = []
    for lst2 in lst:
        if isinstance(lst2, list):
            for e in lst2:
                result.append(e)
        else:
            result.append(lst2)

    return result


def parse_program(stm, parameters=[], name="base"):
    ret = []
    parser.parse_program(
        _lib,
        stm,
        ret.append,
        parameters,
        name,
        config=AppConfig(semantics="c19-1", verbose=0),
    )
    return flatten(ret)


class TestCase(ASTTestCase):
    def setUp(self):
        self.print = False

    def assert_equal_program(self, program, expected):
        # Parse expected program as a list to test.
        expected_program = [x.strip() for x in expected.split(".") if x.strip()]

        # Apply Transformer to parsed program
        program = [
            function_transformer.rule_to_symbolic_term_adapter(_lib, stm)
            for stm in program
        ]

        program = program_to_str(program)
        ctl_a = Control(_lib)

        temp = []
        ctl_a.parse_string(program)
        ctl_a.ground()
        ctl_a.observe(Reifier(_lib, temp.append), preprocess=False)

        temp = [str(e) for e in temp]
        if len(temp) != len(expected_program):
            self.fail(
                f"Lists differ (different lenghts {len(temp)} and {len(expected_program)}: {temp}"
            )
        for e1, e2 in zip(temp, expected_program):
            self.assertEqual(e1, e2)
        self.assertListEqual(temp, expected_program)


class Test(TestCase):
    def test_epistemic_rules(self):
        self.assert_equal_program(
            parse_program("b :- &k{ not a}."),
            "tag(incremental). atom_tuple(0). atom_tuple(0,1). literal_tuple(0). rule(disjunction(0),normal(0)). atom_tuple(1). atom_tuple(1,2). rule(choice(1),normal(0)). atom_tuple(2). atom_tuple(2,3). literal_tuple(1). literal_tuple(1,2). rule(disjunction(2),normal(1)). literal_tuple(2). literal_tuple(2,3). output(u(b),2). output(not1(u(a)),0). output(k(not1(u(a))),1).",
        )

        self.assert_equal_program(
            parse_program(":- &k{-a}. -a."),
            "tag(incremental). atom_tuple(0). atom_tuple(0,1). literal_tuple(0). rule(disjunction(0),normal(0)). atom_tuple(1). literal_tuple(1). literal_tuple(1,2). rule(disjunction(1),normal(1)). atom_tuple(2). atom_tuple(2,2). rule(choice(2),normal(0)). output(u(-a),0). output(k(u(-a)),1).",
        )
