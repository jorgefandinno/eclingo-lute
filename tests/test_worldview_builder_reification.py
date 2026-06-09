import unittest
from typing import Sequence

import clingo
from clingo.ast import Sign
from clingo.symbol import Function, Symbol

import eclingo as _eclingo
from eclingo.literals import Literal
from eclingo.solver.candidate import Candidate
from eclingo.solver.world_view import EpistemicLiteral, WorldView
from eclingo.solver.world_view_builder import (
    WorldWiewBuilderReification,
    WorldWiewBuilderReificationWithShow,
)
from tests.parse_programs import parse_program as _parse_reified

# python -m unittest tests.test_worldview_builder_reification.TestEclingoWViewReification

""" Helper function to generate candidates for a given program and test them"""


def world_view_builder(tested_candidates):
    config = _eclingo.config.AppConfig()
    config.eclingo_semantics = "c19-1"
    control = clingo.Control(["0"], message_limit=0)
    control.configuration.solve.models = 0
    control.configuration.solve.project = "auto,3"

    world_view_builder = WorldWiewBuilderReification()

    wviews = []
    for candidate in tested_candidates:
        wview = world_view_builder(candidate)
        if wview not in wviews:
            wviews.append(wview)

    return sorted(wviews)


class TestCase(unittest.TestCase):
    maxDiff = None

    def assert_models(self, candidates, expected):
        self.assertEqual(candidates, expected)


class TestEclingoWViewReification(TestCase):
    def test_wview_reification1(self):
        # echo ":- k(u(a)). u(a). {k(u(a))} :- u(a)." | clingo --output=reify
        # "a. b :- &k{a}."
        self.assert_models(
            world_view_builder(
                [
                    Candidate(
                        pos=[
                            Function(
                                "k",
                                [Function("u", [Function("a", [], True)], True)],
                                True,
                            )
                        ],
                        neg=[],
                    )
                ]
            ),
            [WorldView([EpistemicLiteral(Function("a", [], True), 0, False)])],
        )

    def test_wview_reification2(self):
        # echo "a. b :- &k{ not not a }." | eclingo --output=reify --semantics c19-1 --reification
        self.assert_models(
            world_view_builder(
                [
                    Candidate(
                        pos=[
                            Function(
                                "k",
                                [
                                    Function(
                                        "not2",
                                        [
                                            Function(
                                                "u", [Function("a", [], True)], True
                                            )
                                        ],
                                        True,
                                    )
                                ],
                                True,
                            )
                        ],
                        neg=[],
                    )
                ]
            ),
            [
                WorldView(
                    [
                        EpistemicLiteral(
                            Literal(Function("a", [], True), Sign.DoubleNegation),
                            0,
                            False,
                        )
                    ]
                )
            ],
        )

    def test_wview_reification3(self):
        # echo "-a. b:- &k{-a}. c :- b." | eclingo --semantics c19-1 --reification --output=reify
        self.assert_models(
            world_view_builder(
                [
                    Candidate(
                        pos=[
                            Function(
                                "k",
                                [Function("u", [Function("a", [], False)], True)],
                                True,
                            )
                        ],
                        neg=[],
                    )
                ]
            ),
            [
                WorldView(
                    [
                        EpistemicLiteral(
                            Literal(Function("a", [], False), Sign.NoSign), 0, False
                        )
                    ]
                )
            ],
        )

    def test_wview_reification4(self):
        # echo "-a. b :- &k{-a}. c :- &k{b}." | eclingo --semantics c19-1 --reification
        self.assert_models(
            world_view_builder(
                [
                    Candidate(
                        pos=[
                            Function(
                                "k",
                                [Function("u", [Function("b", [], True)], True)],
                                True,
                            ),
                            Function(
                                "k",
                                [Function("u", [Function("a", [], False)], True)],
                                True,
                            ),
                        ],
                        neg=[],
                    ),
                ]
            ),
            [
                WorldView(
                    [
                        EpistemicLiteral(Function("b", [], True), Sign.NoSign, False),
                        EpistemicLiteral(Function("a", [], False), 0, False),
                    ]
                )
            ],
        )

    def test_wview_reification5(self):
        # echo "-a. b :- &k{-a}." | eclingo --semantics c19-1 --reification
        self.assert_models(
            world_view_builder(
                [
                    Candidate(
                        pos=[
                            Function(
                                "k",
                                [Function("u", [Function("a", [], False)], True)],
                                True,
                            )
                        ],
                        neg=[],
                    )
                ]
            ),
            [WorldView([EpistemicLiteral(Function("a", [], False), 0, False)])],
        )

    def test_wview_reification6(self):
        # echo "b :- &k{ not a }. c :- &k{ b }." | eclingo --semantics c19-1 --reification
        self.assert_models(
            world_view_builder(
                [
                    Candidate(
                        pos=[
                            Function(
                                "k",
                                [
                                    Function(
                                        "not1",
                                        [
                                            Function(
                                                "u", [Function("a", [], True)], True
                                            )
                                        ],
                                        True,
                                    )
                                ],
                            ),
                            Function(
                                "k",
                                [Function("u", [Function("b", [], True)], True)],
                                True,
                            ),
                        ],
                        neg=[],
                    )
                ]
            ),
            [
                WorldView(
                    [
                        EpistemicLiteral(
                            Literal(Function("b", [], True), Sign.NoSign), 0, False
                        ),
                    ]
                )
            ],
        )

    def test_wview_reification7(self):
        # echo "b :- &k{ not a }. c :- &k{ b }. {a}." | eclingo --semantics c19-1 --reification
        self.assert_models(
            world_view_builder(
                [
                    Candidate(
                        pos=[],
                        neg=[
                            Function(
                                "k",
                                [
                                    Function(
                                        "not1",
                                        [
                                            Function(
                                                "u", [Function("a", [], True)], True
                                            )
                                        ],
                                        True,
                                    )
                                ],
                            ),
                            Function(
                                "k",
                                [Function("u", [Function("b", [], True)], True)],
                                True,
                            ),
                        ],
                    )
                ]
            ),
            [
                WorldView(
                    [
                        EpistemicLiteral(
                            Literal(Function("a", [], True), Sign.NoSign), 0, True
                        ),
                    ]
                )
            ],
        )

    def test_wview_reification8(self):
        # echo "b :- &k{ not a }. c :- &k{ a }. a." | eclingo --semantics c19-1 --reification
        self.assert_models(
            world_view_builder(
                [
                    Candidate(
                        pos=[
                            Function(
                                "k",
                                [Function("u", [Function("a", [], True)], True)],
                                True,
                            ),
                        ],
                        neg=[
                            Function(
                                "k",
                                [
                                    Function(
                                        "not1",
                                        [
                                            Function(
                                                "u", [Function("a", [], True)], True
                                            )
                                        ],
                                        True,
                                    )
                                ],
                            ),
                        ],
                    )
                ]
            ),
            [
                WorldView(
                    [
                        EpistemicLiteral(
                            Literal(Function("a", [], True), Sign.NoSign),
                            0,
                        ),
                    ]
                )
            ],
        )


# reification of: {a}. #show a/0.
_PRG_OPTIONAL_A_WITH_SHOW = (
    "tag(incremental). atom_tuple(0). atom_tuple(0,1). literal_tuple(0). "
    "rule(choice(0),normal(0)). atom_tuple(1). atom_tuple(1,2). "
    "literal_tuple(1). literal_tuple(1,1). rule(disjunction(1),normal(1)). "
    "output(u(a),1). literal_tuple(2). literal_tuple(2,2). output(show_statement(a),2)."
)


class TestEclingoWViewReificationWithShow(TestCase):
    def test_show_m_symbol(self):
        # {a}. #show a/0. — a is optional, so world view is &m{a}
        # This exercises world_view_builder.py line 183: the elif branch where
        # show_statement(a) is present but u(a) is not in the cautious model
        # (true in some answer sets but not all) and not1(u(a)) is also absent.
        reified = _parse_reified(_PRG_OPTIONAL_A_WITH_SHOW)
        builder = WorldWiewBuilderReificationWithShow(reified)
        wv = builder(Candidate(pos=[], neg=[]))
        self.assertEqual(
            wv,
            WorldView(
                [EpistemicLiteral(Function("a", [], True), Sign.NoSign, is_m=True)]
            ),
        )
